from collections.abc import Sequence
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine.result import RowMapping
from sqlalchemy.ext.asyncio.engine import AsyncConnection
from sqlalchemy.sql import Executable, asc, desc, func

from src.models import (
    SkillLexicon,
    Status,
    VacanciesActivity,
    Vacancy,
    VacancyExtract,
    VacancySkill,
)
from src.types import DataDict, ParamsSchema, ScoringParamsSchema


async def select_all(conn: AsyncConnection, stmt: Executable) -> Sequence[RowMapping]:
    return (await conn.execute(stmt)).mappings().all()


async def select_one(conn: AsyncConnection, stmt: Executable) -> RowMapping | None:
    return (await conn.execute(stmt)).mappings().one_or_none()


async def insert_and_reactivate_vacancies(
    conn: AsyncConnection, data: DataDict | list[DataDict]
) -> list[str]:
    rows = await select_all(
        conn,
        stmt=(
            insert(Vacancy)
            .values(data)
            .on_conflict_do_update(
                index_elements=[Vacancy.source, Vacancy.external_id],
                set_={'status': Status.new, 'date_last_seen': None},
                where=(Vacancy.status == Status.inactive),
            )
            .returning(Vacancy.id)
        ),
    )

    return [row['id'] for row in rows]


async def insert_vacancies_activity(
    conn: AsyncConnection, data: DataDict | list[DataDict]
) -> None:
    stmt = (
        insert(VacanciesActivity)
        .values(data)
        .on_conflict_do_nothing(
            index_elements=['vacancy_id'], index_where=sa.text('date_ended IS NULL')
        )
    )
    await conn.execute(stmt)


async def update_vacancy(conn: AsyncConnection, vacancy_id: str, data: DataDict) -> None:
    stmt = sa.update(Vacancy).values(data).where(Vacancy.id == vacancy_id)
    await conn.execute(stmt)


async def close_vacancies_activity(
    conn: AsyncConnection, vacancy_id: str, date_ended: datetime
) -> None:
    await conn.execute(
        statement=(
            sa.update(VacanciesActivity)
            .values(date_ended=date_ended)
            .where(
                VacanciesActivity.vacancy_id == vacancy_id,
                VacanciesActivity.date_ended.is_(None),
            )
        )
    )


async def select_vacancy_by_id(
    conn: AsyncConnection, vacancy_id: str
) -> RowMapping | None:
    return await select_one(
        conn,
        stmt=(
            sa.select(
                Vacancy.title, Vacancy.category, Vacancy.experience, Vacancy.description
            ).where(Vacancy.id == vacancy_id)
        ),
    )


async def select_vacancy_extract_info(
    conn: AsyncConnection, vacancy_id: str
) -> RowMapping | None:
    return await select_one(
        conn,
        stmt=(
            sa.select(
                VacancyExtract.prompt_version,
                sa.func.count(VacancySkill.id).label('skill_count'),
            )
            .select_from(
                VacancyExtract.__table__.join(
                    VacancySkill,
                    VacancyExtract.vacancy_id == VacancySkill.vacancy_id,
                    isouter=True,
                )
            )
            .where(VacancyExtract.vacancy_id == vacancy_id)
            .group_by(VacancyExtract.prompt_version)
        ),
    )


async def select_vacancy_extract_response(
    conn: AsyncConnection, vacancy_id: str
) -> str | None:
    row = await select_one(
        conn,
        stmt=(
            sa.select(VacancyExtract.raw_response).where(
                VacancyExtract.vacancy_id == vacancy_id
            )
        ),
    )

    return row['raw_response'] if row else None


async def select_vacancies_to_process(
    conn: AsyncConnection, time_from: timedelta, status: Status | None
) -> Sequence[RowMapping]:
    busy = sa.exists(
        sa.text(
            """
            FROM procrastinate_jobs
            WHERE queueing_lock = vacancies.id::text
              AND status IN (
                  'todo'::procrastinate_job_status,
                  'doing'::procrastinate_job_status
              )
            """
        )
    )

    if status:
        status_stmt = Vacancy.status == status
    else:
        status_stmt = Vacancy.status.in_((Status.new, Status.active))

    stmt = (
        sa.select(Vacancy.id, Vacancy.url, Vacancy.content_hash)
        .where(
            sa.or_(
                Vacancy.date_last_seen.is_(None),
                Vacancy.date_last_seen < func.now() - time_from,
            ),
            status_stmt,
            ~busy,
        )
        .order_by(Vacancy.date_last_seen)
        # .limit(1)
    )

    return await select_all(conn, stmt)


async def select_vacancies(
    conn: AsyncConnection, params: ParamsSchema
) -> tuple[int, Sequence[RowMapping]]:
    _order = desc if params.order == 2 else asc

    filters = []
    if params.categories:
        filters.append(Vacancy.category.in_(params.categories))

    if params.exp:
        filters.append(Vacancy.experience <= params.exp * 12.0)

    if params.salary_min:
        filters.append(
            sa.or_(
                Vacancy.salary_min >= params.salary_min, Vacancy.salary_level.isnot(None)
            )
        )

    if params.eng_lvl:
        filters.append(Vacancy.english_level <= params.eng_lvl)

    if params.active_only:
        _from = Vacancy.__table__.join(
            VacanciesActivity,
            sa.and_(
                Vacancy.id == VacanciesActivity.vacancy_id,
                VacanciesActivity.date_ended.is_(None),
            ),
        )
        c_date_started = VacanciesActivity.date_started
    else:
        lat = (
            sa.select(VacanciesActivity.date_started)
            .where(Vacancy.id == VacanciesActivity.vacancy_id)
            .order_by(_order(VacanciesActivity.date_started))
            .limit(1)
            .lateral()
        )
        _from = Vacancy.__table__.join(lat, sa.true())
        c_date_started = lat.c.date_started

    total_count = await conn.scalar(
        sa.select(func.count()).select_from(_from).where(*filters)
    )

    if not total_count:
        return 0, []

    stmt = (
        sa.select(
            Vacancy.id,
            Vacancy.source,
            Vacancy.category,
            Vacancy.company,
            Vacancy.title,
            Vacancy.url,
            Vacancy.location_str,
            Vacancy.salary_min,
            Vacancy.salary_max,
            Vacancy.salary_level,
            Vacancy.experience,
            Vacancy.status,
            c_date_started,
            # func.count().over().label('count'),
        )
        .select_from(_from)
        .where(*filters)
        .order_by(_order(c_date_started))
        .offset(params.offset)
        .limit(params.limit + 1)
    )

    return total_count, await select_all(conn, stmt)


async def select_vacancy_skill_matches(
    conn: AsyncConnection,
    params: ScoringParamsSchema,
    similarity_threshold: float,
) -> Sequence[RowMapping]:

    _from = Vacancy.__table__
    filters = [Vacancy.status == Status.active]
    if params.exp:
        filters.append(
            sa.or_(
                Vacancy.experience.is_(None),
                Vacancy.experience <= params.exp * 12.0,
            )
        )
    if params.english_level:
        filters.append(
            sa.or_(
                Vacancy.english_level.is_(None),
                Vacancy.english_level <= params.english_level,
            )
        )
    if params.salary_min:
        filters.append(
            sa.or_(
                Vacancy.salary_min >= params.salary_min, Vacancy.salary_level.isnot(None)
            )
        )

    if params.job_family:
        filters.append(VacancyExtract.job_family == params.job_family)
        _from = _from.join(VacancyExtract, VacancyExtract.vacancy_id == Vacancy.id)

    filtered_vacancies = (
        sa.select(Vacancy.id).select_from(_from).where(*filters).cte('filtered_vacancies')
    )
    required_skill_names = (
        sa.select(VacancySkill.skill_name)
        .select_from(filtered_vacancies)
        .join(VacancySkill, VacancySkill.vacancy_id == filtered_vacancies.c.id)
        .distinct()
        .cte('required_skill_names')
    )
    required_skills = (
        sa.select(
            required_skill_names.c.skill_name,
            SkillLexicon.expanded_vector,
        )
        .select_from(required_skill_names)
        .join(
            SkillLexicon,
            SkillLexicon.skill_name == required_skill_names.c.skill_name,
        )
        .cte('required_skills')
    )

    user_skills = (
        sa.values(
            sa.column('skill_name', sa.Text),
            sa.column('depth', sa.SmallInteger),
            name='user_skills',
        )
        .data([(skill.skill_name, int(skill.depth)) for skill in params.skills])
        .cte('user_skills')
    )
    user_vectors = (
        sa.select(
            user_skills.c.skill_name.label('user_skill_name'),
            user_skills.c.depth.label('user_depth'),
            SkillLexicon.expanded_vector.label('user_vector'),
        )
        .select_from(user_skills)
        .join(SkillLexicon, SkillLexicon.skill_name == user_skills.c.skill_name)
        .cte('user_vectors')
    )

    similarity = sa.case(
        (
            required_skills.c.skill_name == user_vectors.c.user_skill_name,
            1.0,
        ),
        else_=(
            1.0
            - required_skills.c.expanded_vector.cosine_distance(
                user_vectors.c.user_vector
            )
        ),
    )
    best_match = (
        sa.select(
            user_vectors.c.user_skill_name,
            user_vectors.c.user_depth,
            similarity.label('similarity'),
        )
        .order_by(similarity.desc().nulls_last())
        .limit(1)
        .lateral('best_skill_match')
    )
    skill_matches = (
        sa.select(
            required_skills.c.skill_name,
            best_match.c.user_skill_name,
            best_match.c.user_depth,
            best_match.c.similarity,
        )
        .select_from(required_skills)
        .join(best_match, sa.true())
        .where(best_match.c.similarity >= similarity_threshold)
        .cte('skill_matches')
    )

    skill_totals = (
        sa.select(
            VacancySkill.vacancy_id,
            func.sum(VacancySkill.importance).label('total_importance'),
        )
        .select_from(filtered_vacancies)
        .join(VacancySkill, VacancySkill.vacancy_id == filtered_vacancies.c.id)
        .group_by(VacancySkill.vacancy_id)
        .cte('skill_totals')
    )

    stmt = (
        sa.select(
            Vacancy.id,
            Vacancy.source,
            Vacancy.category,
            Vacancy.company,
            Vacancy.title,
            Vacancy.url,
            Vacancy.location_str,
            Vacancy.salary_min,
            Vacancy.salary_max,
            Vacancy.salary_level,
            Vacancy.experience,
            Vacancy.status,
            VacancySkill.depth.label('required_depth'),
            VacancySkill.importance,
            skill_totals.c.total_importance,
            # skill_matches.c.user_skill_name,
            skill_matches.c.user_depth,
            skill_matches.c.similarity,
        )
        .select_from(filtered_vacancies)
        .join(Vacancy, Vacancy.id == filtered_vacancies.c.id)
        .join(VacancySkill, VacancySkill.vacancy_id == Vacancy.id)
        .join(skill_matches, skill_matches.c.skill_name == VacancySkill.skill_name)
        .join(skill_totals, skill_totals.c.vacancy_id == Vacancy.id)
    )

    return await select_all(conn, stmt)


async def insert_vacancy_extract(conn: AsyncConnection, data: DataDict) -> None:
    await conn.execute(statement=(insert(VacancyExtract).values(data)))


async def delete_vacancy_extract(conn: AsyncConnection, vacancy_id: str) -> None:
    """
    Also removes all vacancy skills.
    vacancy_skills.vacancy_id -> vacancy_extract.vacancy_id
    """
    await conn.execute(
        statement=(
            sa.delete(VacancyExtract).where(VacancyExtract.vacancy_id == vacancy_id)
        )
    )


async def select_skill_lexicon_matches(
    conn: AsyncConnection, data: Sequence[str]
) -> Sequence[RowMapping]:
    q = (
        sa.values(sa.column('s_norm', sa.Text), name='q')
        .data([(name,) for name in data])
        .cte('q')
    )

    sl_n = SkillLexicon.skill_name_norm

    same_stems = func.to_tsvector('english', sl_n) == func.to_tsvector(
        'english', q.c.s_norm
    )
    trgm_similar = func.similarity(sl_n, q.c.s_norm)
    len_abs = func.abs(func.length(sl_n) - func.length(q.c.s_norm))

    lat = (
        sa.select(
            SkillLexicon.skill_name,
            trgm_similar.label('trgm_similar'),
        )
        .select_from(SkillLexicon)
        .where(
            sa.or_(
                sa.and_(same_stems, trgm_similar >= 0.75),
                sa.and_(len_abs <= 4, trgm_similar >= 0.61),
            )
        )
        .order_by(same_stems.desc(), trgm_similar.desc())
        .limit(1)
        .lateral()
    )

    return await select_all(
        conn,
        stmt=(
            sa.select(q.c.s_norm, lat.c.skill_name, lat.c.trgm_similar)
            .select_from(q)
            .join(lat, sa.true())
        ),
    )


async def select_new_skill_lexicon(
    conn: AsyncConnection, data: Sequence[str]
) -> list[str]:
    q = (
        sa.values(sa.column('skill_name', sa.Text), name='q')
        .data([(name,) for name in data])
        .cte('q')
    )
    rows = await select_all(
        conn,
        stmt=(
            sa.select(q.c.skill_name).where(
                ~sa.exists().where(SkillLexicon.skill_name == q.c.skill_name)
            )
        ),
    )

    if not rows:
        return []

    return [row['skill_name'] for row in rows]


async def insert_skill_lexicon(
    conn: AsyncConnection, data: DataDict | list[DataDict]
) -> None:
    await conn.execute(
        statement=(
            insert(SkillLexicon)
            .values(data)
            # several workers can insert the same skill at the same time
            .on_conflict_do_nothing(index_elements=['skill_name'])
        ),
    )


async def select_skill_lexicon_for_expand(conn: AsyncConnection, limit: int) -> list[str]:
    rows = await select_all(
        conn,
        stmt=(
            sa.select(SkillLexicon.skill_name)
            .where(SkillLexicon.expanded.is_(None))
            .limit(limit + 1)
            .order_by(SkillLexicon.skill_name)
        ),
    )
    return [row['skill_name'] for row in rows]


async def update_skill_lexicon_expand(
    conn: AsyncConnection, data: DataDict | list[DataDict]
) -> None:
    stmt = (
        sa.update(SkillLexicon)
        .where(
            SkillLexicon.skill_name == sa.bindparam('b_skill_name'),
            SkillLexicon.expanded.is_(None),
        )
        .values(expanded=sa.bindparam('b_expanded'))
    )
    b_data = [
        {'b_skill_name': d['skill_name'], 'b_expanded': d['expanded']} for d in data
    ]

    await conn.execute(stmt, b_data)


async def select_skill_lexicon_for_embed(
    conn: AsyncConnection, limit: int
) -> Sequence[RowMapping]:
    return await select_all(
        conn,
        stmt=(
            sa.select(SkillLexicon.skill_name, SkillLexicon.expanded)
            .where(
                SkillLexicon.expanded.isnot(None),
                SkillLexicon.expanded != '',
                SkillLexicon.expanded_vector.is_(None),
            )
            .limit(limit + 1)
            .order_by(SkillLexicon.skill_name)
        ),
    )


async def update_skill_lexicon_embed(
    conn: AsyncConnection, data: DataDict | list[DataDict]
) -> None:
    stmt = (
        sa.update(SkillLexicon)
        .where(
            SkillLexicon.skill_name == sa.bindparam('b_skill_name'),
            SkillLexicon.expanded_vector.is_(None),
        )
        .values(
            expanded_vector=sa.bindparam('b_expanded_vector'),
            embedding_model=sa.bindparam('b_embedding_model'),
        )
    )
    b_data = [
        {
            'b_skill_name': d['skill_name'],
            'b_expanded_vector': d['expanded_vector'],
            'b_embedding_model': d['embedding_model'],
        }
        for d in data
    ]

    await conn.execute(stmt, b_data)


async def insert_vacancy_skills(
    conn: AsyncConnection, data: DataDict | list[DataDict]
) -> None:
    await conn.execute(insert(VacancySkill).values(data))
