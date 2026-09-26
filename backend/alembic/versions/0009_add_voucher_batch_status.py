"""add status to voucher_batches

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade():
    # Nullable with no backfill: the 21 pre-existing rows are all completed
    # batches from before background jobs existed, and a NULL status reads as
    # "legacy, not a job" everywhere it is consumed.
    op.add_column('voucher_batches', sa.Column('status', sa.String(), nullable=True))


def downgrade():
    op.drop_column('voucher_batches', 'status')
