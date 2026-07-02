"""Probe a URL with yt-dlp and fetch page for embedded video links."""
import re
import sys
import urllib.request
from urllib.parse import urlparse

from yt_dlp import YoutubeDL

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def find_video_urls(html: str) -> list[str]:
    patterns = [
        r"https?://[^\s\"'<>\\]+(?:bilibili|youtube|douyin|ixigua|video|m3u8|mp4)[^\s\"'<>\\]*",
        r"\"(https?://[^\"]+)\"",
    ]
    found: set[str] = set()
    for pat in patterns:
        for m in re.finditer(pat, html, re.I):
            u = m.group(1) if m.lastindex else m.group(0)
            if any(k in u.lower() for k in ("bilibili", "youtube", "douyin", "video", "m3u8", "mp4", "player")):
                found.add(u.rstrip("\\"))
    return sorted(found)


def try_ytdlp(url: str) -> None:
    print(f"\n=== yt-dlp extract: {url}")
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            print("title:", info.get("title"))
            print("webpage_url:", info.get("webpage_url"))
            print("extractor:", info.get("extractor"))
    except Exception as e:
        print("ERROR:", e)


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else ""
    print("URL:", url)
    try:
        html = fetch_html(url)
        print("HTML length:", len(html))
        urls = find_video_urls(html)
        print("Found candidate URLs:", len(urls))
        for u in urls[:30]:
            print(" ", u)
    except Exception as e:
        print("fetch error:", e)
    try_ytdlp(url)
