from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user, require_character
from app.models import MemoryItem, User
from app.schemas import (
    DeleteResponse,
    MemoryCreate,
    MemoryForgetResponse,
    MemoryOut,
    MemoryResolveResponse,
    MemoryUpdate,
)
from app.services.memory import (
    MemoryCaptureError,
    MemoryConflictResolutionError,
    clear_memories,
    create_memory,
    delete_memory,
    forget_low_value_memories,
    forget_memory,
    memory_preferences_from_boundaries,
    resolve_memory_conflict,
    restore_memory,
    retrieve_memories,
    update_memory,
)
from app.services.relationship import get_current_relationship
from app.services.safety import adult_gate_status

router = APIRouter(prefix="/characters/{character_id}/memories", tags=["memory"])


@router.get("", response_model=list[MemoryOut])
async def list_memories(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    state: Literal["active", "forgotten", "all"] = Query(default="active"),
    scope: Literal["general", "adult"] = Query(default="general"),
) -> list[MemoryItem]:
    character = await require_character(character_id, user, session)
    conditions = [
        MemoryItem.user_id == user.id,
        MemoryItem.character_id == character.id,
        MemoryItem.scope == scope,
    ]
    if state == "active":
        conditions.append(MemoryItem.forgotten_at.is_(None))
    elif state == "forgotten":
        conditions.append(MemoryItem.forgotten_at.is_not(None))
    result = await session.execute(
        select(MemoryItem).where(*conditions).order_by(MemoryItem.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=MemoryOut, status_code=201)
async def add_memory(
    character_id: uuid.UUID,
    payload: MemoryCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MemoryItem:
    character = await require_character(character_id, user, session)
    if payload.scope == "adult":
        relationship = await get_current_relationship(session, user.id, character.id)
        gate = adult_gate_status(user, character, "adult", relationship=relationship)
        preferences = memory_preferences_from_boundaries(character.boundaries_json)
        if gate["allowed"] is not True:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Adult continuity is unavailable until every age, consent, "
                    "and relationship gate passes."
                ),
            )
        if (
            preferences.get("adult_memory_storage") is not True
            or preferences.get("private_mode_default") is True
        ):
            raise HTTPException(
                status_code=409,
                detail="Adult memory storage is off for this character.",
            )
    try:
        memory = await create_memory(
            session,
            user_id=user.id,
            character_id=character.id,
            content=payload.content,
            scope=payload.scope,
            memory_type=payload.memory_type,
            importance=payload.importance,
            confidence=payload.confidence,
            emotional_weight=payload.emotional_weight,
            pinned=payload.pinned,
        )
    except MemoryCaptureError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(memory)
    return memory


@router.get("/search", response_model=list[MemoryOut])
async def search_memories(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str = Query(default="", max_length=120),
    scope: Literal["general", "adult"] = Query(default="general"),
) -> list[MemoryItem]:
    character = await require_character(character_id, user, session)
    memories = await retrieve_memories(
        session,
        user_id=user.id,
        character_id=character.id,
        query=q,
        limit=10,
        scopes=(scope,),
    )
    await session.commit()
    return memories


@router.post("/forget", response_model=MemoryForgetResponse)
async def forget_memories(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MemoryForgetResponse:
    character = await require_character(character_id, user, session)
    forgotten = await forget_low_value_memories(session, user.id, character.id)
    await session.commit()
    return MemoryForgetResponse(forgotten=forgotten)


@router.delete("", response_model=DeleteResponse)
async def delete_all_memories(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeleteResponse:
    character = await require_character(character_id, user, session)
    deleted = await clear_memories(session, user.id, character.id)
    await session.commit()
    return DeleteResponse(deleted=deleted)


@router.patch("/{memory_id}", response_model=MemoryOut)
async def patch_memory(
    character_id: uuid.UUID,
    memory_id: uuid.UUID,
    payload: MemoryUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MemoryItem:
    character = await require_character(character_id, user, session)
    memory = await _require_memory(session, user.id, character.id, memory_id)
    try:
        await update_memory(
            memory=memory,
            session=session,
            **payload.model_dump(exclude_unset=True),
        )
    except MemoryCaptureError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(memory)
    return memory


@router.post("/{memory_id}/forget", response_model=MemoryOut)
async def forget_one_memory(
    character_id: uuid.UUID,
    memory_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MemoryItem:
    character = await require_character(character_id, user, session)
    memory = await _require_memory(session, user.id, character.id, memory_id)
    await forget_memory(session, memory)
    await session.commit()
    await session.refresh(memory)
    return memory


@router.post("/{memory_id}/restore", response_model=MemoryOut)
async def restore_one_memory(
    character_id: uuid.UUID,
    memory_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MemoryItem:
    character = await require_character(character_id, user, session)
    memory = await _require_memory(session, user.id, character.id, memory_id)
    await restore_memory(session, memory)
    await session.commit()
    await session.refresh(memory)
    return memory


@router.post("/{memory_id}/resolve", response_model=MemoryResolveResponse)
async def resolve_memory(
    character_id: uuid.UUID,
    memory_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MemoryResolveResponse:
    character = await require_character(character_id, user, session)
    memory = await _require_memory(session, user.id, character.id, memory_id)
    try:
        resolved_memory, removed_ids = await resolve_memory_conflict(session, memory)
    except MemoryConflictResolutionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(resolved_memory)
    return MemoryResolveResponse(
        memory=resolved_memory,
        removed=len(removed_ids),
        removed_memory_ids=removed_ids,
    )


@router.delete("/{memory_id}", response_model=DeleteResponse)
async def remove_memory(
    character_id: uuid.UUID,
    memory_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeleteResponse:
    character = await require_character(character_id, user, session)
    memory = await _require_memory(session, user.id, character.id, memory_id)
    await delete_memory(session, memory)
    await session.commit()
    return DeleteResponse(deleted=1)


async def _require_memory(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    memory_id: uuid.UUID,
) -> MemoryItem:
    result = await session.execute(
        select(MemoryItem).where(
            MemoryItem.id == memory_id,
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
        )
    )
    memory = result.scalar_one_or_none()
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory was not found.")
    return memory
