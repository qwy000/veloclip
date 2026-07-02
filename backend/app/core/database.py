from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from app.core.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    email_verified INTEGER NOT NULL DEFAULT 0,
    stripe_customer_id TEXT,
    plan TEXT NOT NULL DEFAULT 'free',
    plan_expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    token_type TEXT NOT NULL,
    code TEXT,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_auth_tokens_hash ON auth_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_auth_tokens_user ON auth_tokens(user_id);

CREATE TABLE IF NOT EXISTS stripe_subscriptions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    stripe_subscription_id TEXT NOT NULL UNIQUE,
    plan TEXT NOT NULL,
    status TEXT NOT NULL,
    current_period_end TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS processed_webhook_events (
    event_id TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checkout_sessions (
    idempotency_key TEXT PRIMARY KEY,
    stripe_session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    plan TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _connect() -> sqlite3.Connection:
    path = settings.database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


class Database:
    def __init__(self) -> None:
        self._conn = _connect()
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def create_user(self, email: str, password_hash: str) -> dict[str, Any]:
        user_id = str(uuid.uuid4())
        now = _now_iso()
        with self.transaction():
            self._conn.execute(
                """
                INSERT INTO users (id, email, password_hash, email_verified, created_at, updated_at)
                VALUES (?, ?, ?, 0, ?, ?)
                """,
                (user_id, email.lower(), password_hash, now, now),
            )
        return self.get_user_by_id(user_id)  # type: ignore[return-value]

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE",
            (email.lower(),),
        ).fetchone()
        return dict(row) if row else None

    def get_user_by_stripe_customer(self, stripe_customer_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM users WHERE stripe_customer_id = ?",
            (stripe_customer_id,),
        ).fetchone()
        return dict(row) if row else None

    def mark_email_verified(self, user_id: str) -> None:
        now = _now_iso()
        with self.transaction():
            self._conn.execute(
                "UPDATE users SET email_verified = 1, updated_at = ? WHERE id = ?",
                (now, user_id),
            )

    def update_user_password(self, user_id: str, password_hash: str) -> None:
        now = _now_iso()
        with self.transaction():
            self._conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (password_hash, now, user_id),
            )

    def update_stripe_customer(self, user_id: str, stripe_customer_id: str) -> None:
        now = _now_iso()
        with self.transaction():
            self._conn.execute(
                "UPDATE users SET stripe_customer_id = ?, updated_at = ? WHERE id = ?",
                (stripe_customer_id, now, user_id),
            )

    def set_user_plan(
        self,
        user_id: str,
        plan: str,
        plan_expires_at: str | None = None,
    ) -> None:
        now = _now_iso()
        with self.transaction():
            self._conn.execute(
                """
                UPDATE users SET plan = ?, plan_expires_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (plan, plan_expires_at, now, user_id),
            )

    def create_auth_token(
        self,
        user_id: str,
        token_hash: str,
        token_type: str,
        expires_at: str,
        code: str | None = None,
    ) -> str:
        token_id = str(uuid.uuid4())
        now = _now_iso()
        with self.transaction():
            self._conn.execute(
                """
                INSERT INTO auth_tokens (id, user_id, token_hash, token_type, code, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (token_id, user_id, token_hash, token_type, code, expires_at, now),
            )
        return token_id

    def get_valid_auth_token(self, token_hash: str, token_type: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT * FROM auth_tokens
            WHERE token_hash = ? AND token_type = ? AND used_at IS NULL
            """,
            (token_hash, token_type),
        ).fetchone()
        if not row:
            return None
        record = dict(row)
        if record["expires_at"] < _now_iso():
            return None
        return record

    def get_valid_auth_token_by_code(
        self, user_id: str, code: str, token_type: str
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT * FROM auth_tokens
            WHERE user_id = ? AND code = ? AND token_type = ? AND used_at IS NULL
            ORDER BY created_at DESC LIMIT 1
            """,
            (user_id, code, token_type),
        ).fetchone()
        if not row:
            return None
        record = dict(row)
        if record["expires_at"] < _now_iso():
            return None
        return record

    def mark_auth_token_used(self, token_id: str) -> None:
        now = _now_iso()
        with self.transaction():
            self._conn.execute(
                "UPDATE auth_tokens SET used_at = ? WHERE id = ?",
                (now, token_id),
            )

    def invalidate_user_tokens(self, user_id: str, token_type: str) -> None:
        now = _now_iso()
        with self.transaction():
            self._conn.execute(
                """
                UPDATE auth_tokens SET used_at = ?
                WHERE user_id = ? AND token_type = ? AND used_at IS NULL
                """,
                (now, user_id, token_type),
            )

    def is_webhook_processed(self, event_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM processed_webhook_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        return row is not None

    def mark_webhook_processed(self, event_id: str) -> None:
        with self.transaction():
            self._conn.execute(
                "INSERT OR IGNORE INTO processed_webhook_events (event_id, processed_at) VALUES (?, ?)",
                (event_id, _now_iso()),
            )

    def upsert_subscription(
        self,
        user_id: str,
        stripe_subscription_id: str,
        plan: str,
        status: str,
        current_period_end: str | None,
    ) -> None:
        now = _now_iso()
        existing = self._conn.execute(
            "SELECT id FROM stripe_subscriptions WHERE stripe_subscription_id = ?",
            (stripe_subscription_id,),
        ).fetchone()
        with self.transaction():
            if existing:
                self._conn.execute(
                    """
                    UPDATE stripe_subscriptions
                    SET status = ?, current_period_end = ?, updated_at = ?
                    WHERE stripe_subscription_id = ?
                    """,
                    (status, current_period_end, now, stripe_subscription_id),
                )
            else:
                self._conn.execute(
                    """
                    INSERT INTO stripe_subscriptions
                    (id, user_id, stripe_subscription_id, plan, status, current_period_end, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        user_id,
                        stripe_subscription_id,
                        plan,
                        status,
                        current_period_end,
                        now,
                        now,
                    ),
                )

    def get_active_subscription(self, user_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT * FROM stripe_subscriptions
            WHERE user_id = ? AND status IN ('active', 'trialing', 'past_due')
            ORDER BY updated_at DESC LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        return dict(row) if row else None

    def save_checkout_session(
        self, idempotency_key: str, stripe_session_id: str, user_id: str, plan: str
    ) -> None:
        with self.transaction():
            self._conn.execute(
                """
                INSERT OR REPLACE INTO checkout_sessions
                (idempotency_key, stripe_session_id, user_id, plan, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (idempotency_key, stripe_session_id, user_id, plan, _now_iso()),
            )

    def get_checkout_by_idempotency(self, idempotency_key: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM checkout_sessions WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        return dict(row) if row else None

    def get_checkout_by_stripe_session_id(self, stripe_session_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM checkout_sessions WHERE stripe_session_id = ?",
            (stripe_session_id,),
        ).fetchone()
        return dict(row) if row else None


db = Database()
