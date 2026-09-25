from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles

import src.queries as queries
from src.jobs import (
    ENQUEUE_VACANCIES,
    EXTRACT_VACANCY,
    LEXICON_EMBED,
    LEXICON_EXPAND,
    PROCESS_FEED,
)
from src.services.worker import app as worker
from src.shared.resources import resources
from src.types import DataDict, ParamsSchema, ScoringParamsSchema


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await resources.start()

    try:
        async with worker.open_async():
            yield
    finally:
        await resources.stop()


app = FastAPI(title='Vacancy Desk', lifespan=lifespan)


@app.get('/feed')
async def process_feed_run_job(
    category: Annotated[str, Query(max_length=20)],
) -> DataDict:
    await worker.configure_task(PROCESS_FEED).defer_async(category=category)

    return {'result': 'ok'}


@app.get('/enqueue-vacancies')
async def enqueue_vacancies_run_job() -> DataDict:
    await worker.configure_task(ENQUEUE_VACANCIES).defer_async()

    return {'result': 'ok'}


@app.post('/api/vacancies')
async def get_vacancies(params: ParamsSchema) -> DataDict:
    return await queries.get_vacancies(params)


@app.post('/api/vacancies/score')
async def get_scored_vacancies(params: ScoringParamsSchema) -> DataDict:
    return await queries.get_scored_vacancies(params)


@app.get('/api/ai/extract')
async def ai_extract() -> DataDict:
    for vacancy_id in ('01a0a482-5b03-7370-90ea-fcb1df4261eb',):
        await worker.configure_task(
            EXTRACT_VACANCY,
            queueing_lock=f'extract:{vacancy_id}',
            lock=vacancy_id,
        ).defer_async(vacancy_id=vacancy_id)

    return {'result': 'ok'}


@app.get('/api/ai/lexicon-expand')
async def ai_lexicon_expand() -> DataDict:
    await worker.configure_task(LEXICON_EXPAND).defer_async()

    return {'result': 'ok'}


@app.get('/api/ai/lexicon-embed')
async def ai_lexicon_embed() -> DataDict:
    await worker.configure_task(LEXICON_EMBED).defer_async()

    return {'result': 'ok'}


DIST = Path(__file__).parent / 'dist'
app.mount('/', StaticFiles(directory=DIST, html=True), name='static')
