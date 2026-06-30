"""AI 视频分析：总结、思维导图、问答。"""
from __future__ import annotations

from app.services import llm
from app.services.transcript import extract_for_analysis, truncate_for_llm

SUMMARY_PROMPT = """你是一位专业的视频内容分析师。请根据以下视频字幕，生成结构化的中文总结。

视频标题：{title}
{context_note}

要求：
1. 用一句话概括核心主题（加粗）
2. 分 3-6 个要点段落，每段有小标题（##）
3. 如有重要数据/结论请突出
4. 使用 Markdown 格式，全部中文"""

SUMMARY_PROMPT_METADATA = """你是一位专业的视频内容分析师。该视频**未检测到可用字幕**，请仅根据以下元数据（标题、简介、作者等）生成结构化中文总结。

视频标题：{title}
{context_note}

要求：
1. 开头明确说明「本总结基于视频元数据，未使用字幕」
2. 用一句话概括可能的核心主题（加粗），并标注为推测
3. 分 3-5 个要点段落，每段有小标题（##）
4. 不要编造字幕中才有的具体细节
5. 使用 Markdown 格式，全部中文"""

MINDMAP_PROMPT = """根据以下视频字幕，生成适合思维导图展示的 Markdown 大纲。

要求：
- 第一行用 # 作为中心主题
- 用 ##、### 和 - 列表项组织，层次清晰，3-4 层深度
- 全部中文，简洁有力
- 只输出 Markdown，不要其他说明

视频标题：{title}
{context_note}

内容：
{transcript}"""

MINDMAP_PROMPT_METADATA = """该视频**未检测到可用字幕**。请根据以下元数据生成思维导图 Markdown 大纲。

要求：
- 第一行用 # 作为中心主题
- 用 ##、### 和 - 列表项组织，层次清晰
- 基于标题/简介/标签合理推测结构，不要编造具体台词
- 只输出 Markdown，不要其他说明

视频标题：{title}
{context_note}

元数据：
{transcript}"""

CHAT_SYSTEM_PROMPT = """你是 VeloClip 的视频内容助手。用户正在学习以下视频，请基于字幕内容回答问题。
如果字幕中没有相关信息，请诚实说明，不要编造。
回答简洁清晰，使用中文 Markdown（可含列表）。

视频标题：{title}
{context_note}

内容：
{transcript}"""

CHAT_SYSTEM_PROMPT_METADATA = """你是 VeloClip 的视频内容助手。该视频**未检测到可用字幕**，请仅基于元数据回答问题。
若信息不足请诚实说明，不要编造字幕细节。
回答简洁清晰，使用中文 Markdown（可含列表）。

视频标题：{title}
{context_note}

元数据：
{transcript}"""


def _truncated_note(was_truncated: bool) -> str:
    if was_truncated:
        return "（注：内容较长，以下仅为前半部分）"
    return ""


def _source_note(source: str) -> str:
    if source == "danmaku":
        return "（注：当前为 B 站弹幕文本，非官方 CC，AI 结果仅供参考）"
    if source == "metadata":
        return "（注：未检测到字幕，当前基于视频标题/简介等元数据分析）"
    if source == "auto":
        return "（注：当前为平台自动生成的字幕）"
    return ""


def _analysis_context(source: str, truncated: bool) -> str:
    return _truncated_note(truncated) + _source_note(source)


def run_analyze(url: str) -> dict:
    """提取字幕（或元数据降级）并生成总结 + 思维导图 Markdown。"""
    result = extract_for_analysis(url)
    title, language, segments, source = (
        result.title,
        result.language,
        result.segments,
        result.source,
    )
    transcript, truncated = truncate_for_llm(segments)
    context_note = _analysis_context(source, truncated)
    is_metadata = source == "metadata"

    summary_prompt = SUMMARY_PROMPT_METADATA if is_metadata else SUMMARY_PROMPT
    mindmap_prompt = MINDMAP_PROMPT_METADATA if is_metadata else MINDMAP_PROMPT

    summary = llm.chat_completion(
        [
            {
                "role": "system",
                "content": summary_prompt.format(title=title, context_note=context_note),
            },
            {"role": "user", "content": f"内容：\n{transcript}"},
        ],
        temperature=0.5,
    )

    mindmap = llm.chat_completion(
        [
            {"role": "system", "content": "你是思维导图专家，只输出 Markdown 大纲。"},
            {
                "role": "user",
                "content": mindmap_prompt.format(
                    title=title,
                    context_note=context_note,
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
    subtitle_source: str | None = None,
) -> str:
    """基于字幕或元数据内容的 AI 问答。"""
    source = subtitle_source or "cc"
    if transcript_text and transcript_text.strip():
        title = "视频"
        transcript = transcript_text.strip()
        truncated = len(transcript) > 12000
        if truncated:
            transcript = transcript[:12000]
    else:
        extracted = extract_for_analysis(url)
        title = extracted.title
        source = extracted.source
        segments = extracted.segments
        transcript, truncated = truncate_for_llm(segments)

    context_note = _analysis_context(source, truncated)
    system_prompt = (
        CHAT_SYSTEM_PROMPT_METADATA if source == "metadata" else CHAT_SYSTEM_PROMPT
    )
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": system_prompt.format(
                title=title, context_note=context_note, transcript=transcript
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
