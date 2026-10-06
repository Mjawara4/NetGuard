"""Public captive-portal plan listing and hosted-checkout creation."""

from typing import Optional
from urllib.parse import urlencode, urlsplit
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.core import Device, Organization, PaymentIntent, Site
from app.services.modempay import create_payment_intent
from app.utils.encryption import decrypt_value


router = APIRouter()


class PayRequest(BaseModel):
    router: UUID
    mac: Optional[str] = None
    plan: str
    login: Optional[str] = None


def _pricing(device: Device) -> dict:
    template = device.voucher_template or {}
    pricing = template.get("profile_pricing", {})
    return pricing if isinstance(pricing, dict) else {}


async def _load_context(db: AsyncSession, device_id: UUID):
    result = await db.execute(
        select(Device, Organization)
        .join(Site, Device.site_id == Site.id)
        .join(Organization, Site.organization_id == Organization.id)
        .where(Device.id == device_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Router not found")
    return row[0], row[1]


def _available(org: Organization) -> bool:
    return bool(
        org.payments_enabled
        and org.modempay_secret_key
        and org.modempay_webhook_secret
    )


@router.get("/plans")
async def get_plans(router: UUID, db: AsyncSession = Depends(get_db)):
    device, org = await _load_context(db, router)
    if not _available(org):
        return {"enabled": False, "plans": []}

    plans = []
    for profile, details in _pricing(device).items():
        if not isinstance(details, dict) or "price" not in details:
            continue
        plans.append({
            "profile": profile,
            "price": details["price"],
            "currency": details.get("currency", "GMD"),
        })
    return {"enabled": True, "plans": plans}


@router.get("/status")
async def payment_status(intent: UUID, router: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PaymentIntent).where(
            PaymentIntent.id == intent,
            PaymentIntent.device_id == router,
        )
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {"status": payment.status, "voucher_username": payment.voucher_username}


@router.post("/pay")
async def pay(payload: PayRequest, db: AsyncSession = Depends(get_db)):
    device, org = await _load_context(db, payload.router)
    if not _available(org):
        raise HTTPException(status_code=409, detail="Payments are not available for this router")

    details = _pricing(device).get(payload.plan)
    if not isinstance(details, dict) or "price" not in details:
        raise HTTPException(status_code=400, detail="Unknown plan")
    amount = details["price"]
    currency = details.get("currency", "GMD")
    local_intent_id = uuid4()
    login_url = None
    if payload.login:
        parsed_login = urlsplit(payload.login)
        if (parsed_login.scheme not in {"http", "https"} or not parsed_login.hostname
                or parsed_login.username or parsed_login.password or len(payload.login) > 500):
            raise HTTPException(status_code=400, detail="Invalid hotspot login URL")
        login_url = payload.login
    metadata = {
        "payment_intent_id": str(local_intent_id),
        "device_id": str(device.id),
        "mac": payload.mac,
        "plan": payload.plan,
    }
    return_params = {
        "router": str(device.id),
        "payment": "success",
        "intent": str(local_intent_id),
    }
    cancel_params = {"router": str(device.id)}
    if login_url:
        return_params["login"] = login_url
        cancel_params["login"] = login_url
    try:
        result = await create_payment_intent(
            decrypt_value(org.modempay_secret_key),
            amount,
            currency,
            metadata,
            f"https://app.netguard.fun/buy?{urlencode(return_params)}",
            f"https://app.netguard.fun/buy?{urlencode(cancel_params)}",
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise HTTPException(
                status_code=502,
                detail="Modem Pay rejected the saved API key. Update it in NetGuard Settings.",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail="Modem Pay could not start checkout. Please try again.",
        ) from exc
    intent = PaymentIntent(
        id=local_intent_id,
        device_id=device.id,
        charge_id=result.get("charge_id"),
        plan=payload.plan,
        amount=amount,
        currency=currency,
        status="created",
        customer_mac=payload.mac,
    )
    db.add(intent)
    await db.commit()
    return {"checkout_url": result["payment_link"]}
