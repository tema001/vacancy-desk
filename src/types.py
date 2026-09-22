import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints

from src.enums import EnglishLevel, JobFamily, Seniority, SkillDepth, SkillKind, Status
from src.shared.types import EnumField
from src.shared.utils import dt_now

type DataDict = dict[str, Any]


class ParamsSchema(BaseModel):
    exp: int | None = Field(default=None, gt=0, lt=20)  # years
    salary_min: int | None = Field(default=None, gt=0, lt=100_000)
    categories: (
        list[Annotated[str, StringConstraints(min_length=1, max_length=20)]] | None
    ) = Field(default=None, max_length=10)
    eng_lvl: EnglishLevel | None = None

    active_only: bool = False

    limit: int = Field(default=10, gt=0, le=100)
    order: int = Field(default=2, gt=0, le=2)  # 1 = asc, 2 = desc
    page: int = Field(default=1, gt=0, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


class CandidateSkill(BaseModel):
    skill_name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    depth: EnumField[SkillDepth]


class ScoringParamsSchema(ParamsSchema):
    skills: list[CandidateSkill] = Field(min_length=1, max_length=50)
    job_family: EnumField[JobFamily] | None = None
    english_level: EnumField[EnglishLevel] | None = None


class ExtractedSkill(BaseModel):
    canonical: str
    importance: float = Field(ge=0, le=1)
    depth: EnumField[SkillDepth]
    kind: EnumField[SkillKind] = Field(default=SkillKind.hard)

    @cached_property
    def normalized(self) -> str:
        return re.sub(r'[/_.\-]+', ' ', self.canonical.lower()).strip()


class VacancyLLMExtract(BaseModel):
    job_family: EnumField[JobFamily]
    industry: str | None = None
    skills: list[ExtractedSkill]


class LexiconItem(BaseModel):
    skill_name: str
    expanded: str


class LexiconExpand(BaseModel):
    items: list[LexiconItem]


@dataclass
class ParsedPage:
    status: Status

    @cached_property
    def timestamp(self) -> datetime:
        return dt_now()

    def last_seen(self) -> DataDict:
        return {
            'status': self.status,
            'date_last_seen': self.timestamp,
        }

    def to_db(self) -> DataDict:
        return self.last_seen()


@dataclass
class FullParsedPage(ParsedPage):
    company: str
    title: str
    description: str
    status: Status
    location_str: str | None
    location: list[str] | None
    experience: float | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_level: str | None = None
    english_level: EnglishLevel | None = None
    seniority: Seniority | None = None

    @cached_property
    def content_hash(self) -> bytes:
        _data = (
            f'{self.title},'
            f'{self.description},'
            f'{self.salary_min},'
            f'{self.salary_max},'
            f'{self.salary_level}'
        )
        return hashlib.sha256(_data.encode()).digest()

    def same_content(self, stored: bytes | None) -> bool:
        return stored == self.content_hash

    def to_db(self) -> DataDict:
        return {
            'company': self.company,
            'title': self.title,
            'description': self.description,
            'location_str': self.location_str,
            'location': self.location,
            'experience': self.experience,
            'salary_min': self.salary_min,
            'salary_max': self.salary_max,
            'salary_level': self.salary_level,
            'english_level': self.english_level,
            'seniority': self.seniority,
            ###
            'status': self.status,
            'date_last_seen': self.timestamp,
            'content_hash': self.content_hash,
        }


@dataclass(slots=True)
class ParseJob:
    vacancy_id: str
    url: str
    content_hash: bytes | None

    @classmethod
    def from_db(cls, data: Mapping[str, Any]) -> 'ParseJob':
        return cls(
            vacancy_id=data['id'],
            url=data['url'],
            content_hash=data['content_hash'],
        )
