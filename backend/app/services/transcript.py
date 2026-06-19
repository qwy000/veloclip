"""从视频平台提取字幕/转录文本（带时间戳），不下载视频本体。"""
from __future__ import annotations

import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from yt_dlp import YoutubeDL

from app.services.downloader import _base_opts, resolve_video_url

PREFERRED_LANGS = ["zh-Hans", "zh-CN", "zh-Hant", "zh", "en", "en-US", "en-GB"]
DANMAKU_LANG = "danmaku"
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
    source: str  # cc | auto | danmaku


def _parse_danmaku_xml(content: str, *, max_segments: int = 800) -> list[TranscriptSegment]:
    """解析 B 站弹幕 XML（兜底，非官方 CC）。"""
    root = ET.fromstring(content)
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
    name = path.name.lower()
    content = path.read_text(encoding="utf-8", errors="replace")
    if "danmaku" in name or (content.lstrip().startswith("<?xml") and "<d p=" in content[:2000]):
        return _parse_danmaku_xml(content)
    suffix = path.suffix.lower()
    if suffix == ".vtt" or content.lstrip().startswith("WEBVTT"):
        return _parse_vtt(content)
    if suffix == ".srt":
        return _parse_srt(content)
    return _parse_vtt(content)


def _segments_to_text(segments: list[TranscriptSegment]) -> str:
    return "\n".join(seg.text for seg in segments)


def _pick_subtitle_lang(info: dict) -> tuple[str | None, str]:
    """优先 CC/自动字幕，B 站无 CC 时兜底弹幕。返回 (语言代码, 来源类型)。"""
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
    if DANMAKU_LANG in manual:
        return DANMAKU_LANG, "danmaku"
    return None, ""


def _is_bilibili(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "bilibili.com" in host or host.endswith(".b23.tv") or host == "b23.tv"


def extract_transcript(url: str) -> TranscriptResult:
    """提取字幕，返回标题、语言、分段及来源类型。"""
    video_url, _ = resolve_video_url(url)
    tmp = Path(tempfile.mkdtemp(prefix="veloclip_sub_"))
    try:
        probe_opts = {**_base_opts(video_url), "skip_download": True, "listsubtitles": True}
        with YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if info.get("_type") == "playlist" and info.get("entries"):
                info = info["entries"][0]

        lang, source = _pick_subtitle_lang(info)
        if not lang:
            raise RuntimeError("该视频暂无可用字幕，无法进行 AI 分析。请尝试带官方字幕的视频。")

        is_danmaku = lang == DANMAKU_LANG
        dl_opts = {
            **_base_opts(video_url),
            "skip_download": True,
            "writesubtitles": lang in (info.get("subtitles") or {}),
            "writeautomaticsub": lang in (info.get("automatic_captions") or {}),
            "subtitleslangs": [lang],
            "subtitlesformat": "xml" if is_danmaku else "vtt/srt/best",
            "outtmpl": str(tmp / "video"),
        }
        if lang in (info.get("automatic_captions") or {}):
            dl_opts["writeautomaticsub"] = True
        if lang in (info.get("subtitles") or {}):
            dl_opts["writesubtitles"] = True

        with YoutubeDL(dl_opts) as ydl:
            ydl.extract_info(video_url, download=True)

        allowed_suffixes = (".vtt", ".srt", ".ass", ".xml")
        sub_files = sorted(
            [p for p in tmp.glob("video.*") if p.suffix.lower() in allowed_suffixes],
            key=lambda p: p.stat().st_size,
            reverse=True,
        )
        if not sub_files:
            raise RuntimeError("该视频暂无可用字幕，无法进行 AI 分析。请尝试带官方字幕的视频。")

        segments = _parse_subtitle_file(sub_files[0])
        if not segments:
            raise RuntimeError("字幕文件解析失败，请更换视频链接后重试。")

        title = info.get("title") or "未命名视频"
        if is_danmaku and _is_bilibili(video_url):
            source = "danmaku"
        return TranscriptResult(title=title, language=lang, segments=segments, source=source)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
