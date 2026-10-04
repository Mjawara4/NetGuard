"""Authenticated, organisation-scoped Modem Pay configuration."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.core.database import get_db
from app.models.core import Organization, User, UserRole
from app.utils.encryption import encrypt_value


router = APIRouter()


class PaymentSettingsIn(BaseModel):
    modempay_secret_key: Optional[str] = None
    modempay_webhook_secret: Optional[str] = None
    payments_enabled: Optional[bool] = None


class PaymentSettingsOut(BaseModel):
    configured: bool
    payments_enabled: bool


def _require_org_admin(actor: User) -> None:
    if actor.role not in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN):
        raise HTTPException(status_code=403, detail="Organization admin access required")
    if not actor.organization_id:
        raise HTTPException(status_code=403, detail="User does not belong to an organization")


async def _get_actor_org(db: AsyncSession, actor: User) -> Organization:
    _require_org_admin(actor)
    result = await db.execute(
        select(Organization).where(Organization.id == actor.organization_id)
    )
    org = result.scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.get("/settings", response_model=PaymentSettingsOut)
async def get_payment_settings(
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> PaymentSettingsOut:
    org = await _get_actor_org(db, actor)
    return PaymentSettingsOut(
        configured=bool(org.modempay_secret_key and org.modempay_webhook_secret),
        payments_enabled=bool(org.payments_enabled),
    )


@router.put("/settings", response_model=PaymentSettingsOut)
async def update_payment_settings(
    payload: PaymentSettingsIn,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> PaymentSettingsOut:
    org = await _get_actor_org(db, actor)
    fields = payload.model_fields_set if hasattr(payload, "model_fields_set") else payload.__fields_set__

    for field in ("modempay_secret_key", "modempay_webhook_secret"):
        if field not in fields:
            continue
        plaintext = getattr(payload, field)
        if plaintext:
            ciphertext = encrypt_value(plaintext)
            # Payment credentials must never silently fall back to plaintext.
            if ciphertext == plaintext:
                raise HTTPException(status_code=503, detail="Credential encryption is not configured")
            setattr(org, field, ciphertext)
        else:
            setattr(org, field, None)

    if "payments_enabled" in fields and payload.payments_enabled is not None:
        org.payments_enabled = payload.payments_enabled

    await db.commit()
    return PaymentSettingsOut(
        configured=bool(org.modempay_secret_key and org.modempay_webhook_secret),
        payments_enabled=bool(org.payments_enabled),
    )
