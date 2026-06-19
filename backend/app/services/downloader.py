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
    (("iqiyi.com", "iq.com", "pps.tv"), "iqiyi.txt"),
]

# 可直接被 yt-dlp 识别的视频平台域名
_DIRECT_VIDEO_HOSTS = (
    "youtube.com",
    "youtu.be",
    "bilibili.com",
    "b23.tv",
    "douyin.com",
    "iesdouyin.com",
    "v.douyin.com",
    "tiktok.com",
    "ixigua.com",
    "v.ixigua.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "kuaishou.com",
    "v.kuaishou.com",
    "weibo.com",
    "weibo.cn",
    "iqiyi.com",
    "iq.com",
    "pps.tv",
)

# 从网页 HTML 中提取嵌入视频链接（按优先级排序）
_EMBEDDED_VIDEO_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"https?://(?:www\.)?bilibili\.com/video/[A-Za-z0-9]+/?"), r"\g<0>"),
    (re.compile(r"https?://(?:www\.)?b23\.tv/[A-Za-z0-9]+/?"), r"\g<0>"),
    (
        re.compile(r"https?://(?:www\.)?(?:youtube\.com/watch\?[^\s\"'<>\\]+|youtu\.be/[^\s\"'<>\\]+)"),
        r"\g<0>",
    ),
    (re.compile(r"https?://(?:www\.)?douyin\.com/video/\d+"), r"\g<0>"),
    (re.compile(r"https?://v\.douyin\.com/[A-Za-z0-9/_-]+/?"), r"\g<0>"),
    (re.compile(r"https?://(?:www\.)?ixigua\.com/\d+/?"), r"\g<0>"),
    (re.compile(r"https?://(?:www\.)?tiktok\.com/@[^/]+/video/\d+"), r"\g<0>"),
    (re.compile(r"BV[0-9A-Za-z]{10}"), r"https://www.bilibili.com/video/\g<0>"),
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


def _fetch_page_html(url: str) -> Optional[str]:
    """抓取网页 HTML，用于从课程/文章页提取嵌入的视频链接。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": DESKTOP_UA})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _is_direct_video_url(url: str) -> bool:
    """判断是否为 yt-dlp 可直接识别的视频平台链接或直链。"""
    if re.search(r"\.(mp4|m3u8|webm)(\?|$)", url, re.I):
        return True
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return any(host == h or host.endswith("." + h) for h in _DIRECT_VIDEO_HOSTS)


def _extract_embedded_video_url(html: str) -> Optional[str]:
    """从网页内容中提取第一个可识别的嵌入视频链接。"""
    for pattern, repl in _EMBEDDED_VIDEO_PATTERNS:
        match = pattern.search(html)
        if match:
            extracted = match.expand(repl).rstrip(")]")
            return normalize_url(extracted)
    return None


def resolve_video_url(url: str) -> tuple[str, Optional[str]]:
    """解析用户输入，必要时从网页中提取真实视频链接。

    返回 (video_url, source_page_url)。若用户粘贴的是课程/文章页等嵌入视频的网页，
    source_page_url 为原始链接，video_url 为识别出的平台直链。
    """
    original = (url or "").strip()
    if not original:
        return original, None
    if not urlparse(original).scheme:
        original = "https://" + original

    normalized = normalize_url(original)
    if _is_direct_video_url(normalized):
        return normalized, None

    html = _fetch_page_html(normalized)
    if html:
        embedded = _extract_embedded_video_url(html)
        if embedded and _is_direct_video_url(embedded):
            return embedded, original

    return normalized, None


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
    if not parsed.scheme:
        url = "https://" + url
        parsed = urlparse(url)
    host = parsed.netloc.lower()

    # B 站：统一为 www.bilibili.com/video/{id}
    if "bilibili.com" in host:
        m = re.search(r"/video/([A-Za-z0-9]+)", parsed.path)
        if m:
            return f"https://www.bilibili.com/video/{m.group(1)}"

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


def _format_short_edge(fmt: dict) -> int | None:
    """按视频短边像素衡量清晰度（横屏取 height，竖屏取 width，与平台 720P/1080P 一致）。"""
    w, h = fmt.get("width"), fmt.get("height")
    if isinstance(w, (int, float)) and isinstance(h, (int, float)) and w > 0 and h > 0:
        return int(min(w, h))
    res = fmt.get("resolution") or ""
    m = re.match(r"(\d+)x(\d+)", str(res))
    if m:
        return min(int(m.group(1)), int(m.group(2)))
    h_only = fmt.get("height")
    if isinstance(h_only, (int, float)) and h_only > 0:
        return int(h_only)
    note = f"{fmt.get('format_note') or ''} {fmt.get('format') or ''}"
    m = re.search(r"(\d{3,4})[pP]", note)
    if m:
        return int(m.group(1))
    return None


def _collect_short_edge_heights(raw_formats: list, info: dict | None = None) -> list[int]:
    edges: list[int] = []
    for f in raw_formats:
        edge = _format_short_edge(f)
        if edge and f.get("vcodec") not in (None, "none"):
            edges.append(edge)
    if info:
        w, h = info.get("width"), info.get("height")
        if isinstance(w, (int, float)) and isinstance(h, (int, float)) and w > 0 and h > 0:
            edges.append(int(min(w, h)))
        elif isinstance(h, (int, float)) and h > 0:
            edges.append(int(h))
    return edges


def _best_quality_label(raw_formats: list, info: dict | None = None) -> str:
    """根据可用流计算最佳画质档位的具体分辨率文案（短边像素）。"""
    edges = _collect_short_edge_heights(raw_formats, info)
    if not edges:
        return "最佳画质"
    max_edge = max(edges)
    for std in STANDARD_HEIGHTS:
        if max_edge >= std:
            if std == 2160:
                return "最佳画质 4K"
            return f"最佳画质 {std}p"
    return f"最佳画质 {max_edge}p"


def extract_info(url: str) -> InfoResponse:
    """解析视频信息，归并出标准清晰度档位 + 仅音频选项。"""
    video_url, source_page = resolve_video_url(url)
    opts = {**_base_opts(video_url), "skip_download": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(video_url, download=False)

    # 某些链接可能返回播放列表，取第一条
    if info.get("_type") == "playlist" and info.get("entries"):
        info = info["entries"][0]

    raw_formats = info.get("formats", []) or []

    # 统计每个标准清晰度档位（按短边像素，兼容横屏/竖屏）
    available_heights: dict[int, int] = {}
    short_edges = _collect_short_edge_heights(raw_formats, info)
    if short_edges:
        max_edge = max(short_edges)
        size_by_edge: dict[int, int] = {}
        for f in raw_formats:
            edge = _format_short_edge(f)
            if edge is None or f.get("vcodec") in (None, "none"):
                continue
            size = f.get("filesize") or f.get("filesize_approx") or 0
            if size > size_by_edge.get(edge, 0):
                size_by_edge[edge] = size
        for std in STANDARD_HEIGHTS:
            if max_edge >= std:
                best_size = max(
                    (sz for edge, sz in size_by_edge.items() if edge >= std),
                    default=0,
                )
                available_heights[std] = best_size

    formats: list[FormatOption] = []
    # 最佳画质优先展示，标注具体分辨率
    formats.append(
        FormatOption(
            quality="best",
            label=_best_quality_label(raw_formats, info),
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
        webpage_url=info.get("webpage_url") or video_url,
        resolved_url=video_url if source_page else None,
        formats=formats,
    )


def _format_selector(quality: str) -> str:
    """根据清晰度档位生成 yt-dlp 的 format 选择串。

    优先选择 h264(avc1)+aac(mp4a) 组合，确保 MP4 容器兼容性（避免 VP9/AV1/Opus
    塞进 MP4 导致播放器兼容问题），不可用时回退到任意编码。
    """
    if quality == "best":
        # 最佳画质优先最高分辨率，再尽量选 h264+aac 兼容组合
        return (
            "bestvideo+bestaudio/"
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
        video_url, _ = resolve_video_url(url)
        store.update(task_id, status="downloading", percent=0.0)
        opts = _build_download_opts(task_id, quality, video_url)
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url, download=True)

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
        return "YouTube 触发了人机验证，当前无法免登录解析，请更换其他平台视频链接。"
    if "412" in msg or "precondition failed" in msg:
        return "该平台触发了风控，请稍后重试或粘贴 B 站/YouTube 等平台的直接视频链接。"
    if "drm" in msg:
        return "该视频受版权保护（DRM），无法下载。"
    if "cookie" in msg:
        return "该平台暂无法免登录解析，请粘贴 B 站、抖音、TikTok 等平台的直接视频链接。"
    if "private" in msg or "members-only" in msg or "login" in msg or "sign in" in msg:
        return "该视频需要登录或为私密/会员内容，暂无法下载。"
    if "geo" in msg or "not available in your" in msg:
        return "该视频存在地区限制，当前网络无法访问。"
    if "unsupported url" in msg or "no video" in msg:
        return (
            "未能从该链接识别到可下载的视频。请粘贴 B 站/YouTube/抖音 等平台的直接视频链接，"
            "或包含嵌入视频的课程/文章页面链接。"
        )
    return "解析或下载失败，请稍后重试或更换链接。"
