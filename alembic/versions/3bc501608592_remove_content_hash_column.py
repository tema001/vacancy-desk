"""remove content_hash column

Revision ID: 3bc501608592
Revises: 901b257649ae
Create Date: 2026-09-26 12:34:24.844532

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3bc501608592'
down_revision = '901b257649ae'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('vacancies', 'content_hash')


def downgrade() -> None:
    op.add_column('vacancies', sa.Column('content_hash', postgresql.BYTEA(), autoincrement=False, nullable=True))
