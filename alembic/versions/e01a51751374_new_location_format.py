"""new location format

Revision ID: e01a51751374
Revises:
Create Date: 2026-09-09 10:58:09.307059

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e01a51751374'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('ALTER TABLE vacancies ALTER COLUMN location DROP NOT NULL;')
    op.execute('ALTER TABLE vacancies RENAME COLUMN location TO location_str;')
    op.add_column(
        'vacancies',
        sa.Column('location', postgresql.ARRAY(sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('vacancies', 'location')
    op.execute('ALTER TABLE vacancies RENAME COLUMN location_str TO location;')
