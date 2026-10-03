"""remove nullable is_selected

Revision ID: 261a15c5759a
Revises: e6b2d2876864
Create Date: 2026-10-03 17:44:58.863763

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '261a15c5759a'
down_revision = 'e6b2d2876864'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('profiles', 'is_selected',
               existing_type=sa.BOOLEAN(),
               nullable=False)


def downgrade() -> None:
    op.alter_column('profiles', 'is_selected',
               existing_type=sa.BOOLEAN(),
               nullable=True)
