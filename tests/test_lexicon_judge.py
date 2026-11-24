from sqlalchemy.ext.asyncio.engine import AsyncConnection
from src import utils
from src.enums import SkillAliasStatus, SkillDepth, SkillLexiconStatus
from src.shared.resources import resources
from src.types import JudgeItem

from tests.shared import (
    prepare_profile,
    prepare_profile_skill,
    prepare_skill_alias,
    prepare_skill_lexicon,
    prepare_vacancy,
    prepare_vacancy_extract,
    prepare_vacancy_skill,
    select_alias_rows,
    select_lexicon_rows,
    select_profile_skill_rows,
    select_vacancy_skill_rows,
)


async def prepare_vacancy_with_skills(
    conn: AsyncConnection, suffix: str, skills: list[str]
) -> str:
    vacancy_id = await prepare_vacancy(
        conn, external_id=f'test-{suffix}', url=f'https://example.com/{suffix}'
    )
    await prepare_vacancy_extract(conn, vacancy_id)
    for skill_name in skills:
        await prepare_skill_lexicon(conn, skill_name, status=SkillLexiconStatus.pending)
        await prepare_vacancy_skill(conn, vacancy_id, skill_name)

    return vacancy_id


async def prepare_profile_with_skills(conn: AsyncConnection, skills: list[str]) -> str:
    profile_id = await prepare_profile(conn)
    for skill_name in skills:
        await prepare_skill_lexicon(conn, skill_name, status=SkillLexiconStatus.pending)
        await prepare_profile_skill(conn, profile_id, skill_name)

    return profile_id


def get_skill_names(rows) -> list[str]:
    return [row['skill_name'] for row in rows]


def get_skill_statuses(rows) -> list[tuple[str, SkillLexiconStatus | None]]:
    return [(row['skill_name'], row['status']) for row in rows]


def get_alias_fields(rows) -> list[tuple[str, str | None, SkillAliasStatus, int]]:
    return [
        (row['alias_name'], row['skill_name'], row['status'], row['seen_count'])
        for row in rows
    ]


async def test_rejected_deletes_skill_with_its_links(db) -> None:
    async with resources.engine.connect() as conn:
        vacancy_id_1 = await prepare_vacancy_with_skills(
            conn, '1', ['Teamwork', 'Python']
        )
        vacancy_id_2 = await prepare_vacancy_with_skills(conn, '2', ['Teamwork'])
        profile_id = await prepare_profile_with_skills(conn, ['Teamwork', 'Python'])

        applied = await utils.apply_judge_verdicts(
            conn, [JudgeItem(skill_name='Teamwork', verdict='rejected')]
        )

        vacancy_id_1_rows = await select_vacancy_skill_rows(conn, vacancy_id_1)
        vacancy_id_2_rows = await select_vacancy_skill_rows(conn, vacancy_id_2)

        lexicon_rows = await select_lexicon_rows(conn)
        profile_rows = await select_profile_skill_rows(conn, profile_id)
        alias_rows = await select_alias_rows(conn)

    assert applied == 1
    assert get_skill_statuses(lexicon_rows) == [('Python', SkillLexiconStatus.pending)]
    assert get_skill_names(vacancy_id_1_rows) == ['Python']
    assert vacancy_id_2_rows == []
    assert get_skill_names(profile_rows) == ['Python']
    assert get_alias_fields(alias_rows) == [
        ('Teamwork', None, SkillAliasStatus.rejected, 0)
    ]
    assert alias_rows[0]['is_reviewed'] is False


async def test_rejected_again_increases_seen_count(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_alias(
            conn, 'Teamwork', SkillAliasStatus.rejected, seen_count=3
        )
        await prepare_skill_lexicon(conn, 'TEAMWORK', status=SkillLexiconStatus.pending)

        applied = await utils.apply_judge_verdicts(
            conn, [JudgeItem(skill_name='TEAMWORK', verdict='rejected')]
        )

        lexicon_rows = await select_lexicon_rows(conn)
        alias_rows = await select_alias_rows(conn)

    assert applied == 1
    assert lexicon_rows == []
    # the first spelling stays, only the counter changes
    assert get_alias_fields(alias_rows) == [
        ('Teamwork', None, SkillAliasStatus.rejected, 4),
    ]


async def test_new_canon__same_name_becomes_canonical(db) -> None:
    async with resources.engine.connect() as conn:
        vacancy_id = await prepare_vacancy_with_skills(conn, '1', ['gRPC'])

        applied = await utils.apply_judge_verdicts(
            conn, [JudgeItem(skill_name='gRPC', verdict='new', canonical='gRPC')]
        )

        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

        lexicon_rows = await select_lexicon_rows(conn)
        alias_rows = await select_alias_rows(conn)

    assert applied == 1
    assert get_skill_statuses(lexicon_rows) == [('gRPC', None)]
    assert get_skill_names(vacancy_rows) == ['gRPC']
    assert alias_rows == []


async def test_new_canon__another_spelling_renames_without_alias(db) -> None:
    async with resources.engine.connect() as conn:
        vacancy_id = await prepare_vacancy_with_skills(conn, '1', ['ci-cd'])
        profile_id = await prepare_profile_with_skills(conn, ['ci-cd'])

        applied = await utils.apply_judge_verdicts(
            conn, [JudgeItem(skill_name='ci-cd', verdict='new', canonical='CI/CD')]
        )

        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

        lexicon_rows = await select_lexicon_rows(conn)
        profile_rows = await select_profile_skill_rows(conn, profile_id)
        alias_rows = await select_alias_rows(conn)

    assert applied == 1
    assert get_skill_statuses(lexicon_rows) == [('CI/CD', None)]
    assert get_skill_names(vacancy_rows) == ['CI/CD']
    assert get_skill_names(profile_rows) == ['CI/CD']
    # the same normalized name is found in skill_lexicon, an alias is not needed
    assert alias_rows == []


async def test_new_canon__another_name_keeps_old_name_as_alias(db) -> None:
    async with resources.engine.connect() as conn:
        vacancy_id = await prepare_vacancy_with_skills(conn, '1', ['Postgres'])
        profile_id = await prepare_profile_with_skills(conn, ['Postgres'])

        applied = await utils.apply_judge_verdicts(
            conn,
            [JudgeItem(skill_name='Postgres', verdict='new', canonical='PostgreSQL')],
        )

        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

        lexicon_rows = await select_lexicon_rows(conn)
        profile_rows = await select_profile_skill_rows(conn, profile_id)
        alias_rows = await select_alias_rows(conn)

    assert applied == 1
    assert get_skill_statuses(lexicon_rows) == [('PostgreSQL', None)]
    assert get_skill_names(vacancy_rows) == ['PostgreSQL']
    assert get_skill_names(profile_rows) == ['PostgreSQL']
    assert get_alias_fields(alias_rows) == [
        ('Postgres', 'PostgreSQL', SkillAliasStatus.alias, 0),
    ]


async def test_new_canon__existing_canonical_becomes_alias(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'Go')
        vacancy_id_1 = await prepare_vacancy_with_skills(conn, '1', ['Go', 'Golang'])
        vacancy_id_2 = await prepare_vacancy_with_skills(conn, '2', ['Golang'])
        profile_id = await prepare_profile_with_skills(conn, ['Golang'])

        applied = await utils.apply_judge_verdicts(
            conn, [JudgeItem(skill_name='Golang', verdict='new', canonical='go')]
        )

        vacancy_id_1_rows = await select_vacancy_skill_rows(conn, vacancy_id_1)
        vacancy_id_2_rows = await select_vacancy_skill_rows(conn, vacancy_id_2)

        lexicon_rows = await select_lexicon_rows(conn)
        profile_rows = await select_profile_skill_rows(conn, profile_id)
        alias_rows = await select_alias_rows(conn)

    assert applied == 1
    assert get_skill_statuses(lexicon_rows) == [('Go', None)]
    assert get_skill_names(vacancy_id_1_rows) == ['Go']
    assert get_skill_names(vacancy_id_2_rows) == ['Go']
    assert get_skill_names(profile_rows) == ['Go']
    assert get_alias_fields(alias_rows) == [
        ('Golang', 'Go', SkillAliasStatus.alias, 0),
    ]


async def test_new_canon__pending_canonical_is_skipped(db) -> None:
    async with resources.engine.connect() as conn:
        vacancy_id = await prepare_vacancy_with_skills(conn, '1', ['PG', 'PostgreSQL'])

        applied = await utils.apply_judge_verdicts(
            conn, [JudgeItem(skill_name='PG', verdict='new', canonical='PostgreSQL')]
        )

        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

        lexicon_rows = await select_lexicon_rows(conn)
        alias_rows = await select_alias_rows(conn)

    assert applied == 0
    assert get_skill_statuses(lexicon_rows) == [
        ('PG', SkillLexiconStatus.pending),
        ('PostgreSQL', SkillLexiconStatus.pending),
    ]
    assert get_skill_names(vacancy_rows) == ['PG', 'PostgreSQL']
    assert alias_rows == []


async def test_new_canon__canonical_accepted_earlier_in_batch(db) -> None:
    async with resources.engine.connect() as conn:
        vacancy_id = await prepare_vacancy_with_skills(conn, '1', ['PG', 'PostgreSQL'])

        applied = await utils.apply_judge_verdicts(
            conn,
            [
                JudgeItem(skill_name='PostgreSQL', verdict='new', canonical='PostgreSQL'),
                JudgeItem(skill_name='PG', verdict='new', canonical='PostgreSQL'),
            ],
        )

        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

        lexicon_rows = await select_lexicon_rows(conn)
        alias_rows = await select_alias_rows(conn)

    assert applied == 2
    assert get_skill_statuses(lexicon_rows) == [('PostgreSQL', None)]
    assert get_skill_names(vacancy_rows) == ['PostgreSQL']
    assert get_alias_fields(alias_rows) == [
        ('PG', 'PostgreSQL', SkillAliasStatus.alias, 0),
    ]


async def test_new_canon__canonical_is_alias_becomes_alias(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'Go')
        await prepare_skill_alias(conn, 'Golang', SkillAliasStatus.alias, skill_name='Go')
        vacancy_id = await prepare_vacancy_with_skills(conn, '1', ['Golang language'])

        applied = await utils.apply_judge_verdicts(
            conn,
            [JudgeItem(skill_name='Golang language', verdict='new', canonical='Golang')],
        )

        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

        lexicon_rows = await select_lexicon_rows(conn)
        alias_rows = await select_alias_rows(conn)

    assert applied == 1
    # no second canonical with the alias norm
    assert get_skill_statuses(lexicon_rows) == [('Go', None)]
    assert get_skill_names(vacancy_rows) == ['Go']
    assert get_alias_fields(alias_rows) == [
        ('Golang', 'Go', SkillAliasStatus.alias, 0),
        ('Golang language', 'Go', SkillAliasStatus.alias, 0),
    ]


async def test_new_canon__canonical_rejected_earlier_rejects_skill(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_alias(conn, 'English', SkillAliasStatus.rejected)
        vacancy_id = await prepare_vacancy_with_skills(conn, '1', ['English language'])

        applied = await utils.apply_judge_verdicts(
            conn,
            [
                JudgeItem(
                    skill_name='English language', verdict='new', canonical='English'
                )
            ],
        )

        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

        lexicon_rows = await select_lexicon_rows(conn)
        alias_rows = await select_alias_rows(conn)

    assert applied == 1
    assert lexicon_rows == []
    assert vacancy_rows == []
    assert get_alias_fields(alias_rows) == [
        ('English', None, SkillAliasStatus.rejected, 0),
        ('English language', None, SkillAliasStatus.rejected, 0),
    ]


async def test_alias__moves_vacancy_and_profile_links(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'Go')
        vacancy_id_1 = await prepare_vacancy_with_skills(conn, '1', ['Golang', 'Python'])
        vacancy_id_2 = await prepare_vacancy_with_skills(conn, '2', ['Golang'])
        profile_id = await prepare_profile_with_skills(conn, ['Golang'])

        applied = await utils.apply_judge_verdicts(
            conn, [JudgeItem(skill_name='Golang', verdict='alias', canonical='Go')]
        )

        vacancy_id_1_rows = await select_vacancy_skill_rows(conn, vacancy_id_1)
        vacancy_id_2_rows = await select_vacancy_skill_rows(conn, vacancy_id_2)

        lexicon_rows = await select_lexicon_rows(conn)
        profile_rows = await select_profile_skill_rows(conn, profile_id)
        alias_rows = await select_alias_rows(conn)

    assert applied == 1
    assert get_skill_statuses(lexicon_rows) == [
        ('Go', None),
        ('Python', SkillLexiconStatus.pending),
    ]
    assert get_skill_names(vacancy_id_1_rows) == ['Go', 'Python']
    assert get_skill_names(vacancy_id_2_rows) == ['Go']
    assert get_skill_names(profile_rows) == ['Go']
    assert get_alias_fields(alias_rows) == [
        ('Golang', 'Go', SkillAliasStatus.alias, 0),
    ]


async def test_alias__vacancy_with_both_keeps_canonical_row(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'Go')
        await prepare_skill_lexicon(conn, 'Golang', status=SkillLexiconStatus.pending)
        vacancy_id = await prepare_vacancy_with_skills(conn, '1', [])
        await prepare_vacancy_skill(
            conn, vacancy_id, 'Go', depth=SkillDepth.working, importance=0.3
        )
        await prepare_vacancy_skill(
            conn, vacancy_id, 'Golang', depth=SkillDepth.expert, importance=0.9
        )

        applied = await utils.apply_judge_verdicts(
            conn, [JudgeItem(skill_name='Golang', verdict='alias', canonical='Go')]
        )

        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

    assert applied == 1
    # the canonical row keeps its own values, the alias row is deleted
    assert [
        (row['skill_name'], row['depth'], row['importance']) for row in vacancy_rows
    ] == [('Go', SkillDepth.working, 0.3)]


async def test_alias__canonical_found_by_normalized_name(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'CI/CD')
        vacancy_id = await prepare_vacancy_with_skills(conn, '1', ['CI/CD pipeline'])

        applied = await utils.apply_judge_verdicts(
            conn,
            [JudgeItem(skill_name='CI/CD pipeline', verdict='alias', canonical='ci-cd')],
        )

        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

        lexicon_rows = await select_lexicon_rows(conn)
        alias_rows = await select_alias_rows(conn)

    assert applied == 1
    assert get_skill_statuses(lexicon_rows) == [('CI/CD', None)]
    assert get_skill_names(vacancy_rows) == ['CI/CD']
    assert get_alias_fields(alias_rows) == [
        ('CI/CD pipeline', 'CI/CD', SkillAliasStatus.alias, 0),
    ]


async def test_alias__missing_canonical_is_skipped(db) -> None:
    async with resources.engine.connect() as conn:
        vacancy_id = await prepare_vacancy_with_skills(conn, '1', ['Rustlang'])

        applied = await utils.apply_judge_verdicts(
            conn, [JudgeItem(skill_name='Rustlang', verdict='alias', canonical='Rust')]
        )

        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

        lexicon_rows = await select_lexicon_rows(conn)
        alias_rows = await select_alias_rows(conn)

    assert applied == 0
    assert get_skill_statuses(lexicon_rows) == [('Rustlang', SkillLexiconStatus.pending)]
    assert get_skill_names(vacancy_rows) == ['Rustlang']
    assert alias_rows == []


async def test_alias__pending_canonical_is_skipped(db) -> None:
    async with resources.engine.connect() as conn:
        vacancy_id = await prepare_vacancy_with_skills(conn, '1', ['Golang', 'Go'])

        applied = await utils.apply_judge_verdicts(
            conn, [JudgeItem(skill_name='Golang', verdict='alias', canonical='Go')]
        )

        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

        lexicon_rows = await select_lexicon_rows(conn)
        alias_rows = await select_alias_rows(conn)

    assert applied == 0
    assert get_skill_statuses(lexicon_rows) == [
        ('Go', SkillLexiconStatus.pending),
        ('Golang', SkillLexiconStatus.pending),
    ]
    assert get_skill_names(vacancy_rows) == ['Go', 'Golang']
    assert alias_rows == []
