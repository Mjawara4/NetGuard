"""portal payments: per-org Modem Pay keys + payment_intents ledger

Additive only. Three nullable/defaulted columns on organizations, one new
table. No existing data is touched.

Revision ID: 0010_portal_payments
Revises: 0009
Create Date: 2026-10-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0010_portal_payments"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    # Per-org Modem Pay credentials (encrypted at the app layer) + enable flag.
    op.add_column("organizations", sa.Column("modempay_secret_key", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("modempay_webhook_secret", sa.Text(), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("payments_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # The payment ledger. charge_id is the idempotency key.
    op.create_table(
        "payment_intents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", UUID(as_uuid=True), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("charge_id", sa.String(), nullable=True),
        sa.Column("plan", sa.String(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="GMD"),
        sa.Column("status", sa.String(), nullable=False, server_default="created"),
        sa.Column("voucher_username", sa.String(), nullable=True),
        sa.Column("customer_mac", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_unique_constraint("uq_payment_intents_charge_id", "payment_intents", ["charge_id"])
    op.create_index("ix_payment_intents_device_id", "payment_intents", ["device_id"])


def downgrade():
    op.drop_index("ix_payment_intents_device_id", table_name="payment_intents")
    op.drop_constraint("uq_payment_intents_charge_id", "payment_intents", type_="unique")
    op.drop_table("payment_intents")
    op.drop_column("organizations", "payments_enabled")
    op.drop_column("organizations", "modempay_webhook_secret")
    op.drop_column("organizations", "modempay_secret_key")
