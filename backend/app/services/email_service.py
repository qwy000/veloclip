from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send_smtp(to: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        return
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


def send_email(to: str, subject: str, body: str) -> None:
    if settings.dev_email_log or not settings.smtp_host:
        dev_block = f"=== EMAIL (dev) ===\nTo: {to}\nSubject: {subject}\n{body}\n================="
        logger.info(dev_block)
        # uvicorn 默认不展示 app logger，开发模式同时 print 到控制台
        print(dev_block, flush=True)
    if settings.smtp_host:
        _send_smtp(to, subject, body)


def send_verification_email(to: str, code: str) -> None:
    subject = "VeloClip 邮箱验证码"
    body = (
        f"你的 VeloClip 验证码是：{code}\n\n"
        f"验证码 {settings.email_verify_expire_minutes} 分钟内有效。\n"
        "如非本人操作，请忽略此邮件。"
    )
    send_email(to, subject, body)


def send_magic_link_email(to: str, link: str) -> None:
    subject = "VeloClip 登录链接"
    body = (
        f"点击以下链接登录 VeloClip（{settings.magic_link_expire_minutes} 分钟内有效）：\n\n"
        f"{link}\n\n"
        "如非本人操作，请忽略此邮件。"
    )
    send_email(to, subject, body)
