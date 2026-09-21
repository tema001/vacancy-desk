from src.enums import JobFamily, SkillDepth, SkillKind
from src.shared.resources import resources
from src.types import ExtractedSkill, VacancyLLMExtract
from src.utils import _add_vacancy_skill_and_lexicon

from tests.shared import (
    prepare_skill_lexicon,
    prepare_vacancy,
    prepare_vacancy_extract,
    select_lexicon_rows,
    select_vacancy_skill_rows,
)


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

        lexicon_rows = await select_lexicon_rows(conn)
        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

    assert len(lexicon_rows) == 1
    lexicon = lexicon_rows[0]
    assert lexicon['skill_name'] == 'Python'
    assert lexicon['skill_name_norm'] == 'python'
    assert lexicon['kind'] == SkillKind.hard

    assert len(vacancy_rows) == 1
    vacancy_skill = vacancy_rows[0]
    assert vacancy_skill['skill_name'] == 'Python'
    assert vacancy_skill['depth'] == SkillDepth.working
    assert vacancy_skill['importance'] == 1.0


async def test_reuses_existing_canonical_without_lexicon_insert(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'Python')
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(conn, vacancy_id, _extract('python'))

        lexicon_rows = await select_lexicon_rows(conn)
        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

    assert [row['skill_name'] for row in lexicon_rows] == ['Python']
    assert len(vacancy_rows) == 1
    assert vacancy_rows[0]['skill_name'] == 'Python'


async def test_links_spelling_variant_to_existing_skill(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'Vector database')
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(
            conn, vacancy_id, _extract('vector databases')
        )

        lexicon_rows = await select_lexicon_rows(conn)
        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

    assert [row['skill_name'] for row in lexicon_rows] == ['Vector database']
    assert len(vacancy_rows) == 1
    assert vacancy_rows[0]['skill_name'] == 'Vector database'


async def test_does_not_link_opengl_to_opengles(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'OpenGL')

        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(conn, vacancy_id, _extract('opengles'))

        lexicon_rows = await select_lexicon_rows(conn)
        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

    assert [row['skill_name'] for row in lexicon_rows] == ['OpenGL', 'Opengles']
    assert len(vacancy_rows) == 1
    assert vacancy_rows[0]['skill_name'] == 'Opengles'


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

        lexicon_rows = await select_lexicon_rows(conn)
        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

    expected = [
        'FastAPI',
        'Python',
        'Vector database'
    ]
    assert [row['skill_name'] for row in lexicon_rows] == expected
    assert [row['skill_name'] for row in vacancy_rows] == expected


async def test_dedupes_skills_that_match_the_same_lexicon_name(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'Odoo')
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(
            conn,
            vacancy_id,
            data=VacancyLLMExtract(
                job_family=JobFamily.backend,
                skills=[
                    _skill('Odoo', importance=0.45),
                    _skill('Odoo ORM', importance=0.4),
                ],
            ),
        )

        lexicon_rows = await select_lexicon_rows(conn)
        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

    assert [row['skill_name'] for row in lexicon_rows] == ['Odoo']
    assert len(vacancy_rows) == 1
    assert vacancy_rows[0]['skill_name'] == 'Odoo'
    assert vacancy_rows[0]['importance'] == 0.45
    assert vacancy_rows[0]['depth'] == SkillDepth.working
