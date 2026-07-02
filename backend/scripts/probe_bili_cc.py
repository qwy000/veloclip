"""Probe Bilibili CC subtitle sources."""
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.downloader import DESKTOP_UA, resolve_video_url
from yt_dlp import YoutubeDL
from app.services.downloader import _base_opts

url = sys.argv[1] if len(sys.argv) > 1 else "https://www.bilibili.com/video/BV1mAAmzqEfP"
video_url, _ = resolve_video_url(url)

with YoutubeDL({**_base_opts(video_url), "skip_download": True, "listsubtitles": True}) as ydl:
    info = ydl.extract_info(video_url, download=False)

print("subs:", list((info.get("subtitles") or {}).keys()))
print("cid in info:", info.get("cid"), "id:", info.get("id"))

bvid = info.get("id") or "BV1mAAmzqEfP"
view_api = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
req = urllib.request.Request(view_api, headers={"User-Agent": DESKTOP_UA})
with urllib.request.urlopen(req, timeout=15) as r:
    view = json.loads(r.read())
cid = (view.get("data") or {}).get("cid")
print("view cid:", cid)

if cid:
    wbi = f"https://api.bilibili.com/x/player/wbi/v2?bvid={bvid}&cid={cid}"
    req2 = urllib.request.Request(
        wbi, headers={"User-Agent": DESKTOP_UA, "Referer": "https://www.bilibili.com/"}
    )
    with urllib.request.urlopen(req2, timeout=15) as r2:
        wbi_data = json.loads(r2.read())
    sub = (wbi_data.get("data") or {}).get("subtitle") or {}
    print("wbi tracks:", json.dumps(sub.get("subtitles") or [], ensure_ascii=False)[:500])
