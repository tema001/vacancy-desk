from datetime import datetime
from zoneinfo import ZoneInfo

from src.shared.resources import resources


def dt_now() -> datetime:
    tz = resources.config['app']['time_zone']
    return datetime.now(ZoneInfo(tz))
