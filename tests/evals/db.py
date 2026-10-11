from collections.abc import Iterable, Sequence
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine.result import RowMapping
from sqlalchemy.ext.asyncio.engine import AsyncConnection
from sqlalchemy.sql import func
from src.db import TOKEN_RE, select_all
from src.models import Vacancy, VacancyChunk


async def select_vacancies_for_bm25_eval(
    conn: AsyncConnection,
    keywords: Iterable[str],
    date_from: datetime,
    date_to: datetime,
) -> Sequence[RowMapping]:
    """
    Copy of src.db.select_vacancies_for_bm25
    """
    match = func.regexp_matches(
        Vacancy.title + ' ' + Vacancy.description, TOKEN_RE, 'gi', type_=ARRAY(sa.Text)
    ).column_valued('m')

    tokenized = (
        sa.select(
            Vacancy.id,
            func.array(
                sa.select(func.lower(match[1])).correlate(Vacancy).scalar_subquery(),
                type_=ARRAY(sa.Text),
            ).label('tokens'),
        )
        .where(
            Vacancy.date_created >= date_from,
            Vacancy.date_created < date_to,
        )
        .cte('tokenized')
    )
    all_info = sa.select(
        tokenized.c.id,
        tokenized.c.tokens,
        func.count().over().label('total_count'),
        func.avg(func.coalesce(func.array_length(tokenized.c.tokens, 1), 0))
        .over()
        .label('avg_length'),
    ).cte('all_info')

    return await select_all(
        conn, stmt=sa.select(all_info).where(all_info.c.tokens.overlap(keywords))
    )


async def select_vacancy_for_similarities_eval(
    conn: AsyncConnection,
    embed_query: Iterable[float],
    date_from: datetime,
    date_to: datetime,
) -> Sequence[RowMapping]:
    """
    Copy of src.db.select_vacancy_similarities
    """
    similarity = 1 - VacancyChunk.embedding.cosine_distance(embed_query)
    cos_sim = (
        sa.select(VacancyChunk.vacancy_id, similarity.label('similarity'))
        .join(Vacancy, Vacancy.id == VacancyChunk.vacancy_id)
        .where(
            Vacancy.date_created >= date_from,
            Vacancy.date_created < date_to,
        )
        .cte('cos_sim')
    )

    max_similarity = func.max(cos_sim.c.similarity).label('similarity')

    return await select_all(
        conn,
        stmt=(
            sa.select(cos_sim.c.vacancy_id, max_similarity)
            .group_by(cos_sim.c.vacancy_id)
            .order_by(max_similarity.desc())
            .limit(50)
        ),
    )
