"""Probe Bilibili subtitle tracks for a video."""
import json
import urllib.request

from app.services.downloader import DESKTOP_UA, resolve_video_url
from yt_dlp import YoutubeDL
from app.services.downloader import _base_opts

url = "https://www.bilibili.com/video/BV1awjw6qEog"
video_url, _ = resolve_video_url(url)

opts = {**_base_opts(video_url), "skip_download": True, "listsubtitles": True}
with YoutubeDL(opts) as ydl:
    info = ydl.extract_info(video_url, download=False)

print("title:", info.get("title"))
print("subs keys:", list((info.get("subtitles") or {}).keys()))
for lang, subs in (info.get("subtitles") or {}).items():
    print(f"  {lang}:", subs)

# wbi/v2 subtitle API
cid = info.get("cid")
aid = info.get("aid") or info.get("id")
if cid:
    api = f"https://api.bilibili.com/x/player/wbi/v2?bvid=BV1awjw6qEog&cid={cid}"
    req = urllib.request.Request(api, headers={"User-Agent": DESKTOP_UA, "Referer": "https://www.bilibili.com/"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    sub = (data.get("data") or {}).get("subtitle") or {}
    print("need_login_subtitle:", sub.get("need_login_subtitle"))
    print("subtitle list:", json.dumps(sub.get("subtitles") or [], ensure_ascii=False)[:500])
