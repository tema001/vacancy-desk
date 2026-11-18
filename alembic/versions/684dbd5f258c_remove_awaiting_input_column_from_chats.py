"""remove awaiting_input column from chats

Revision ID: 684dbd5f258c
Revises: 23d979258083
Create Date: 2026-11-18 21:47:44.669140

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '684dbd5f258c'
down_revision = '23d979258083'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('chats', 'awaiting_input')


def downgrade() -> None:
    op.add_column('chats', sa.Column('awaiting_input', sa.BOOLEAN(), autoincrement=False, nullable=False))
