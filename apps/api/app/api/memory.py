from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user, require_character
from app.models import MemoryItem, User
from app.schemas import DeleteResponse, MemoryCreate, MemoryForgetResponse, MemoryOut, MemoryUpdate
from app.services.memory import (
    clear_memories,
    create_memory,
    delete_memory,
    forget_low_value_memories,
    retrieve_memories,
    update_memory,
)

router = APIRouter(prefix="/characters/{character_id}/memories", tags=["memory"])


@router.get("", response_model=list[MemoryOut])
async def list_memories(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[MemoryItem]:
    character = await require_character(character_id, user, session)
    result = await session.execute(
        select(MemoryItem)
        .where(MemoryItem.user_id == user.id, MemoryItem.character_id == character.id)
        .order_by(MemoryItem.created_at.desc())
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
    memory = await create_memory(
        session,
        user_id=user.id,
        character_id=character.id,
        content=payload.content,
        memory_type=payload.memory_type,
        importance=payload.importance,
        confidence=payload.confidence,
        emotional_weight=payload.emotional_weight,
        pinned=payload.pinned,
    )
    await session.commit()
    await session.refresh(memory)
    return memory


@router.get("/search", response_model=list[MemoryOut])
async def search_memories(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str = Query(default="", max_length=120),
) -> list[MemoryItem]:
    character = await require_character(character_id, user, session)
    memories = await retrieve_memories(
        session,
        user_id=user.id,
        character_id=character.id,
        query=q,
        limit=10,
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
    await update_memory(memory=memory, session=session, **payload.model_dump(exclude_unset=True))
    await session.commit()
    await session.refresh(memory)
    return memory


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
