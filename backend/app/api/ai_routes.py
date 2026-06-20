from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    AiAnalyzeRequest,
    AiAnalyzeResponse,
    AiChatRequest,
    AiChatResponse,
    TranscriptSegment,
)
from app.services import ai_analyzer
from app.services import downloader
from app.services import transcript as transcript_svc

router = APIRouter(prefix="/api/ai")


@router.post("/analyze", response_model=AiAnalyzeResponse)
def analyze_video(req: AiAnalyzeRequest) -> AiAnalyzeResponse:
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="请输入视频链接")
    try:
        result = ai_analyzer.run_analyze(url)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=_friendly_ai_error(str(exc)))
    return AiAnalyzeResponse(
        title=result["title"],
        language=result["language"],
        segments=[
            TranscriptSegment(start=s.start, end=s.end, text=s.text)
            for s in result["segments"]
        ],
        full_text=result["full_text"],
        summary=result["summary"],
        mindmap=result["mindmap"],
        truncated=result["truncated"],
        subtitle_source=result.get("subtitle_source"),
    )


@router.post("/transcript")
def get_transcript(req: AiAnalyzeRequest) -> dict:
    """仅提取字幕/转录文本（带时间戳），不调用大模型。"""
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="请输入视频链接")
    try:
        result = transcript_svc.extract_transcript(url)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=_friendly_ai_error(str(exc)))
    return {
        "title": result.title,
        "language": result.language,
        "subtitle_source": result.source,
        "segments": [
            {"start": s.start, "end": s.end, "text": s.text} for s in result.segments
        ],
        "full_text": "\n".join(s.text for s in result.segments),
    }


@router.post("/chat", response_model=AiChatResponse)
def chat_about_video(req: AiChatRequest) -> AiChatResponse:
    url = req.url.strip()
    question = req.question.strip()
    if not url:
        raise HTTPException(status_code=400, detail="请输入视频链接")
    if not question:
        raise HTTPException(status_code=400, detail="请输入问题")
    try:
        answer = ai_analyzer.run_chat(
            url=url,
            question=question,
            transcript_text=req.transcript_text,
            history=[{"role": m.role, "content": m.content} for m in req.history],
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=_friendly_ai_error(str(exc)))
    return AiChatResponse(answer=answer)


def _friendly_ai_error(message: str) -> str:
    msg = message.lower()
    if "deepseek_api_key" in msg or "未配置 deepseek" in message.lower():
        return "未配置 DeepSeek API Key，请在 backend/.env 中设置 DEEPSEEK_API_KEY。"
    if "暂无可用字幕" in message or "抖音公开接口" in message or "no subtitles" in msg:
        return message
    if "errno 22" in msg or "invalid argument" in msg or "字幕文件写入失败" in message:
        return (
            "字幕文件写入失败（Windows 路径或 ffmpeg 兼容性问题）。"
            "请稍后重试或更换视频。"
        )
    if "401" in message or "authentication" in msg or "invalid api key" in msg:
        return "DeepSeek API Key 无效或已过期，请检查 backend/.env 中的 DEEPSEEK_API_KEY。"
    if "402" in message or "insufficient" in msg or "balance" in msg:
        return "DeepSeek 账户余额不足，请充值后重试。"
    if "429" in message or "rate limit" in msg:
        return "DeepSeek 请求过于频繁，请稍后再试。"
    if "deepseek 未返回有效正文" in message or "finish_reason=length" in msg:
        return message
    if message.startswith("DeepSeek API 错误"):
        return message[:300]
    if "unsupported url" in msg or "no video" in msg:
        return downloader._friendly_error(message)
    return message[:300] if len(message) > 300 else message
