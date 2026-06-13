"""URL 解析与网页嵌入视频识别回归测试。"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services import downloader  # noqa: E402

SAMPLE_HTML = """
<p>课程视频：<a href="https://www.bilibili.com/video/BV1YvmbYbEgS/">B站</a></p>
<p>备用：https://bilibili.com/video/BV1YvmbYbEgS</p>
"""


def test_normalize_bilibili_without_www():
    url = downloader.normalize_url("https://bilibili.com/video/BV1YvmbYbEgS")
    assert url == "https://www.bilibili.com/video/BV1YvmbYbEgS"


def test_extract_embedded_from_html():
    url = downloader._extract_embedded_video_url(SAMPLE_HTML)
    assert url == "https://www.bilibili.com/video/BV1YvmbYbEgS"


def test_resolve_from_course_page():
    page = "https://www.codefather.cn/course/1/section/2"
    with patch.object(downloader, "_fetch_page_html", return_value=SAMPLE_HTML):
        video, source = downloader.resolve_video_url(page)
    assert source == page
    assert video == "https://www.bilibili.com/video/BV1YvmbYbEgS"


def test_direct_url_skips_fetch():
    direct = "https://www.bilibili.com/video/BV1abc12345"
    with patch.object(downloader, "_fetch_page_html") as mock_fetch:
        video, source = downloader.resolve_video_url(direct)
    mock_fetch.assert_not_called()
    assert source is None
    assert video == direct


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
