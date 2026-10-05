import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.core import Device, Organization, PaymentIntent
from app.routers import payment_webhook as webhook


pytestmark = pytest.mark.asyncio


def _context(status="created"):
    device = Device(id=uuid.uuid4(), site_id=uuid.uuid4(), name="r", ip_address="10.0.0.1")
    device.voucher_template = {"profile_pricing": {"3-Hours": {"price": 10, "currency": "GMD"}}}
    org = Organization(name="o", payments_enabled=True)
    org.modempay_webhook_secret = "whsec"
    intent = PaymentIntent(
        id=uuid.uuid4(), device_id=device.id, charge_id="ch_1", plan="3-Hours",
        amount=10, currency="GMD", status=status,
    )
    return intent, device, org


def _body(amount=10, charge_id="ch_1"):
    return json.dumps({
        "event": "charge.succeeded",
        "payload": {"id": charge_id, "amount": amount, "currency": "GMD", "metadata": {}},
    }, separators=(",", ":")).encode()


def _signature(body):
    return hmac.new(b"whsec", body, hashlib.sha512).hexdigest()


def _db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


async def test_unsigned_webhook_rejected_and_nothing_written(monkeypatch):
    db = _db()
    add_user = MagicMock()
    monkeypatch.setattr(webhook, "_load_locked_intent", AsyncMock(return_value=_context()))
    monkeypatch.setattr(webhook, "_add_router_user", add_user)
    with pytest.raises(HTTPException) as error:
        await webhook.process_webhook(_body(), "bad", db)
    assert error.value.status_code == 400
    add_user.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


async def test_replayed_charge_grants_once(monkeypatch):
    context = _context()
    db = _db()
    add_user = MagicMock()
    monkeypatch.setattr(webhook, "_load_locked_intent", AsyncMock(return_value=context))
    monkeypatch.setattr(webhook, "_add_router_user", add_user)
    body = _body()
    await webhook.process_webhook(body, _signature(body), db)
    await webhook.process_webhook(body, _signature(body), db)
    add_user.assert_called_once()
    assert context[0].status == "fulfilled"
    assert db.commit.await_count == 1


async def test_amount_mismatch_rejected(monkeypatch):
    db = _db()
    add_user = MagicMock()
    monkeypatch.setattr(webhook, "_load_locked_intent", AsyncMock(return_value=_context()))
    monkeypatch.setattr(webhook, "_add_router_user", add_user)
    body = _body(amount=1)
    with pytest.raises(HTTPException) as error:
        await webhook.process_webhook(body, _signature(body), db)
    assert error.value.status_code == 400
    add_user.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


async def test_router_user_maps_legacy_ssh_port_to_api_port(monkeypatch):
    device = Device(id=uuid.uuid4(), site_id=uuid.uuid4(), name="r", ip_address="10.0.0.1")
    device.ssh_port = 22
    device.ssh_username = "netguard"
    device.ssh_password = "secret"
    connection = MagicMock()
    pool = MagicMock(return_value=connection)
    monkeypatch.setattr(webhook, "decrypt_device_secrets", lambda value: value)
    monkeypatch.setattr("app.routers.hotspot.get_api_pool", pool)

    webhook._add_router_user(device, "ABC12345", "ABC12345", "3-Hours", "3h", "ch_1")

    assert pool.call_args.args[-1] == 8728
