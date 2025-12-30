"""Add Database Indexes for Performance

Revision ID: 0003_add_indexes
Revises: 0002_add_wireguard_fields
Create Date: 2025-12-25 00:02:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_add_indexes'
down_revision: Union[str, None] = '0002_add_wireguard_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Index on metrics for faster time-series queries
    # Note: TimescaleDB may already have indexes, but this ensures they exist
    op.create_index(
        'idx_metrics_device_time',
        'metrics',
        ['device_id', 'time'],
        unique=False,
        if_not_exists=True
    )
    
    # Index on metrics by metric_type for filtering
    op.create_index(
        'idx_metrics_type_time',
        'metrics',
        ['metric_type', 'time'],
        unique=False,
        if_not_exists=True
    )
    
    # Index on alerts for faster queries
    op.create_index(
        'idx_alerts_device_status',
        'alerts',
        ['device_id', 'status', 'created_at'],
        unique=False,
        if_not_exists=True
    )
    
    # Index on devices by site for faster lookups
    op.create_index(
        'idx_devices_site',
        'devices',
        ['site_id'],
        unique=False,
        if_not_exists=True
    )
    
    # Index on users email (may already exist, but ensure it)
    op.create_index(
        'ix_users_email',
        'users',
        ['email'],
        unique=True,
        if_not_exists=True
    )


def downgrade() -> None:
    op.drop_index('idx_metrics_device_time', table_name='metrics', if_exists=True)
    op.drop_index('idx_metrics_type_time', table_name='metrics', if_exists=True)
    op.drop_index('idx_alerts_device_status', table_name='alerts', if_exists=True)
    op.drop_index('idx_devices_site', table_name='devices', if_exists=True)
    # Note: Don't drop ix_users_email as it may have been created in initial schema
