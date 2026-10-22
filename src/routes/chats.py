from fastapi import APIRouter, HTTPException, status

from src.ai_agent import utils
from src.types import ChatMessageSchema, DataDict

router = APIRouter(tags=['chats'])


@router.get('/api/chats/active')
async def get_active_chat() -> DataDict:
    return await utils.get_active_chat()


@router.post('/api/chats/new', status_code=status.HTTP_201_CREATED)
async def create_chat() -> DataDict:
    return await utils.create_new_chat()


@router.post('/api/chats/{chat_id}/messages')
async def create_chat_message(chat_id: str, body: ChatMessageSchema) -> DataDict:
    result = await utils.process_chat_message(chat_id, body.text)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return result
