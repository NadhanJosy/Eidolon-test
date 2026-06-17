from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Character,
    Conversation,
    EpisodicJournal,
    MemoryItem,
    Message,
    RelationshipState,
    User,
    utc_now,
)
from app.services.journal import list_journals
from app.services.memory import retrieve_memories
from app.services.relationship import get_or_create_relationship
from app.services.safety import adult_gate_status


@dataclass(frozen=True)
class ReasoningContext:
    relationship: RelationshipState
    memories: list[MemoryItem]
    journals: list[EpisodicJournal]
    recent_messages: list[Message]
    safety_status: dict
    time_context: str


async def build_reasoning_context(
    session: AsyncSession,
    *,
    user: User,
    character: Character,
    conversation: Conversation,
    current_message: str,
    requested_mode: str,
) -> ReasoningContext:
    relationship = await get_or_create_relationship(session, user.id, character.id)
    memories = await retrieve_memories(
        session,
        user_id=user.id,
        character_id=character.id,
        query=current_message,
        limit=7,
    )
    journals = await list_journals(session, user.id, character.id, limit=4)
    recent_messages = await _list_recent_messages(session, conversation.id, limit=14)
    now = utc_now()
    return ReasoningContext(
        relationship=relationship,
        memories=memories,
        journals=journals,
        recent_messages=recent_messages,
        safety_status=adult_gate_status(user, character, requested_mode),
        time_context=now.strftime("%A, %Y-%m-%d %H:%M UTC"),
    )


async def _list_recent_messages(
    session: AsyncSession,
    conversation_id,
    *,
    limit: int,
) -> list[Message]:
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))
