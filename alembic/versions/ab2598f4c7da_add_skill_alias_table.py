"""add_skill_alias_table

Revision ID: ab2598f4c7da
Revises: 684dbd5f258c
Create Date: 2026-11-23 15:15:25.122269

"""
from alembic import op
import sqlalchemy as sa

from src.shared.types import SmallIntEnum
import src.enums as enum

# revision identifiers, used by Alembic.
revision = 'ab2598f4c7da'
down_revision = '684dbd5f258c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('skill_alias',
    sa.Column('alias_name', sa.Text(), nullable=False),
    sa.Column(
        'alias_name_norm',
        sa.Text(),
        sa.Computed("trim(regexp_replace(lower(alias_name), '[/_.\\-]+', ' ', 'g'))", persisted=True),
        nullable=False
    ),
    sa.Column('skill_name', sa.Text(), nullable=True),
    sa.Column('status', SmallIntEnum(enum.SkillAliasStatus), nullable=False),
    sa.Column('seen_count', sa.Integer(), nullable=False),
    sa.Column('is_reviewed', sa.Boolean(), nullable=False),
    sa.Column('date_created', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('(skill_name IS NOT NULL) = (status = 1)', name='ck_skill_alias_skill_name_iff_alias'),
    sa.ForeignKeyConstraint(['skill_name'], ['skill_lexicon.skill_name'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('alias_name_norm')
    )
    op.add_column('skill_lexicon', sa.Column('status', SmallIntEnum(enum.SkillLexiconStatus), nullable=True))
    op.create_unique_constraint('uq_skill_lexicon_skill_name_norm', 'skill_lexicon', ['skill_name_norm'])


def downgrade() -> None:
    op.drop_constraint('uq_skill_lexicon_skill_name_norm', 'skill_lexicon', type_='unique')
    op.drop_column('skill_lexicon', 'status')
    op.drop_table('skill_alias')
