from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class InfoRequest(BaseModel):
    url: str = Field(..., description="视频链接")


class FormatOption(BaseModel):
    quality: str = Field(..., description="清晰度标识，如 1080p / 720p / best / audio")
    label: str = Field(..., description="给用户展示的文案")
    ext: str = Field(default="mp4", description="目标文件扩展名")
    filesize: Optional[int] = Field(default=None, description="预估字节大小")
    type: Literal["video", "audio"] = Field(default="video")


class InfoResponse(BaseModel):
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    uploader: Optional[str] = None
    webpage_url: Optional[str] = None
    resolved_url: Optional[str] = Field(
        default=None,
        description="从网页中自动识别出的真实视频链接（若用户粘贴的是嵌入视频的页面）",
    )
    formats: list[FormatOption]


class DownloadRequest(BaseModel):
    url: str = Field(..., description="视频链接")
    quality: str = Field(default="best", description="清晰度标识，对应 FormatOption.quality")


class DownloadResponse(BaseModel):
    task_id: str


class ProgressResponse(BaseModel):
    status: Literal["queued", "downloading", "processing", "finished", "error", "cancelled"]
    percent: float = 0.0
    speed: Optional[str] = None
    eta: Optional[str] = None
    filename: Optional[str] = None
    error: Optional[str] = None


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class AiAnalyzeRequest(BaseModel):
    url: str = Field(..., description="视频链接")


class AiAnalyzeResponse(BaseModel):
    title: str
    language: Optional[str] = None
    segments: list[TranscriptSegment]
    full_text: str
    summary: str
    mindmap: str
    truncated: bool = False
    subtitle_source: Optional[str] = Field(
        default=None, description="cc | auto | danmaku | metadata"
    )


class AiChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AiChatRequest(BaseModel):
    url: str = Field(..., description="视频链接（用于无缓存字幕时重新提取）")
    question: str = Field(..., description="用户问题")
    transcript_text: Optional[str] = Field(
        default=None, description="已提取的字幕全文，传入可避免重复拉取"
    )
    subtitle_source: Optional[str] = Field(
        default=None, description="cc | auto | danmaku | metadata，与 transcript_text 配套"
    )
    history: list[AiChatMessage] = Field(default_factory=list)


class AiChatResponse(BaseModel):
    answer: str
