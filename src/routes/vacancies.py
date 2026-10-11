from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, status

import src.queries as queries
from src.types import DataDict, ParamsSchema

router = APIRouter(tags=['vacancies'])


@router.post('/api/vacancies')
async def get_vacancies(params: ParamsSchema) -> DataDict:
    return await queries.get_vacancies(params)


@router.post('/api/vacancies/score')
async def get_scored_vacancies() -> DataDict:
    result = await queries.get_scored_vacancies()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='No selected profile found',
        )

    return result


@router.post('/api/hybrid-search')
async def process_hybrid_search(
    query: Annotated[str, Body(min_length=3, embed=True)],
) -> DataDict:
    return await queries.get_search_response(query)
