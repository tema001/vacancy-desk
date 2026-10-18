"""init_langgraph_checkpoints

Revision ID: 24dda7f6f41d
Revises: 7090fe9338ea
Create Date: 2026-10-18 12:29:47.216137

"""
from alembic import op
import sqlalchemy as sa
from langgraph.checkpoint.postgres.base import MIGRATIONS

# revision identifiers, used by Alembic.
revision = '24dda7f6f41d'
down_revision = '7090fe9338ea'
branch_labels = None
depends_on = None


def upgrade() -> None:
    for query in MIGRATIONS:
        if 'CONCURRENTLY' in query:
            query = query.replace('CONCURRENTLY ', '')

        op.execute(query)

    op.execute(f'INSERT INTO checkpoint_migrations (v) VALUES ({len(MIGRATIONS) - 1})')


def downgrade() -> None:
    ...