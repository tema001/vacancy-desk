"""add_chats_table

Revision ID: 2b2489e59234
Revises: 24dda7f6f41d
Create Date: 2026-10-19 21:37:09.057973

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2b2489e59234'
down_revision = '24dda7f6f41d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('chats',
    sa.Column('id', sa.Uuid(as_uuid=False), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('awaiting_input', sa.Boolean(), nullable=False),
    sa.Column('date_created', sa.DateTime(timezone=True), nullable=False),
    sa.Column('date_updated', sa.DateTime(timezone=True), nullable=False),
    sa.Column('date_deleted', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('chats')
