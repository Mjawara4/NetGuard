"""add alert resolution_summary

Revision ID: 0006
Revises: 0005_add_hotspot_sales_table
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = 'b10bed5a6f5d'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('alerts', sa.Column('resolution_summary', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('alerts', 'resolution_summary')
