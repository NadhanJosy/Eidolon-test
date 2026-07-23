from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user, require_character, require_conversation
from app.models import ContinuityThread, User
from app.schemas import (
    ContinuityThreadCreate,
    ContinuityThreadOut,
    ContinuityThreadUpdate,
    DeleteResponse,
)
from app.services.continuity import (
    ContinuityThreadError,
    create_continuity_thread,
    delete_continuity_thread,
    list_continuity_threads,
    update_continuity_thread,
)
from app.services.conversation_privacy import conversation_is_private
from app.services.proactive_presence import cancel_pending_for_character

router = APIRouter(prefix="/characters/{character_id}/threads", tags=["continuity"])


@router.get("", response_model=list[ContinuityThreadOut])
async def get_continuity_threads(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    status: Literal["open", "resolved", "all"] = Query(default="open"),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ContinuityThread]:
    character = await require_character(character_id, user, session)
    return await list_continuity_threads(
        session,
        user_id=user.id,
        character_id=character.id,
        status=status,
        limit=limit,
    )


@router.post("", response_model=ContinuityThreadOut, status_code=201)
async def add_continuity_thread(
    character_id: uuid.UUID,
    payload: ContinuityThreadCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ContinuityThread:
    character = await require_character(character_id, user, session)
    if payload.conversation_id is not None:
        conversation = await require_conversation(payload.conversation_id, user, session)
        if conversation.character_id != character.id:
            raise HTTPException(status_code=404, detail="Conversation was not found.")
        if conversation_is_private(conversation):
            raise HTTPException(
                status_code=409,
                detail="Living threads stay off inside a private conversation.",
            )
    try:
        thread = await create_continuity_thread(
            session,
            user_id=user.id,
            character_id=character.id,
            conversation_id=payload.conversation_id,
            content=payload.content,
            thread_kind=payload.thread_kind,
            salience=payload.salience,
        )
    except ContinuityThreadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(thread)
    return thread


@router.patch("/{thread_id}", response_model=ContinuityThreadOut)
async def patch_continuity_thread(
    character_id: uuid.UUID,
    thread_id: uuid.UUID,
    payload: ContinuityThreadUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ContinuityThread:
    character = await require_character(character_id, user, session)
    thread = await _require_thread(session, user.id, character.id, thread_id)
    if payload.model_fields_set:
        await cancel_pending_for_character(
            session,
            character_id=character.id,
            continuity_thread_id=thread.id,
            reason_code="continuity_source_changed",
        )
    try:
        await update_continuity_thread(
            session,
            thread,
            **payload.model_dump(exclude_unset=True),
        )
    except ContinuityThreadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(thread)
    return thread


@router.delete("/{thread_id}", response_model=DeleteResponse)
async def remove_continuity_thread(
    character_id: uuid.UUID,
    thread_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeleteResponse:
    character = await require_character(character_id, user, session)
    thread = await _require_thread(session, user.id, character.id, thread_id)
    await cancel_pending_for_character(
        session,
        character_id=character.id,
        continuity_thread_id=thread.id,
        reason_code="continuity_source_deleted",
    )
    await delete_continuity_thread(session, thread)
    await session.commit()
    return DeleteResponse(deleted=1)


async def _require_thread(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    thread_id: uuid.UUID,
) -> ContinuityThread:
    result = await session.execute(
        select(ContinuityThread).where(
            ContinuityThread.id == thread_id,
            ContinuityThread.user_id == user_id,
            ContinuityThread.character_id == character_id,
        )
    )
    thread = result.scalar_one_or_none()
    if thread is None:
        raise HTTPException(status_code=404, detail="Living thread was not found.")
    return thread
