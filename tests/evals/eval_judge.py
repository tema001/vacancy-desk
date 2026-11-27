import asyncio
import json
from pathlib import Path
from typing import TypedDict

import src.db as db
from langfuse import propagate_attributes
from langfuse.model import PromptClient
from pydantic import ValidationError
from src.shared.resources import resources
from src.shared.utils import JSON_TEXT, LOW_REASONING, openai_input
from src.types import JudgeItem, JudgeVerdict, LexiconJudge
from src.utils import validate_judge_items

DATASET_PATH = Path(__file__).resolve().parent / 'data' / 'lexicon_judge.json'
PROMPT_NAME = 'lexicon-judge'
PROMPT_LABEL = 'experimental'
BATCH_SIZE = 10
CONCURRENCY = 3


class JudgeCase(TypedDict):
    skill_name: str
    verdict: str
    canonical: str | None
    titles: list[str]


async def request_judge(
    prompt: PromptClient,
    batch: list[str],
    titles: dict[str, list[str]],
    canonical_skills: list[str],
) -> str:
    candidates = [{'skill_name': name, 'titles': titles.get(name, [])} for name in batch]
    compiled_prompt = prompt.compile(
        candidates=candidates, canonical_skills=canonical_skills
    )
    with propagate_attributes(prompt=prompt, trace_name=f'{prompt.name}-eval'):
        resp = await resources.llm.responses.create(
            model=prompt.config['model'],
            input=openai_input(compiled_prompt),
            text=JSON_TEXT,
            reasoning=LOW_REASONING,
        )
    return resp.output_text


async def request_judges(
    prompt: PromptClient,
    names: list[str],
    titles: dict[str, list[str]],
    canonical_skills: list[str],
) -> list[str]:
    # candidates go in batches of BATCH_SIZE, as in process_lexicon_judging
    batches = [names[i : i + BATCH_SIZE] for i in range(0, len(names), BATCH_SIZE)]
    semaphore = asyncio.Semaphore(CONCURRENCY)

    tasks = []
    async with asyncio.TaskGroup() as tg:
        for i, batch in enumerate(batches, start=1):
            await semaphore.acquire()

            print(f'request {i}/{len(batches)}: {len(batch)} candidates')
            task = tg.create_task(request_judge(prompt, batch, titles, canonical_skills))
            task.add_done_callback(lambda _: semaphore.release())

            tasks.append(task)

    return [task.result() for task in tasks]


def parse_verdicts(responses: list[str], names: list[str]) -> list[JudgeItem]:
    verdicts: list[JudgeItem] = []
    for raw_resp in responses:
        try:
            data = LexiconJudge.model_validate_json(raw_resp)
        except ValidationError as e:
            print(f'invalid response, skip: {e}')
            continue

        verdicts.extend(validate_judge_items(data.items, sent=names))

    return verdicts


def format_verdict(verdict: str | None, canonical: str | None) -> str:
    if verdict is None:
        return 'no valid verdict'
    if canonical is None:
        return verdict
    return f'{verdict} -> {canonical}'


def evaluate(cases: list[JudgeCase], verdicts: list[JudgeItem]) -> dict[str, float]:
    expected_rejects = predicted_rejects = correct_rejects = 0
    expected_named = correct_named = 0

    verdicts_by_name = {item.skill_name: item for item in verdicts}
    for case in cases:
        item = verdicts_by_name.get(case['skill_name'])
        verdict = item.verdict if item else None
        canonical = item.canonical if item else None

        should_reject = case['verdict'] == JudgeVerdict.rejected
        is_rejected = verdict == JudgeVerdict.rejected
        expected_rejects += should_reject
        predicted_rejects += is_rejected
        correct_rejects += should_reject and is_rejected

        # alias and new are right only with the expected canonical name
        is_correct = (
            is_rejected
            if should_reject
            else (verdict == case['verdict'] and canonical == case['canonical'])
        )
        if not should_reject:
            expected_named += 1
            correct_named += is_correct

        if not is_correct:
            print(case['skill_name'])
            print(f'  expected: {format_verdict(case["verdict"], case["canonical"])}')
            print(f'  got:      {format_verdict(verdict, canonical)}')

    reject_precision = correct_rejects / predicted_rejects if predicted_rejects else 0.0
    reject_recall = correct_rejects / expected_rejects if expected_rejects else 0.0
    canonical_accuracy = correct_named / expected_named if expected_named else 0.0
    return {
        'reject_precision': reject_precision,
        'reject_recall': reject_recall,
        'canonical_accuracy': canonical_accuracy,
    }


async def main() -> None:
    await resources.start(start_llm=True)
    try:
        cases: list[JudgeCase] = json.loads(DATASET_PATH.read_text())
        names = [case['skill_name'] for case in cases]
        titles = {case['skill_name']: case['titles'] for case in cases}

        async with resources.engine.connect() as conn:
            canonical_skills = await db.select_canonical_skill_names(conn)

        # hide the candidates and the names expected as "new",
        # otherwise the judge finds them in the canonical list
        hidden = set(names)
        for case in cases:
            if case['verdict'] == JudgeVerdict.new and case['canonical']:
                hidden.add(case['canonical'])
        canonical_skills = [name for name in canonical_skills if name not in hidden]

        prompt = resources.langfuse.get_prompt(PROMPT_NAME, label=PROMPT_LABEL)
        print(f'prompt: {prompt.name} v{prompt.version} ({PROMPT_LABEL})')

        responses = await request_judges(prompt, names, titles, canonical_skills)
    finally:
        await resources.stop()

    print()
    verdicts = parse_verdicts(responses, names)
    scores = evaluate(cases, verdicts)

    print()
    print(f'{len(cases)} candidates, {len(verdicts)} valid verdicts')
    for name, value in scores.items():
        print(f'  {name}={value:.3f}')


if __name__ == '__main__':
    # docker compose run --rm -v ./tests:/app/tests worker \
    # python -m tests.evals.eval_judge
    asyncio.run(main())
