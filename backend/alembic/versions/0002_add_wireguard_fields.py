"""Add WireGuard fields to Device

Revision ID: 0002_add_wireguard_fields
Revises: 0001_initial_schema
Create Date: 2025-12-25 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_add_wireguard_fields'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('devices', sa.Column('wg_public_key', sa.String(), nullable=True))
    op.add_column('devices', sa.Column('wg_ip_address', sa.String(), nullable=True))
    op.add_column('devices', sa.Column('wg_private_key', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('devices', 'wg_private_key')
    op.drop_column('devices', 'wg_ip_address')
    op.drop_column('devices', 'wg_public_key')
