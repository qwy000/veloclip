from __future__ import annotations

from fastapi import APIRouter, Depends

from app.models.schemas import (
    AuthTokenResponse,
    EmailOnlyRequest,
    LoginRequest,
    MagicLinkVerifyRequest,
    MessageResponse,
    RegisterRequest,
    UserPublic,
    VerifyEmailRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=MessageResponse)
def register(req: RegisterRequest) -> MessageResponse:
    result = auth_service.register_user(req.email, req.password)
    return MessageResponse(**result)


@router.post("/verify-email", response_model=AuthTokenResponse)
def verify_email(req: VerifyEmailRequest) -> AuthTokenResponse:
    result = auth_service.verify_email(req.email, req.code)
    return AuthTokenResponse(**result)


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(req: EmailOnlyRequest) -> MessageResponse:
    result = auth_service.resend_verification(req.email)
    return MessageResponse(**result)


@router.post("/login", response_model=AuthTokenResponse)
def login(req: LoginRequest) -> AuthTokenResponse:
    result = auth_service.login_user(req.email, req.password)
    return AuthTokenResponse(**result)


@router.post("/magic-link", response_model=MessageResponse)
def magic_link(req: EmailOnlyRequest) -> MessageResponse:
    result = auth_service.request_magic_link(req.email)
    return MessageResponse(**result)


@router.post("/magic-link/verify", response_model=AuthTokenResponse)
def verify_magic_link(req: MagicLinkVerifyRequest) -> AuthTokenResponse:
    result = auth_service.verify_magic_link(req.token)
    return AuthTokenResponse(**result)


@router.get("/me", response_model=UserPublic)
def me(user: dict = Depends(auth_service.get_current_user)) -> UserPublic:
    return UserPublic(**auth_service.public_user(user))
