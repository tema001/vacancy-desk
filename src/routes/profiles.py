import secrets

from fastapi import APIRouter, HTTPException, Response, status

import src.db as db
import src.queries as queries
from src.enums import ProfileStatus
from src.jobs import EXTRACT_PROFILE
from src.services.worker import app as worker
from src.shared.resources import resources
from src.shared.types import ItemUUID
from src.types import DataDict, ProfileCreateSchema, ProfileUpdateSchema

router = APIRouter(tags=['profiles'])


@router.post('/api/profiles', status_code=status.HTTP_202_ACCEPTED)
async def create_new_profile(body: ProfileCreateSchema) -> DataDict:
    name = body.name or f'Noname-{secrets.token_hex(3)}'

    async with resources.engine.begin() as conn:
        pending_id = await db.select_pending_profile_id(conn)
        if pending_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={'profile_id': pending_id},
            )

        profile_id = await db.insert_new_profile(
            conn, data={'text': body.text, 'name': name}
        )

    await worker.configure_task(
        EXTRACT_PROFILE,
        queueing_lock=f'profile-extract:{profile_id}',
        lock=profile_id,
    ).defer_async(profile_id=profile_id)

    return {'id': profile_id}


@router.get('/api/profiles')
async def get_all_profiles() -> DataDict:
    return await queries.get_all_profiles()


@router.get('/api/profiles/{profile_id}')
async def get_profile(profile_id: ItemUUID) -> DataDict:
    profile = await queries.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return profile


@router.patch('/api/profiles/{profile_id}')
async def update_profile(profile_id: ItemUUID, body: ProfileUpdateSchema) -> Response:
    async with resources.engine.begin() as conn:
        row = await db.select_profile_status(conn, profile_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        if row['status'] != ProfileStatus.ready:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={'profile_id': profile_id},
            )

        await db.update_profile(conn, profile_id, data={'is_selected': body.is_selected})

    return Response(status_code=status.HTTP_200_OK)


@router.delete('/api/profiles/{profile_id}')
async def delete_profile(profile_id: ItemUUID) -> Response:
    async with resources.engine.begin() as conn:
        row = await db.select_profile_status(conn, profile_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        if row['status'] == ProfileStatus.pending:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={'profile_id': profile_id},
            )

        await db.delete_profile(conn, profile_id)

    return Response(status_code=status.HTTP_200_OK)
