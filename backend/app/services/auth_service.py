from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.database import db
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_token,
    generate_verification_code,
    hash_password,
    hash_token,
    verify_password,
)
from app.services.email_service import send_magic_link_email, send_verification_email

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)


def _send_email_verification(user_id: str, email: str) -> str:
    code = generate_verification_code()
    expires = (
        datetime.now(UTC) + timedelta(minutes=settings.email_verify_expire_minutes)
    ).isoformat()
    db.invalidate_user_tokens(user_id, "email_verify")
    db.create_auth_token(user_id, hash_token(code), "email_verify", expires, code=code)
    send_verification_email(email, code)
    return code


def _with_dev_code(payload: dict, code: str | None = None) -> dict:
    if settings.dev_email_log and code:
        payload["dev_code"] = code
    return payload


def register_user(email: str, password: str) -> dict:
    email = email.strip().lower()
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="密码至少 8 位")

    existing = db.get_user_by_email(email)
    if existing:
        if existing["email_verified"]:
            raise HTTPException(status_code=409, detail="该邮箱已注册，请直接登录")
        db.update_user_password(existing["id"], hash_password(password))
        code = _send_email_verification(existing["id"], email)
        return _with_dev_code(
            {
                "message": "该邮箱已注册但未验证，已更新密码并重新发送验证码",
                "email": email,
                "need_verify": True,
            },
            code,
        )

    user = db.create_user(email, hash_password(password))
    code = _send_email_verification(user["id"], email)
    return _with_dev_code(
        {"message": "注册成功，请查收邮箱验证码", "email": email, "need_verify": True},
        code,
    )


def verify_email(email: str, code: str) -> dict:
    user = db.get_user_by_email(email.strip().lower())
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user["email_verified"]:
        token = create_access_token(user["id"], user["email"])
        return {"access_token": token, "token_type": "bearer", "user": public_user(user)}

    record = db.get_valid_auth_token_by_code(user["id"], code.strip(), "email_verify")
    if not record:
        raise HTTPException(status_code=400, detail="验证码无效或已过期")

    db.mark_auth_token_used(record["id"])
    db.mark_email_verified(user["id"])
    user = db.get_user_by_id(user["id"])
    token = create_access_token(user["id"], user["email"])  # type: ignore[index]
    return {"access_token": token, "token_type": "bearer", "user": public_user(user)}


def login_user(email: str, password: str) -> dict:
    user = db.get_user_by_email(email.strip().lower())
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not user["email_verified"]:
        raise HTTPException(
            status_code=403,
            detail="请先验证邮箱后再登录（可在注册页用同一邮箱重新提交以获取验证码）",
        )
    token = create_access_token(user["id"], user["email"])
    return {"access_token": token, "token_type": "bearer", "user": public_user(user)}


def request_magic_link(email: str) -> dict:
    user = db.get_user_by_email(email.strip().lower())
    if not user:
        raise HTTPException(status_code=404, detail="该邮箱尚未注册，请先注册")
    if not user["email_verified"]:
        raise HTTPException(status_code=403, detail="请先完成邮箱验证")

    raw_token = generate_token()
    expires = (
        datetime.now(UTC) + timedelta(minutes=settings.magic_link_expire_minutes)
    ).isoformat()
    db.invalidate_user_tokens(user["id"], "magic_link")
    db.create_auth_token(user["id"], hash_token(raw_token), "magic_link", expires)
    link = f"{settings.app_base_url}/auth/magic?token={raw_token}"
    send_magic_link_email(user["email"], link)
    return {"message": "登录链接已发送，请查收邮箱"}


def verify_magic_link(raw_token: str) -> dict:
    record = db.get_valid_auth_token(hash_token(raw_token.strip()), "magic_link")
    if not record:
        raise HTTPException(status_code=400, detail="登录链接无效或已过期")

    db.mark_auth_token_used(record["id"])
    user = db.get_user_by_id(record["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    token = create_access_token(user["id"], user["email"])
    return {"access_token": token, "token_type": "bearer", "user": public_user(user)}


def resend_verification(email: str) -> dict:
    user = db.get_user_by_email(email.strip().lower())
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user["email_verified"]:
        logger.info("跳过发送验证码：%s 已完成邮箱验证，请直接登录", user["email"])
        return {
            "message": "该邮箱已完成验证，无需验证码，请使用密码直接登录",
            "email": user["email"],
            "already_verified": True,
        }

    code = _send_email_verification(user["id"], user["email"])
    return _with_dev_code({"message": "验证码已重新发送", "email": user["email"]}, code)


def public_user(user: dict) -> dict:
    membership = get_membership_status(user)
    return {
        "id": user["id"],
        "email": user["email"],
        "email_verified": bool(user["email_verified"]),
        "membership": membership,
    }


def get_membership_status(user: dict) -> dict:
    plan = user.get("plan") or "free"
    expires_at = user.get("plan_expires_at")
    now = datetime.now(UTC)

    if plan == "ultimate" and expires_at:
        try:
            exp = datetime.fromisoformat(expires_at)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)
            if exp <= now:
                plan = "free"
                expires_at = None
        except ValueError:
            pass

    sub = db.get_active_subscription(user["id"])
    has_subscription = bool(sub and sub["status"] in ("active", "trialing", "past_due"))
    if has_subscription:
        plan = sub["plan"]
        expires_at = sub.get("current_period_end")

    labels = {"free": "免费版", "pro": "Pro 会员", "ultimate": "旗舰版"}
    can_manage = has_subscription and bool(user.get("stripe_customer_id"))
    return {
        "plan": plan,
        "plan_label": labels.get(plan, plan),
        "expires_at": expires_at,
        "is_premium": plan in ("pro", "ultimate"),
        "has_subscription": has_subscription,
        "can_manage_subscription": can_manage,
    }


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    try:
        payload = decode_access_token(credentials.credentials)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录") from exc

    user = db.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user
