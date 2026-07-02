from __future__ import annotations

import os
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


class Settings:
    app_base_url: str = _env("APP_BASE_URL", "http://localhost:5173")
    database_path: Path = Path(_env("DATABASE_PATH", str(_BACKEND_ROOT / "data" / "veloclip.db")))

    jwt_secret: str = _env("JWT_SECRET", "dev-change-me-in-production")
    jwt_expire_hours: int = int(_env("JWT_EXPIRE_HOURS", "168"))

    smtp_host: str = _env("SMTP_HOST")
    smtp_port: int = int(_env("SMTP_PORT", "587"))
    smtp_user: str = _env("SMTP_USER")
    smtp_password: str = _env("SMTP_PASSWORD")
    smtp_from: str = _env("SMTP_FROM", "noreply@veloclip.local")
    dev_email_log: bool = _env("DEV_EMAIL_LOG", "true").lower() in ("1", "true", "yes")

    stripe_secret_key: str = _env("STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = _env("STRIPE_WEBHOOK_SECRET")
    stripe_price_pro_monthly: str = _env("STRIPE_PRICE_PRO_MONTHLY")
    stripe_price_ultimate_onetime: str = _env("STRIPE_PRICE_ULTIMATE_ONETIME")
    stripe_currency: str = _env("STRIPE_CURRENCY", "cny").lower()

    email_verify_expire_minutes: int = int(_env("EMAIL_VERIFY_EXPIRE_MINUTES", "30"))
    magic_link_expire_minutes: int = int(_env("MAGIC_LINK_EXPIRE_MINUTES", "15"))


settings = Settings()
