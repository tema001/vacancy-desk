"""add skill related models

Revision ID: 75f39e848cbb
Revises: 4d0f29fc5752
Create Date: 2026-09-13 23:33:44.744712

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from src.shared.types import SmallIntEnum
import src.enums as enum
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '75f39e848cbb'
down_revision: Union[str, Sequence[str], None] = '4d0f29fc5752'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'skill_lexicon',
        sa.Column('skill_name', sa.Text(), nullable=False),
        sa.Column('kind', SmallIntEnum(enum.SkillKind), nullable=False),
        sa.Column('expanded', sa.String(), nullable=True),
        sa.Column('expanded_vector', Vector(dim=1536), nullable=True),
        sa.Column('embedding_model', sa.String(), nullable=True),
        sa.Column('date_created', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('skill_name'),
    )
    op.create_table(
        'vacancy_extract',
        sa.Column('vacancy_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('job_family', SmallIntEnum(enum.JobFamily), nullable=False),
        sa.Column('prompt_version', sa.String(), nullable=False),
        sa.Column('industry', sa.String(), nullable=True),
        sa.Column('raw_response', sa.String(), nullable=False),
        sa.Column('completeness', sa.Float(), nullable=False),
        sa.Column('date_created', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['vacancy_id'], ['vacancies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('vacancy_id'),
    )
    op.create_table(
        'vacancy_skills',
        sa.Column(
            'id',
            sa.Uuid(as_uuid=False),
            server_default=sa.text('uuidv7()'),
            nullable=False,
        ),
        sa.Column('vacancy_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('skill_name', sa.Text(), nullable=False),
        sa.Column('depth', SmallIntEnum(enum.SkillDepth), nullable=False),
        sa.Column('importance', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ['skill_name'],
            ['skill_lexicon.skill_name'],
            onupdate='CASCADE',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['vacancy_id'], ['vacancy_extract.vacancy_id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('vacancy_id', 'skill_name'),
    )


def downgrade() -> None:
    op.drop_table('vacancy_skills')
    op.drop_table('vacancy_extract')
    op.drop_table('skill_lexicon')
