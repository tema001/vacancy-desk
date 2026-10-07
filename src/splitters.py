import re

CHUNK_CHARS = 2000
CHUNK_OVERLAP = 150
MIN_CHUNK_CHARS = 200


def split_vacancy_text(title: str, body: str) -> list[str]:
    if not body:
        return []

    header = f'Title: {title}\n\n'
    if len(header) + len(body) <= CHUNK_CHARS:
        return [f'{header}{body}']

    budget = CHUNK_CHARS - len(header)
    return [
        f'{header}{part}' for part in _split_into_chunks(body, budget, CHUNK_OVERLAP)
    ]


def _split_into_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    paragraphs = [part for part in re.split(r'\n\s*\n', text) if part]
    if not paragraphs:
        chunks = _split_long_text(text, chunk_size, overlap)
    else:
        chunks = []
        draft_chunk = ''
        for paragraph in paragraphs:
            if len(paragraph) > chunk_size:
                if draft_chunk:
                    chunks.append(draft_chunk)
                    draft_chunk = ''
                chunks.extend(_split_long_text(paragraph, chunk_size, overlap))
                continue

            candidate = f'{draft_chunk}\n\n{paragraph}' if draft_chunk else paragraph
            if len(candidate) <= chunk_size:
                draft_chunk = candidate
                continue

            chunks.append(draft_chunk)
            overlap_text = _get_overlap_text(draft_chunk, overlap)
            draft_chunk = f'{overlap_text}\n\n{paragraph}' if overlap_text else paragraph
            if len(draft_chunk) > chunk_size:
                draft_chunk = paragraph

        if draft_chunk:
            chunks.append(draft_chunk)

    if len(chunks) > 1 and len(chunks[-1]) < MIN_CHUNK_CHARS:
        chunks[-2] = f'{chunks[-2]}\n\n{chunks[-1]}'
        chunks.pop()
    return chunks


def _get_overlap_text(text: str, overlap: int) -> str:
    """Return the ending of this chunk to copy onto the next chunk.

    Looks at the last `overlap` characters. If a period or newline is there,
    returns the text after it. Otherwise returns an empty string.
    """
    if overlap <= 0 or not text:
        return ''

    cut = max(len(text) - overlap, 0)
    start = _boundary_after(text, cut, len(text))
    if start is None:
        return ''
    return text[start:].lstrip()


def _split_long_text(text: str, size: int, overlap: int) -> list[str]:
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = _boundary_after(text, end, len(text))
            if boundary is not None:
                end = boundary
            else:
                split_at = text.rfind(' ', start, end)
                if split_at > start:
                    end = split_at

        part = text[start:end].strip()
        if part:
            parts.append(part)
        if end >= len(text):
            break
        start = _next_overlap_start(text, start, end, overlap)
    return parts


def _next_overlap_start(text: str, start: int, end: int, overlap: int) -> int:
    """Return where the next chunk should start in `text`.

    Checks the last `overlap` characters of the chunk that just ended.
    If a period or newline is there, the next chunk starts just after it,
    so that ending is copied. If not, the next chunk starts at `end`.
    """
    cut = max(end - overlap, start + 1)
    boundary = _boundary_after(text, cut, end)
    if boundary is None or boundary <= start:
        return end
    return boundary


def _boundary_after(text: str, cut: int, end: int) -> int | None:
    """Return the position right after the first period or newline.

    The search is only inside `text[cut:end]`. Returns None if that range
    has no period and no newline.
    """
    window = text[cut:end]
    dot = window.find('.')
    newline = window.find('\n')
    positions = [index for index in (dot, newline) if index != -1]
    if not positions:
        return None
    return cut + min(positions) + 1
