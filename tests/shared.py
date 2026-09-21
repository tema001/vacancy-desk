from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine.result import RowMapping
from sqlalchemy.ext.asyncio.engine import AsyncConnection

from src.db import (
    insert_and_reactivate_vacancies,
    insert_skill_lexicon,
    insert_vacancy_extract,
    select_all,
)
from src.enums import JobFamily, SkillKind, Source, Status
from src.models import SkillLexicon, VacancySkill


async def prepare_vacancy(
    conn: AsyncConnection,
    *,
    external_id: str = 'test-1',
    source: Source = Source.djinni,
    category: str = 'Python',
    company: str = 'Acme',
    title: str = 'Backend',
    description: str = 'desc',
    url: str = 'https://example.com/1',
    status: Status = Status.active,
) -> str:
    vacancy_ids = await insert_and_reactivate_vacancies(
        conn,
        data={
            'source': source,
            'external_id': external_id,
            'category': category,
            'company': company,
            'title': title,
            'description': description,
            'url': url,
            'content_hash': b'\x00' * 32,
            'status': status,
        },
    )
    return vacancy_ids[0]


async def prepare_vacancy_extract(
    conn: AsyncConnection,
    vacancy_id: str,
    *,
    job_family: JobFamily = JobFamily.backend,
    prompt_version: str = 'test',
    raw_response: str = '{}',
    industry: str | None = None,
) -> None:
    await insert_vacancy_extract(
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
    await insert_skill_lexicon(conn, data={'skill_name': skill_name, 'kind': kind})


async def select_lexicon_rows(conn: AsyncConnection) -> Sequence[RowMapping]:
    return await select_all(
        conn,
        stmt=sa.select(SkillLexicon).order_by(SkillLexicon.skill_name),
    )


async def select_vacancy_skill_rows(
    conn: AsyncConnection, vacancy_id: str
) -> Sequence[RowMapping]:
    return await select_all(
        conn,
        stmt=(
            sa.select(VacancySkill)
            .where(VacancySkill.vacancy_id == vacancy_id)
            .order_by(VacancySkill.skill_name)
        ),
    )
