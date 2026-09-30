import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.staticfiles import StaticFiles
from pydantic import AfterValidator

import src.db as db
import src.queries as queries
from src.jobs import (
    ENQUEUE_VACANCIES,
    EXTRACT_PROFILE,
    EXTRACT_VACANCY,
    LEXICON_EMBED,
    LEXICON_EXPAND,
    PROCESS_FEED,
)
from src.services.worker import app as worker
from src.shared.resources import resources
from src.shared.types import uuid_schema
from src.types import DataDict, ParamsSchema, ProfileCreateSchema, ScoringParamsSchema


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


@app.post('/api/profiles', status_code=status.HTTP_202_ACCEPTED)
async def create_new_profile(body: ProfileCreateSchema) -> DataDict:
    name = body.name or f'Noname-{secrets.token_hex(3)}'

    async with resources.engine.begin() as conn:
        pending_id = await db.select_pending_profile_id(conn)
        if pending_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={'profile_id': pending_id},
            )

        profile_id = await db.insert_new_profile(
            conn, data={'text': body.text, 'name': name}
        )

    await worker.configure_task(
        EXTRACT_PROFILE,
        queueing_lock=f'profile-extract:{profile_id}',
        lock=profile_id,
    ).defer_async(profile_id=profile_id)

    return {'id': profile_id}


@app.get('/api/profiles/{profile_id}')
async def get_profile(
    profile_id: Annotated[str, AfterValidator(uuid_schema)],
) -> DataDict:
    profile = await queries.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return profile


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
