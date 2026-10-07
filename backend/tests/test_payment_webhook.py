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


def _context(status="created", plan="3-Hours", amount=10, pricing=None):
    device = Device(id=uuid.uuid4(), site_id=uuid.uuid4(), name="r", ip_address="10.0.0.1")
    device.voucher_template = {
        "profile_pricing": pricing if pricing is not None else {"3-Hours": {"price": 10, "currency": "GMD"}}
    }
    org = Organization(name="o", payments_enabled=True)
    org.modempay_webhook_secret = "whsec"
    intent = PaymentIntent(
        id=uuid.uuid4(), device_id=device.id, charge_id="ch_1", plan=plan,
        amount=amount, currency="GMD", status=status,
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
    invalidate = MagicMock()
    refresh = MagicMock()
    monkeypatch.setattr(webhook, "_load_locked_intent", AsyncMock(return_value=context))
    monkeypatch.setattr(webhook, "_add_router_user", add_user)
    monkeypatch.setattr(webhook.hotspot_cache, "invalidate", invalidate)
    monkeypatch.setattr(webhook.hotspot_cache, "request_refresh", refresh)
    body = _body()
    await webhook.process_webhook(body, _signature(body), db)
    await webhook.process_webhook(body, _signature(body), db)
    add_user.assert_called_once()
    assert context[0].status == "fulfilled"
    # One commit reserves the voucher code, one records the fulfilment.
    assert db.commit.await_count == 2
    invalidate.assert_called_once_with(str(context[1].id), "users")
    refresh.assert_called_once_with(str(context[1].id))


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


def _patch(monkeypatch, context, add_user=None):
    add_user = add_user or MagicMock()
    monkeypatch.setattr(webhook, "_load_locked_intent", AsyncMock(return_value=context))
    monkeypatch.setattr(webhook, "_add_router_user", add_user)
    monkeypatch.setattr(webhook.hotspot_cache, "invalidate", MagicMock())
    monkeypatch.setattr(webhook.hotspot_cache, "request_refresh", MagicMock())
    return add_user


async def test_price_edited_after_checkout_still_delivers_what_was_paid_for(monkeypatch):
    # The customer paid 10 at checkout; the operator has since raised the price.
    context = _context(pricing={"3-Hours": {"price": 15, "currency": "GMD"}})
    db = _db()
    add_user = _patch(monkeypatch, context)
    body = _body(amount=10)
    out = await webhook.process_webhook(body, _signature(body), db)
    assert out["status"] == "fulfilled"
    add_user.assert_called_once()
    assert db.add.call_args.args[0].price == 10


async def test_plan_removed_after_checkout_still_delivers(monkeypatch):
    context = _context(pricing={})
    add_user = _patch(monkeypatch, context)
    body = _body()
    out = await webhook.process_webhook(body, _signature(body), _db())
    assert out["status"] == "fulfilled"
    add_user.assert_called_once()


async def test_hand_named_profile_gets_its_duration_from_the_name(monkeypatch):
    context = _context(plan="24hours", amount=25,
                       pricing={"24hours": {"price": 25.0, "currency": "D"}})
    add_user = _patch(monkeypatch, context)
    body = _body(amount=25)
    await webhook.process_webhook(body, _signature(body), _db())
    device, username, password, plan, duration, charge_id = add_user.call_args.args
    assert (plan, duration) == ("24hours", "24h")


async def test_retry_after_a_failed_commit_reuses_the_same_voucher(monkeypatch):
    context = _context()
    db = _db()
    # Reserve commits; the fulfilment commit fails once, after the router
    # already has the user. Modem Pay then retries the webhook.
    calls = []

    def commit():
        calls.append(1)
        if len(calls) == 2:
            context[0].status = "paid"  # what the rolled-back row still says
            raise RuntimeError("db gone")

    db.commit = AsyncMock(side_effect=commit)
    add_user = _patch(monkeypatch, context)
    body = _body()
    with pytest.raises(RuntimeError):
        await webhook.process_webhook(body, _signature(body), db)
    out = await webhook.process_webhook(body, _signature(body), db)
    assert out["status"] == "fulfilled"
    first, second = (call.args[1] for call in add_user.call_args_list)
    assert first == second == out["voucher_username"]


async def test_router_timeout_asks_modem_pay_to_retry(monkeypatch):
    import time
    context = _context()
    db = _db()
    _patch(monkeypatch, context, add_user=lambda *args: time.sleep(0.3))
    monkeypatch.setattr(webhook, "ROUTER_TIMEOUT_SECONDS", 0.05)
    body = _body()
    with pytest.raises(HTTPException) as error:
        await webhook.process_webhook(body, _signature(body), db)
    assert error.value.status_code == 504
    assert context[0].status != "fulfilled"
    db.add.assert_not_called()


async def test_router_user_that_already_exists_counts_as_created(monkeypatch):
    device = Device(id=uuid.uuid4(), site_id=uuid.uuid4(), name="r", ip_address="10.0.0.1")
    connection = MagicMock()
    connection.get_api.return_value.get_resource.return_value.add.side_effect = Exception(
        "failure: already have user with this name for this server")
    monkeypatch.setattr(webhook, "decrypt_device_secrets", lambda value: value)
    monkeypatch.setattr("app.routers.hotspot.get_api_pool", MagicMock(return_value=connection))

    webhook._add_router_user(device, "abcd1234", "abcd1234", "3-Hours", "3h", "ch_1")
    connection.disconnect.assert_called_once()


async def test_router_user_other_failures_still_raise(monkeypatch):
    device = Device(id=uuid.uuid4(), site_id=uuid.uuid4(), name="r", ip_address="10.0.0.1")
    connection = MagicMock()
    connection.get_api.return_value.get_resource.return_value.add.side_effect = Exception(
        "input does not match any value of profile")
    monkeypatch.setattr(webhook, "decrypt_device_secrets", lambda value: value)
    monkeypatch.setattr("app.routers.hotspot.get_api_pool", MagicMock(return_value=connection))

    with pytest.raises(Exception, match="profile"):
        webhook._add_router_user(device, "abcd1234", "abcd1234", "3-Hours", "3h", "ch_1")


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
