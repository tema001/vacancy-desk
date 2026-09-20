import pytest
import sqlalchemy as sa
from src.shared.resources import resources


@pytest.fixture(scope='session')
async def init_resources():
    await resources.start(start_llm=False)
    yield
    await resources.stop()


@pytest.fixture
async def db(init_resources):
    yield
    async with resources.engine.begin() as conn:
        await conn.execute(
            sa.text(
                'TRUNCATE vacancy_skills, vacancy_extract, vacancies_activity,'
                ' vacancies, skill_lexicon RESTART IDENTITY CASCADE'
            )
        )
