import uuid
from urllib.parse import parse_qs, urlsplit
from unittest.mock import AsyncMock, MagicMock

import pytest
import httpx
from fastapi import HTTPException

from app.models.core import Device, Organization, PaymentIntent
from app.routers import buy


pytestmark = pytest.mark.asyncio


def _db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


async def test_plans_come_from_profile_pricing(monkeypatch):
    dev = Device(id=uuid.uuid4(), name="r", ip_address="10.0.0.1", site_id=uuid.uuid4())
    dev.voucher_template = {"profile_pricing": {"3-Hours": {"price": 10, "currency": "GMD"}}}
    org = Organization(name="o", payments_enabled=True)
    org.modempay_secret_key = "encrypted"
    org.modempay_webhook_secret = "encrypted"
    monkeypatch.setattr(buy, "_load_context", AsyncMock(return_value=(dev, org)))

    out = await buy.get_plans(router=dev.id, db=_db())
    assert {"profile": "3-Hours", "price": 10, "currency": "GMD"} in out["plans"]


async def test_pay_refused_when_payments_disabled(monkeypatch):
    dev = Device(id=uuid.uuid4(), name="r", ip_address="10.0.0.1", site_id=uuid.uuid4())
    dev.voucher_template = {"profile_pricing": {"3-Hours": {"price": 10}}}
    org = Organization(name="o", payments_enabled=False)
    monkeypatch.setattr(buy, "_load_context", AsyncMock(return_value=(dev, org)))

    with pytest.raises(HTTPException) as error:
        await buy.pay(buy.PayRequest(router=dev.id, mac="AA:BB", plan="3-Hours"), db=_db())
    assert error.value.status_code == 409


async def test_pay_uses_server_price_and_persists_intent(monkeypatch):
    dev = Device(id=uuid.uuid4(), name="r", ip_address="10.0.0.1", site_id=uuid.uuid4())
    dev.voucher_template = {"profile_pricing": {"3-Hours": {"price": 10, "currency": "GMD"}}}
    org = Organization(name="o", payments_enabled=True)
    org.modempay_secret_key = "ciphertext"
    org.modempay_webhook_secret = "ciphertext"
    monkeypatch.setattr(buy, "_load_context", AsyncMock(return_value=(dev, org)))
    monkeypatch.setattr(buy, "decrypt_value", lambda value: "sk_test")
    create = AsyncMock(return_value={"payment_link": "https://checkout.test/1", "charge_id": "ch_1"})
    monkeypatch.setattr(buy, "create_payment_intent", create)
    db = _db()

    out = await buy.pay(buy.PayRequest(router=dev.id, mac="AA:BB", plan="3-Hours"), db=db)
    assert out == {"checkout_url": "https://checkout.test/1"}
    assert create.await_args.args[1:3] == (10, "GMD")
    assert create.await_args.args[3]["payment_intent_id"]
    assert f"router={dev.id}" in create.await_args.args[4]
    assert f"intent={db.add.call_args.args[0].id}" in create.await_args.args[4]
    assert db.add.call_args.args[0].charge_id == "ch_1"
    db.commit.assert_awaited_once()


async def test_pay_preserves_router_login_url_through_checkout(monkeypatch):
    dev = Device(id=uuid.uuid4(), name="r", ip_address="10.0.0.1", site_id=uuid.uuid4())
    dev.voucher_template = {"profile_pricing": {"3-Hours": {"price": 10, "currency": "GMD"}}}
    org = Organization(name="o", payments_enabled=True)
    org.modempay_secret_key = "ciphertext"
    org.modempay_webhook_secret = "ciphertext"
    monkeypatch.setattr(buy, "_load_context", AsyncMock(return_value=(dev, org)))
    monkeypatch.setattr(buy, "decrypt_value", lambda value: "sk_test")
    create = AsyncMock(return_value={"payment_link": "https://checkout.test/1", "charge_id": "ch_1"})
    monkeypatch.setattr(buy, "create_payment_intent", create)

    await buy.pay(buy.PayRequest(
        router=dev.id, mac="AA:BB", plan="3-Hours", login="http://mowifi.io/login"
    ), db=_db())

    return_query = parse_qs(urlsplit(create.await_args.args[4]).query)
    cancel_query = parse_qs(urlsplit(create.await_args.args[5]).query)
    assert return_query["login"] == ["http://mowifi.io/login"]
    assert cancel_query["login"] == ["http://mowifi.io/login"]


async def test_payment_status_returns_fulfilled_voucher():
    device_id = uuid.uuid4()
    intent = PaymentIntent(
        id=uuid.uuid4(), device_id=device_id, plan="3-Hours", amount=10,
        currency="GMD", status="fulfilled", voucher_username="ABC12345",
    )
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = intent
    db.execute = AsyncMock(return_value=result)

    out = await buy.payment_status(intent=intent.id, router=device_id, db=db)

    assert out == {"status": "fulfilled", "voucher_username": "ABC12345"}


async def test_pay_reports_rejected_modempay_key(monkeypatch):
    dev = Device(id=uuid.uuid4(), name="r", ip_address="10.0.0.1", site_id=uuid.uuid4())
    dev.voucher_template = {"profile_pricing": {"3-Hours": {"price": 10, "currency": "GMD"}}}
    org = Organization(name="o", payments_enabled=True)
    org.modempay_secret_key = "ciphertext"
    org.modempay_webhook_secret = "ciphertext"
    monkeypatch.setattr(buy, "_load_context", AsyncMock(return_value=(dev, org)))
    monkeypatch.setattr(buy, "decrypt_value", lambda value: "sk_test_invalid")
    request = httpx.Request("POST", "https://api.modempay.com/v1/payments")
    response = httpx.Response(401, request=request)
    rejected = httpx.HTTPStatusError("unauthorized", request=request, response=response)
    monkeypatch.setattr(buy, "create_payment_intent", AsyncMock(side_effect=rejected))

    with pytest.raises(HTTPException) as error:
        await buy.pay(buy.PayRequest(router=dev.id, mac="AA:BB", plan="3-Hours"), db=_db())

    assert error.value.status_code == 502
    assert "rejected the saved API key" in error.value.detail


def _hagie_shaped():
    """Pricing as typed by hand on a router NetGuard did not provision."""
    dev = Device(id=uuid.uuid4(), name="r", ip_address="10.0.0.1", site_id=uuid.uuid4())
    dev.voucher_template = {"profile_pricing": {
        "24hours": {"price": 25.0, "currency": "D"},
        "VIP": {"price": 500.0, "currency": "D"},
    }}
    org = Organization(name="o", payments_enabled=True)
    org.modempay_secret_key = "ciphertext"
    org.modempay_webhook_secret = "ciphertext"
    return dev, org


async def test_plans_offer_only_what_fulfilment_can_deliver(monkeypatch):
    dev, org = _hagie_shaped()
    monkeypatch.setattr(buy, "_load_context", AsyncMock(return_value=(dev, org)))

    out = await buy.get_plans(router=dev.id, db=_db())
    assert out["plans"] == [{"profile": "24hours", "price": 25, "currency": "GMD"}]


async def test_pay_refuses_a_plan_fulfilment_could_not_deliver(monkeypatch):
    dev, org = _hagie_shaped()
    monkeypatch.setattr(buy, "_load_context", AsyncMock(return_value=(dev, org)))
    create = AsyncMock()
    monkeypatch.setattr(buy, "create_payment_intent", create)

    with pytest.raises(HTTPException) as error:
        await buy.pay(buy.PayRequest(router=dev.id, mac="AA:BB", plan="VIP"), db=_db())
    assert error.value.status_code == 400
    create.assert_not_awaited()


async def test_pay_charges_in_the_iso_currency(monkeypatch):
    dev, org = _hagie_shaped()
    monkeypatch.setattr(buy, "_load_context", AsyncMock(return_value=(dev, org)))
    monkeypatch.setattr(buy, "decrypt_value", lambda value: "sk_test")
    create = AsyncMock(return_value={"payment_link": "https://checkout.test/1", "charge_id": "ch_1"})
    monkeypatch.setattr(buy, "create_payment_intent", create)
    db = _db()

    await buy.pay(buy.PayRequest(router=dev.id, mac="AA:BB", plan="24hours"), db=db)
    assert create.await_args.args[1:3] == (25, "GMD")
    intent = db.add.call_args.args[0]
    assert (intent.amount, intent.currency) == (25, "GMD")


def _status_db(intent):
    db = _db()
    result = MagicMock()
    result.scalar_one_or_none.return_value = intent
    db.execute = AsyncMock(return_value=result)
    return db


async def test_status_withholds_the_voucher_until_it_exists_on_the_router():
    intent = PaymentIntent(id=uuid.uuid4(), device_id=uuid.uuid4(), plan="3-Hours",
                           amount=10, currency="GMD", status="paid", voucher_username="abcd1234")
    out = await buy.payment_status(intent=intent.id, router=intent.device_id, db=_status_db(intent))
    assert out == {"status": "paid", "voucher_username": None}


async def test_status_returns_the_voucher_once_fulfilled():
    intent = PaymentIntent(id=uuid.uuid4(), device_id=uuid.uuid4(), plan="3-Hours",
                           amount=10, currency="GMD", status="fulfilled", voucher_username="abcd1234")
    out = await buy.payment_status(intent=intent.id, router=intent.device_id, db=_status_db(intent))
    assert out == {"status": "fulfilled", "voucher_username": "abcd1234"}


async def test_a_retired_router_is_not_found_by_the_buy_page():
    from unittest.mock import AsyncMock, MagicMock
    import uuid
    from fastapi import HTTPException
    from app.routers import buy
    result = MagicMock()
    result.first.return_value = None
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    with pytest.raises(HTTPException) as error:
        await buy._load_context(db, uuid.uuid4())
    assert error.value.status_code == 404
    assert "archived_at IS NULL" in str(db.execute.await_args.args[0])
