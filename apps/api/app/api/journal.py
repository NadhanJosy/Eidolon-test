from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user, require_character, require_conversation
from app.models import EpisodicJournal, User
from app.schemas import EpisodicJournalCreate, EpisodicJournalOut
from app.services.journal import create_journal, list_journals

router = APIRouter(prefix="/characters/{character_id}/journals", tags=["journal"])


@router.get("", response_model=list[EpisodicJournalOut])
async def get_journals(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[EpisodicJournal]:
    character = await require_character(character_id, user, session)
    return await list_journals(session, user.id, character.id)


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
