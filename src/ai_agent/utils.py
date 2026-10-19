from collections.abc import Mapping
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
        'awaiting_input': chat['awaiting_input'],
        'date_created': chat['date_created'].isoformat(),
        'date_updated': chat['date_updated'].isoformat(),
    }


async def get_active_chat() -> DataDict:
    async with resources.engine.connect() as conn:
        chat_row = await db.select_active_chat(conn)
        if chat_row is None:
            return {'chat': None}

        row = await db.select_thread_messages(conn, chat_row['id'])

    chat_resp = _get_chat_response(chat_row)
    if row is None:
        return {'chat': chat_resp, 'messages': []}

    loaded = _serde.loads_typed((row['type'], row['blob']))
    messages = []
    for message in loaded:
        if not isinstance(message, HumanMessage | AIMessage):
            continue

        if isinstance(message, AIMessage) and message.tool_calls:
            continue

        messages.append({'role': message.type, 'text': message.text})

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


async def process_chat_message(chat_id: str, text: str) -> DataDict | None:
    async with resources.engine.connect() as conn:
        await_input = await db.select_chat_awaiting_input(conn, chat_id)

    if await_input is None:
        return None

    result = await send_chat_message(chat_id, text, awaiting_input=await_input)

    data = {'date_updated': dt_now()}
    if result['awaiting_input'] != await_input:
        data['awaiting_input'] = result['awaiting_input']

    async with resources.engine.begin() as conn:
        await db.update_chat(conn, chat_id, data)

    return result


async def send_chat_message(chat_id: str, text: str, *, awaiting_input: bool) -> DataDict:
    config: RunnableConfig = {'configurable': {'thread_id': chat_id}}
    if awaiting_input:
        result = await resources.agent.ainvoke(Command(resume=text), config=config)
    else:
        result = await resources.agent.ainvoke(
            {'messages': [HumanMessage(text)]}, config=config
        )

    interrupts = result.get('__interrupt__')
    if interrupts:
        value = interrupts[0].value
        return {'reply': str(value), 'awaiting_input': True}

    return {'text': result['messages'][-1].text, 'awaiting_input': False}
