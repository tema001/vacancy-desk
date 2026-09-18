from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from src.types import DataDict

SIMILARITY_THRESHOLD = 0.38

_MATCH_FIELDS = {
    'required_depth',
    'importance',
    'similarity',
    'user_depth',
    'user_skill_name',
    'total_importance',
}


@dataclass(slots=True)
class _VacancyScore:
    vacancy: DataDict
    total_importance: float
    weighted_sum: float = 0.0


def _depth_fit(user_depth: int, required_depth: int) -> float:
    if user_depth >= required_depth:
        return 1.0
    return user_depth / required_depth


def score_vacancy_matches(rows: Sequence[Any]) -> list[DataDict]:
    scores: dict[str, _VacancyScore] = {}

    for row in rows:
        vacancy_id = str(row['id'])
        if vacancy_id not in scores:
            vacancy = {
                key: value for key, value in row.items() if key not in _MATCH_FIELDS
            }
            scores[vacancy_id] = _VacancyScore(
                vacancy=vacancy,
                total_importance=row['total_importance'],
            )

        similarity = min(row['similarity'], 1.0)
        if similarity < SIMILARITY_THRESHOLD:
            continue

        depth_fit = _depth_fit(
            user_depth=int(row['user_depth']),
            required_depth=int(row['required_depth']),
        )
        scores[vacancy_id].weighted_sum += row['importance'] * similarity * depth_fit

    result: list[DataDict] = []
    for item in scores.values():
        if item.total_importance <= 0:
            continue

        item.vacancy['score'] = round(
            100.0 * item.weighted_sum / item.total_importance, 2
        )
        result.append(item.vacancy)

    result.sort(key=lambda vacancy: vacancy['score'], reverse=True)
    return result
