import math
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

type RankSeq = Sequence[tuple[str, Any]]

SIMILARITY_THRESHOLD = 0.38
RRF_K = 60


@dataclass(slots=True)
class _VacancyScore:
    total_importance: float
    weighted_sum: float = 0.0


def _depth_fit(user_depth: int, required_depth: int) -> float:
    if user_depth >= required_depth:
        return 1.0
    return user_depth / required_depth


def rank_vacancy_matches(
    rows: Sequence[Any], sum_percentile: float | None
) -> list[tuple[str, float]]:
    """
    Returns ranked by score tuple(vacancy_id, match_score)
    """
    scores: dict[str, _VacancyScore] = {}

    for row in rows:
        vacancy_id = row['id']
        if vacancy_id not in scores:
            vacancy_score = _VacancyScore(total_importance=row['total_importance'])
            scores[vacancy_id] = vacancy_score
        else:
            vacancy_score = scores[vacancy_id]

        similarity = min(row['similarity'], 1.0)
        if similarity < SIMILARITY_THRESHOLD:
            continue

        depth_fit = _depth_fit(
            user_depth=int(row['user_depth']),
            required_depth=int(row['required_depth']),
        )
        vacancy_score.weighted_sum += row['importance'] * similarity * depth_fit

    result = []
    for vacancy_id, item in scores.items():
        if item.total_importance <= 0:
            continue

        if sum_percentile:
            completeness = min(1, item.total_importance / sum_percentile)
        else:
            completeness = 1

        score = (100.0 * item.weighted_sum / item.total_importance) * completeness
        result.append((vacancy_id, round(score, 3)))

    result.sort(key=lambda item: item[1], reverse=True)
    return result


# TODO: Add gin index. Compare with pg_search
def rank_bm25(
    keywords: Collection[str],
    documents: Sequence[Mapping[str, Any]],
    N: int,
    avg_dl: float,
) -> list[tuple[str, float]]:
    """
    Returns ranked by score tuple(vacancy_id, bm25_score)
    """
    kw_doc_c = Counter()
    kw_reps = []

    for doc in documents:
        counter = Counter()
        for term in doc['tokens']:
            if term in keywords:
                counter[term] += 1

        for term, count in counter.items():
            if count > 0:
                kw_doc_c[term] += 1

        kw_reps.append(counter)

    k = 1.2
    b = 0.75

    scores = []
    for i, doc in enumerate(documents):
        score = 0
        doc_len = len(doc['tokens'])
        for t in keywords:
            idf = math.log((N - kw_doc_c[t] + 0.5) / (kw_doc_c[t] + 0.5) + 1)
            m = (
                kw_reps[i][t]
                * (k + 1)
                / (kw_reps[i][t] + k * (1 - b + b * (doc_len / avg_dl)))
            )

            score += idf * m

        scores.append((doc['id'], score))

    scores.sort(key=lambda item: item[1], reverse=True)
    return scores


def rrf(bm25_ranks: RankSeq, vector_ranks: RankSeq) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion"""
    scores = {}
    for rank, (vacancy_id, _) in enumerate(bm25_ranks, start=1):
        scores[vacancy_id] = scores.get(vacancy_id, 0.0) + 1 / (RRF_K + rank)
    for rank, (vacancy_id, _) in enumerate(vector_ranks, start=1):
        scores[vacancy_id] = scores.get(vacancy_id, 0.0) + 1 / (RRF_K + rank)

    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
