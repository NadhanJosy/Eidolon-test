from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user, require_character
from app.models import MemoryItem, User
from app.schemas import MemoryCreate, MemoryOut
from app.services.memory import create_memory, retrieve_memories

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
        confidence=payload.confidence,
        emotional_weight=payload.emotional_weight,
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
