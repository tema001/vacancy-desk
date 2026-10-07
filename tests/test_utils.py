from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from src.splitters import CHUNK_CHARS, MIN_CHUNK_CHARS, split_vacancy_text
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


def test_short_description_is_one_chunk() -> None:
    chunks = split_vacancy_text('Backend', 'Python and PostgreSQL')

    assert chunks == ['Title: Backend\n\nPython and PostgreSQL']


def test_empty_description_has_no_chunks() -> None:
    assert split_vacancy_text('Backend', '') == []


def test_long_description_keeps_title_and_the_ending() -> None:
    paragraph = 'requirement ' * 200
    description = f'{paragraph.strip()}\n\nbenefits and visa'
    chunks = split_vacancy_text('Backend', description)

    assert len(chunks) > 1
    assert all(chunk.startswith('Title: Backend\n\n') for chunk in chunks)
    assert all(len(chunk) >= MIN_CHUNK_CHARS for chunk in chunks)
    assert chunks[-1].endswith('benefits and visa')


def test_chunk_continues_to_the_next_sentence() -> None:
    sentence = 'We need strong Python skills. '
    chunks = split_vacancy_text('Backend', sentence * 100)
    header = 'Title: Backend\n\n'
    bodies = [chunk.removeprefix(header) for chunk in chunks]

    assert len(bodies) > 1
    assert all(body.endswith('.') for body in bodies)
    assert len(bodies[0]) >= CHUNK_CHARS - len(header)


def test_overlap_starts_after_a_sentence() -> None:
    sentence = 'We need strong Python skills. '
    chunks = split_vacancy_text('Backend', sentence * 100)
    bodies = [chunk.removeprefix('Title: Backend\n\n') for chunk in chunks]

    assert len(bodies) > 1
    assert all(body.startswith('We need strong Python skills.') for body in bodies[1:])


def test_overlap_starts_after_a_newline() -> None:
    line = 'Build APIs with FastAPI and PostgreSQL\n'
    chunks = split_vacancy_text('Backend', line * 80)
    bodies = [chunk.removeprefix('Title: Backend\n\n') for chunk in chunks]

    assert len(bodies) > 1
    assert all(body.startswith('Build APIs with FastAPI') for body in bodies[1:])


def test_short_last_chunk_is_appended_without_counting_the_title() -> None:
    title = 'Senior Software Engineer (Search Intelligence and AI)'
    header = f'Title: {title}\n\n'
    tail = (
        'We are looking for someone capable of owning significant technical '
        'areas independently and helping shape engineering decisions as the '
        'platform evolves.'
    )
    description = f'{"We need strong Python skills. " * 120}\n\n{tail}'
    chunks = split_vacancy_text(title, description)
    bodies = [chunk.removeprefix(header) for chunk in chunks]

    assert len(header) + len(tail) >= MIN_CHUNK_CHARS
    assert len(tail) < MIN_CHUNK_CHARS
    assert all(len(body) >= MIN_CHUNK_CHARS for body in bodies)
    assert bodies[-1].endswith(tail)


def test_overlap_without_boundary_does_not_split_words() -> None:
    chunks = split_vacancy_text('Backend', 'requirement ' * 400)
    bodies = [chunk.removeprefix('Title: Backend\n\n') for chunk in chunks]

    assert len(bodies) > 1
    assert all(body.startswith('requirement') for body in bodies)
