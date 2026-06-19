"""AI 视频分析：总结、思维导图、问答。"""
from __future__ import annotations

from app.services import llm
from app.services.transcript import extract_transcript, truncate_for_llm

SUMMARY_PROMPT = """你是一位专业的视频内容分析师。请根据以下视频字幕，生成结构化的中文总结。

视频标题：{title}
{truncated_note}

要求：
1. 用一句话概括核心主题（加粗）
2. 分 3-6 个要点段落，每段有小标题（##）
3. 如有重要数据/结论请突出
4. 使用 Markdown 格式，全部中文"""

MINDMAP_PROMPT = """根据以下视频字幕，生成适合思维导图展示的 Markdown 大纲。

要求：
- 第一行用 # 作为中心主题
- 用 ##、### 和 - 列表项组织，层次清晰，3-4 层深度
- 全部中文，简洁有力
- 只输出 Markdown，不要其他说明

视频标题：{title}
{truncated_note}

字幕内容：
{transcript}"""

CHAT_SYSTEM_PROMPT = """你是 VeloClip 的视频内容助手。用户正在学习以下视频，请基于字幕内容回答问题。
如果字幕中没有相关信息，请诚实说明，不要编造。
回答简洁清晰，使用中文 Markdown（可含列表）。

视频标题：{title}
{truncated_note}

字幕内容：
{transcript}"""


def _truncated_note(was_truncated: bool) -> str:
    if was_truncated:
        return "（注：字幕较长，以下仅为前半部分）"
    return ""


def run_analyze(url: str) -> dict:
    """提取字幕并生成总结 + 思维导图 Markdown。"""
    result = extract_transcript(url)
    title, language, segments, source = (
        result.title,
        result.language,
        result.segments,
        result.source,
    )
    transcript, truncated = truncate_for_llm(segments)
    note = _truncated_note(truncated)
    danmaku_note = (
        "（注：当前为 B 站弹幕文本，非官方 CC，AI 结果仅供参考）" if source == "danmaku" else ""
    )

    summary = llm.chat_completion(
        [
            {
                "role": "system",
                "content": SUMMARY_PROMPT.format(title=title, truncated_note=note + danmaku_note),
            },
            {"role": "user", "content": f"字幕内容：\n{transcript}"},
        ],
        temperature=0.5,
    )

    mindmap = llm.chat_completion(
        [
            {"role": "system", "content": "你是思维导图专家，只输出 Markdown 大纲。"},
            {
                "role": "user",
                "content": MINDMAP_PROMPT.format(
                    title=title,
                    truncated_note=note + danmaku_note,
                    transcript=transcript,
                ),
            },
        ],
        temperature=0.4,
    )

    return {
        "title": title,
        "language": language,
        "segments": segments,
        "full_text": "\n".join(s.text for s in segments),
        "summary": summary,
        "mindmap": mindmap,
        "truncated": truncated,
        "subtitle_source": source,
    }


def run_chat(
    *,
    url: str,
    question: str,
    transcript_text: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> str:
    """基于字幕内容的 AI 问答。"""
    if transcript_text and transcript_text.strip():
        title = "视频"
        transcript = transcript_text.strip()
        truncated = len(transcript) > 12000
        if truncated:
            transcript = transcript[:12000]
    else:
        extracted = extract_transcript(url)
        title = extracted.title
        segments = extracted.segments
        transcript, truncated = truncate_for_llm(segments)

    note = _truncated_note(truncated)
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": CHAT_SYSTEM_PROMPT.format(
                title=title, truncated_note=note, transcript=transcript
            ),
        },
    ]
    for msg in history or []:
        role = msg.get("role")
        content = msg.get("content", "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question.strip()})

    return llm.chat_completion(messages, temperature=0.6)
