import src.db as db
from src.enums import JobFamily, ProfileStatus
from src.scoring import SIMILARITY_THRESHOLD, score_vacancy_matches
from src.shared.resources import resources
from src.types import DataDict, ParamsSchema, ScoringProfile


async def get_vacancies(params: ParamsSchema) -> DataDict:
    async with resources.engine.connect() as conn:
        total_count, rows = await db.select_vacancies(conn, params)

    result_rows = [{**r} for r in rows]

    return {
        'total_count': total_count,
        'has_next': len(result_rows) > params.limit,
        'rows': result_rows[: params.limit],
    }


async def get_scored_vacancies() -> DataDict | None:
    async with resources.engine.connect() as conn:
        profile_raw = await db.select_profile_for_scoring(conn)
        if not profile_raw:
            return None

        profile = ScoringProfile.from_db(profile_raw)
        rows = await db.select_vacancy_skill_matches(
            conn,
            profile,
            similarity_threshold=SIMILARITY_THRESHOLD,
        )

    print(len(rows))
    print([row for row in rows if row['similarity'] >= 0.4])
    scored_rows = score_vacancy_matches(rows)
    print(len(scored_rows))

    return {
        'profile': {
            'name': profile.name,
            'job_families': [JobFamily(item).name for item in profile.job_families]
                    if profile.job_families
                    else None
        },
        'rows': scored_rows[:30],
    }


async def get_all_profiles() -> DataDict:
    async with resources.engine.connect() as conn:
        rows = await db.select_all_profiles(conn)

    return {
        'rows': [
            {
                'id': row['id'],
                'name': row['name'],
                'job_families': (
                    [JobFamily(item).name for item in row['job_families']]
                    if row['job_families']
                    else None
                ),
                'status': row['status'].name,
                'is_selected': row['is_selected'],
                'date_created': row['date_created'],
            }
            for row in rows
        ]
    }


async def get_profile(profile_id: str) -> DataDict | None:
    async with resources.engine.connect() as conn:
        row = await db.select_profile_status(conn, profile_id)
        if not row:
            return None

        if row['status'] != ProfileStatus.ready:
            return {'id': profile_id, 'status': row['status'].name}

        skills = await db.select_profile_skills(conn, profile_id)
        row = await db.select_profile(conn, profile_id)
        if not row:
            return None

    return {
        'id': profile_id,
        'name': row['name'],
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
        'is_selected': row['is_selected'],
        'skills': [
            {
                'skill_name': skill['skill_name'],
                'depth': skill['depth'],
            }
            for skill in skills
        ],
    }
