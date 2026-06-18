from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user, require_character
from app.models import Character, User
from app.schemas import (
    AdultGateStatus,
    CharacterCreate,
    CharacterOut,
    CharacterUpdate,
    RelationshipOut,
)
from app.services.relationship import get_current_relationship, get_or_create_relationship
from app.services.safety import adult_gate_status, validate_character_adult_configuration

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
    validate_character_adult_configuration(
        explicit_age=payload.explicit_age,
        adult_mode_allowed=payload.adult_mode_allowed,
    )
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
    updates = payload.model_dump(exclude_unset=True)
    validate_character_adult_configuration(
        explicit_age=updates.get("explicit_age", character.explicit_age),
        adult_mode_allowed=updates.get("adult_mode_allowed", character.adult_mode_allowed),
    )
    for field, value in updates.items():
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
    relationship = await get_current_relationship(session, user.id, character.id)
    await session.commit()
    await session.refresh(relationship)
    return relationship


@router.get("/{character_id}/adult-status", response_model=AdultGateStatus)
async def get_adult_status(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    character = await require_character(character_id, user, session)
    return adult_gate_status(user, character, "adult")
