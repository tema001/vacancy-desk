import sqlalchemy as sa
import src.db as vacancy_db
from src.enums import SkillAliasStatus, SkillDepth, SkillKind, SkillLexiconStatus
from src.shared.resources import resources
from src.types import SkillExtract, VacancySkillExtract
from src.utils import _add_profile_skill_and_lexicon, _add_vacancy_skill_and_lexicon

from tests.shared import (
    prepare_profile,
    prepare_skill_alias,
    prepare_skill_lexicon,
    prepare_vacancy,
    prepare_vacancy_extract,
    select_alias_rows,
    select_lexicon_rows,
    select_profile_skill_rows,
    select_vacancy_skill_rows,
)


def _skill(
    canonical: str,
    *,
    importance: float = 1.0,
    depth: SkillDepth = SkillDepth.working,
) -> VacancySkillExtract:
    return VacancySkillExtract(
        canonical=canonical,
        importance=importance,
        depth=depth,
        kind=SkillKind.hard,
    )


def _skills(*canonicals: str) -> list[VacancySkillExtract]:
    return [_skill(name) for name in canonicals]


async def test_unknown_name_becomes_pending_lexicon_row(db) -> None:
    async with resources.engine.connect() as conn:
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(
            conn, vacancy_id, [_skill('gRPC', importance=0.7, depth=SkillDepth.expert)]
        )

        lexicon_rows = await select_lexicon_rows(conn)
        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)
        alias_rows = await select_alias_rows(conn)

    assert len(lexicon_rows) == 1
    # stored as the LLM spelled it
    assert lexicon_rows[0]['skill_name'] == 'gRPC'
    assert lexicon_rows[0]['kind'] == SkillKind.hard
    assert lexicon_rows[0]['status'] == SkillLexiconStatus.pending

    assert len(vacancy_rows) == 1
    assert vacancy_rows[0]['skill_name'] == 'gRPC'
    assert vacancy_rows[0]['depth'] == SkillDepth.expert
    assert vacancy_rows[0]['importance'] == 0.7

    assert alias_rows == []


async def test_same_unknown_name_from_second_vacancy(db) -> None:
    async with resources.engine.connect() as conn:
        first_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, first_id)
        second_id = await prepare_vacancy(
            conn, external_id='test-2', url='https://example.com/2'
        )
        await prepare_vacancy_extract(conn, second_id)

        await _add_vacancy_skill_and_lexicon(conn, first_id, _skills('Web development'))
        await _add_vacancy_skill_and_lexicon(conn, second_id, _skills('Web development'))

        lexicon_rows = await select_lexicon_rows(conn)
        first_rows = await select_vacancy_skill_rows(conn, first_id)
        second_rows = await select_vacancy_skill_rows(conn, second_id)

    assert [row['skill_name'] for row in lexicon_rows] == ['Web development']
    assert [row['skill_name'] for row in first_rows] == ['Web development']
    assert [row['skill_name'] for row in second_rows] == ['Web development']


async def test_other_spelling_resolves_to_existing_pending_row(db) -> None:
    async with resources.engine.connect() as conn:
        first_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, first_id)
        second_id = await prepare_vacancy(
            conn, external_id='test-2', url='https://example.com/2'
        )
        await prepare_vacancy_extract(conn, second_id)

        await _add_vacancy_skill_and_lexicon(conn, first_id, _skills('CI/CD'))
        await _add_vacancy_skill_and_lexicon(conn, second_id, _skills('ci-cd'))

        lexicon_rows = await select_lexicon_rows(conn)
        second_rows = await select_vacancy_skill_rows(conn, second_id)
        alias_rows = await select_alias_rows(conn)

    assert [row['skill_name'] for row in lexicon_rows] == ['CI/CD']
    assert lexicon_rows[0]['status'] == SkillLexiconStatus.pending
    assert [row['skill_name'] for row in second_rows] == ['CI/CD']
    assert alias_rows == []


async def test_duplicate_names_in_one_call_collapse_into_one_row(db) -> None:
    async with resources.engine.connect() as conn:
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(
            conn,
            vacancy_id,
            [_skill('CI/CD', importance=0.2), _skill('ci-cd', importance=0.9)],
        )

        lexicon_rows = await select_lexicon_rows(conn)
        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

    # stored under the spelling of the skill that wins by prefer
    assert [row['skill_name'] for row in lexicon_rows] == ['ci-cd']
    assert [row['skill_name'] for row in vacancy_rows] == ['ci-cd']
    assert vacancy_rows[0]['importance'] == 0.9


async def test_exact_and_normalized_hits_on_active_rows(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'Python')
        await prepare_skill_lexicon(conn, 'CI/CD')
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        # 'Python' is an exact hit, 'ci-cd' matches by normalized form
        await _add_vacancy_skill_and_lexicon(conn, vacancy_id, _skills('Python', 'ci-cd'))

        lexicon_rows = await select_lexicon_rows(conn)
        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)
        alias_rows = await select_alias_rows(conn)

    assert [row['skill_name'] for row in lexicon_rows] == ['CI/CD', 'Python']
    assert all(row['status'] is None for row in lexicon_rows)
    assert [row['skill_name'] for row in vacancy_rows] == ['CI/CD', 'Python']
    assert alias_rows == []


async def test_one_lexicon_row_per_normalized_form(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'Node.js')
        # another spelling of the same normalized form is skipped, not a second row
        await prepare_skill_lexicon(conn, 'Node-js', status=SkillLexiconStatus.pending)
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(conn, vacancy_id, _skills('node js'))

        lexicon_rows = await select_lexicon_rows(conn)
        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

    assert [(row['skill_name'], row['status']) for row in lexicon_rows] == [
        ('Node.js', None)
    ]
    assert [row['skill_name'] for row in vacancy_rows] == ['Node.js']


async def test_new_skill_saved_meanwhile_under_another_spelling(db, monkeypatch) -> None:
    # simulates another worker that saved 'CI/CD' right after this one looked it up
    original = vacancy_db.select_skill_resolutions
    calls = 0

    async def stale_first_lookup(conn, data):
        nonlocal calls
        calls += 1
        if calls == 1:
            await prepare_skill_lexicon(conn, 'CI/CD', status=SkillLexiconStatus.pending)
            return {}
        return await original(conn, data)

    monkeypatch.setattr(vacancy_db, 'select_skill_resolutions', stale_first_lookup)

    async with resources.engine.connect() as conn:
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(conn, vacancy_id, _skills('ci-cd'))

        lexicon_rows = await select_lexicon_rows(conn)
        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

    assert [row['skill_name'] for row in lexicon_rows] == ['CI/CD']
    assert [row['skill_name'] for row in vacancy_rows] == ['CI/CD']


async def test_alias_matches_any_spelling_of_its_normalized_form(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'CI/CD pipelines')
        await prepare_skill_alias(
            conn, 'CI/CD', SkillAliasStatus.alias, skill_name='CI/CD pipelines'
        )
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(conn, vacancy_id, _skills('ci-cd'))

        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)
        alias_rows = await select_alias_rows(conn)

    assert [row['skill_name'] for row in vacancy_rows] == ['CI/CD pipelines']
    assert [(row['alias_name'], row['alias_name_norm']) for row in alias_rows] == [
        ('CI/CD', 'ci cd')
    ]


async def test_alias_row_resolves_to_canonical(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'Go')
        await prepare_skill_alias(
            conn, 'Golang', SkillAliasStatus.alias, skill_name='Go', seen_count=5
        )
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(conn, vacancy_id, _skills('Golang'))

        lexicon_rows = await select_lexicon_rows(conn)
        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)
        alias_rows = await select_alias_rows(conn)

    assert [row['skill_name'] for row in lexicon_rows] == ['Go']
    assert [row['skill_name'] for row in vacancy_rows] == ['Go']
    assert alias_rows[0]['seen_count'] == 5


async def test_two_names_resolving_to_one_canonical_collapse(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'Go')
        await prepare_skill_alias(conn, 'Golang', SkillAliasStatus.alias, skill_name='Go')
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(
            conn,
            vacancy_id,
            skills=[
                _skill('Go', importance=0.3, depth=SkillDepth.working),
                _skill('Golang', importance=0.6, depth=SkillDepth.advanced),
            ],
        )

        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

    assert len(vacancy_rows) == 1
    assert vacancy_rows[0]['skill_name'] == 'Go'
    assert vacancy_rows[0]['depth'] == SkillDepth.advanced
    assert vacancy_rows[0]['importance'] == 0.6


async def test_strict_trigram_hit_on_active_row_records_alias(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'Vector database')
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(
            conn, vacancy_id, _skills('vector databases')
        )

        lexicon_rows = await select_lexicon_rows(conn)
        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)
        alias_rows = await select_alias_rows(conn)

    assert [row['skill_name'] for row in lexicon_rows] == ['Vector database']
    assert [row['skill_name'] for row in vacancy_rows] == ['Vector database']

    assert len(alias_rows) == 1
    assert alias_rows[0]['alias_name_norm'] == 'vector databases'
    assert alias_rows[0]['alias_name'] == 'vector databases'
    assert alias_rows[0]['status'] == SkillAliasStatus.alias
    assert alias_rows[0]['skill_name'] == 'Vector database'


async def test_near_duplicate_does_not_trigram_match_pending_row(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(
            conn, 'Vector database', status=SkillLexiconStatus.pending
        )
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(
            conn, vacancy_id, _skills('vector databases')
        )

        lexicon_rows = await select_lexicon_rows(conn)
        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)
        alias_rows = await select_alias_rows(conn)

    assert [(row['skill_name'], row['status']) for row in lexicon_rows] == [
        ('Vector database', SkillLexiconStatus.pending),
        ('vector databases', SkillLexiconStatus.pending),
    ]
    assert [row['skill_name'] for row in vacancy_rows] == ['vector databases']
    assert alias_rows == []


async def test_loose_trigram_pair_becomes_pending(db) -> None:
    # similarity 0.67, length diff 2, different stems: only the removed branch matched
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'PostgreSQL')
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(conn, vacancy_id, _skills('Postgres'))

        lexicon_rows = await select_lexicon_rows(conn)
        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)
        alias_rows = await select_alias_rows(conn)

    assert [(row['skill_name'], row['status']) for row in lexicon_rows] == [
        ('Postgres', SkillLexiconStatus.pending),
        ('PostgreSQL', None),
    ]
    assert [row['skill_name'] for row in vacancy_rows] == ['Postgres']
    assert alias_rows == []


async def test_does_not_link_cpp_to_csharp(db) -> None:
    async with resources.engine.begin() as conn:
        await prepare_skill_lexicon(conn, 'C#')
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(conn, vacancy_id, _skills('C++', 'C++17'))

        lexicon_rows = await select_lexicon_rows(conn)
        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)
        alias_rows = await select_alias_rows(conn)

    assert [row['skill_name'] for row in lexicon_rows] == ['C#', 'C++', 'C++17']
    assert [row['skill_name'] for row in vacancy_rows] == ['C++', 'C++17']
    assert alias_rows == []


async def test_rejected_string_is_dropped_and_counted(db) -> None:
    for is_reviewed in (False, True):
        async with resources.engine.connect() as conn:
            await conn.execute(sa.text('TRUNCATE skill_alias, skill_lexicon CASCADE'))
            await prepare_skill_alias(
                conn, 'Teamwork', SkillAliasStatus.rejected, is_reviewed=is_reviewed
            )
            first_id = await prepare_vacancy(conn)
            await prepare_vacancy_extract(conn, first_id)
            second_id = await prepare_vacancy(
                conn, external_id='test-2', url='https://example.com/2'
            )
            await prepare_vacancy_extract(conn, second_id)

            await _add_vacancy_skill_and_lexicon(conn, first_id, _skills('Teamwork'))
            await _add_vacancy_skill_and_lexicon(
                conn, second_id, _skills('Teamwork', 'TEAMWORK')
            )

            lexicon_rows = await select_lexicon_rows(conn)
            first_rows = await select_vacancy_skill_rows(conn, first_id)
            second_rows = await select_vacancy_skill_rows(conn, second_id)
            alias_rows = await select_alias_rows(conn)

        assert lexicon_rows == []
        assert first_rows == []
        assert second_rows == []
        assert alias_rows[0]['status'] == SkillAliasStatus.rejected
        assert alias_rows[0]['seen_count'] == 2
        assert alias_rows[0]['is_reviewed'] is is_reviewed


async def test_empty_normalized_name_is_skipped(db) -> None:
    async with resources.engine.connect() as conn:
        vacancy_id = await prepare_vacancy(conn)
        await prepare_vacancy_extract(conn, vacancy_id)

        await _add_vacancy_skill_and_lexicon(conn, vacancy_id, _skills('-', '/'))

        lexicon_rows = await select_lexicon_rows(conn)
        vacancy_rows = await select_vacancy_skill_rows(conn, vacancy_id)

    assert lexicon_rows == []
    assert vacancy_rows == []


async def test_profile_path_creates_pending_lexicon_row(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'Python')
        profile_id = await prepare_profile(conn)

        await _add_profile_skill_and_lexicon(
            conn,
            profile_id,
            skills=[
                SkillExtract(canonical='python', depth=SkillDepth.advanced),
                SkillExtract(canonical='Web development', depth=SkillDepth.working),
            ],
        )

        profile_rows = await select_profile_skill_rows(conn, profile_id)
        lexicon_rows = await select_lexicon_rows(conn)
        alias_rows = await select_alias_rows(conn)

    assert [row['skill_name'] for row in profile_rows] == ['Python', 'Web development']
    assert [(row['skill_name'], row['status']) for row in lexicon_rows] == [
        ('Python', None),
        ('Web development', SkillLexiconStatus.pending),
    ]
    assert alias_rows == []


async def test_select_skill_lexicon_for_expand_skips_pending(db) -> None:
    async with resources.engine.connect() as conn:
        await prepare_skill_lexicon(conn, 'Python')
        await prepare_skill_lexicon(
            conn, 'Web development', status=SkillLexiconStatus.pending
        )

        names = await vacancy_db.select_skill_lexicon_for_expand(conn, limit=10)

    assert names == ['Python']
