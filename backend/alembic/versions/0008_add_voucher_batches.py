"""Add voucher_batches table

Revision ID: 0008
Revises: 0007
Create Date: 2025-05-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'voucher_batches',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('device_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('batch_name', sa.String(), nullable=False),
        sa.Column('prefix', sa.String(), nullable=False),
        sa.Column('profile', sa.String(), nullable=False),
        sa.Column('time_limit', sa.String(), nullable=True),
        sa.Column('data_limit', sa.String(), nullable=True),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.Column('vouchers', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_voucher_batches_created_at'), 'voucher_batches', ['created_at'], unique=False)
    op.create_index(op.f('ix_voucher_batches_device_id'), 'voucher_batches', ['device_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_voucher_batches_device_id'), table_name='voucher_batches')
    op.drop_index(op.f('ix_voucher_batches_created_at'), table_name='voucher_batches')
    op.drop_table('voucher_batches')
