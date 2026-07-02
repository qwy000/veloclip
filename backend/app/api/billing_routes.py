from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.schemas import (
    BillingPlan,
    BillingStatusResponse,
    CheckoutRequest,
    CheckoutResponse,
    MembershipInfo,
    PortalResponse,
    SyncCheckoutRequest,
    SyncCheckoutResponse,
)
from app.services import auth_service, billing_service

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/plans", response_model=list[BillingPlan])
def list_plans() -> list[BillingPlan]:
    return [BillingPlan(**p) for p in billing_service.get_plans()]


@router.get("/status", response_model=BillingStatusResponse)
def billing_status(user: dict = Depends(auth_service.get_current_user)) -> BillingStatusResponse:
    membership = auth_service.get_membership_status(user)
    return BillingStatusResponse(
        membership=MembershipInfo(**membership),
        stripe_customer_id=user.get("stripe_customer_id"),
    )


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(
    req: CheckoutRequest,
    user: dict = Depends(auth_service.get_current_user),
) -> CheckoutResponse:
    if not user.get("email_verified"):
        raise HTTPException(status_code=403, detail="请先验证邮箱后再购买")
    result = billing_service.create_checkout_session(user, req.plan)
    return CheckoutResponse(**result)


@router.post("/sync-checkout", response_model=SyncCheckoutResponse)
def sync_checkout(
    req: SyncCheckoutRequest,
    user: dict = Depends(auth_service.get_current_user),
) -> SyncCheckoutResponse:
    result = billing_service.sync_checkout_session(user, req.session_id.strip())
    return SyncCheckoutResponse(**result)


@router.post("/portal", response_model=PortalResponse)
def portal(user: dict = Depends(auth_service.get_current_user)) -> PortalResponse:
    result = billing_service.create_portal_session(user)
    return PortalResponse(**result)


@router.post("/webhook")
async def stripe_webhook(request: Request) -> dict:
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    return billing_service.handle_webhook(payload, sig)
