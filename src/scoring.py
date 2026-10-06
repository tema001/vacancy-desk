from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from src.types import DataDict

SIMILARITY_THRESHOLD = 0.38


@dataclass(slots=True)
class _VacancyScore:
    total_importance: float
    weighted_sum: float = 0.0


def _depth_fit(user_depth: int, required_depth: int) -> float:
    if user_depth >= required_depth:
        return 1.0
    return user_depth / required_depth


def score_vacancy_matches(
    rows: Sequence[Any], sum_percentile: float | None
) -> list[DataDict]:
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

    result: list[DataDict] = []
    for vacancy_id, item in scores.items():
        if item.total_importance <= 0:
            continue

        if sum_percentile:
            completeness = min(1, item.total_importance / sum_percentile)
        else:
            completeness = 1

        score = (100.0 * item.weighted_sum / item.total_importance) * completeness
        result.append(
            {
                'id': vacancy_id,
                'score': round(score, 2),
            }
        )

    result.sort(key=lambda vacancy: vacancy['score'], reverse=True)
    return result
