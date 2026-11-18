import json
import time
from collections.abc import AsyncIterator, Mapping
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.types import Command

from src.ai_agent import db
from src.shared.resources import resources
from src.shared.utils import dt_now
from src.types import DataDict

_serde = JsonPlusSerializer()


def _get_chat_response(chat: Mapping[Any, Any]) -> DataDict:
    return {
        'id': chat['id'],
        'date_created': chat['date_created'].isoformat(),
        'date_updated': chat['date_updated'].isoformat(),
    }


async def get_active_chat() -> DataDict:
    async with resources.engine.connect() as conn:
        chat_row = await db.select_active_chat(conn)
        if chat_row is None:
            return {'chat': None, 'messages': []}

        row = await db.select_thread_messages(conn, chat_row['id'])

    chat_resp = _get_chat_response(chat_row)
    if row is None:
        return {'chat': chat_resp, 'messages': []}

    loaded = _serde.loads_typed((row['type'], row['blob']))
    messages = []
    for message in loaded:
        if not isinstance(message, HumanMessage | AIMessage):
            continue

        if isinstance(message, AIMessage) and not message.text:
            continue

        meta = message.response_metadata
        messages.append(
            {
                'id': message.id,
                'role': message.type,
                'text': message.text,
                'created_at': meta.get('finished_at', meta.get('created_at')),
            }
        )

    return {'chat': chat_resp, 'messages': messages}


async def create_new_chat() -> DataDict:
    async with resources.engine.begin() as conn:
        old_ids = await db.delete_active_chats(conn)
        chat_row = await db.insert_chat(conn)

    print('Create new chat. Deleted chats:', old_ids)
    # if old_ids:
    #     checkpointer = resources.agent.checkpointer
    #     assert checkpointer
    #
    #     for chat_id in old_ids:
    #         await checkpointer.adelete_thread(chat_id)

    return {'chat': _get_chat_response(chat_row), 'messages': []}


def _human_message(text: str) -> HumanMessage:
    # Same key and unix-seconds format as response_metadata of OpenAI replies.
    return HumanMessage(text, response_metadata={'created_at': time.time()})


async def process_chat_message(chat_id: str, text: str) -> AsyncIterator[str] | None:
    async with resources.engine.connect() as conn:
        if not await db.select_chat_exists(conn, chat_id):
            return None

        await_input = await db.select_thread_has_interrupt(conn, chat_id)

    return stream_chat_message(chat_id, text, awaiting_input=await_input)


def sse_format(event: str, payload: DataDict) -> str:
    return f'event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n'


async def stream_chat_message(
    chat_id: str, text: str, *, awaiting_input: bool
) -> AsyncIterator[str]:
    config: RunnableConfig = {'configurable': {'thread_id': chat_id}}
    _input: Command[Any] | DataDict = (
        Command(resume=text) if awaiting_input else {'messages': [_human_message(text)]}
    )

    need_awaiting = False
    try:
        async for event in resources.agent.astream(
            _input, config=config, stream_mode=['updates', 'messages'], version='v2'
        ):
            if event['type'] == 'messages':
                msg, metadata = event['data']
                if metadata['langgraph_node'] in ('agent', 'final_response') and msg.text:
                    yield sse_format('token', payload={'text': msg.text})

            elif event['type'] == 'updates' and '__interrupt__' in event['data']:
                need_awaiting = True
                interrupts = event['data']['__interrupt__']
                yield sse_format('interrupt', payload={'text': str(interrupts[0].value)})
    except Exception as exc:
        print(f'Chat {chat_id}: agent stream failed: {exc!r}')
        yield sse_format('error', payload={'text': 'Something went wrong. Try again.'})
        return

    async with resources.engine.begin() as conn:
        await db.update_chat(conn, chat_id, data={'date_updated': dt_now()})

    yield sse_format(
        'done', payload={'awaiting_input': need_awaiting, 'created_at': time.time()}
    )
