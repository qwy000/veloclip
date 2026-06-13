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
