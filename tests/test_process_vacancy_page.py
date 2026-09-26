from dataclasses import replace
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio.engine import AsyncConnection
from src.enums import EnglishLevel, Seniority, Status
from src.shared.resources import resources
from src.shared.utils import dt_now
from src.types import FullParsedPage, InactivePage
from src.utils import process_vacancy_page

from tests.shared import (
    ParseMock,
    make_parse_job,
    page_from_vacancy,
    prepare_activity,
    prepare_vacancy,
    prepare_vacancy_extract,
    select_activity_rows,
    select_extract_row,
    select_vacancy_row,
)

PARSED_DATA: dict[str, Any] = {
    'status': Status.active,
    'company': 'Acme',
    'description': 'desc',
    'location_str': 'Europe, Ukraine, Kyiv',
    'location': ['kyiv'],
    'experience': 24.0,
    'salary_min': 3000,
    'salary_max': 5000,
    'english_level': EnglishLevel.B2,
    'seniority': Seniority.middle,
}


async def _prepare_parsed_vacancy(
    conn: AsyncConnection, **overrides: Any
) -> tuple[str, FullParsedPage]:
    data = PARSED_DATA.copy()
    if overrides:
        data.update(overrides)

    vacancy_id = await prepare_vacancy(conn, **data)
    vacancy = await select_vacancy_row(conn, vacancy_id)
    assert vacancy
    return vacancy_id, page_from_vacancy(vacancy)


async def test_new_vacancy_opens_activity_and_extracts(db, parse_mock: ParseMock) -> None:
    async with resources.engine.begin() as conn:
        vacancy_id = await prepare_vacancy(conn)
        vacancy = await select_vacancy_row(conn, vacancy_id)
    assert vacancy

    page = page_from_vacancy(vacancy)
    parse_mock.set_page(page)
    await process_vacancy_page(make_parse_job(vacancy_id))

    async with resources.engine.connect() as conn:
        vacancy = await select_vacancy_row(conn, vacancy_id)
        activities = await select_activity_rows(conn, vacancy_id)

    assert vacancy
    assert vacancy['status'] == Status.active
    assert vacancy['company'] == page.company
    assert vacancy['description'] == page.description
    assert vacancy['params_hash'] == page.params_hash
    assert vacancy['description_hash'] == page.description_hash
    assert vacancy['salary_min'] == page.salary_min
    assert len(activities) == 1
    assert activities[0]['date_ended'] is None
    assert parse_mock.extracted_ids == [vacancy_id]


async def test_unchanged_content_only_updates_last_seen(
    db, parse_mock: ParseMock
) -> None:
    async with resources.engine.begin() as conn:
        vacancy_id, page = await _prepare_parsed_vacancy(conn)
        await prepare_activity(conn, vacancy_id)
        await prepare_vacancy_extract(conn, vacancy_id)

    parse_mock.set_page(page)
    await process_vacancy_page(make_parse_job(vacancy_id, page=page))

    async with resources.engine.connect() as conn:
        vacancy = await select_vacancy_row(conn, vacancy_id)
        activities = await select_activity_rows(conn, vacancy_id)
        extract = await select_extract_row(conn, vacancy_id)

    assert vacancy
    assert vacancy['date_last_seen']
    assert len(activities) == 1
    assert activities[0]['date_ended'] is None
    assert extract
    assert parse_mock.extracted_ids == []


async def test_params_change_vacancy_without_extract(db, parse_mock: ParseMock) -> None:
    async with resources.engine.begin() as conn:
        vacancy_id, page = await _prepare_parsed_vacancy(conn)
        await prepare_activity(conn, vacancy_id)
        await prepare_vacancy_extract(conn, vacancy_id)

    changed = replace(page, salary_min=4000, title='Backend / Python')
    parse_mock.set_page(changed)
    await process_vacancy_page(make_parse_job(vacancy_id, page=page))

    async with resources.engine.connect() as conn:
        vacancy = await select_vacancy_row(conn, vacancy_id)
        activities = await select_activity_rows(conn, vacancy_id)
        extract = await select_extract_row(conn, vacancy_id)

    assert vacancy
    assert vacancy['title'] == changed.title
    assert vacancy['salary_min'] == changed.salary_min
    assert vacancy['params_hash'] == changed.params_hash
    assert vacancy['description_hash'] == page.description_hash
    assert len(activities) == 1
    assert activities[0]['date_ended'] is None
    assert extract
    assert parse_mock.extracted_ids == []


async def test_description_change_replaces_extract(db, parse_mock: ParseMock) -> None:
    async with resources.engine.begin() as conn:
        vacancy_id, page = await _prepare_parsed_vacancy(conn)
        await prepare_activity(conn, vacancy_id)
        await prepare_vacancy_extract(conn, vacancy_id)

    changed = replace(page, description='new desc')
    parse_mock.set_page(changed)
    await process_vacancy_page(make_parse_job(vacancy_id, page=page))

    async with resources.engine.connect() as conn:
        vacancy = await select_vacancy_row(conn, vacancy_id)
        activities = await select_activity_rows(conn, vacancy_id)
        extract = await select_extract_row(conn, vacancy_id)

    assert vacancy
    assert vacancy['description'] == changed.description
    assert vacancy['params_hash'] == page.params_hash
    assert vacancy['description_hash'] == changed.description_hash
    assert len(activities) == 1
    assert activities[0]['date_ended'] is None
    assert extract is None
    assert parse_mock.extracted_ids == [vacancy_id]


async def test_inactive_page_clears_params_hash_and_closes_activity(
    db, parse_mock: ParseMock
) -> None:
    async with resources.engine.begin() as conn:
        vacancy_id, page = await _prepare_parsed_vacancy(conn)
        await prepare_activity(conn, vacancy_id)
        await prepare_vacancy_extract(conn, vacancy_id)

    parse_mock.set_page(InactivePage())
    await process_vacancy_page(make_parse_job(vacancy_id, page=page))

    async with resources.engine.connect() as conn:
        vacancy = await select_vacancy_row(conn, vacancy_id)
        activities = await select_activity_rows(conn, vacancy_id)
        extract = await select_extract_row(conn, vacancy_id)

    assert vacancy
    assert vacancy['status'] == Status.inactive
    assert vacancy['params_hash'] is None
    assert len(activities) == 1
    assert activities[0]['date_ended']
    assert extract
    assert parse_mock.extracted_ids == []


async def test_not_found_clears_params_hash_and_closes_activity(
    db, parse_mock: ParseMock
) -> None:
    async with resources.engine.begin() as conn:
        vacancy_id, page = await _prepare_parsed_vacancy(conn)
        await prepare_activity(conn, vacancy_id)

    parse_mock.set_not_found()
    await process_vacancy_page(make_parse_job(vacancy_id, page=page))

    async with resources.engine.connect() as conn:
        vacancy = await select_vacancy_row(conn, vacancy_id)
        activities = await select_activity_rows(conn, vacancy_id)

    assert vacancy
    assert vacancy['status'] == Status.inactive
    assert vacancy['params_hash'] is None
    assert len(activities) == 1
    assert activities[0]['date_ended']
    assert parse_mock.extracted_ids == []


async def test_reactivated_same_description_opens_activity_without_extract(
    db, parse_mock: ParseMock
) -> None:
    async with resources.engine.begin() as conn:
        vacancy_id, page = await _prepare_parsed_vacancy(conn, status=Status.new)
        ended_at = dt_now() - timedelta(days=1)
        await prepare_activity(
            conn, vacancy_id, date_started=ended_at, date_ended=ended_at
        )
        await prepare_vacancy_extract(conn, vacancy_id)

    parse_mock.set_page(page)
    await process_vacancy_page(make_parse_job(vacancy_id, page=page, params_hash=None))

    async with resources.engine.connect() as conn:
        vacancy = await select_vacancy_row(conn, vacancy_id)
        activities = await select_activity_rows(conn, vacancy_id)
        extract = await select_extract_row(conn, vacancy_id)

    assert vacancy
    assert vacancy['status'] == Status.active
    assert vacancy['params_hash'] == page.params_hash
    assert vacancy['description_hash'] == page.description_hash
    assert len(activities) == 2
    assert activities[0]['date_ended']
    assert activities[1]['date_ended'] is None
    assert extract
    assert parse_mock.extracted_ids == []


async def test_reactivated_new_description_opens_activity_and_replaces_extract(
    db, parse_mock: ParseMock
) -> None:
    async with resources.engine.begin() as conn:
        vacancy_id, page = await _prepare_parsed_vacancy(conn, status=Status.new)
        ended_at = dt_now() - timedelta(days=1)
        await prepare_activity(
            conn, vacancy_id, date_started=ended_at, date_ended=ended_at
        )
        await prepare_vacancy_extract(conn, vacancy_id)

    changed = replace(page, description='new desc')
    parse_mock.set_page(changed)
    await process_vacancy_page(make_parse_job(vacancy_id, page=page, params_hash=None))

    async with resources.engine.connect() as conn:
        vacancy = await select_vacancy_row(conn, vacancy_id)
        activities = await select_activity_rows(conn, vacancy_id)
        extract = await select_extract_row(conn, vacancy_id)

    assert vacancy
    assert vacancy['status'] == Status.active
    assert vacancy['params_hash'] == changed.params_hash
    assert vacancy['description_hash'] == changed.description_hash
    assert len(activities) == 2
    assert activities[0]['date_ended']
    assert activities[1]['date_ended'] is None
    assert extract is None
    assert parse_mock.extracted_ids == [vacancy_id]
