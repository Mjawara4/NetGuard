"""Per-org Modem Pay credentials: stored encrypted, never read back, admin-only."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.core import Organization, User, UserRole
from app.routers import payments_settings as ps

pytestmark = pytest.mark.asyncio


def _db(org):
    result = MagicMock()
    result.scalars.return_value.first.return_value = org
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    return db


def _admin(org_id):
    return User(id=uuid.uuid4(), role=UserRole.ORG_ADMIN, organization_id=org_id)


def _viewer(org_id):
    return User(id=uuid.uuid4(), role=UserRole.VIEWER, organization_id=org_id)


async def test_secret_is_stored_encrypted_and_never_returned():
    oid = uuid.uuid4()
    org = Organization(id=oid, name="o")
    db = _db(org)
    await ps.update_payment_settings(
        ps.PaymentSettingsIn(modempay_secret_key="sk_test_ABC123",
                             modempay_webhook_secret="whsec_XYZ",
                             payments_enabled=True),
        db=db, actor=_admin(oid))
    # encrypted at rest -- the raw stored value is not the plaintext
    assert org.modempay_secret_key and org.modempay_secret_key != "sk_test_ABC123"
    assert org.modempay_webhook_secret and org.modempay_webhook_secret != "whsec_XYZ"
    assert org.payments_enabled is True
    # read-back never exposes the secret
    got = await ps.get_payment_settings(db=_db(org), actor=_admin(oid))
    blob = str(got.model_dump() if hasattr(got, "model_dump") else got)
    assert "sk_test_ABC123" not in blob and "whsec_XYZ" not in blob
    assert (got.configured if hasattr(got, "configured") else got["configured"]) is True


async def test_unset_org_reports_not_configured():
    oid = uuid.uuid4()
    org = Organization(id=oid, name="o")
    got = await ps.get_payment_settings(db=_db(org), actor=_admin(oid))
    assert (got.configured if hasattr(got, "configured") else got["configured"]) is False


async def test_non_admin_cannot_set_keys():
    oid = uuid.uuid4()
    with pytest.raises(HTTPException) as e:
        await ps.update_payment_settings(
            ps.PaymentSettingsIn(modempay_secret_key="x"),
            db=_db(Organization(id=oid, name="o")), actor=_viewer(oid))
    assert e.value.status_code == 403


async def test_partial_update_leaves_untouched_fields_alone():
    oid = uuid.uuid4()
    org = Organization(id=oid, name="o")
    org.modempay_secret_key = "already-encrypted-blob"
    await ps.update_payment_settings(
        ps.PaymentSettingsIn(payments_enabled=True),  # only the flag
        db=_db(org), actor=_admin(oid))
    assert org.modempay_secret_key == "already-encrypted-blob"  # not wiped
    assert org.payments_enabled is True
