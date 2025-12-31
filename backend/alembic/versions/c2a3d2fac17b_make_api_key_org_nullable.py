"""make_api_key_org_nullable

Revision ID: c2a3d2fac17b
Revises: 0004_add_voucher_template
Create Date: 2025-12-31 07:13:34.981561

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2a3d2fac17b'
down_revision: Union[str, None] = '0004_add_voucher_template'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make organization_id nullable in api_keys table
    op.alter_column('api_keys', 'organization_id',
               existing_type=sa.UUID(),
               nullable=True)


def downgrade() -> None:
    # Make organization_id NOT nullable in api_keys table
    op.alter_column('api_keys', 'organization_id',
               existing_type=sa.UUID(),
               nullable=False)
