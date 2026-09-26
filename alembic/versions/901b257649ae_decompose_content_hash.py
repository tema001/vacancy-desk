"""decompose content_hash

Revision ID: 901b257649ae
Revises: b7f1c9e2a046
Create Date: 2026-09-26 11:38:15.729666

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '901b257649ae'
down_revision = 'b7f1c9e2a046'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('vacancies', sa.Column('params_hash', sa.LargeBinary(length=32), nullable=True))
    op.add_column('vacancies', sa.Column('description_hash', sa.LargeBinary(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column('vacancies', 'description_hash')
    op.drop_column('vacancies', 'params_hash')
