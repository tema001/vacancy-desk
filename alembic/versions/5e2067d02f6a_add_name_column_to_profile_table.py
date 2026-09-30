"""add name column to profile table

Revision ID: 5e2067d02f6a
Revises: 774986b08f3f
Create Date: 2026-09-30 18:06:15.945514

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5e2067d02f6a'
down_revision = '774986b08f3f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('profiles', sa.Column('name', sa.String(), nullable=False))


def downgrade() -> None:
    op.drop_column('profiles', 'name')
