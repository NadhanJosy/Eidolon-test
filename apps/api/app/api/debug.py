from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_session
from app.dependencies import get_current_user, require_character, require_conversation
from app.llm.factory import get_llm_provider
from app.models import Message, ScheduledJob, User
from app.schemas import MessageOut, ScheduledJobOut
from app.services.journal import list_journals
from app.services.memory import retrieve_memories
from app.services.proactive import create_inactivity_proactive_message
from app.services.prompt import assemble_prompt
from app.services.relationship import get_or_create_relationship

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/character/{character_id}")
async def debug_character(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    character = await require_character(character_id, user, session)
    relationship = await get_or_create_relationship(session, user.id, character.id)
    memories = await retrieve_memories(
        session,
        user_id=user.id,
        character_id=character.id,
        query="",
        limit=10,
        mark_recalled=False,
    )
    journals = await list_journals(session, user.id, character.id, limit=4)
    prompt = assemble_prompt(
        user=user,
        character=character,
        relationship=relationship,
        memories=memories,
        journals=journals,
        recent_messages=[],
        current_message="debug preview",
        content_mode="sfw",
    )
    await session.commit()
    return {
        "character": {
            "id": str(character.id),
            "name": character.name,
            "description": character.description,
            "explicit_age": character.explicit_age,
            "adult_mode_allowed": character.adult_mode_allowed,
        },
        "relationship": {
            "trust": relationship.trust,
            "intimacy": relationship.intimacy,
            "warmth": relationship.warmth,
            "tension": relationship.tension,
            "familiarity": relationship.familiarity,
            "attachment": relationship.attachment,
            "mood": relationship.mood,
            "conflict_state": relationship.conflict_state,
            "repair_needed": relationship.repair_needed,
            "tags_json": relationship.tags_json,
            "timeline": (relationship.metadata_json or {}).get("timeline", []),
        },
        "memories": [
            {
                "id": str(memory.id),
                "memory_type": memory.memory_type,
                "content": memory.content,
                "importance": memory.importance,
                "confidence": memory.confidence,
                "pinned": memory.pinned,
            }
            for memory in memories
        ],
        "journals": [
            {
                "id": str(journal.id),
                "journal_type": journal.journal_type,
                "title": journal.title,
                "summary": journal.summary,
                "importance": journal.importance,
                "emotional_tags_json": journal.emotional_tags_json,
            }
            for journal in journals
        ],
        "prompt_context": {
            "prompt_version": prompt.prompt_version,
            "content_mode": prompt.content_mode,
            "llm_provider": get_llm_provider().name,
            "prompt_preview": _compact_prompt(prompt.prompt),
            "prompt_chars": len(prompt.prompt),
        },
    }


@router.get("/conversation/{conversation_id}")
async def debug_conversation(
    conversation_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    conversation = await require_conversation(conversation_id, user, session)
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(desc(Message.created_at))
        .limit(20)
    )
    messages = list(reversed(result.scalars().all()))
    return {
        "conversation": {
            "id": str(conversation.id),
            "character_id": str(conversation.character_id),
            "title": conversation.title,
        },
        "recent_messages": [
            MessageOut.model_validate(message).model_dump(mode="json") for message in messages
        ],
    }


@router.get("/jobs", response_model=list[ScheduledJobOut])
async def debug_jobs(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ScheduledJob]:
    result = await session.execute(
        select(ScheduledJob)
        .where(ScheduledJob.user_id == user.id)
        .order_by(desc(ScheduledJob.created_at))
        .limit(50)
    )
    return list(result.scalars().all())


@router.post("/conversation/{conversation_id}/proactive", response_model=MessageOut | None)
async def debug_create_proactive(
    conversation_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Message | None:
    conversation = await require_conversation(conversation_id, user, session)
    settings = get_settings()
    message = await create_inactivity_proactive_message(
        session,
        conversation,
        inactivity_hours=settings.proactive_inactivity_hours,
        force=True,
    )
    await session.commit()
    if message is not None:
        await session.refresh(message)
    return message


def _compact_prompt(prompt: str) -> str:
    if len(prompt) <= 4000:
        return prompt
    return prompt[:3997].rstrip() + "..."
