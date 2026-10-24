from datetime import datetime
from enum import IntEnum
from typing import Any
from zoneinfo import ZoneInfo

from src.shared.resources import resources


def dt_now() -> datetime:
    tz = resources.config['app']['time_zone']
    return datetime.now(ZoneInfo(tz))


def enum_name(value: Any) -> str | None:
    if isinstance(value, IntEnum):
        return value.name
    return None
