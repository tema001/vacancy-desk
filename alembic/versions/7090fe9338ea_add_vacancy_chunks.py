"""add vacancy_chunks

Revision ID: 7090fe9338ea
Revises: 261a15c5759a
Create Date: 2026-10-08 22:25:08.673417

"""
from alembic import op
import sqlalchemy as sa

from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '7090fe9338ea'
down_revision = '261a15c5759a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('vacancy_chunks',
    sa.Column('id', sa.Uuid(as_uuid=False), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('vacancy_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('fragment', sa.SmallInteger(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('content_hash', sa.LargeBinary(length=32), nullable=False),
    sa.Column('embedding', Vector(dim=1536), nullable=True),
    sa.Column('embedding_model', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['vacancy_id'], ['vacancies.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('vacancy_id', 'fragment', name='uq_vacancy_chunks_vacancy_id_fragment')
    )
    op.create_index('ix_vacancy_chunks_embedding', 'vacancy_chunks', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index(op.f('ix_vacancy_chunks_vacancy_id'), 'vacancy_chunks', ['vacancy_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_vacancy_chunks_vacancy_id'), table_name='vacancy_chunks')
    op.drop_index('ix_vacancy_chunks_embedding', table_name='vacancy_chunks', postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_table('vacancy_chunks')
