import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TypedDict
from zoneinfo import ZoneInfo

import tests.evals.db as evals_db
from src.scoring import rank_bm25, rrf
from src.shared.resources import resources

QUERIES_PATH = Path(__file__).resolve().parent / 'data' / 'queries.json'


class QueryCase(TypedDict):
    query: str
    relevant_ids: list[str]


@dataclass
class MetricObj:
    label: str
    fn: Callable[[list[str], set[str]], float]
    max_fn: Callable[[set[str]], float] | None


def precision_at_10(ranked_ids: list[str], relevant: set[str]) -> float:
    k = 10
    return sum(vacancy_id in relevant for vacancy_id in ranked_ids[:k]) / k


def max_precision_at_10(relevant: set[str]) -> float:
    return min(len(relevant), 10) / 10


def reciprocal_rank(ranked_ids: list[str], relevant: set[str]) -> float:
    for rank, vacancy_id in enumerate(ranked_ids, start=1):
        if vacancy_id in relevant:
            return 1 / rank
    return 0.0


async def rank_query(
    query: str, date_from: datetime, date_to: datetime
) -> dict[str, list[str]]:
    text = query.strip()
    keywords = set(re.findall(evals_db.TOKEN_RE, text.lower()))

    model = resources.config['llm']['embedding_model']
    resp = await resources.llm.embeddings.create(
        name='chunk-embed',
        model=model,
        input=text,
        dimensions=1536,
    )
    embed_query = resp.data[0].embedding

    async with resources.engine.connect() as conn:
        bm_rows = await evals_db.select_vacancies_for_bm25_eval(
            conn, keywords, date_from=date_from, date_to=date_to
        )
        if bm_rows:
            first = bm_rows[0]
            bm25_rank = rank_bm25(
                keywords,
                bm_rows,
                N=int(first['total_count']),
                avg_dl=float(first['avg_length']),
            )
        else:
            bm25_rank = []

        cosine_rows = await evals_db.select_vacancy_for_similarities_eval(
            conn, embed_query, date_from=date_from, date_to=date_to
        )

    cosine_rank = [(row['vacancy_id'], row['similarity']) for row in cosine_rows]
    fused = rrf(bm25_rank, cosine_rank)

    return {
        'bm25': [vacancy_id for vacancy_id, _ in bm25_rank],
        'cosine': [vacancy_id for vacancy_id, _ in cosine_rank],
        'rrf': [vacancy_id for vacancy_id, _ in fused],
    }


async def evaluate(
    cases: list[QueryCase], date_from: datetime, date_to: datetime
) -> None:
    #           p@10  mrr
    #             v    v
    # { 'bm25': [1.0, 1.0], ... }
    totals = {}
    for case in cases:
        query = case['query']
        relevant = set(case['relevant_ids'])

        ranked = await rank_query(query, date_from, date_to)
        if not totals:
            totals = {rank_name: [0.0] * len(METRICS) for rank_name in ranked}

        max_scores = ', '.join(
            f'max {m.label}={m.max_fn(relevant):.3f}' for m in METRICS if m.max_fn
        )

        print(f'{query} | {max_scores}')
        for rank_name, ids in ranked.items():
            metric_scores = [m.fn(ids, relevant) for m in METRICS]
            for i, score in enumerate(metric_scores):
                totals[rank_name][i] += score

            rendered = '  '.join(
                f'{m.label}={score:.3f}'
                for m, score in zip(METRICS, metric_scores, strict=True)
            )
            print(f'  {rank_name}  {rendered}')

    count = len(cases)
    print(f'mean over {count} queries')
    for rank_name, sums in totals.items():
        rendered = '  '.join(
            f'{m.label}={total / count:.3f}'
            for m, total in zip(METRICS, sums, strict=True)
        )
        print(f'  {rank_name}  {rendered}')


async def main() -> None:
    test_data = json.loads(QUERIES_PATH.read_text())
    if not test_data:
        print(f'{QUERIES_PATH} is empty')
        return

    await resources.start(start_llm=True)
    try:
        tz = ZoneInfo(resources.config['app']['time_zone'])
        date_from = datetime.fromisoformat(test_data['from']).replace(tzinfo=tz)
        date_to = datetime.fromisoformat(test_data['to']).replace(tzinfo=tz)

        await evaluate(test_data['cases'], date_from, date_to)
    finally:
        await resources.stop()


if __name__ == '__main__':
    # python react typescript | max P@10=0.800
    #   bm25  P@10=0.600  MRR=1.000
    #   cosine  P@10=0.500  MRR=1.000
    #   rrf  P@10=0.700  MRR=1.000
    # senior python fastapi postgresql | max P@10=1.000
    #   bm25  P@10=0.500  MRR=1.000
    #   cosine  P@10=0.700  MRR=1.000
    #   rrf  P@10=0.900  MRR=1.000
    # mean over 2 queries
    #   bm25  P@10=0.550  MRR=1.000
    #   cosine  P@10=0.600  MRR=1.000
    #   rrf  P@10=0.800  MRR=1.000

    METRICS = (
        MetricObj(label='P@10', fn=precision_at_10, max_fn=max_precision_at_10),
        MetricObj(label='MRR', fn=reciprocal_rank, max_fn=None),
    )
    asyncio.run(main())
