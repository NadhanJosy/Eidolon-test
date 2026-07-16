from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user, require_character, require_conversation
from app.models import EpisodicJournal, User
from app.schemas import (
    DeleteResponse,
    EpisodicJournalCreate,
    EpisodicJournalOut,
    EpisodicJournalUpdate,
)
from app.services.journal import (
    JournalMutationError,
    create_journal,
    delete_manual_journal,
    list_journals,
    update_manual_journal,
)

router = APIRouter(prefix="/characters/{character_id}/journals", tags=["journal"])


@router.get("", response_model=list[EpisodicJournalOut])
async def get_journals(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    scope: Literal["general", "adult"] = Query(default="general"),
) -> list[EpisodicJournal]:
    character = await require_character(character_id, user, session)
    return await list_journals(session, user.id, character.id, scope=scope)


@router.post("", response_model=EpisodicJournalOut, status_code=201)
async def add_journal(
    character_id: uuid.UUID,
    payload: EpisodicJournalCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EpisodicJournal:
    character = await require_character(character_id, user, session)
    if payload.conversation_id is not None:
        conversation = await require_conversation(payload.conversation_id, user, session)
        if conversation.character_id != character.id:
            raise HTTPException(status_code=404, detail="Conversation was not found.")
    journal = await create_journal(
        session,
        user.id,
        character.id,
        conversation_id=payload.conversation_id,
        scope="general",
        journal_type=payload.journal_type,
        title=payload.title,
        summary=payload.summary,
        emotional_tags_json=payload.emotional_tags_json,
        unresolved_threads_json=payload.unresolved_threads_json,
        callbacks_json=payload.callbacks_json,
        importance=payload.importance,
        metadata_json={"source": "manual"},
    )
    await session.commit()
    await session.refresh(journal)
    return journal


@router.patch("/{journal_id}", response_model=EpisodicJournalOut)
async def patch_journal(
    character_id: uuid.UUID,
    journal_id: uuid.UUID,
    payload: EpisodicJournalUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EpisodicJournal:
    character = await require_character(character_id, user, session)
    journal = await _require_journal(session, user.id, character.id, journal_id)
    try:
        await update_manual_journal(
            session,
            journal,
            **payload.model_dump(exclude_unset=True),
        )
    except JournalMutationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(journal)
    return journal


@router.delete("/{journal_id}", response_model=DeleteResponse)
async def remove_journal(
    character_id: uuid.UUID,
    journal_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeleteResponse:
    character = await require_character(character_id, user, session)
    journal = await _require_journal(session, user.id, character.id, journal_id)
    try:
        await delete_manual_journal(session, journal)
    except JournalMutationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return DeleteResponse(deleted=1)


async def _require_journal(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    journal_id: uuid.UUID,
) -> EpisodicJournal:
    result = await session.execute(
        select(EpisodicJournal).where(
            EpisodicJournal.id == journal_id,
            EpisodicJournal.user_id == user_id,
            EpisodicJournal.character_id == character_id,
        )
    )
    journal = result.scalar_one_or_none()
    if journal is None:
        raise HTTPException(status_code=404, detail="Journal entry was not found.")
    return journal
