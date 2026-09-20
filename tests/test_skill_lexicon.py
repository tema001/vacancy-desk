import sqlalchemy as sa
from src.db import select_all, select_one
from src.enums import JobFamily, SkillDepth, SkillKind
from src.models import SkillLexicon, VacancySkill
from src.shared.resources import resources
from src.types import ExtractedSkill, VacancyLLMExtract
from src.utils import _add_vacancy_skill_and_lexicon

from tests.prepare import prepare_skill_lexicon, prepare_vacancy, prepare_vacancy_extract


def _skill(canonical: str, *, importance: float = 1.0) -> ExtractedSkill:
    return ExtractedSkill(
        canonical=canonical,
        importance=importance,
        depth=SkillDepth.working,
        kind=SkillKind.hard,
    )


def _extract(*canonicals: str) -> VacancyLLMExtract:
    return VacancyLLMExtract(
        job_family=JobFamily.backend,
        skills=[_skill(name) for name in canonicals],
    )


async def test_inserts_new_skill_into_lexicon_and_vacancy(db) -> None:
    async with resources.engine.connect() as conn:
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(conn, vacancy_id, _extract('python'))

        lexicon = await select_one(conn, stmt=sa.select(SkillLexicon))
        vacancy_skill = await select_one(
            conn,
            stmt=sa.select(VacancySkill).where(VacancySkill.vacancy_id == vacancy_id),
        )

    assert lexicon is not None
    assert lexicon['skill_name'] == 'Python'
    assert lexicon['skill_name_norm'] == 'python'
    assert lexicon['kind'] == SkillKind.hard

    assert vacancy_skill is not None
    assert vacancy_skill['skill_name'] == 'Python'
    assert vacancy_skill['depth'] == SkillDepth.working
    assert vacancy_skill['importance'] == 1.0


async def test_reuses_existing_canonical_without_lexicon_insert(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'Python')
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(conn, vacancy_id, _extract('python'))

        lexicon_rows = await select_all(conn, stmt=sa.select(SkillLexicon.skill_name))
        vacancy_skill = await select_one(
            conn,
            stmt=sa.select(VacancySkill).where(VacancySkill.vacancy_id == vacancy_id),
        )

    assert [row['skill_name'] for row in lexicon_rows] == ['Python']
    assert vacancy_skill is not None
    assert vacancy_skill['skill_name'] == 'Python'


async def test_links_spelling_variant_to_existing_skill(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'Vector database')
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(
            conn, vacancy_id, _extract('vector databases')
        )

        lexicon_rows = await select_all(conn, stmt=sa.select(SkillLexicon.skill_name))
        vacancy_skill = await select_one(
            conn,
            stmt=sa.select(VacancySkill).where(VacancySkill.vacancy_id == vacancy_id),
        )

    assert [row['skill_name'] for row in lexicon_rows] == ['Vector database']
    assert vacancy_skill is not None
    assert vacancy_skill['skill_name'] == 'Vector database'


async def test_does_not_link_opengl_to_opengles(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'OpenGL')

        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(conn, vacancy_id, _extract('opengles'))

        lexicon_rows = await select_all(
            conn,
            stmt=sa.select(SkillLexicon.skill_name).order_by(SkillLexicon.skill_name),
        )
        names = [row['skill_name'] for row in lexicon_rows]
        vacancy_skill = await select_one(
            conn,
            stmt=sa.select(VacancySkill).where(VacancySkill.vacancy_id == vacancy_id),
        )

    assert names == ['OpenGL', 'Opengles']
    assert vacancy_skill is not None
    assert vacancy_skill['skill_name'] == 'Opengles'


async def test_mixes_existing_match_and_new_skills(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'Python')
        await prepare_skill_lexicon(conn, 'Vector database')

        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(
            conn,
            vacancy_id,
            _extract('Python', 'Vector databases', 'FastAPI'),
        )

        lexicon_names = [
            row['skill_name']
            for row in await select_all(
                conn,
                stmt=sa.select(SkillLexicon.skill_name).order_by(SkillLexicon.skill_name),
            )
        ]
        vacancy_names = [
            row['skill_name']
            for row in await select_all(
                conn,
                stmt=(
                    sa.select(VacancySkill.skill_name)
                    .where(VacancySkill.vacancy_id == vacancy_id)
                    .order_by(VacancySkill.skill_name)
                ),
            )
        ]

    assert lexicon_names == ['FastAPI', 'Python', 'Vector database']
    assert vacancy_names == ['FastAPI', 'Python', 'Vector database']
