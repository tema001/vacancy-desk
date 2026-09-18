from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles

import src.tasks as tasks
import src.utils as utils
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
    await tasks.process_feed.defer_async(category=category)

    return {'result': 'ok'}


@app.get('/enqueue-vacancies')
async def enqueue_vacancies_run_job() -> DataDict:
    await tasks.enqueue_vacancies.defer_async()

    return {'result': 'ok'}


@app.post('/api/vacancies')
async def get_vacancies(params: ParamsSchema) -> DataDict:
    return await utils.get_vacancies(params)


@app.post('/api/vacancies/score')
async def get_scored_vacancies(params: ScoringParamsSchema) -> DataDict:
    return await utils.get_scored_vacancies(params)


@app.get('/api/ai/extract')
async def ai_extract() -> DataDict:
    for vacancy_id in ('01a0a482-5b03-7370-90ea-fcb1df4261eb',):
        await tasks.extract_vacancy.configure(
            queueing_lock=f'extract:{vacancy_id}', lock=vacancy_id
        ).defer_async(vacancy_id=vacancy_id)

    return {'result': 'ok'}


@app.get('/api/ai/lexicon-expand')
async def ai_lexicon_expand() -> DataDict:
    await tasks.lexicon_expand.defer_async()

    return {'result': 'ok'}


@app.get('/api/ai/lexicon-embed')
async def ai_lexicon_embed() -> DataDict:
    await tasks.lexicon_embed.defer_async()

    return {'result': 'ok'}


DIST = Path(__file__).parent / 'dist'
app.mount('/', StaticFiles(directory=DIST, html=True), name='static')
