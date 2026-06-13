"""yt-dlp 封装：解析视频信息、构造下载选项、执行下载并回写进度。

设计要点：直接使用 yt-dlp 的 Python API（YoutubeDL），不修改其源码、不拼接命令行，
通过 imageio-ffmpeg 提供的 ffmpeg 二进制完成音视频合并 / 音频转码。
"""
from __future__ import annotations

import os
import re
import urllib.request
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

import imageio_ffmpeg
from yt_dlp import YoutubeDL

from app.core.tasks import store
from app.models.schemas import FormatOption, InfoResponse
from app.services import bili_patch

# 运行时给 B 站提取器打补丁，绕过 /video/ 页面的 WAF 风控（详见 bili_patch.py）
bili_patch.apply_patch()

# 解析 ffmpeg 二进制路径（imageio-ffmpeg 自带，免手动安装）
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

# 我们对外暴露的标准清晰度档位（从高到低）
STANDARD_HEIGHTS = [2160, 1440, 1080, 720, 480, 360]

# 统一使用的桌面浏览器 UA
DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# 存放各平台 cookies 的目录（Netscape 格式），文件不入库（见 .gitignore）
COOKIES_DIR = Path(__file__).resolve().parents[2] / "cookies"

# 域名 -> cookies 文件名 的映射，便于不同平台分别提供登录态
PLATFORM_COOKIE_MAP: list[tuple[tuple[str, ...], str]] = [
    (("youtube.com", "youtu.be"), "youtube.txt"),
    (("bilibili.com", "b23.tv"), "bilibili.txt"),
    (("douyin.com", "iesdouyin.com"), "douyin.txt"),
    (("tiktok.com",), "tiktok.txt"),
    (("instagram.com",), "instagram.txt"),
    (("x.com", "twitter.com"), "twitter.txt"),
    (("kuaishou.com",), "kuaishou.txt"),
    (("ixigua.com", "toutiao.com"), "ixigua.txt"),
    (("weibo.com", "weibo.cn"), "weibo.txt"),
]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _clean(text: Optional[str]) -> Optional[str]:
    """去除 yt-dlp 进度字符串里的 ANSI 颜色码与多余空白。"""
    if not text:
        return None
    return _ANSI_RE.sub("", text).strip() or None


def _follow_redirect(url: str) -> Optional[str]:
    """跟随短链跳转，返回最终真实地址。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": DESKTOP_UA})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.geturl()
    except Exception:
        return None


def normalize_url(url: str) -> str:
    """规范化各平台链接，修正 yt-dlp 无法直接识别的形式。

    典型场景：
    - 抖音 `https://www.douyin.com/jingxuan?modal_id=ID` -> `/video/ID`
    - 西瓜 `https://m.ixigua.com/dx/ID` -> `https://www.ixigua.com/ID/`
    - 抖音/B站/西瓜 短链 -> 跟随跳转后再规范化
    """
    url = (url or "").strip()
    if not url:
        return url
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    # 抖音：从 modal_id 查询参数中提取视频 id
    if "douyin.com" in host:
        qs = parse_qs(parsed.query)
        if "modal_id" in qs and qs["modal_id"]:
            return f"https://www.douyin.com/video/{qs['modal_id'][0]}"

    # 西瓜视频：m 站 /dx/ID、裸 ID 等形式 yt-dlp 不识别或会丢末位数字，
    # 统一规范化为 `https://www.ixigua.com/{id}/`（结尾斜杠满足提取器正则，
    # 避免贪婪匹配把末位数字算进无关分组）。
    if "ixigua.com" in host and host != "v.ixigua.com":
        m = re.search(r"(\d{6,})", parsed.path)
        if m:
            return f"https://www.ixigua.com/{m.group(1)}/"

    # 短链：解析跳转后递归规范化
    if (
        host in ("v.douyin.com", "b23.tv", "v.ixigua.com", "v.kuaishou.com")
        or host.endswith(".b23.tv")
    ):
        real = _follow_redirect(url)
        if real and real != url:
            return normalize_url(real)

    return url


def _resolve_cookiefile(url: str) -> Optional[str]:
    """按平台匹配 cookies 文件；env > 平台专属 > 全局 cookies.txt。"""
    env_file = os.getenv("YTDLP_COOKIES")
    if env_file and Path(env_file).exists():
        return env_file

    host = urlparse(url).netloc.lower()
    for hosts, fname in PLATFORM_COOKIE_MAP:
        if any(h in host for h in hosts):
            candidate = COOKIES_DIR / fname
            if candidate.exists():
                return str(candidate)

    global_file = COOKIES_DIR / "cookies.txt"
    if global_file.exists():
        return str(global_file)
    return None


def _base_opts(url: str = "") -> dict:
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        # 必须传 ffmpeg 二进制的完整路径：imageio-ffmpeg 的文件名是
        # ffmpeg-win64-vX.Y.Z.exe（非标准名），若只传目录 yt-dlp 会按 "ffmpeg.exe"
        # 查找而匹配不到，导致 "ffmpeg is not installed" 无法合并。传完整路径时
        # yt-dlp 用 'ffmpeg' in filename 识别并直接采用该二进制。
        "ffmpeg_location": FFMPEG_PATH,
        # 避免在某些平台因播放列表导致一次性抓取过多
        "noplaylist": True,
        # 默认 UA，缓解部分站点的简单风控
        "http_headers": {"User-Agent": DESKTOP_UA},
        # YouTube 多客户端回退，缓解 "确认你不是机器人" 等风控
        "extractor_args": {"youtube": {"player_client": ["tv", "web_safari", "android"]}},
        # 防止个别平台（如直播流/失效链接）导致请求长时间挂起
        "socket_timeout": 20,
    }

    # Cookies（突破 YouTube/B站 等登录态/风控的关键）：
    #   1) 优先 env: YTDLP_COOKIES=/path/to/cookies.txt
    #   2) 平台专属文件: backend/cookies/youtube.txt、bilibili.txt ...
    #   3) 全局文件: backend/cookies/cookies.txt
    cookie_file = _resolve_cookiefile(url)
    if cookie_file:
        opts["cookiefile"] = cookie_file

    # 或从浏览器直接读取（需浏览器已关闭且未启用应用绑定加密）
    cookies_browser = os.getenv("YTDLP_COOKIES_FROM_BROWSER")
    if cookies_browser and not cookie_file:
        opts["cookiesfrombrowser"] = (cookies_browser,)

    return opts


def extract_info(url: str) -> InfoResponse:
    """解析视频信息，归并出标准清晰度档位 + 仅音频选项。"""
    url = normalize_url(url)
    opts = {**_base_opts(url), "skip_download": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # 某些链接可能返回播放列表，取第一条
    if info.get("_type") == "playlist" and info.get("entries"):
        info = info["entries"][0]

    raw_formats = info.get("formats", []) or []

    # 统计每个标准高度可达到的最大码率对应的预估大小
    available_heights: dict[int, int] = {}
    for f in raw_formats:
        height = f.get("height")
        if not height or f.get("vcodec") in (None, "none"):
            continue
        size = f.get("filesize") or f.get("filesize_approx") or 0
        for std in STANDARD_HEIGHTS:
            if height >= std:
                # 记录该档位下较大的预估体积
                if size and size > available_heights.get(std, 0):
                    available_heights[std] = size
                else:
                    available_heights.setdefault(std, 0)
                break

    formats: list[FormatOption] = []
    # 最佳画质优先展示
    formats.append(
        FormatOption(
            quality="best",
            label="最佳画质（自动）",
            ext="mp4",
            filesize=None,
            type="video",
        )
    )
    for std in STANDARD_HEIGHTS:
        if std in available_heights:
            size = available_heights[std] or None
            formats.append(
                FormatOption(
                    quality=f"{std}p",
                    label=f"{std}p MP4",
                    ext="mp4",
                    filesize=size,
                    type="video",
                )
            )

    # 仅音频
    has_audio = any(f.get("acodec") not in (None, "none") for f in raw_formats)
    if has_audio or not formats:
        formats.append(
            FormatOption(
                quality="audio",
                label="仅音频 MP3",
                ext="mp3",
                filesize=None,
                type="audio",
            )
        )

    raw_duration = info.get("duration")
    duration = int(raw_duration) if isinstance(raw_duration, (int, float)) else None

    return InfoResponse(
        title=info.get("title") or "未命名视频",
        thumbnail=info.get("thumbnail"),
        duration=duration,
        uploader=info.get("uploader") or info.get("channel"),
        webpage_url=info.get("webpage_url") or url,
        formats=formats,
    )


def _format_selector(quality: str) -> str:
    """根据清晰度档位生成 yt-dlp 的 format 选择串。

    优先选择 h264(avc1)+aac(mp4a) 组合，确保 MP4 容器兼容性（避免 VP9/AV1/Opus
    塞进 MP4 导致播放器兼容问题），不可用时回退到任意编码。
    """
    if quality == "best":
        return (
            "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/"
            "bestvideo[vcodec^=avc1]+bestaudio/"
            "bestvideo+bestaudio/best"
        )
    if quality == "audio":
        return "bestaudio/best"
    m = re.match(r"(\d+)p", quality)
    if m:
        h = int(m.group(1))
        return (
            f"bestvideo[height<={h}][vcodec^=avc1]+bestaudio[acodec^=mp4a]/"
            f"bestvideo[height<={h}][vcodec^=avc1]+bestaudio/"
            f"bestvideo[height<={h}]+bestaudio/"
            f"best[height<={h}]/best"
        )
    return (
        "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/"
        "bestvideo[vcodec^=avc1]+bestaudio/"
        "bestvideo+bestaudio/best"
    )


def _build_download_opts(task_id: str, quality: str, url: str) -> dict:
    task = store.get(task_id)
    assert task is not None
    outtmpl = str(task.workdir / "%(title).80s.%(ext)s")

    opts = {
        **_base_opts(url),
        "format": _format_selector(quality),
        "outtmpl": outtmpl,
        "progress_hooks": [_make_hook(task_id)],
        "postprocessor_hooks": [_make_pp_hook(task_id)],
        # 文件名中替换非法字符，保证跨平台
        "restrictfilenames": False,
        "windowsfilenames": True,
    }

    if quality == "audio":
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        opts["merge_output_format"] = "mp4"
        # 把 MP4 的 moov atom 移到文件头（faststart），否则浏览器/播放器
        # 必须先下载整个文件才能开始播放，大文件常表现为"播放几秒后中断"
        opts["postprocessor_args"] = {
            "Merger": ["-movflags", "+faststart"],
        }

    return opts


def _make_hook(task_id: str):
    state = {"max_pct": 0.0}

    def hook(d: dict) -> None:
        task = store.get(task_id)
        if task and task.is_cancelled:
            raise RuntimeError("下载已取消")

        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes") or 0
            raw_pct = (downloaded / total * 100) if total else 0.0
            # 下载阶段上限 95%（100% 留给最终完成）；
            # 仅允许单调递增，防止多流下载（视频流→音频流）进度重置导致的闪跳
            new_pct = round(min(raw_pct, 95.0), 1)
            new_pct = max(new_pct, state["max_pct"])
            state["max_pct"] = new_pct
            store.update(
                task_id,
                status="downloading",
                percent=new_pct,
                speed=_clean(d.get("_speed_str")),
                eta=_clean(d.get("_eta_str")),
            )
        elif status == "finished":
            state["max_pct"] = 98.0
            store.update(task_id, status="processing", percent=98.0)

    return hook


def _make_pp_hook(task_id: str):
    def hook(d: dict) -> None:
        task = store.get(task_id)
        if task and task.is_cancelled:
            raise RuntimeError("下载已取消")
        if d.get("status") == "started":
            store.update(task_id, status="processing")

    return hook


def run_download(task_id: str, url: str, quality: str) -> None:
    """在后台线程中执行的下载主流程。"""
    try:
        url = normalize_url(url)
        store.update(task_id, status="downloading", percent=0.0)
        opts = _build_download_opts(task_id, quality, url)
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        if info.get("_type") == "playlist" and info.get("entries"):
            info = info["entries"][0]

        task = store.get(task_id)
        # 找到最终产物文件（取 workdir 下最新/最大文件）
        final_file = _resolve_output_file(task.workdir, info, quality)
        if not final_file:
            raise RuntimeError("未找到下载结果文件")

        store.update(
            task_id,
            status="finished",
            percent=100.0,
            filepath=str(final_file),
            filename=final_file.name,
            speed=None,
            eta=None,
        )
    except Exception as exc:  # noqa: BLE001 — 对外统一暴露友好错误
        task = store.get(task_id)
        if task and (task.status == "cancelled" or task.is_cancelled):
            store.update(task_id, status="cancelled")
            return
        store.update(task_id, status="error", error=_friendly_error(str(exc)))


def _resolve_output_file(workdir: Path, info: dict, quality: str) -> Optional[Path]:
    # 优先用 yt-dlp 给出的最终路径
    requested = info.get("requested_downloads")
    if requested:
        fp = requested[0].get("filepath")
        if fp and Path(fp).exists():
            return Path(fp)
    # 回退：扫描工作目录里体积最大的文件
    files = [p for p in workdir.glob("*") if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_size)


def _friendly_error(message: str) -> str:
    msg = message.lower()
    if "sign in to confirm" in msg or "not a bot" in msg or "confirm you" in msg:
        return "YouTube 触发了人机验证，需要提供登录 Cookie 才能下载（参考 backend/cookies/README）。"
    if "412" in msg or "precondition failed" in msg:
        return "该平台触发了风控（如 B 站），请提供登录 Cookie 后重试（参考 backend/cookies/README）。"
    if "drm" in msg:
        return "该视频受版权保护（DRM），无法下载。"
    if "cookie" in msg:
        return "该平台需要 Cookie 才能解析（如西瓜/快手/微博等），请在 backend/cookies 放置对应平台 Cookie 后重试（参考 backend/cookies/README）。"
    if "private" in msg or "members-only" in msg or "login" in msg or "sign in" in msg:
        return "该视频需要登录或为私密/会员内容，请提供对应平台的登录 Cookie 后重试。"
    if "geo" in msg or "not available in your" in msg:
        return "该视频存在地区限制，当前网络无法访问。"
    if "unsupported url" in msg or "no video" in msg:
        return "暂不支持该链接或未识别到视频，请检查链接是否正确。"
    return "解析或下载失败，请稍后重试或更换链接。"
