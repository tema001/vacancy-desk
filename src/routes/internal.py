from typing import Annotated

from fastapi import APIRouter, Query

from src.jobs import (
    ENQUEUE_VACANCIES,
    EXTRACT_VACANCY,
    LEXICON_EMBED,
    LEXICON_EXPAND,
    PROCESS_FEED,
)
from src.services.worker import app as worker
from src.types import DataDict

router = APIRouter(tags=['internal'])


@router.get('/feed')
async def process_feed_run_job(
    category: Annotated[str, Query(max_length=20)],
) -> DataDict:
    await worker.configure_task(PROCESS_FEED).defer_async(category=category)

    return {'result': 'ok'}


@router.get('/enqueue-vacancies')
async def enqueue_vacancies_run_job() -> DataDict:
    await worker.configure_task(ENQUEUE_VACANCIES).defer_async()

    return {'result': 'ok'}


@router.get('/api/ai/extract')
async def ai_extract() -> DataDict:
    for vacancy_id in ('01a0a482-5b03-7370-90ea-fcb1df4261eb',):
        await worker.configure_task(
            EXTRACT_VACANCY,
            queueing_lock=f'extract:{vacancy_id}',
            lock=vacancy_id,
        ).defer_async(vacancy_id=vacancy_id)

    return {'result': 'ok'}


@router.get('/api/ai/lexicon-expand')
async def ai_lexicon_expand() -> DataDict:
    await worker.configure_task(LEXICON_EXPAND).defer_async()

    return {'result': 'ok'}


@router.get('/api/ai/lexicon-embed')
async def ai_lexicon_embed() -> DataDict:
    await worker.configure_task(LEXICON_EMBED).defer_async()

    return {'result': 'ok'}
