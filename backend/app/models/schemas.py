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


# ---------------------------------------------------------------------------
# Auth & Billing
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    email: str
    password: str


class VerifyEmailRequest(BaseModel):
    email: str
    code: str = Field(..., min_length=6, max_length=6)


class EmailOnlyRequest(BaseModel):
    email: str


class MagicLinkVerifyRequest(BaseModel):
    token: str


class MembershipInfo(BaseModel):
    plan: str
    plan_label: str
    expires_at: Optional[str] = None
    is_premium: bool = False
    has_subscription: bool = Field(
        default=False,
        description="是否有 Stripe 月订（Pro）",
    )
    can_manage_subscription: bool = Field(
        default=False,
        description="是否可在 Stripe 客户门户管理/取消续费",
    )


class UserPublic(BaseModel):
    id: str
    email: str
    email_verified: bool
    membership: MembershipInfo


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class MessageResponse(BaseModel):
    message: str
    email: Optional[str] = None
    need_verify: Optional[bool] = None
    already_verified: Optional[bool] = None
    dev_code: Optional[str] = Field(
        default=None,
        description="仅 DEV_EMAIL_LOG=true 时返回，便于本地开发",
    )


class CheckoutRequest(BaseModel):
    plan: Literal["pro", "ultimate"]


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class SyncCheckoutRequest(BaseModel):
    session_id: str = Field(..., min_length=1)


class SyncCheckoutResponse(BaseModel):
    status: Literal["pending", "synced"]
    message: str
    membership: Optional[MembershipInfo] = None


class PortalResponse(BaseModel):
    portal_url: str


class BillingPlan(BaseModel):
    id: str
    name: str
    price_display: str
    period: str
    stripe_price_id: Optional[str] = None
    checkout_mode: Optional[str] = None
    currency_note: Optional[str] = None
    renewal_note: Optional[str] = None


class BillingStatusResponse(BaseModel):
    membership: MembershipInfo
    stripe_customer_id: Optional[str] = None
