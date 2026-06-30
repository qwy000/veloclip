"""从视频平台提取字幕/转录文本（带时间戳），不下载视频本体。"""
from __future__ import annotations

import logging
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.services.downloader import _base_opts, resolve_video_url

logger = logging.getLogger(__name__)

PREFERRED_LANGS = ["zh-Hans", "zh-CN", "zh-Hant", "zh", "en", "en-US", "en-GB"]
DANMAKU_LANG = "danmaku"
SUBTITLE_SUFFIXES = (".vtt", ".srt", ".ass", ".xml", ".json3", ".ttml")
_TIME_RE = re.compile(
    r"(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})[.,](?P<ms>\d{3})"
    r"\s*-->\s*"
    r"(?P<h2>\d{1,2}):(?P<m2>\d{2}):(?P<s2>\d{2})[.,](?P<ms2>\d{3})"
)


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptResult:
    title: str
    language: str | None
    segments: list[TranscriptSegment]
    source: str  # cc | auto | danmaku | metadata


def _is_bilibili(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "bilibili.com" in host or host.endswith(".b23.tv") or host == "b23.tv"


def _is_douyin(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "douyin.com" in host or host in ("v.douyin.com", "iesdouyin.com")


def _is_x(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host in ("x.com", "twitter.com", "www.x.com", "www.twitter.com", "mobile.twitter.com")


def _allows_metadata_fallback(url: str) -> bool:
    """抖音硬字幕场景仍阻断；其余平台无字幕时允许元数据降级。"""
    return not _is_douyin(url)


def _ensure_subtitle_dir(tmp: Path) -> Path:
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp


def _subtitle_stem(tmp: Path) -> str:
    """固定短文件名，避免标题特殊字符导致 Windows 写入失败。"""
    return str(_ensure_subtitle_dir(tmp) / "video")


def _parse_danmaku_xml(content: str, *, max_segments: int = 800) -> list[TranscriptSegment]:
    """解析 B 站弹幕 XML（兜底，非官方 CC）。"""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        logger.warning("danmaku XML parse error: %s", exc)
        return []
    raw: list[tuple[float, str]] = []
    for node in root.findall("d"):
        attr = node.get("p", "")
        text = (node.text or "").strip()
        if not text or len(text) < 2:
            continue
        try:
            start = float(attr.split(",")[0])
        except (ValueError, IndexError):
            continue
        raw.append((start, text))

    raw.sort(key=lambda x: x[0])
    segments: list[TranscriptSegment] = []
    seen: set[str] = set()
    for start, text in raw:
        if text in seen:
            continue
        seen.add(text)
        end = start + 2.0
        segments.append(TranscriptSegment(start=start, end=end, text=text))
        if len(segments) >= max_segments:
            break
    return segments


def _ts_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _parse_vtt(content: str) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        if block.startswith("WEBVTT") or block.startswith("NOTE"):
            continue
        lines = block.strip().splitlines()
        if not lines:
            continue
        time_line = lines[0]
        match = _TIME_RE.search(time_line)
        if not match:
            continue
        start = _ts_to_seconds(match["h"], match["m"], match["s"], match["ms"])
        end = _ts_to_seconds(match["h2"], match["m2"], match["s2"], match["ms2"])
        text = " ".join(
            re.sub(r"<[^>]+>", "", line).strip()
            for line in lines[1:]
            if line.strip() and not line.strip().isdigit()
        )
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            segments.append(TranscriptSegment(start=start, end=end, text=text))
    return _dedupe_segments(segments)


def _parse_srt(content: str) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        time_idx = 0
        if lines[0].isdigit():
            time_idx = 1
        if time_idx >= len(lines):
            continue
        match = _TIME_RE.search(lines[time_idx])
        if not match:
            continue
        start = _ts_to_seconds(match["h"], match["m"], match["s"], match["ms"])
        end = _ts_to_seconds(match["h2"], match["m2"], match["s2"], match["ms2"])
        text = " ".join(lines[time_idx + 1 :])
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            segments.append(TranscriptSegment(start=start, end=end, text=text))
    return _dedupe_segments(segments)


def _dedupe_segments(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    """合并相邻重复文本（部分 VTT 含滚动重复行）。"""
    if not segments:
        return segments
    merged: list[TranscriptSegment] = [segments[0]]
    for seg in segments[1:]:
        prev = merged[-1]
        if seg.text == prev.text and seg.start <= prev.end + 0.5:
            merged[-1] = TranscriptSegment(start=prev.start, end=seg.end, text=prev.text)
        else:
            merged.append(seg)
    return merged


def _parse_subtitle_file(path: Path) -> list[TranscriptSegment]:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.error("read subtitle file failed path=%s error=%s", path, exc)
        return []
    if not content.strip():
        logger.warning("subtitle file empty path=%s", path)
        return []

    name = path.name.lower()
    try:
        if "danmaku" in name or (content.lstrip().startswith("<?xml") and "<d p=" in content[:2000]):
            return _parse_danmaku_xml(content)
        suffix = path.suffix.lower()
        if suffix == ".vtt" or content.lstrip().startswith("WEBVTT"):
            return _parse_vtt(content)
        if suffix == ".srt":
            return _parse_srt(content)
        return _parse_vtt(content)
    except Exception as exc:  # noqa: BLE001
        logger.error("parse subtitle failed path=%s error=%s", path, exc)
        return []


def _subtitle_opts(url: str, tmp: Path) -> dict:
    """字幕下载专用 yt-dlp 选项：固定短路径、仅拉字幕、不调用 ffmpeg。"""
    base = dict(_base_opts(url))
    base.pop("ffmpeg_location", None)
    stem = _subtitle_stem(tmp)
    return {
        **base,
        "skip_download": True,
        "windowsfilenames": True,
        "restrictfilenames": True,
        "trim_file_name": 80,
        "outtmpl": {"default": stem, "subtitle": stem},
    }


def _pick_subtitle_lang(info: dict, *, video_url: str) -> tuple[str | None, str]:
    """优先官方 CC/自动字幕；B 站 CC 失败时在下载阶段回退弹幕。"""
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    cc_manual = {k: v for k, v in manual.items() if k != DANMAKU_LANG}

    for lang in PREFERRED_LANGS:
        if lang in cc_manual:
            return lang, "cc"
        if lang in auto:
            return lang, "auto"

    if cc_manual:
        return next(iter(cc_manual)), "cc"
    if auto:
        return next(iter(auto)), "auto"
    if _is_bilibili(video_url) and DANMAKU_LANG in manual:
        return DANMAKU_LANG, "danmaku"
    if DANMAKU_LANG in manual:
        return DANMAKU_LANG, "danmaku"
    return None, ""


def _no_subtitle_error(url: str) -> str:
    if _is_douyin(url):
        return (
            "抖音公开接口未返回可下载的字幕轨，无法进行 AI 分析。"
            "播放器中显示的字幕可能是烧录在画面里的硬字幕。"
            "请尝试 B 站等提供 CC 字幕的视频。"
        )
    return "该视频暂无可用字幕，无法进行 AI 分析。请尝试带官方字幕的视频。"


def _subtitle_write_error(exc: BaseException, url: str) -> str:
    msg = str(exc).lower()
    if "errno 22" in msg or "invalid argument" in msg:
        return (
            "字幕文件写入失败（Windows 路径或 ffmpeg 兼容性问题）。"
            "请稍后重试或更换视频。"
        )
    if _is_douyin(url):
        return _no_subtitle_error(url)
    return str(exc)


def _collect_subtitle_files(tmp: Path) -> list[Path]:
    """收集临时目录内已写入的字幕文件（非空、合法后缀）。"""
    _ensure_subtitle_dir(tmp)
    found: list[Path] = []
    for pattern in ("video.*", "video"):
        for path in tmp.glob(pattern):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix and suffix not in SUBTITLE_SUFFIXES:
                continue
            try:
                if path.stat().st_size <= 0:
                    logger.warning("skip empty subtitle file path=%s", path)
                    continue
            except OSError as exc:
                logger.warning("stat subtitle file failed path=%s error=%s", path, exc)
                continue
            found.append(path)
    return sorted(found, key=lambda p: p.stat().st_size, reverse=True)


def _cleanup_partial_subtitles(tmp: Path) -> None:
    for pattern in ("video.*", "video"):
        for path in tmp.glob(pattern):
            if path.is_file():
                path.unlink(missing_ok=True)


def _download_subtitle_files(
    video_url: str, info: dict, lang: str, *, is_danmaku: bool, tmp: Path
) -> list[Path]:
    """下载字幕到临时目录，B 站 CC 失败时回退弹幕。"""
    _ensure_subtitle_dir(tmp)
    langs_to_try: list[tuple[str, bool]] = [(lang, is_danmaku)]
    if _is_bilibili(video_url) and not is_danmaku and DANMAKU_LANG in (info.get("subtitles") or {}):
        langs_to_try.append((DANMAKU_LANG, True))

    last_exc: BaseException | None = None
    for try_lang, try_danmaku in langs_to_try:
        formats = ["xml"] if try_danmaku else ["srt", "vtt", "best"]
        for sub_fmt in formats:
            dl_opts = {
                **_subtitle_opts(video_url, tmp),
                "writesubtitles": try_lang in (info.get("subtitles") or {}),
                "writeautomaticsub": try_lang in (info.get("automatic_captions") or {}),
                "subtitleslangs": [try_lang],
                "subtitlesformat": sub_fmt,
            }
            if try_lang in (info.get("automatic_captions") or {}):
                dl_opts["writeautomaticsub"] = True
            if try_lang in (info.get("subtitles") or {}):
                dl_opts["writesubtitles"] = True
            try:
                logger.info(
                    "subtitle download attempt url=%s lang=%s format=%s danmaku=%s",
                    video_url,
                    try_lang,
                    sub_fmt,
                    try_danmaku,
                )
                with YoutubeDL(dl_opts) as ydl:
                    ydl.extract_info(video_url, download=True)
                sub_files = _collect_subtitle_files(tmp)
                if sub_files:
                    logger.info(
                        "subtitle file written path=%s size=%d",
                        sub_files[0],
                        sub_files[0].stat().st_size,
                    )
                    return sub_files
                logger.warning(
                    "subtitle download produced no files url=%s lang=%s format=%s",
                    video_url,
                    try_lang,
                    sub_fmt,
                )
            except (OSError, RuntimeError, DownloadError) as exc:
                last_exc = exc
                logger.warning(
                    "subtitle download failed url=%s lang=%s format=%s error=%s",
                    video_url,
                    try_lang,
                    sub_fmt,
                    exc,
                )
                _cleanup_partial_subtitles(tmp)

    if last_exc:
        raise RuntimeError(_subtitle_write_error(last_exc, video_url)) from last_exc
    return []


def _probe_video_info(video_url: str, tmp: Path) -> dict:
    _ensure_subtitle_dir(tmp)
    probe_opts = {**_subtitle_opts(video_url, tmp), "listsubtitles": True}
    try:
        with YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if info.get("_type") == "playlist" and info.get("entries"):
                info = info["entries"][0]
            return info
    except (OSError, DownloadError) as exc:
        raise RuntimeError(_subtitle_write_error(exc, video_url)) from exc


def _build_metadata_text(info: dict, video_url: str) -> str:
    parts: list[str] = []
    title = info.get("title") or "未命名视频"
    parts.append(f"标题：{title}")

    description = (info.get("description") or "").strip()
    if description:
        parts.append(f"简介：{description[:4000]}")

    uploader = info.get("uploader") or info.get("channel") or info.get("creator")
    if uploader:
        parts.append(f"作者：{uploader}")

    duration = info.get("duration")
    if isinstance(duration, (int, float)) and duration > 0:
        parts.append(f"时长：{int(duration)} 秒")

    tags = info.get("tags")
    if isinstance(tags, list) and tags:
        parts.append(f"标签：{', '.join(str(t) for t in tags[:20])}")

    categories = info.get("categories")
    if isinstance(categories, list) and categories:
        parts.append(f"分类：{', '.join(str(c) for c in categories)}")

    view_count = info.get("view_count")
    if isinstance(view_count, int) and view_count > 0:
        parts.append(f"播放量：{view_count}")

    parts.append(f"来源链接：{video_url}")
    parts.append("（注：该视频未检测到可用字幕，以下分析基于视频元数据）")
    return "\n".join(parts)


def _metadata_transcript_result(info: dict, video_url: str) -> TranscriptResult:
    text = _build_metadata_text(info, video_url)
    title = info.get("title") or "未命名视频"
    segments = [TranscriptSegment(start=0.0, end=0.0, text=text)] if text.strip() else []
    logger.info(
        "using metadata fallback for analysis url=%s platform=%s segments=%d",
        video_url,
        urlparse(video_url).netloc,
        len(segments),
    )
    return TranscriptResult(title=title, language=None, segments=segments, source="metadata")


def _extract_subtitle_from_info(video_url: str, info: dict, tmp: Path) -> TranscriptResult:
    lang, source = _pick_subtitle_lang(info, video_url=video_url)
    if not lang:
        raise RuntimeError(_no_subtitle_error(video_url))

    is_danmaku = lang == DANMAKU_LANG
    sub_files = _download_subtitle_files(
        video_url, info, lang, is_danmaku=is_danmaku, tmp=tmp
    )
    if not sub_files:
        raise RuntimeError(_no_subtitle_error(video_url))

    segments = _parse_subtitle_file(sub_files[0])
    if not segments:
        logger.warning(
            "subtitle parse yielded empty segments url=%s file=%s",
            video_url,
            sub_files[0],
        )
        raise RuntimeError("字幕文件解析失败，请更换视频链接后重试。")

    if sub_files[0].suffix.lower() == ".xml" and _is_bilibili(video_url):
        source = "danmaku"
        lang = DANMAKU_LANG

    title = info.get("title") or "未命名视频"
    return TranscriptResult(title=title, language=lang, segments=segments, source=source)


def extract_transcript(url: str, *, allow_metadata_fallback: bool = False) -> TranscriptResult:
    """提取字幕；allow_metadata_fallback=True 时无字幕可降级为元数据分析。"""
    video_url, _ = resolve_video_url(url)
    tmp = Path(tempfile.mkdtemp(prefix="vcsub_"))
    try:
        info = _probe_video_info(video_url, tmp)
        try:
            return _extract_subtitle_from_info(video_url, info, tmp)
        except RuntimeError as exc:
            if allow_metadata_fallback and _allows_metadata_fallback(video_url):
                logger.warning(
                    "subtitle extraction failed, fallback to metadata url=%s reason=%s",
                    video_url,
                    exc,
                )
                result = _metadata_transcript_result(info, video_url)
                if result.segments:
                    return result
            raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def extract_for_analysis(url: str) -> TranscriptResult:
    """AI 分析专用：无字幕时（除抖音外）降级为元数据，不中断分析流程。"""
    return extract_transcript(url, allow_metadata_fallback=True)


def truncate_for_llm(segments: list[TranscriptSegment], max_chars: int = 12000) -> tuple[str, bool]:
    """将字幕截断到 LLM 可接受长度，返回 (文本, 是否被截断)。"""
    parts: list[str] = []
    total = 0
    truncated = False
    for seg in segments:
        line = seg.text
        if total + len(line) + 1 > max_chars:
            truncated = True
            break
        parts.append(line)
        total += len(line) + 1
    return "\n".join(parts), truncated
