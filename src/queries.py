import src.db as db
from src.enums import JobFamily, ProfileStatus
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


async def get_profile(profile_id: str) -> DataDict | None:
    async with resources.engine.connect() as conn:
        row = await db.select_profile(conn, profile_id)
        if not row:
            return None

        if row['status'] != ProfileStatus.ready:
            return {'id': profile_id, 'status': row['status'].name}

        skills = await db.select_profile_skills(conn, profile_id)

    return {
        'id': row['id'],
        'text': row['text'],
        'job_families': (
            [JobFamily(item).name for item in row['job_families']]
            if row['job_families']
            else None
        ),
        'experience': row['experience'],
        'english_level': row['english_level'],
        'seniority': row['seniority'].name if row['seniority'] else None,
        'status': row['status'].name,
        'skills': [
            {
                'skill_name': skill['skill_name'],
                'depth': skill['depth'],
            }
            for skill in skills
        ],
    }
