from src.enums import Seniority

_INTERN = (
    'internship',
    'intern',
    'trainee',
    'стажування',
)

_LEAD = (
    'engineering manager',
    'tech lead',
    'team lead',
    'teamlead',
    'head of',
    'тімлід',
    'principal',
    'architect',
    'lead',
)

_LEVELS: dict[str, Seniority] = {
    'internship': Seniority.intern,
    'intern': Seniority.intern,
    'trainee': Seniority.intern,
    'стажер': Seniority.intern,
    'junior': Seniority.junior,
    'джуніор': Seniority.junior,
    'mid-level': Seniority.middle,
    'middle': Seniority.middle,
    'мідл': Seniority.middle,
    'mid': Seniority.middle,
    'senior': Seniority.senior,
    'сіньйор': Seniority.senior,
}

_RANGE_SEP = ('/', '|', ' or ', ' чи ')
_LEVEL_WORDS = tuple(sorted(_LEVELS, key=len, reverse=True))


def _has_phrase(text: str, phrase: str) -> bool:
    start = 0
    while True:
        i = text.find(phrase, start)
        if i < 0:
            return False

        left = i == 0 or not text[i - 1].isalnum()
        right = i + len(phrase)
        if left and (right == len(text) or not text[right].isalnum()):
            return True

        start = i + 1


def _left_phrase(text: str) -> Seniority | None:
    for word in _LEVEL_WORDS:
        if not text.endswith(word):
            continue
        start = len(text) - len(word)
        if start == 0 or not text[start - 1].isalnum():
            return _LEVELS[word]
    return None


def _right_phrase(text: str) -> Seniority | None:
    for word in _LEVEL_WORDS:
        if not text.startswith(word):
            continue
        end = len(word)
        if end == len(text) or not text[end].isalnum():
            return _LEVELS[word]
    return None


def _range_level(text: str) -> Seniority | None:
    if not any(sep in text for sep in _RANGE_SEP):
        return None

    for sep in _RANGE_SEP:
        i = text.find(sep)
        if i < 0:
            continue
        left = _left_phrase(text[:i].rstrip())
        right = _right_phrase(text[i + len(sep) :].lstrip())
        if left and right:
            return min(left, right)

    return None


def seniority_from_years(years: float) -> Seniority:
    if years < 2:
        return Seniority.junior
    if years < 5:
        return Seniority.middle
    return Seniority.senior


def seniority_from_title(title: str, years: float | None = None) -> Seniority | None:
    text = title.lower()
    if any(_has_phrase(text, word) for word in _INTERN):
        return Seniority.intern

    if found := _range_level(text):
        return found

    if any(_has_phrase(text, word) for word in _LEAD):
        return Seniority.lead

    levels = [_LEVELS[word] for word in _LEVEL_WORDS if _has_phrase(text, word)]
    if levels:
        return min(levels)

    if years:
        return seniority_from_years(years)

    return None
