"""Small async client for the Modem Pay hosted-checkout API."""

import hashlib
import hmac
from typing import Any, Dict, Optional

import httpx


API_URL = "https://api.modempay.com/v1/payments"
_transport: Optional[httpx.AsyncBaseTransport] = None


def verify_webhook(raw_body: bytes, signature: str, webhook_secret: str) -> bool:
    """Verify Modem Pay's lowercase hex HMAC-SHA512 signature."""
    if not signature or not webhook_secret:
        return False
    expected = hmac.new(webhook_secret.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


async def create_payment_intent(
    secret_key: str,
    amount: int,
    currency: str,
    metadata: Dict[str, Any],
    return_url: str,
    cancel_url: str,
) -> Dict[str, Optional[str]]:
    """Create a hosted checkout using the contract shipped by the official SDK."""
    payload = {
        "data": {
            "amount": amount,
            "currency": currency,
            "metadata": metadata,
            "return_url": return_url,
            "cancel_url": cancel_url,
            "from_sdk": False,
        }
    }
    async with httpx.AsyncClient(transport=_transport, timeout=30.0) as client:
        response = await client.post(
            API_URL,
            headers={"Authorization": f"Bearer {secret_key}"},
            json=payload,
        )
        response.raise_for_status()

    body = response.json()
    data = body.get("data", body)
    payment_link = data.get("payment_link") or data.get("link")
    if not payment_link:
        raise ValueError("Modem Pay response did not include a payment link")
    return {
        "payment_link": payment_link,
        "charge_id": data.get("charge_id") or data.get("id"),
    }
