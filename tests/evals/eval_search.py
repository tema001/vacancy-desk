import argparse
import asyncio
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, TypedDict
from zoneinfo import ZoneInfo

import tests.evals.db as evals_db
from langfuse import Evaluation, propagate_attributes
from src.scoring import rank_bm25, rrf
from src.shared.resources import resources

QUERIES_PATH = Path(__file__).resolve().parent / 'data' / 'queries.json'
LANGFUSE_DATASET = 'search-eval'
LANGFUSE_EXPERIMENT = 'search-ranking'


class QueryCase(TypedDict):
    query: str
    relevant_ids: list[str]


@dataclass
class MetricObj:
    label: str
    fn: Callable[[list[str], set[str]], float]
    max_fn: Callable[[set[str]], float] | None


def precision_at(ranked_ids: list[str], relevant: set[str], k: int) -> float:
    return sum(vacancy_id in relevant for vacancy_id in ranked_ids[:k]) / k


def max_precision_at(relevant: set[str], k: int) -> float:
    return min(len(relevant), k) / k


def reciprocal_rank(ranked_ids: list[str], relevant: set[str]) -> float:
    for rank, vacancy_id in enumerate(ranked_ids, start=1):
        if vacancy_id in relevant:
            return 1 / rank
    return 0.0


def recall_at(ranked_ids: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    hits = sum(vacancy_id in relevant for vacancy_id in ranked_ids[:k])
    return hits / len(relevant)


def max_recall_at(relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return min(len(relevant), k) / len(relevant)


def _dcg_at(ranked_ids: list[str], relevant: set[str], k: int) -> float:
    gain = 0.0
    for rank, vacancy_id in enumerate(ranked_ids[:k], start=1):
        if vacancy_id in relevant:
            gain += 1.0 / math.log2(rank + 1)
    return gain


def ndcg_at(ranked_ids: list[str], relevant: set[str], k: int) -> float:
    ideal_hits = min(len(relevant), k)
    if ideal_hits == 0:
        return 0.0
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return _dcg_at(ranked_ids, relevant, k) / idcg


def parse_date(value: str, tz: ZoneInfo) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=tz)


async def rank_query(
    query: str, date_from: datetime, date_to: datetime
) -> dict[str, list[str]]:
    text = query.strip()
    keywords = set(re.findall(evals_db.TOKEN_RE, text.lower()))

    model = resources.config['llm']['embedding_model']
    with propagate_attributes(trace_name='search-text-embed'):
        resp = await resources.llm.embeddings.create(
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
            )[:50]
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
    #            p@k  rr
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
    print()
    print(f'mean over {count} queries')
    for rank_name, sums in totals.items():
        rendered = '  '.join(
            f'{m.label}={total / count:.3f}'
            for m, total in zip(METRICS, sums, strict=True)
        )
        print(f'  {rank_name}  {rendered}')


def metrics_evaluator(
    *,
    input: Any,
    output: dict[str, list[str]],
    expected_output: Any,
    metadata: dict[str, Any] | None,
    **kwargs: Any,
) -> list[Evaluation]:
    relevant = set(expected_output['relevant_ids'])
    return [
        Evaluation(name=f'{rank_name}_{m.label}', value=m.fn(ids, relevant))
        for rank_name, ids in output.items()
        for m in METRICS
    ]


async def evaluate_langfuse(tz: ZoneInfo) -> None:
    dataset = resources.langfuse.get_dataset(LANGFUSE_DATASET)
    if not dataset.items:
        print(f'langfuse dataset {LANGFUSE_DATASET} is empty')
        return

    # precomputed rankings output
    # { query: { 'bm25': [...], ... } }
    ranked: dict[str, dict[str, list[str]]] = {}
    for item in dataset.items:
        date_from = parse_date(item.metadata['from'], tz)
        date_to = parse_date(item.metadata['to'], tz)
        ranked[item.id] = await rank_query(item.input['query'], date_from, date_to)

    def task(*, item: Any, **kwargs: Any) -> dict[str, list[str]]:
        return ranked[item.id]

    result = dataset.run_experiment(
        name=LANGFUSE_EXPERIMENT,
        task=task,
        evaluators=[metrics_evaluator],
    )
    print(result.format())


async def main(cloud_run: bool) -> None:
    await resources.start(start_llm=True)
    try:
        tz = ZoneInfo(resources.config['app']['time_zone'])

        if cloud_run:
            await evaluate_langfuse(tz)
            return

        test_data = json.loads(QUERIES_PATH.read_text())
        if not test_data:
            print(f'{QUERIES_PATH} is empty')
            return

        date_from = parse_date(test_data['from'], tz)
        date_to = parse_date(test_data['to'], tz)

        await evaluate(test_data['cases'], date_from, date_to)
    finally:
        await resources.stop()


if __name__ == '__main__':
    # docker compose run --rm -v ./tests:/app/tests app python -m tests.evals.eval_search
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--cloud',
        dest='cloud_run',
        action='store_true',
        help='run as a Langfuse experiment instead of locally on data/queries.json',
    )
    args = parser.parse_args()

    # python react typescript | max P@10=0.800, max R@20=1.000
    #   bm25  P@10=0.600  RR=1.000  R@20=1.000  nDCG@10=0.758
    #   cosine  P@10=0.500  RR=1.000  R@20=0.875  nDCG@10=0.674
    #   rrf  P@10=0.700  RR=1.000  R@20=1.000  nDCG@10=0.891
    # senior python fastapi postgresql | max P@10=1.000, max R@20=1.000
    #   bm25  P@10=0.500  RR=1.000  R@20=0.615  nDCG@10=0.508
    #   cosine  P@10=0.600  RR=1.000  R@20=0.769  nDCG@10=0.699
    #   rrf  P@10=0.900  RR=1.000  R@20=0.923  nDCG@10=0.915
    #
    # mean over 2 queries
    #   bm25  P@10=0.550  RR=1.000  R@20=0.808  nDCG@10=0.633
    #   cosine  P@10=0.550  RR=1.000  R@20=0.822  nDCG@10=0.687
    #   rrf  P@10=0.800  RR=1.000  R@20=0.962  nDCG@10=0.903

    k_10 = 10
    k_20 = 20
    METRICS = (
        MetricObj(
            label=f'P@{k_10}',
            fn=partial(precision_at, k=k_10),
            max_fn=partial(max_precision_at, k=k_10),
        ),
        MetricObj(label='RR', fn=reciprocal_rank, max_fn=None),
        MetricObj(
            label=f'R@{k_20}',
            fn=partial(recall_at, k=k_20),
            max_fn=partial(max_recall_at, k=k_20),
        ),
        MetricObj(
            label=f'nDCG@{k_10}',
            fn=partial(ndcg_at, k=k_10),
            max_fn=None,
        ),
    )
    asyncio.run(main(args.cloud_run))
