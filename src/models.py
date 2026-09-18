from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.enums import (
    EnglishLevel,
    JobFamily,
    Seniority,
    SkillDepth,
    SkillKind,
    Source,
    Status,
)
from src.shared.types import SmallIntEnum


class Base(DeclarativeBase):
    pass


class Vacancy(Base):
    __tablename__ = 'vacancies'
    __table_args__ = (
        UniqueConstraint('source', 'external_id', name='uq_vacancies_source_external_id'),
    )

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        primary_key=True,
        server_default=text('uuidv7()'),
    )
    source: Mapped[Source] = mapped_column(SmallIntEnum(Source))
    external_id: Mapped[str] = mapped_column(Text)

    category: Mapped[str] = mapped_column(Text)
    company: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[bytes] = mapped_column(LargeBinary(32))

    location_str: Mapped[str | None] = mapped_column(Text)
    location: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    salary_min: Mapped[int | None]
    salary_max: Mapped[int | None]
    salary_level: Mapped[str | None] = mapped_column(Text)
    experience: Mapped[float | None]
    english_level: Mapped[EnglishLevel | None] = mapped_column(SmallIntEnum(EnglishLevel))
    seniority: Mapped[Seniority | None] = mapped_column(SmallIntEnum(Seniority))

    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )
    # internal technical
    status: Mapped[Status] = mapped_column(SmallIntEnum(Status), default=Status.active)
    date_last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VacanciesActivity(Base):
    __tablename__ = 'vacancies_activity'
    __table_args__ = (
        Index(
            'uq_vacancy_id_date_ended_is_null',
            'vacancy_id',
            unique=True,
            postgresql_where='date_ended IS NULL',
        ),
        Index(
            'ix_va_vacancy_id_date_started',
            'vacancy_id',
            text('date_started DESC'),
        ),
    )

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        primary_key=True,
        server_default=text('uuidv7()'),
    )
    vacancy_id: Mapped[str] = mapped_column(ForeignKey('vacancies.id'))
    date_started: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    date_ended: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SkillLexicon(Base):
    __tablename__ = 'skill_lexicon'

    skill_name: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[SkillKind] = mapped_column(SmallIntEnum(SkillKind))
    expanded: Mapped[str | None]
    expanded_vector: Mapped[list[float] | None] = mapped_column(Vector(1536))
    embedding_model: Mapped[str | None]

    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )


class VacancyExtract(Base):
    __tablename__ = 'vacancy_extract'

    vacancy_id: Mapped[str] = mapped_column(
        ForeignKey('vacancies.id', ondelete='CASCADE'), primary_key=True
    )
    job_family: Mapped[JobFamily] = mapped_column(SmallIntEnum(JobFamily))
    prompt_version: Mapped[str]
    industry: Mapped[str | None]
    raw_response: Mapped[str]
    completeness: Mapped[float]

    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )


class VacancySkill(Base):
    __tablename__ = 'vacancy_skills'
    __table_args__ = (UniqueConstraint('vacancy_id', 'skill_name'),)

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        primary_key=True,
        server_default=text('uuidv7()'),
    )

    vacancy_id: Mapped[str] = mapped_column(
        ForeignKey('vacancy_extract.vacancy_id', ondelete='CASCADE')
    )
    skill_name: Mapped[str] = mapped_column(
        ForeignKey('skill_lexicon.skill_name', onupdate='CASCADE', ondelete='CASCADE')
    )
    depth: Mapped[SkillDepth] = mapped_column(SmallIntEnum(SkillDepth))
    importance: Mapped[float]
