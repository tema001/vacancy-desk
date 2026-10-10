import re
from collections.abc import Iterable, Iterator

CHUNK_CHARS = 2000
CHUNK_OVERLAP = 150
MIN_CHUNK_CHARS = 200

_LEVELS = (
    re.compile(r'.+?(?:\n\s*\n|\Z)', re.S),
    re.compile(r'[^.\n]*[.\n]\s*|[^.\n]+'),
    re.compile(r'\S+\s*|\s+'),
)
_BOUNDARY = re.compile(r'[.\n]')


def split_vacancy_text(title: str, body: str) -> list[str]:
    if not body.strip():
        return []
    header = f'Title: {title}\n\n'

    if len(header) + len(body) <= CHUNK_CHARS:
        return [f'{header}{body}']

    budget = CHUNK_CHARS - len(header)
    chunks = _merge(_pieces(body, budget), budget, CHUNK_OVERLAP)

    return [f'{header}{chunk}' for chunk in chunks]


def _pieces(text: str, size: int, level: int = 0) -> Iterator[str]:
    if len(text) <= size:
        yield text
    elif level == len(_LEVELS):
        yield from (text[i : i + size] for i in range(0, len(text), size))
    else:
        for part in _LEVELS[level].findall(text):
            yield from _pieces(part, size, level + 1)


def _merge(pieces: Iterable[str], size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    draft = ''
    carried = 0
    for piece in pieces:
        if draft and len(draft) + len(piece) > size:
            chunks.append(draft)
            tail = _overlap_tail(draft, overlap)
            draft = tail if len(tail) + len(piece) <= size else ''
            carried = len(draft)
        draft += piece

    if chunks and len(draft) - carried < MIN_CHUNK_CHARS:
        chunks[-1] += draft[carried:]
    else:
        chunks.append(draft)

    return [chunk for chunk in chunks]


def _overlap_tail(text: str, overlap: int) -> str:
    match = _BOUNDARY.search(text, max(len(text) - overlap, 0))
    tail = text[match.end() :] if match else ''

    return tail if tail.strip() else ''
