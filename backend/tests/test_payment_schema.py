"""Schema for portal payments: per-org Modem Pay keys + the intent ledger."""
from app.models.core import Organization, PaymentIntent


def test_org_has_payment_columns():
    cols = Organization.__table__.columns
    assert "modempay_secret_key" in cols
    assert "modempay_webhook_secret" in cols
    assert "payments_enabled" in cols
    # default False, not null
    assert cols["payments_enabled"].default.arg is False
    assert cols["payments_enabled"].nullable is False
    # secrets nullable (an org may not have set up payments)
    assert cols["modempay_secret_key"].nullable is True
    assert cols["modempay_webhook_secret"].nullable is True


def test_payment_intent_model_shape():
    cols = PaymentIntent.__table__.columns
    for name in ("id", "device_id", "charge_id", "plan", "amount",
                 "currency", "status", "voucher_username", "customer_mac",
                 "created_at", "updated_at"):
        assert name in cols, name
    # charge_id is the idempotency key: unique
    assert cols["charge_id"].unique is True
    assert cols["device_id"].nullable is False
