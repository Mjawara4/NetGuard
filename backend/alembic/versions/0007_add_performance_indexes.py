"""add_performance_indexes

Revision ID: 0007
Revises: 0006
Create Date: 2025-05-29 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Core composite index for metrics lookups by device + type + time
    op.create_index(
        'idx_metrics_device_type_time',
        'metrics',
        ['device_id', 'metric_type', 'time'],
        unique=False,
        if_not_exists=True
    )


def downgrade() -> None:
    op.drop_index('idx_metrics_device_type_time', table_name='metrics', if_exists=True)
