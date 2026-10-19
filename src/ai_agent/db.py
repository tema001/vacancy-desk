import sqlalchemy as sa
from sqlalchemy.dialects.postgresql.dml import insert
from sqlalchemy.engine.row import RowMapping
from sqlalchemy.ext.asyncio.engine import AsyncConnection

from src.db import select_all, select_one
from src.models import Chat
from src.types import DataDict

CHAT_COLUMNS = (
    Chat.id,
    Chat.awaiting_input,
    Chat.date_created,
    Chat.date_updated,
)


async def select_thread_messages(
    conn: AsyncConnection, thread_id: str
) -> RowMapping | None:
    query = sa.text("""
        SELECT b.type, b.blob
        FROM checkpoints c
        JOIN checkpoint_blobs b
          ON b.thread_id = c.thread_id
         AND b.checkpoint_ns = c.checkpoint_ns
         AND b.channel = 'messages'
         AND b.version = c.checkpoint -> 'channel_versions' ->> 'messages'
        WHERE c.thread_id = :thread_id
          AND c.checkpoint_ns = ''
        ORDER BY c.checkpoint_id DESC
        LIMIT 1;
    """)
    return await select_one(conn, query.bindparams(thread_id=thread_id))


async def insert_chat(conn: AsyncConnection) -> RowMapping:
    row = await select_one(conn, stmt=insert(Chat).values().returning(*CHAT_COLUMNS))
    assert row
    return row


async def select_active_chat(conn: AsyncConnection) -> RowMapping | None:
    return await select_one(
        conn,
        stmt=(
            sa.select(*CHAT_COLUMNS)
            .where(Chat.date_deleted.is_(None))
            .order_by(Chat.date_created.desc())
            .limit(1)
        ),
    )


async def delete_active_chats(conn: AsyncConnection) -> list[str]:
    rows = await select_all(
        conn,
        stmt=(
            sa.update(Chat)
            .values(date_deleted=sa.func.now())
            .where(Chat.date_deleted.is_(None))
            .returning(Chat.id)
        ),
    )
    return [row['id'] for row in rows]


async def select_chat_awaiting_input(conn: AsyncConnection, chat_id: str) -> bool | None:
    row = await select_one(
        conn,
        stmt=sa.select(Chat.awaiting_input).where(
            Chat.id == chat_id, Chat.date_deleted.is_(None)
        ),
    )
    return row['awaiting_input'] if row else None


async def update_chat(conn: AsyncConnection, chat_id: str, data: DataDict) -> None:
    await conn.execute(sa.update(Chat).values(data).where(Chat.id == chat_id))
