"""Add Voucher Template Column

Revision ID: 0004_add_voucher_template
Revises: 0003_add_indexes
Create Date: 2025-12-30 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0004_add_voucher_template'
down_revision: Union[str, None] = '0003_add_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('devices', sa.Column('voucher_template', postgresql.JSON(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('devices', 'voucher_template')
