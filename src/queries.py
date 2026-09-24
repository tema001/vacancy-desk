import src.db as db
from src.scoring import SIMILARITY_THRESHOLD, score_vacancy_matches
from src.shared.resources import resources
from src.types import DataDict, ParamsSchema, ScoringParamsSchema


async def get_vacancies(params: ParamsSchema) -> DataDict:
    async with resources.engine.connect() as conn:
        total_count, rows = await db.select_vacancies(conn, params)

    result_rows = [{**r} for r in rows]

    return {
        'total_count': total_count,
        'has_next': len(result_rows) > params.limit,
        'rows': result_rows[: params.limit],
    }


async def get_scored_vacancies(params: ScoringParamsSchema) -> DataDict:
    async with resources.engine.connect() as conn:
        rows = await db.select_vacancy_skill_matches(
            conn,
            params,
            similarity_threshold=SIMILARITY_THRESHOLD,
        )

    print(len(rows))
    scored_rows = score_vacancy_matches(rows)
    total_count = len(scored_rows)
    page_rows = scored_rows[params.offset : params.offset + params.limit]

    return {
        'total_count': total_count,
        'has_next': params.offset + params.limit < total_count,
        'rows': page_rows,
    }
