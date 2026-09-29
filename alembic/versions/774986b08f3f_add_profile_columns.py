"""add profile columns

Revision ID: 774986b08f3f
Revises: 3bc501608592
Create Date: 2026-09-28 20:39:17.467032

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from src.shared.types import SmallIntEnum
import src.enums as enum

# revision identifiers, used by Alembic.
revision = '774986b08f3f'
down_revision = '3bc501608592'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('profiles',
        sa.Column('id', sa.Uuid(as_uuid=False), server_default=sa.text('uuidv7()'), nullable=False),
        sa.Column('text', sa.String(), nullable=False),
        sa.Column('prompt_version', sa.String(), nullable=True),
        sa.Column('raw_response', sa.String(), nullable=True),
        sa.Column('job_families', postgresql.ARRAY(sa.SmallInteger()), nullable=True),
        sa.Column('experience', sa.Float(), nullable=True),
        sa.Column('english_level', SmallIntEnum(enum.EnglishLevel), nullable=True),
        sa.Column('seniority', SmallIntEnum(enum.Seniority), nullable=True),
        sa.Column('status', SmallIntEnum(enum.ProfileStatus), nullable=False),
        sa.Column('date_created', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('profile_skills',
        sa.Column('id', sa.Uuid(as_uuid=False), server_default=sa.text('uuidv7()'), nullable=False),
        sa.Column('profile_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('skill_name', sa.Text(), nullable=False),
        sa.Column('depth', SmallIntEnum(enum.SkillDepth), nullable=False),
        sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['skill_name'], ['skill_lexicon.skill_name'], onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('profile_id', 'skill_name')
    )


def downgrade() -> None:
    op.drop_table('profile_skills')
    op.drop_table('profiles')
