from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user, require_character
from app.models import Character, User
from app.schemas import CharacterCreate, CharacterOut, CharacterUpdate, RelationshipOut
from app.services.relationship import get_or_create_relationship

router = APIRouter(prefix="/characters", tags=["characters"])


@router.get("", response_model=list[CharacterOut])
async def list_characters(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Character]:
    result = await session.execute(
        select(Character).where(Character.owner_user_id == user.id).order_by(Character.created_at)
    )
    return list(result.scalars().all())


@router.post("", response_model=CharacterOut, status_code=201)
async def create_character(
    payload: CharacterCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Character:
    character = Character(owner_user_id=user.id, **payload.model_dump())
    session.add(character)
    await session.flush()
    await get_or_create_relationship(session, user.id, character.id)
    await session.commit()
    await session.refresh(character)
    return character


@router.get("/{character_id}", response_model=CharacterOut)
async def get_character(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Character:
    return await require_character(character_id, user, session)


@router.patch("/{character_id}", response_model=CharacterOut)
async def update_character(
    character_id: uuid.UUID,
    payload: CharacterUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Character:
    character = await require_character(character_id, user, session)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(character, field, value)
    await session.commit()
    await session.refresh(character)
    return character


@router.get("/{character_id}/relationship", response_model=RelationshipOut)
async def get_relationship(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    character = await require_character(character_id, user, session)
    relationship = await get_or_create_relationship(session, user.id, character.id)
    await session.commit()
    await session.refresh(relationship)
    return relationship
