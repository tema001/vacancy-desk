import re

import src.db as db
from src.enums import JobFamily, ProfileStatus
from src.scoring import SIMILARITY_THRESHOLD, rank_bm25, rank_vacancy_matches, rrf
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
            profile=profile,
            similarity_threshold=SIMILARITY_THRESHOLD,
        )
        p25 = await db.select_total_importance_percentile(
            conn, percentile=0.25, profile=profile
        )

        scored_rows = rank_vacancy_matches(rows, p25)[:30]
        vacancies = await db.select_vacancies_by_ids(
            conn, ids=[r[0] for r in scored_rows]
        )

    vacancies_map = {v['id']: v for v in vacancies}
    final_rows = [{**vacancies_map[row[0]], 'score': row[1]} for row in scored_rows]

    return {
        'total_count': len(scored_rows),
        'profile': profile.to_api(),
        'rows': final_rows,
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


async def get_search_response(query: str) -> DataDict:
    _query = query.strip()
    keywords = set(re.findall(db.TOKEN_RE, _query.lower()))

    model = resources.config['llm']['embedding_model']
    resp = await resources.llm.embeddings.create(
        name='chunk-embed',
        model=model,
        input=_query,
        dimensions=1536,
    )
    embed_query = resp.data[0].embedding

    async with resources.engine.connect() as conn:
        bm_rows = await db.select_vacancies_for_bm25(conn, keywords)
        if bm_rows:
            f = bm_rows[0]
            bm25_rank = rank_bm25(
                keywords, bm_rows, N=int(f['total_count']), avg_dl=float(f['avg_length'])
            )
            assert len(bm_rows) == len(bm25_rank)
        else:
            bm25_rank = []

        cosine_rows = await db.select_vacancy_similarities(conn, embed_query)
        cosine_rank = [(row['vacancy_id'], row['similarity']) for row in cosine_rows]

        rrf_rank = rrf(bm25_rank, cosine_rank)
        print('rrf_rank', rrf_rank)
        ranked_ids = [r[0] for r in rrf_rank[:30]]

        vacancies = await db.select_vacancies_by_ids(conn, ranked_ids)

    vacancies_map = {v['id']: {**v} for v in vacancies}
    final_rows = [vacancies_map[id_] for id_ in ranked_ids]

    return {
        'total_count': len(final_rows),
        'rows': final_rows,
    }
