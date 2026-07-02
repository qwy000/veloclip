import re
import urllib.request

url = "https://www.codefather.cn/course/2027618983506640897/section/2027619709460971521"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
patterns = [
    r"https?://(?:www\.)?bilibili\.com/video/[A-Za-z0-9]+/?",
    r"BV[0-9A-Za-z]{10}",
    r"https?://(?:www\.)?youtube\.com/watch\?[^\s\"'<>]+",
    r"https?://youtu\.be/[^\s\"'<>]+",
    r"https?://(?:www\.)?douyin\.com/video/\d+",
    r"\"videoUrl\"\s*:\s*\"([^\"]+)\"",
    r"\"url\"\s*:\s*\"(https?://[^\"]+)\"",
]
for p in patterns:
    ms = re.findall(p, html)
    print(p, "=>", ms[:8])
