"""B 站 AI 分析联调脚本。

用法（在后端目录）：
    python scripts/test_ai_integration.py
    python scripts/test_ai_integration.py --analyze   # 需配置 DEEPSEEK_API_KEY
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

BILI_TEST_URL = "https://www.bilibili.com/video/BV1awjw6qEog"


def test_transcript(url: str = BILI_TEST_URL) -> bool:
    from app.services.transcript import extract_transcript

    print(f"[transcript] {url}")
    result = extract_transcript(url)
    print(f"  title: {result.title}")
    print(f"  lang: {result.language}  source: {result.source}  segments: {len(result.segments)}")
    if result.segments:
        s = result.segments[0]
        print(f"  first: [{s.start:.1f}s] {s.text[:80]}")
    ok = len(result.segments) > 0
    print("  PASS" if ok else "  FAIL")
    return ok


def test_metadata_fallback(url: str) -> bool:
    from app.services.transcript import extract_for_analysis

    print(f"[metadata-fallback] {url}")
    result = extract_for_analysis(url)
    ok = result.source == "metadata" and len(result.segments) > 0
    print(f"  source={result.source} segments={len(result.segments)}")
    print("  PASS" if ok else "  FAIL (may need URL without subtitles)")
    return ok


def test_analyze(url: str = BILI_TEST_URL) -> bool:
    from app.services.ai_analyzer import run_analyze

    print(f"[analyze] {url} (calls DeepSeek, may take ~60s)")
    data = run_analyze(url)
    print(f"  title: {data['title']}")
    print(f"  source: {data.get('subtitle_source')}")
    print(f"  summary len: {len(data['summary'])}")
    print(f"  mindmap len: {len(data['mindmap'])}")
    print(f"  summary preview: {data['summary'][:120]}...")
    ok = bool(data["summary"] and data["mindmap"])
    print("  PASS" if ok else "  FAIL")
    return ok


def test_http(base: str = "http://127.0.0.1:8000", url: str = BILI_TEST_URL) -> bool:
    import urllib.request

    payload = json.dumps({"url": url}).encode()
    req = urllib.request.Request(
        f"{base}/api/ai/transcript",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    print(f"[http] POST {base}/api/ai/transcript")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        print(f"  FAIL: {exc}")
        return False
    print(f"  title: {data.get('title')}")
    print(f"  source: {data.get('subtitle_source')}  segments: {len(data.get('segments', []))}")
    ok = len(data.get("segments", [])) > 0
    print("  PASS" if ok else "  FAIL")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analyze", action="store_true", help="含 DeepSeek 完整分析")
    parser.add_argument("--http", action="store_true", help="通过 HTTP API 测试")
    parser.add_argument("--metadata", action="store_true", help="测试无字幕元数据降级")
    parser.add_argument("--url", default=BILI_TEST_URL)
    args = parser.parse_args()

    ok = test_transcript(args.url)
    if args.metadata:
        ok = test_metadata_fallback(args.url) and ok
    if args.http:
        ok = test_http(url=args.url) and ok
    if args.analyze:
        ok = test_analyze(args.url) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
