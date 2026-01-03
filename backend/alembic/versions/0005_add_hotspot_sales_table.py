"""Add hotspot_sales table

Revision ID: 0005_add_hotspot_sales_table
Revises: c2a3d2fac17b
Create Date: 2026-01-03 01:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0005_add_hotspot_sales_table'
down_revision: Union[str, None] = 'c2a3d2fac17b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'hotspot_sales',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('device_id', sa.UUID(), nullable=False),
        sa.Column('site_id', sa.UUID(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('profile', sa.String(), nullable=False),
        sa.Column('comment', sa.String(), nullable=True),
        sa.Column('uptime', sa.String(), nullable=True),
        sa.Column('uptime_sec', sa.Integer(), nullable=True),
        sa.Column('bytes_total', sa.Integer(), nullable=True),
        sa.Column('price', sa.Integer(), nullable=True),
        sa.Column('currency', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('sync_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hotspot_sales_created_at'), 'hotspot_sales', ['created_at'], unique=False)
    op.create_index(op.f('ix_hotspot_sales_username'), 'hotspot_sales', ['username'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_hotspot_sales_username'), table_name='hotspot_sales')
    op.drop_index(op.f('ix_hotspot_sales_created_at'), table_name='hotspot_sales')
    op.drop_table('hotspot_sales')
