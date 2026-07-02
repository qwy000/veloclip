from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.database import db
from app.main import app


class AuthBillingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.email = "testuser@example.com"
        self.password = "password123"
        existing = db.get_user_by_email(self.email)
        if existing:
            with db.transaction():
                db._conn.execute("DELETE FROM auth_tokens WHERE user_id = ?", (existing["id"],))  # noqa: SLF001
                db._conn.execute("DELETE FROM stripe_subscriptions WHERE user_id = ?", (existing["id"],))  # noqa: SLF001
                db._conn.execute("DELETE FROM users WHERE id = ?", (existing["id"],))

    def test_register_verify_login_flow(self) -> None:
        with patch("app.services.auth_service.send_verification_email") as mock_send:
            res = self.client.post(
                "/api/auth/register",
                json={"email": self.email, "password": self.password},
            )
            self.assertEqual(res.status_code, 200)
            mock_send.assert_called_once()
            code = mock_send.call_args[0][1]

        res = self.client.post(
            "/api/auth/verify-email",
            json={"email": self.email, "code": code},
        )
        self.assertEqual(res.status_code, 200)
        token = res.json()["access_token"]
        self.assertTrue(token)

        res = self.client.post(
            "/api/auth/login",
            json={"email": self.email, "password": self.password},
        )
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["email"], self.email)
        self.assertEqual(res.json()["membership"]["plan"], "free")

    def test_webhook_idempotency(self) -> None:
        from app.services import billing_service
        from app.core.config import settings

        event_id = "evt_test_idempotent_001"
        db.mark_webhook_processed(event_id)
        self.assertTrue(db.is_webhook_processed(event_id))

        with patch.object(settings, "stripe_webhook_secret", "whsec_test"):
            with patch.object(billing_service, "_handle_checkout_completed"):
                with patch.object(billing_service, "_ensure_stripe") as mock_stripe:
                    mock_stripe.return_value.construct_event.return_value = {
                        "id": event_id,
                        "type": "checkout.session.completed",
                        "data": {"object": {"metadata": {"user_id": "x", "plan": "ultimate"}, "mode": "payment"}},
                    }
                    result = billing_service.handle_webhook(b"{}", "sig")
                    self.assertEqual(result["status"], "already_processed")

    def test_reregister_unverified_updates_password(self) -> None:
        email = "rereg@example.com"
        existing = db.get_user_by_email(email)
        if existing:
            with db.transaction():
                db._conn.execute("DELETE FROM auth_tokens WHERE user_id = ?", (existing["id"],))  # noqa: SLF001
                db._conn.execute("DELETE FROM users WHERE id = ?", (existing["id"],))

        with patch("app.services.auth_service.send_verification_email") as mock_send:
            self.client.post("/api/auth/register", json={"email": email, "password": "password123"})
            mock_send.reset_mock()
            res = self.client.post(
                "/api/auth/register",
                json={"email": email, "password": "newpass123"},
            )
            self.assertEqual(res.status_code, 200)
            self.assertIn("未验证", res.json()["message"])
            mock_send.assert_called_once()

        user = db.get_user_by_email(email)
        from app.core.security import verify_password

        self.assertTrue(verify_password("newpass123", user["password_hash"]))  # type: ignore[index]

        res = self.client.get("/api/billing/plans")
        self.assertEqual(res.status_code, 200)
        plans = res.json()
        self.assertEqual(len(plans), 3)
        ids = {p["id"] for p in plans}
        self.assertEqual(ids, {"free", "pro", "ultimate"})


if __name__ == "__main__":
    unittest.main()
