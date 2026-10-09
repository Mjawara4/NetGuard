"""devices.archived_at: retire a router without losing its payment history

Additive only: one nullable column. No existing row is touched.

Revision ID: 0011_device_archived_at
Revises: 0010_portal_payments
Create Date: 2026-10-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_device_archived_at"
down_revision = "0010_portal_payments"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("devices", sa.Column("archived_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("devices", "archived_at")
