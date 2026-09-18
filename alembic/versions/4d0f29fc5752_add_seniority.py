"""add seniority

Revision ID: 4d0f29fc5752
Revises: e01a51751374
Create Date: 2026-09-12 14:06:20.210620

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from src.enums import Seniority
from src.shared.types import SmallIntEnum

# revision identifiers, used by Alembic.
revision: str = '4d0f29fc5752'
down_revision: Union[str, Sequence[str], None] = 'e01a51751374'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'vacancies', sa.Column('seniority', SmallIntEnum(Seniority), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('vacancies', 'seniority')
