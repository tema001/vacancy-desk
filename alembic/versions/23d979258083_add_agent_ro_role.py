"""add_agent_ro_read-only_role

Revision ID: 23d979258083
Revises: 4ecfba40aef7
Create Date: 2026-11-07 17:12:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '23d979258083'
down_revision = '4ecfba40aef7'
branch_labels = None
depends_on = None


def _role_exists() -> bool:
    row = (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname = 'agent_ro'"))
        .scalar()
    )
    return row is not None


def upgrade() -> None:
    if not _role_exists():
        with op.get_context().autocommit_block():
            op.execute(
                sa.text(
                    "CREATE ROLE agent_ro LOGIN PASSWORD 'l65XbV7fc4owbikIcSfkUP8A' "
                    'NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOREPLICATION'
                )
            )

    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                EXECUTE format(
                    'GRANT CONNECT ON DATABASE %I TO agent_ro',
                    current_database()
                );
            END
            $$
            """
        )
    )
    op.execute(sa.text('GRANT pg_read_all_data TO agent_ro'))
    op.execute(sa.text('ALTER ROLE agent_ro SET default_transaction_read_only = on'))
    op.execute(sa.text("ALTER ROLE agent_ro SET statement_timeout = '15s'"))
    op.execute(sa.text("ALTER ROLE agent_ro SET lock_timeout = '3s'"))


def downgrade() -> None:
    if not _role_exists():
        return

    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                EXECUTE format(
                    'REVOKE CONNECT ON DATABASE %I FROM agent_ro',
                    current_database()
                );
            END
            $$
            """
        )
    )
    op.execute(sa.text('REVOKE pg_read_all_data FROM agent_ro'))
    with op.get_context().autocommit_block():
        op.execute(sa.text('DROP ROLE agent_ro'))
