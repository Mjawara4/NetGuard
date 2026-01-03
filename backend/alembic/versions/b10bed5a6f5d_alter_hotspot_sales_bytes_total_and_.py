"""alter hotspot_sales bytes_total and price to bigint

Revision ID: b10bed5a6f5d
Revises: 0005_add_hotspot_sales_table
Create Date: 2026-01-03 02:08:02.755610

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b10bed5a6f5d'
down_revision: Union[str, None] = '0005_add_hotspot_sales_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('hotspot_sales', 'bytes_total',
               existing_type=sa.INTEGER(),
               type_=sa.BigInteger(),
               existing_nullable=True)
    op.alter_column('hotspot_sales', 'price',
               existing_type=sa.INTEGER(),
               type_=sa.BigInteger(),
               existing_nullable=True)


def downgrade() -> None:
    op.alter_column('hotspot_sales', 'price',
               existing_type=sa.BigInteger(),
               type_=sa.INTEGER(),
               existing_nullable=True)
    op.alter_column('hotspot_sales', 'bytes_total',
               existing_type=sa.BigInteger(),
               type_=sa.INTEGER(),
               existing_nullable=True)

