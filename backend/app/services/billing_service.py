from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import stripe
from fastapi import HTTPException

from app.core.config import settings
from app.core.database import db

logger = logging.getLogger(__name__)

PLAN_PRO = "pro"
PLAN_ULTIMATE = "ultimate"

ACTIVE_SUB_STATUSES = {"active", "trialing", "past_due"}


def _stripe_client() -> stripe.StripeClient | None:
    if not settings.stripe_secret_key:
        return None
    return stripe.StripeClient(settings.stripe_secret_key)


def get_plans() -> list[dict[str, Any]]:
    currency = settings.stripe_currency
    is_cny = currency == "cny"
    return [
        {
            "id": "free",
            "name": "免费版",
            "price_display": "¥0",
            "period": "永久",
            "stripe_price_id": None,
            "checkout_mode": None,
        },
        {
            "id": PLAN_PRO,
            "name": "Pro 会员",
            "price_display": "¥19" if is_cny else "$2.99",
            "period": "月",
            "stripe_price_id": settings.stripe_price_pro_monthly or None,
            "checkout_mode": "subscription",
            "currency_note": None if is_cny else "以 USD 结算，约合 ¥19/月",
        },
        {
            "id": PLAN_ULTIMATE,
            "name": "旗舰版",
            "price_display": "¥149" if is_cny else "$19.99",
            "period": "12 个月",
            "stripe_price_id": settings.stripe_price_ultimate_onetime or None,
            "checkout_mode": "payment",
            "currency_note": None if is_cny else "以 USD 结算，约合 ¥149/年",
            "renewal_note": "一次性购买 12 个月，到期不自动续费",
        },
    ]


def _ensure_stripe() -> stripe.StripeClient:
    client = _stripe_client()
    if not client:
        raise HTTPException(status_code=503, detail="Stripe 未配置，请联系管理员")
    return client


def get_or_create_stripe_customer(user: dict) -> str:
    client = _ensure_stripe()
    if user.get("stripe_customer_id"):
        return user["stripe_customer_id"]

    customer = client.v1.customers.create(params={"email": user["email"], "metadata": {"user_id": user["id"]}})
    db.update_stripe_customer(user["id"], customer.id)
    return customer.id


def create_checkout_session(user: dict, plan: str) -> dict[str, str]:
    if plan not in (PLAN_PRO, PLAN_ULTIMATE):
        raise HTTPException(status_code=400, detail="无效的会员方案")

    from app.services import auth_service

    membership = auth_service.get_membership_status(user)
    current = membership["plan"]
    if plan == PLAN_PRO and current in (PLAN_PRO, PLAN_ULTIMATE):
        raise HTTPException(status_code=400, detail=f"您已是{membership['plan_label']}，无需重复购买 Pro")
    if plan == PLAN_ULTIMATE and current == PLAN_ULTIMATE:
        raise HTTPException(status_code=400, detail="您已是旗舰版会员，无需重复购买")

    client = _ensure_stripe()
    customer_id = get_or_create_stripe_customer(user)

    if plan == PLAN_PRO:
        price_id = settings.stripe_price_pro_monthly
        mode = "subscription"
    else:
        price_id = settings.stripe_price_ultimate_onetime
        mode = "payment"

    if not price_id:
        raise HTTPException(status_code=503, detail=f"方案 {plan} 的 Stripe Price 未配置")

    idempotency_key = f"{user['id']}:{plan}:{datetime.now(UTC).strftime('%Y%m%d%H%M')}"
    existing = db.get_checkout_by_idempotency(idempotency_key)
    if existing:
        session = client.v1.checkout.sessions.retrieve(existing["stripe_session_id"])
        if session.url and session.status == "open":
            return {"checkout_url": session.url, "session_id": session.id}

    success_url = f"{settings.app_base_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{settings.app_base_url}/billing/cancel"

    params: dict[str, Any] = {
        "mode": mode,
        "customer": customer_id,
        "client_reference_id": user["id"],
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {"user_id": user["id"], "plan": plan},
    }
    if mode == "subscription":
        params["subscription_data"] = {"metadata": {"user_id": user["id"], "plan": plan}}

    session = client.v1.checkout.sessions.create(
        params=params,
        options={"idempotency_key": idempotency_key},
    )
    db.save_checkout_session(idempotency_key, session.id, user["id"], plan)
    if not session.url:
        raise HTTPException(status_code=500, detail="创建支付会话失败")
    return {"checkout_url": session.url, "session_id": session.id}


_portal_configuration_id: str | None = None


def _get_portal_configuration_id(client: stripe.StripeClient) -> str:
    global _portal_configuration_id  # noqa: PLW0603
    if _portal_configuration_id:
        return _portal_configuration_id

    configs = client.v1.billing_portal.configurations.list(params={"limit": 1})
    if configs.data:
        _portal_configuration_id = configs.data[0].id
        return _portal_configuration_id

    config = client.v1.billing_portal.configurations.create(
        params={
            "features": {
                "subscription_cancel": {
                    "enabled": True,
                    "mode": "at_period_end",
                    "cancellation_reason": {
                        "enabled": True,
                        "options": [
                            "too_expensive",
                            "missing_features",
                            "switched_service",
                            "unused",
                            "other",
                        ],
                    },
                },
                "payment_method_update": {"enabled": True},
                "invoice_history": {"enabled": True},
            },
        }
    )
    _portal_configuration_id = config.id
    return _portal_configuration_id


def create_portal_session(user: dict) -> dict[str, str]:
    client = _ensure_stripe()
    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="尚未绑定 Stripe 客户，请先购买会员")

    from app.services import auth_service

    membership = auth_service.get_membership_status(user)
    if not membership["can_manage_subscription"]:
        raise HTTPException(status_code=400, detail="当前方案无自动续费，无需管理订阅")

    portal = client.v1.billing_portal.sessions.create(
        params={
            "customer": customer_id,
            "return_url": f"{settings.app_base_url}/#pricing",
            "configuration": _get_portal_configuration_id(client),
        }
    )
    return {"portal_url": portal.url}


def handle_webhook(payload: bytes, sig_header: str | None) -> dict[str, str]:
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook secret 未配置")

    client = _ensure_stripe()
    try:
        event = client.construct_event(payload, sig_header or "", settings.stripe_webhook_secret)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="Webhook 签名验证失败") from exc

    event_id = event.get("id", "")
    if not event_id:
        raise HTTPException(status_code=400, detail="无效事件")

    if db.is_webhook_processed(event_id):
        return {"status": "already_processed"}

    event_type = event.get("type", "")
    data_object = event.get("data", {}).get("object", {})

    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(data_object)
        elif event_type == "customer.subscription.updated":
            _handle_subscription_updated(data_object)
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(data_object)
        elif event_type == "invoice.payment_failed":
            _handle_payment_failed(data_object)
        else:
            logger.info("Unhandled webhook event: %s", event_type)
    except Exception:
        logger.exception("Webhook handler failed for %s", event_type)
        raise

    db.mark_webhook_processed(event_id)
    return {"status": "ok"}


def _user_id_from_metadata(obj: dict) -> str | None:
    meta = obj.get("metadata") or {}
    uid = meta.get("user_id")
    if uid:
        return uid
    ref = obj.get("client_reference_id")
    return ref if ref else None


def _stripe_metadata_to_dict(metadata: Any) -> dict:
    if not metadata:
        return {}
    if isinstance(metadata, dict):
        return metadata
    to_dict = getattr(metadata, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return {}


def _checkout_session_dict(session: dict | Any) -> dict:
    if isinstance(session, dict):
        return session
    return {
        "metadata": _stripe_metadata_to_dict(session.metadata),
        "client_reference_id": session.client_reference_id,
        "mode": session.mode,
        "subscription": session.subscription,
    }


def _handle_checkout_completed(session: dict | Any) -> None:
    session_data = _checkout_session_dict(session)
    user_id = _user_id_from_metadata(session_data)
    if not user_id:
        logger.warning("checkout.session.completed without user_id")
        return

    plan = (session_data.get("metadata") or {}).get("plan", "")
    mode = session_data.get("mode")

    if mode == "payment" and plan == PLAN_ULTIMATE:
        expires = (datetime.now(UTC) + timedelta(days=365)).isoformat()
        db.set_user_plan(user_id, PLAN_ULTIMATE, expires)
        logger.info("Granted ultimate plan to user %s until %s", user_id, expires)
    elif mode == "subscription":
        sub_id = session_data.get("subscription")
        if sub_id:
            client = _ensure_stripe()
            sub = client.v1.subscriptions.retrieve(sub_id)
            _sync_subscription(user_id, sub)


def _handle_subscription_updated(subscription: dict) -> None:
    user_id = _user_id_from_metadata(subscription)
    if not user_id and subscription.get("customer"):
        user_id = _find_user_by_customer(subscription["customer"])
    if not user_id:
        logger.warning("subscription.updated without user_id")
        return
    _sync_subscription(user_id, subscription)


def _handle_subscription_deleted(subscription: dict) -> None:
    user_id = _user_id_from_metadata(subscription)
    if not user_id and subscription.get("customer"):
        user_id = _find_user_by_customer(subscription["customer"])
    if not user_id:
        return

    db.upsert_subscription(
        user_id,
        subscription["id"],
        PLAN_PRO,
        "canceled",
        None,
    )
    user = db.get_user_by_id(user_id)
    if user and user.get("plan") == PLAN_PRO:
        db.set_user_plan(user_id, "free", None)


def _handle_payment_failed(invoice: dict) -> None:
    sub_id = invoice.get("subscription")
    if not sub_id:
        return
    client = _ensure_stripe()
    sub = client.v1.subscriptions.retrieve(sub_id)
    _handle_subscription_updated(sub)


def _find_user_by_customer(customer_id: str) -> str | None:
    user = db.get_user_by_stripe_customer(customer_id)
    return user["id"] if user else None


def _sync_subscription(user_id: str, subscription: dict | Any) -> None:
    sub_id = subscription["id"] if isinstance(subscription, dict) else subscription.id
    status = subscription["status"] if isinstance(subscription, dict) else subscription.status
    period_end = None
    if isinstance(subscription, dict):
        period_end_ts = subscription.get("current_period_end")
    else:
        period_end_ts = getattr(subscription, "current_period_end", None)
    if period_end_ts:
        period_end = datetime.fromtimestamp(period_end_ts, tz=UTC).isoformat()

    plan = PLAN_PRO
    if isinstance(subscription, dict):
        meta = subscription.get("metadata") or {}
    else:
        meta = _stripe_metadata_to_dict(subscription.metadata)
    if meta.get("plan"):
        plan = meta["plan"]

    db.upsert_subscription(user_id, sub_id, plan, status, period_end)

    if status in ACTIVE_SUB_STATUSES:
        db.set_user_plan(user_id, plan, period_end)
    elif status in ("canceled", "unpaid", "incomplete_expired"):
        user = db.get_user_by_id(user_id)
        if user and user.get("plan") == plan:
            ultimate_exp = user.get("plan_expires_at")
            if ultimate_exp:
                try:
                    exp = datetime.fromisoformat(ultimate_exp)
                    if exp.tzinfo is None:
                        exp = exp.replace(tzinfo=UTC)
                    if exp > datetime.now(UTC):
                        return
                except ValueError:
                    pass
            db.set_user_plan(user_id, "free", None)


def sync_checkout_session(user: dict, session_id: str) -> dict[str, Any]:
    """支付成功页主动同步 Stripe Checkout Session（本地开发 webhook 未转发时的兜底）。"""
    client = _ensure_stripe()
    session = client.v1.checkout.sessions.retrieve(session_id)
    session_data = _checkout_session_dict(session)

    owner_id = _user_id_from_metadata(session_data)
    local = db.get_checkout_by_stripe_session_id(session_id)
    if owner_id != user["id"] and (not local or local["user_id"] != user["id"]):
        raise HTTPException(status_code=403, detail="无权访问此支付会话")

    payment_status = getattr(session, "payment_status", None)
    status = getattr(session, "status", None)
    if payment_status != "paid" and status != "complete":
        return {
            "status": "pending",
            "message": "支付尚未完成，请稍后再试",
        }

    _handle_checkout_completed(session)
    updated = db.get_user_by_id(user["id"])
    if not updated:
        raise HTTPException(status_code=404, detail="用户不存在")

    from app.services import auth_service

    membership = auth_service.get_membership_status(updated)
    logger.info("Synced checkout session %s for user %s -> plan %s", session_id, user["id"], membership["plan"])
    return {
        "status": "synced",
        "message": "会员状态已更新",
        "membership": membership,
    }
