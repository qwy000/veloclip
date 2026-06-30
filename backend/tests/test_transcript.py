"""字幕提取与元数据降级单元测试（stdlib unittest，无需 pytest）。"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.transcript import (  # noqa: E402
    TranscriptSegment,
    _build_metadata_text,
    _collect_subtitle_files,
    _ensure_subtitle_dir,
    _is_x,
    _metadata_transcript_result,
    _parse_danmaku_xml,
    _parse_srt,
    _parse_subtitle_file,
    _pick_subtitle_lang,
    truncate_for_llm,
)


class TestSubtitleParsing(unittest.TestCase):
    def test_parse_srt_basic(self) -> None:
        content = "1\n00:00:01,000 --> 00:00:03,000\nHello world\n"
        segs = _parse_srt(content)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0].text, "Hello world")

    def test_parse_danmaku_invalid_xml(self) -> None:
        segs = _parse_danmaku_xml("<broken")
        self.assertEqual(segs, [])

    def test_parse_subtitle_file_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "video.srt"
            path.write_text(
                "1\n00:00:00,000 --> 00:00:02,000\n中文测试\n",
                encoding="utf-8",
            )
            segs = _parse_subtitle_file(path)
            self.assertEqual(segs[0].text, "中文测试")

    def test_collect_subtitle_files_skips_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _ensure_subtitle_dir(tmp)
            empty = tmp / "video.srt"
            empty.write_text("", encoding="utf-8")
            valid = tmp / "video.vtt"
            valid.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nok\n", encoding="utf-8")
            files = _collect_subtitle_files(tmp)
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].suffix, ".vtt")


class TestMetadataFallback(unittest.TestCase):
    def test_build_metadata_text(self) -> None:
        info = {
            "title": "Test Video",
            "description": "Desc line",
            "uploader": "Author",
            "duration": 120,
            "tags": ["tag1", "tag2"],
        }
        text = _build_metadata_text(info, "https://x.com/user/status/1")
        self.assertIn("Test Video", text)
        self.assertIn("未检测到可用字幕", text)
        self.assertIn("Author", text)

    def test_metadata_transcript_result(self) -> None:
        info = {"title": "X Post", "description": "Hello from X"}
        result = _metadata_transcript_result(info, "https://x.com/i/status/123")
        self.assertEqual(result.source, "metadata")
        self.assertEqual(len(result.segments), 1)
        self.assertIn("X Post", result.segments[0].text)

    def test_is_x(self) -> None:
        self.assertTrue(_is_x("https://x.com/foo/status/1"))
        self.assertTrue(_is_x("https://twitter.com/foo/status/1"))
        self.assertFalse(_is_x("https://bilibili.com/video/BV1"))


class TestSubtitleLangPick(unittest.TestCase):
    def test_bilibili_prefers_cc_over_danmaku(self) -> None:
        info = {
            "subtitles": {"zh-CN": [{}], "danmaku": [{}]},
            "automatic_captions": {},
        }
        lang, source = _pick_subtitle_lang(info, video_url="https://www.bilibili.com/video/BV1")
        self.assertEqual(lang, "zh-CN")
        self.assertEqual(source, "cc")

    def test_bilibili_danmaku_when_no_cc(self) -> None:
        info = {"subtitles": {"danmaku": [{}]}, "automatic_captions": {}}
        lang, source = _pick_subtitle_lang(info, video_url="https://www.bilibili.com/video/BV1")
        self.assertEqual(lang, "danmaku")
        self.assertEqual(source, "danmaku")


class TestTruncate(unittest.TestCase):
    def test_truncate_for_llm(self) -> None:
        segs = [TranscriptSegment(start=0, end=1, text="a" * 100) for _ in range(200)]
        text, truncated = truncate_for_llm(segs, max_chars=500)
        self.assertTrue(truncated)
        self.assertLessEqual(len(text), 500)


if __name__ == "__main__":
    unittest.main()
