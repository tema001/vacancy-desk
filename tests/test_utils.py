from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from src.types import ExperiencePeriod
from src.utils import months_from_periods


@pytest.fixture
def freeze_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        'src.utils.dt_now',
        lambda: datetime(2026, 9, 2, tzinfo=ZoneInfo('Europe/Kyiv')),
    )


def test_contiguous_jobs_merge_to_calendar_span(freeze_now) -> None:
    periods = [
        ExperiencePeriod(start='2020-03', end='2021-06'),
        ExperiencePeriod(start='2021-06', end='2022-03'),
        ExperiencePeriod(start='2022-03', end='2023-05'),
        ExperiencePeriod(start='2023-05', end='2023-09'),
        ExperiencePeriod(start='2023-09', end=None),
    ]

    assert months_from_periods(periods) == 78.0


def test_overlapping_jobs_are_not_double_counted(freeze_now) -> None:
    periods = [
        ExperiencePeriod(start='2022-01', end='2023-06'),
        ExperiencePeriod(start='2022-10', end='2024-01'),
    ]

    assert months_from_periods(periods) == 24.0


def test_gap_keeps_separate_spans(freeze_now) -> None:
    periods = [
        ExperiencePeriod(start='2020-01', end='2020-07'),
        ExperiencePeriod(start='2021-01', end='2021-07'),
    ]

    assert months_from_periods(periods) == 12.0


def test_explicit_empty_and_invalid_periods(freeze_now) -> None:
    assert months_from_periods([]) is None
    assert (
        months_from_periods([ExperiencePeriod(start='Sep 2023', end='2024-01')]) is None
    )
