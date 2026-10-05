"""Signed Modem Pay webhook fulfillment for captive-portal purchases."""

import json
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.core import Device, Organization, PaymentIntent, Site, VoucherSale, decrypt_device_secrets
from app.services.modempay import verify_webhook
from app.services import hotspot_cache
from app.services.voucher_jobs import generate_candidate
from app.utils.encryption import decrypt_value


router = APIRouter()
PLAN_DURATIONS = {"3-Hours": "3h", "24-Hours": "24h", "7-Days": "7d", "30-Days": "30d"}


async def _load_locked_intent(db, charge_id, local_intent_id):
    conditions = []
    if charge_id:
        conditions.append(PaymentIntent.charge_id == charge_id)
    if local_intent_id:
        try:
            conditions.append(PaymentIntent.id == UUID(str(local_intent_id)))
        except (TypeError, ValueError):
            pass
    if not conditions:
        return None
    result = await db.execute(
        select(PaymentIntent, Device, Organization)
        .join(Device, PaymentIntent.device_id == Device.id)
        .join(Site, Device.site_id == Site.id)
        .join(Organization, Site.organization_id == Organization.id)
        .where(or_(*conditions))
        .with_for_update()
    )
    return result.first()


def _add_router_user(device, username, password, plan, duration, charge_id):
    from app.routers.hotspot import get_api_pool

    decrypt_device_secrets(device)
    port = getattr(device, "ssh_port", 8728) or 8728
    # Device onboarding historically stored SSH's port (22) in this field,
    # while RouterOS API is exposed on 8728. Other hotspot routes already
    # apply this compatibility mapping.
    if int(port) == 22:
        port = 8728
    connection = get_api_pool(
        device.ip_address,
        device.ssh_username or "admin",
        device.ssh_password or "admin",
        int(port),
    )
    try:
        connection.get_api().get_resource("/ip/hotspot/user").add(**{
            "name": username,
            "password": password,
            "profile": plan,
            "limit-uptime": duration,
            "comment": f"Modem Pay {charge_id}",
        })
    finally:
        connection.disconnect()


async def process_webhook(raw_body: bytes, signature: str, db: AsyncSession):
    try:
        event = json.loads(raw_body)
    except (TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid webhook body")

    if event.get("event") != "charge.succeeded":
        return {"status": "ignored"}
    charge = event.get("payload") or event.get("data") or {}
    metadata = charge.get("metadata") or {}
    charge_id = charge.get("id") or charge.get("charge_id")
    row = await _load_locked_intent(db, charge_id, metadata.get("payment_intent_id"))
    if not row:
        raise HTTPException(status_code=404, detail="Payment intent not found")
    intent, device, org = row

    webhook_secret = decrypt_value(org.modempay_webhook_secret or "")
    if not verify_webhook(raw_body, signature, webhook_secret):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    if not charge_id:
        raise HTTPException(status_code=400, detail="Missing charge id")
    if intent.status == "fulfilled":
        return {"status": "already_fulfilled"}

    # Only the locally stored intent and current server-side price choose the grant.
    pricing = (device.voucher_template or {}).get("profile_pricing", {})
    details = pricing.get(intent.plan)
    if not isinstance(details, dict) or "price" not in details:
        raise HTTPException(status_code=400, detail="Plan is no longer available")
    try:
        paid = Decimal(str(charge.get("amount")))
        expected = Decimal(str(details["price"]))
    except (InvalidOperation, TypeError):
        raise HTTPException(status_code=400, detail="Invalid payment amount")
    if paid != expected or charge.get("currency", intent.currency) != details.get("currency", intent.currency):
        raise HTTPException(status_code=400, detail="Payment amount does not match the plan")

    duration = PLAN_DURATIONS.get(intent.plan)
    if not duration:
        raise HTTPException(status_code=400, detail="Unsupported plan duration")
    username, password = generate_candidate("", length=8, random_mode=True)
    _add_router_user(device, username, password, intent.plan, duration, charge_id)

    db.add(VoucherSale(
        device_id=device.id,
        site_id=device.site_id,
        username=username,
        profile=intent.plan,
        comment=f"Modem Pay {charge_id}",
        uptime=duration,
        price=int(expected),
        currency=details.get("currency", intent.currency),
    ))
    intent.charge_id = charge_id
    intent.status = "fulfilled"
    intent.voucher_username = username
    await db.commit()
    # Hotspot Manager serves users from Redis rather than querying the router
    # on every page load. Make the newly purchased voucher visible promptly.
    hotspot_cache.invalidate(str(device.id), "users")
    hotspot_cache.request_refresh(str(device.id))
    return {"status": "fulfilled", "voucher_username": username}


@router.post("/webhook")
async def payment_webhook(
    request: Request,
    x_modem_signature: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
):
    return await process_webhook(await request.body(), x_modem_signature, db)
