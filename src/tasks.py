import random
from datetime import timedelta

from procrastinate import RetryStrategy, exceptions

from src import db, utils
from src.enums import Status
from src.jobs import (
    ENQUEUE_VACANCIES,
    EXTRACT_VACANCY,
    LEXICON_EMBED,
    LEXICON_EXPAND,
    PARSE_VACANCY,
    PROCESS_FEED,
)
from src.services.worker import app
from src.shared.resources import resources
from src.types import ParseJob


@app.task(name=PROCESS_FEED, retry=RetryStrategy(max_attempts=2, wait=60))
async def process_feed(*, category: str) -> None:
    await utils.process_feed(category)


@app.task(name=PARSE_VACANCY, retry=RetryStrategy(max_attempts=2, wait=60))
async def parse_vacancy(*, vacancy_id: str) -> None:
    async with resources.engine.connect() as conn:
        row = await db.select_vacancy_for_parse(conn, vacancy_id)

    if not row:
        print(f'No vacancy! vacancy_id: {vacancy_id}')
        return

    await utils.process_vacancy_page(ParseJob.from_db(row))


@app.task(name=EXTRACT_VACANCY, retry=RetryStrategy(max_attempts=2, wait=30))
async def extract_vacancy(*, vacancy_id: str) -> None:
    await utils.process_vacancy_extract(vacancy_id)


@app.task(
    name=LEXICON_EXPAND,
    queueing_lock='lexicon_expand',
    lock='lexicon_expand',
    retry=RetryStrategy(max_attempts=2, wait=30),
)
async def lexicon_expand() -> None:
    await utils.process_lexicon_expanding()


@app.task(
    name=LEXICON_EMBED,
    queueing_lock='lexicon_embed',
    lock='lexicon_embed',
    retry=RetryStrategy(max_attempts=2, wait=30),
)
async def lexicon_embed() -> None:
    await utils.process_lexicon_embedding()


@app.task(name=ENQUEUE_VACANCIES, queueing_lock='enqueue_vacancies')
async def enqueue_vacancies(status: Status | None = None) -> None:
    async with resources.engine.connect() as conn:
        rows = await db.select_vacancies_to_process(
            conn, time_from=timedelta(hours=4), status=status
        )

    for i, row in enumerate(rows):
        try:
            lock_id = row['id']
            schedule_sec = (i * 8) + random.uniform(0.5, 5.0)  # noqa: S311

            await parse_vacancy.configure(
                queueing_lock=f'parse:{lock_id}',
                lock=lock_id,
                schedule_in={'milliseconds': int(schedule_sec * 1000)},
            ).defer_async(vacancy_id=row['id'])
        except exceptions.AlreadyEnqueued:
            pass
