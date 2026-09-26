from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx2
import pytest
import sqlalchemy as sa
import src.db as vacancy_db
from sqlalchemy.engine.result import RowMapping
from sqlalchemy.ext.asyncio.engine import AsyncConnection
from src.enums import EnglishLevel, JobFamily, Seniority, SkillKind, Source, Status
from src.models import (
    SkillLexicon,
    VacanciesActivity,
    Vacancy,
    VacancyExtract,
    VacancySkill,
)
from src.shared.utils import dt_now
from src.types import FullParsedPage, ParsedPage, ParseJob

_UNSET: Any = object()


def page_from_vacancy(vacancy: Mapping[str, Any]) -> FullParsedPage:
    return FullParsedPage(
        company=vacancy['company'],
        title=vacancy['title'],
        description=vacancy['description'],
        status=Status.active,
        location_str=vacancy['location_str'],
        location=vacancy['location'],
        experience=vacancy['experience'],
        salary_min=vacancy['salary_min'],
        salary_max=vacancy['salary_max'],
        salary_level=vacancy['salary_level'],
        english_level=vacancy['english_level'],
        seniority=vacancy['seniority'],
    )


def make_parse_job(
    vacancy_id: str,
    *,
    url: str = 'https://example.com/1',
    page: FullParsedPage | None = None,
    params_hash: Any = _UNSET,
    desc_hash: Any = _UNSET,
) -> ParseJob:
    if params_hash is _UNSET:
        params_hash = page.params_hash if page else None
    if desc_hash is _UNSET:
        desc_hash = page.description_hash if page else None
    return ParseJob(
        vacancy_id=vacancy_id,
        url=url,
        params_hash=params_hash,
        desc_hash=desc_hash,
    )


async def prepare_vacancy(
    conn: AsyncConnection,
    *,
    external_id: str = 'test-1',
    source: Source = Source.djinni,
    category: str = 'Python',
    company: str = '',
    title: str = 'Backend',
    description: str = '',
    url: str = 'https://example.com/1',
    status: Status = Status.new,
    params_hash: bytes | None = None,
    description_hash: bytes | None = None,
    location_str: str | None = None,
    location: list[str] | None = None,
    experience: float | None = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
    salary_level: str | None = None,
    english_level: EnglishLevel | None = None,
    seniority: Seniority | None = None,
) -> str:
    data: dict[str, Any] = {
        'source': source,
        'external_id': external_id,
        'status': status,
        'category': category,
        'title': title,
        'url': url,
        'description': description,
        'company': company,
    }
    optional = {
        'params_hash': params_hash,
        'description_hash': description_hash,
        'location_str': location_str,
        'location': location,
        'experience': experience,
        'salary_min': salary_min,
        'salary_max': salary_max,
        'salary_level': salary_level,
        'english_level': english_level,
        'seniority': seniority,
    }
    data.update({key: value for key, value in optional.items() if value is not None})
    vacancy_ids = await vacancy_db.insert_and_reactivate_vacancies(conn, data=data)
    return vacancy_ids[0]


async def prepare_activity(
    conn: AsyncConnection,
    vacancy_id: str,
    *,
    date_started: datetime | None = None,
    date_ended: datetime | None = None,
) -> None:
    await vacancy_db.insert_vacancies_activity(
        conn,
        data={
            'vacancy_id': vacancy_id,
            'date_started': date_started or dt_now(),
            'date_ended': date_ended,
        },
    )


async def prepare_vacancy_extract(
    conn: AsyncConnection,
    vacancy_id: str,
    *,
    job_family: JobFamily = JobFamily.backend,
    prompt_version: str = 'test',
    raw_response: str = '{}',
    industry: str | None = None,
) -> None:
    await vacancy_db.insert_vacancy_extract(
        conn,
        data={
            'vacancy_id': vacancy_id,
            'prompt_version': prompt_version,
            'job_family': job_family,
            'raw_response': raw_response,
            'industry': industry,
        },
    )


async def prepare_skill_lexicon(
    conn: AsyncConnection,
    skill_name: str,
    *,
    kind: SkillKind = SkillKind.hard,
) -> None:
    await vacancy_db.insert_skill_lexicon(
        conn, data={'skill_name': skill_name, 'kind': kind}
    )


async def select_lexicon_rows(conn: AsyncConnection) -> Sequence[RowMapping]:
    return await vacancy_db.select_all(
        conn,
        stmt=sa.select(SkillLexicon).order_by(SkillLexicon.skill_name),
    )


async def select_vacancy_skill_rows(
    conn: AsyncConnection, vacancy_id: str
) -> Sequence[RowMapping]:
    return await vacancy_db.select_all(
        conn,
        stmt=(
            sa.select(VacancySkill)
            .where(VacancySkill.vacancy_id == vacancy_id)
            .order_by(VacancySkill.skill_name)
        ),
    )


async def select_vacancy_row(conn: AsyncConnection, vacancy_id: str) -> RowMapping | None:
    return await vacancy_db.select_one(
        conn, stmt=sa.select(Vacancy).where(Vacancy.id == vacancy_id)
    )


async def select_activity_rows(
    conn: AsyncConnection, vacancy_id: str
) -> Sequence[RowMapping]:
    return await vacancy_db.select_all(
        conn,
        stmt=(
            sa.select(VacanciesActivity)
            .where(VacanciesActivity.vacancy_id == vacancy_id)
            .order_by(VacanciesActivity.date_started)
        ),
    )


async def select_extract_row(conn: AsyncConnection, vacancy_id: str) -> RowMapping | None:
    return await vacancy_db.select_one(
        conn,
        stmt=sa.select(VacancyExtract).where(VacancyExtract.vacancy_id == vacancy_id),
    )


class ParseMock:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.extract = MagicMock()
        self.extract.configure.return_value.defer_async = AsyncMock()
        monkeypatch.setattr('src.tasks.extract_vacancy', self.extract)
        monkeypatch.setattr('src.utils.fetch_vacancy_body', self._empty_fetch)
        self._monkeypatch = monkeypatch

    @staticmethod
    async def _empty_fetch(url: str) -> str:
        return ''

    def set_page(self, page: ParsedPage) -> None:
        async def fake_parse(body: str) -> ParsedPage:
            return page

        self._monkeypatch.setattr('src.utils.parse_vacancy_page', fake_parse)

    def set_not_found(self) -> None:
        async def fake_fetch(url: str) -> str:
            request = httpx2.Request('GET', url)
            response = httpx2.Response(404, request=request)
            raise httpx2.HTTPStatusError('Not Found', request=request, response=response)

        self._monkeypatch.setattr('src.utils.fetch_vacancy_body', fake_fetch)

    @property
    def extracted_ids(self) -> list[str]:
        defer = self.extract.configure.return_value.defer_async
        return [call.kwargs['vacancy_id'] for call in defer.await_args_list]
