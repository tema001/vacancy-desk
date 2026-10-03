"""add is_selected column to profile table

Revision ID: e6b2d2876864
Revises: 5e2067d02f6a
Create Date: 2026-10-03 16:07:16.013592

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6b2d2876864'
down_revision = '5e2067d02f6a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('profiles', sa.Column('is_selected', sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column('profiles', 'is_selected')
