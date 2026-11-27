import re
from datetime import datetime
from enum import IntEnum
from typing import Any, cast
from zoneinfo import ZoneInfo

from openai.types.responses import ResponseInputParam, ResponseTextConfigParam
from openai.types.shared_params.reasoning import Reasoning

from src.shared.resources import resources

JSON_TEXT: ResponseTextConfigParam = {'format': {'type': 'json_object'}}
LOW_REASONING: Reasoning = {'effort': 'low'}


def dt_now() -> datetime:
    tz = resources.config['app']['time_zone']
    return datetime.now(ZoneInfo(tz))


def enum_name(value: Any) -> str | None:
    if isinstance(value, IntEnum):
        return value.name
    return None


def normalize_skill_name(name: str) -> str:
    return re.sub(r'[/_.\-]+', ' ', name.lower()).strip()


def openai_input(compiled: object) -> str | ResponseInputParam:
    if isinstance(compiled, str):
        return compiled
    if isinstance(compiled, list):
        return cast(ResponseInputParam, compiled)
    raise TypeError(f'unexpected compiled prompt: {type(compiled).__name__}')
