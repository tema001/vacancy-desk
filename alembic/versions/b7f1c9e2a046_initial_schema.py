"""initial schema

Revision ID: b7f1c9e2a046
Revises:
Create Date: 2026-09-20 19:45:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

from src.shared.types import SmallIntEnum
import src.enums as enum


# revision identifiers, used by Alembic.
revision = 'b7f1c9e2a046'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector;')
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm;')

    op.create_table(
        'vacancies',
        sa.Column(
            'id',
            sa.Uuid(as_uuid=False),
            server_default=sa.text('uuidv7()'),
            nullable=False,
        ),
        sa.Column('source', SmallIntEnum(enum.Source), nullable=False),
        sa.Column('external_id', sa.Text(), nullable=False),
        sa.Column('category', sa.Text(), nullable=False),
        sa.Column('company', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.LargeBinary(length=32), nullable=False),
        sa.Column('location_str', sa.Text(), nullable=True),
        sa.Column('location', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('salary_min', sa.Integer(), nullable=True),
        sa.Column('salary_max', sa.Integer(), nullable=True),
        sa.Column('salary_level', sa.Text(), nullable=True),
        sa.Column('experience', sa.Float(), nullable=True),
        sa.Column('english_level', SmallIntEnum(enum.EnglishLevel), nullable=True),
        sa.Column('seniority', SmallIntEnum(enum.Seniority), nullable=True),
        sa.Column('date_created', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', SmallIntEnum(enum.Status), nullable=False),
        sa.Column('date_last_seen', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'source', 'external_id', name='uq_vacancies_source_external_id'
        ),
    )
    op.create_table(
        'vacancies_activity',
        sa.Column(
            'id',
            sa.Uuid(as_uuid=False),
            server_default=sa.text('uuidv7()'),
            nullable=False,
        ),
        sa.Column('vacancy_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('date_started', sa.DateTime(timezone=True), nullable=False),
        sa.Column('date_ended', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['vacancy_id'], ['vacancies.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_vacancy_id_date_ended_is_null',
        'vacancies_activity',
        ['vacancy_id'],
        unique=True,
        postgresql_where=sa.text('date_ended IS NULL'),
    )
    op.create_index(
        'ix_va_vacancy_id_date_started',
        'vacancies_activity',
        ['vacancy_id', sa.text('date_started DESC')],
    )
    op.create_table(
        'skill_lexicon',
        sa.Column('skill_name', sa.Text(), nullable=False),
        sa.Column(
            'skill_name_norm',
            sa.Text(),
            sa.Computed(
                "trim(regexp_replace(lower(skill_name), '[/_.\\-]+', ' ', 'g'))",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column('kind', SmallIntEnum(enum.SkillKind), nullable=False),
        sa.Column('expanded', sa.Text(), nullable=True),
        sa.Column('expanded_vector', Vector(dim=1536), nullable=True),
        sa.Column('embedding_model', sa.Text(), nullable=True),
        sa.Column('date_created', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('skill_name'),
    )
    op.create_table(
        'vacancy_extract',
        sa.Column('vacancy_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('job_family', SmallIntEnum(enum.JobFamily), nullable=False),
        sa.Column('prompt_version', sa.Text(), nullable=False),
        sa.Column('industry', sa.Text(), nullable=True),
        sa.Column('raw_response', sa.Text(), nullable=False),
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
    op.drop_index('ix_va_vacancy_id_date_started', table_name='vacancies_activity')
    op.drop_index('uq_vacancy_id_date_ended_is_null', table_name='vacancies_activity')
    op.drop_table('vacancies_activity')
    op.drop_table('vacancies')
    op.execute('DROP EXTENSION IF EXISTS pg_trgm;')
    op.execute('DROP EXTENSION IF EXISTS vector;')
