import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict

import tests.evals.db as evals_db
from langfuse import propagate_attributes
from langfuse.model import PromptClient
from pydantic import ValidationError
from sqlalchemy import RowMapping
from src.shared.resources import resources
from src.shared.utils import (
    JSON_TEXT,
    LOW_REASONING,
    normalize_skill_name,
    openai_input,
)
from src.types import VacancyLLMExtract

DATASET_PATH = Path(__file__).resolve().parent / 'data' / 'vacancy_extract.json'
PROMPT_NAME = 'vacancy-extract'
PROMPT_LABEL = 'experimental'
CONCURRENCY = 5


class ExtractCase(TypedDict):
    vacancy_id: str
    must: list[str]
    ok: list[str]


def match_skills(
    output: list[str], expected_skills: list[str], aliases: dict[str, str]
) -> dict[str, str]:
    expected_by_norm = {normalize_skill_name(skill): skill for skill in expected_skills}
    # output name -> expected skill name; an alias counts as a match with wrong spelling
    matched = {}
    for name in output:
        norm = normalize_skill_name(name)
        if norm in expected_by_norm:
            matched[name] = expected_by_norm[norm]
        elif norm in aliases:
            alias_norm = normalize_skill_name(aliases[norm])
            if alias_norm in expected_by_norm:
                matched[name] = expected_by_norm[alias_norm]
    return matched


def evaluate_case(
    case: ExtractCase, output: list[str], aliases: dict[str, str]
) -> dict[str, float]:
    matched = match_skills(output, case['must'] + case['ok'], aliases)

    scores = {}
    if case['must']:
        found_must = set(matched.values()) & set(case['must'])
        scores['must_recall'] = len(found_must) / len(case['must'])
    if output:
        scores['precision'] = len(matched) / len(output)
    if matched:
        exact = sum(name == expected for name, expected in matched.items())
        scores['naming_accuracy'] = exact / len(matched)

    missing = [skill for skill in case['must'] if skill not in matched.values()]
    extra = [name for name in output if name not in matched]
    misspelled = [
        f'{name} -> {expected}' for name, expected in matched.items() if name != expected
    ]
    if missing:
        print(f'  missing must: {", ".join(missing)}')
    if extra:
        print(f'  extra: {", ".join(extra)}')
    if misspelled:
        print(f'  misspelled: {", ".join(misspelled)}')

    return scores


async def request_extract(prompt: PromptClient, row: RowMapping) -> str:
    compiled_prompt = prompt.compile(
        title=row['title'],
        experience=row['experience'],
        description=row['description'],
    )
    with propagate_attributes(prompt=prompt, trace_name=f'{prompt.name}-eval'):
        resp = await resources.llm.responses.create(
            model=prompt.config['model'],
            input=openai_input(compiled_prompt),
            text=JSON_TEXT,
            reasoning=LOW_REASONING,
            metadata={'vacancy_id': row['id']},
        )
    return resp.output_text


async def request_extracts(
    prompt: PromptClient, rows: Sequence[RowMapping]
) -> dict[str, str]:
    # vacancy_id -> raw LLM response, kept only in memory
    semaphore = asyncio.Semaphore(CONCURRENCY)
    tasks = {}
    async with asyncio.TaskGroup() as tg:
        for i, row in enumerate(rows, start=1):
            await semaphore.acquire()

            print(f'request {i}/{len(rows)}: {row["id"]}')
            task = tg.create_task(request_extract(prompt, row))
            task.add_done_callback(lambda _: semaphore.release())

            tasks[row['id']] = task

    return {vacancy_id: task.result() for vacancy_id, task in tasks.items()}


async def main() -> None:
    await resources.start(start_llm=True)
    try:
        cases: list[ExtractCase] = json.loads(DATASET_PATH.read_text())
        async with resources.engine.connect() as conn:
            rows = await evals_db.select_vacancies_for_extract_eval(
                conn, [case['vacancy_id'] for case in cases]
            )
            aliases = await evals_db.select_skill_aliases_eval(conn)

        prompt = resources.langfuse.get_prompt(PROMPT_NAME, label=PROMPT_LABEL)
        print(f'prompt: {prompt.name} v{prompt.version} ({PROMPT_LABEL})')

        responses = await request_extracts(prompt, rows)
    finally:
        await resources.stop()

    rows_by_id = {row['id']: row for row in rows}
    print()

    totals: dict[str, list[float]] = {
        'must_recall': [],
        'precision': [],
        'naming_accuracy': [],
    }
    for case in cases:
        row = rows_by_id.get(case['vacancy_id'])
        if not row:
            print(f'{case["vacancy_id"]} | no vacancy, skip')
            continue

        try:
            data = VacancyLLMExtract.model_validate_json(responses[row['id']])
        except ValidationError as e:
            print(f'{case["vacancy_id"]} | invalid response, skip: {e}')
            continue
        output = [skill.canonical for skill in data.skills]

        print(f'{case["vacancy_id"]} | {row["title"]}')
        scores = evaluate_case(case, output, aliases)
        print('  ' + '  '.join(f'{name}={value:.3f}' for name, value in scores.items()))
        for name, value in scores.items():
            totals[name].append(value)

    print()
    print('mean over vacancies')
    for name, values in totals.items():
        mean = sum(values) / len(values) if values else 0.0
        print(f'  {name}={mean:.3f}  (n={len(values)})')


if __name__ == '__main__':
    # docker compose run --rm -v ./tests:/app/tests app python -m tests.evals.eval_extract
    asyncio.run(main())
