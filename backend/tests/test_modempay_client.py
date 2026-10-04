import hashlib
import hmac

import httpx
import pytest

from app.services.modempay import create_payment_intent, verify_webhook


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()


def test_valid_signature_accepted():
    body = b'{"event":"charge.succeeded"}'
    assert verify_webhook(body, _sign(body, "whsec"), "whsec") is True


def test_tampered_body_rejected():
    body = b'{"event":"charge.succeeded"}'
    assert verify_webhook(b'{"event":"evil"}', _sign(body, "whsec"), "whsec") is False


def test_wrong_or_missing_signature_rejected():
    body = b'{"x":1}'
    assert verify_webhook(body, _sign(body, "whsec"), "other") is False
    assert verify_webhook(body, "", "whsec") is False


@pytest.mark.asyncio
async def test_create_payment_intent_uses_official_api_contract(monkeypatch):
    seen = {}

    async def handler(request: httpx.Request):
        seen["request"] = request
        return httpx.Response(200, json={
            "status": True,
            "data": {"payment_link": "https://checkout.modempay.com/pi_1", "id": "ch_1"},
        })

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr("app.services.modempay._transport", transport)
    result = await create_payment_intent(
        "sk_test_ABC", 1000, "GMD", {"plan": "3-Hours"},
        "https://app.netguard.fun/buy/success", "https://app.netguard.fun/buy",
    )

    request = seen["request"]
    assert str(request.url) == "https://api.modempay.com/v1/payments"
    assert request.headers["Authorization"] == "Bearer sk_test_ABC"
    assert result == {"payment_link": "https://checkout.modempay.com/pi_1", "charge_id": "ch_1"}
    assert b'"data"' in request.content and b'"from_sdk":false' in request.content
