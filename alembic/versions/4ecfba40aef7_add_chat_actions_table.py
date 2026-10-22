"""add_chat_actions_table

Revision ID: 4ecfba40aef7
Revises: 2b2489e59234
Create Date: 2026-10-22 00:06:31.112806

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from src.shared.types import SmallIntEnum
import src.enums as enum


# revision identifiers, used by Alembic.
revision = '4ecfba40aef7'
down_revision = '2b2489e59234'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('chat_actions',
    sa.Column('id', sa.Uuid(as_uuid=False), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('chat_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('action_type', SmallIntEnum(enum.ChatActionType), nullable=False),
    sa.Column('item_id', sa.String(), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('date_created', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['chat_id'], ['chats.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('chat_actions')
