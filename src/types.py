import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import Annotated, Any, Self

from pydantic import BaseModel, Field, StringConstraints

from src.enums import (
    EnglishLevel,
    JobFamily,
    Seniority,
    SkillDepth,
    SkillKind,
    VacancyStatus,
)
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


class ProfileCreateSchema(BaseModel):
    text: Annotated[str, StringConstraints(min_length=10, max_length=5000)]
    name: Annotated[str, StringConstraints(min_length=5, max_length=100)] | None = None


class ProfileUpdateSchema(BaseModel):
    is_selected: bool


class SkillExtract(BaseModel):
    canonical: str
    depth: EnumField[SkillDepth]
    kind: EnumField[SkillKind] = Field(default=SkillKind.hard)

    @cached_property
    def normalized(self) -> str:
        return re.sub(r'[/_.\-]+', ' ', self.canonical.lower()).strip()

    def prefer(self, other: Self) -> Self:
        return other if other.depth > self.depth else self


class VacancySkillExtract(SkillExtract):
    importance: float = Field(ge=0, le=1)

    def prefer(self, other: Self) -> Self:
        if other.depth != self.depth:
            return other if other.depth > self.depth else self
        return other if other.importance > self.importance else self


class VacancyLLMExtract(BaseModel):
    job_family: EnumField[JobFamily]
    industry: str | None = None
    skills: list[VacancySkillExtract]


class ExperiencePeriod(BaseModel):
    start: str  # YYYY-MM
    end: str | None = None


class ProfileLLMExtract(BaseModel):
    skills: list[SkillExtract]
    job_families: list[EnumField[JobFamily]] | None = Field(default=None, max_length=5)
    experience: float | None = None
    experience_periods: list[ExperiencePeriod] = Field(default_factory=list)
    eng_lvl: EnumField[EnglishLevel] | None = None
    seniority: EnumField[Seniority] | None = None


class LexiconItem(BaseModel):
    skill_name: str
    expanded: str


class LexiconExpand(BaseModel):
    items: list[LexiconItem]


@dataclass
class ParsedPage:
    status: VacancyStatus

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
class InactivePage(ParsedPage):
    status: VacancyStatus = VacancyStatus.inactive

    def to_db(self) -> DataDict:
        return {
            **self.last_seen(),
            'params_hash': None,
        }


@dataclass
class FullParsedPage(ParsedPage):
    company: str
    title: str
    description: str
    status: VacancyStatus
    location_str: str | None
    location: list[str] | None
    experience: float | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_level: str | None = None
    english_level: EnglishLevel | None = None
    seniority: Seniority | None = None

    @cached_property
    def params_hash(self) -> bytes:
        _data = (
            f'{self.title},'
            f'{self.salary_min},'
            f'{self.salary_max},'
            f'{self.salary_level},'
            f'{self.experience},'
            f'{self.english_level}'
        )
        return hashlib.sha256(_data.encode()).digest()

    @cached_property
    def description_hash(self) -> bytes:
        return hashlib.sha256(self.description.encode()).digest()

    def same_params(self, stored: bytes | None) -> bool:
        return stored == self.params_hash

    def same_description(self, stored: bytes | None) -> bool:
        return stored == self.description_hash

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
            'params_hash': self.params_hash,
            'description_hash': self.description_hash,
        }


@dataclass(slots=True)
class ParseJob:
    vacancy_id: str
    url: str
    params_hash: bytes | None
    desc_hash: bytes | None

    @classmethod
    def from_db(cls, row: Mapping[str, Any]) -> Self:
        return cls(
            vacancy_id=row['id'],
            url=row['url'],
            params_hash=row['params_hash'],
            desc_hash=row['description_hash'],
        )


@dataclass(slots=True)
class ScoringProfile:
    id: str
    name: str
    job_families: list[int]
    english_level: EnglishLevel | None
    experience: float | None
    seniority: Seniority | None

    @classmethod
    def from_db(cls, row: Mapping[str, Any]) -> Self:
        return cls(
            id=row['id'],
            name=row['name'],
            job_families=row['job_families'],
            english_level=row['english_level'],
            experience=row['experience'],
            seniority=row['seniority'],
        )
