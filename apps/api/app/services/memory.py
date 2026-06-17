from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MemoryItem, utc_now

MEMORY_TRIGGERS = (
    "remember that ",
    "my favorite ",
    "i like ",
    "i love ",
    "i prefer ",
    "call me ",
)
UNSAFE_MEMORY_TERMS = ("password", "secret", "token", "underage", "minor", "coerce", "exploit")


async def create_memory(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    content: str,
    memory_type: str = "preference",
    confidence: float = 0.8,
    emotional_weight: float = 0.0,
    source_message_id: uuid.UUID | None = None,
) -> MemoryItem:
    memory = MemoryItem(
        user_id=user_id,
        character_id=character_id,
        source_message_id=source_message_id,
        memory_type=memory_type,
        content=content.strip(),
        confidence=confidence,
        emotional_weight=emotional_weight,
        embedding=None,
        decay_score=0.0,
        metadata_json={},
    )
    session.add(memory)
    await session.flush()
    return memory


async def retrieve_memories(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    query: str = "",
    limit: int = 5,
    mark_recalled: bool = True,
) -> list[MemoryItem]:
    statement = select(MemoryItem).where(
        MemoryItem.user_id == user_id,
        MemoryItem.character_id == character_id,
    )
    terms = [term for term in query.lower().split() if len(term) > 2]
    if terms:
        statement = statement.where(or_(*(MemoryItem.content.ilike(f"%{term}%") for term in terms)))
    statement = statement.order_by(
        MemoryItem.confidence.desc(),
        MemoryItem.emotional_weight.desc(),
        MemoryItem.created_at.desc(),
    ).limit(limit)
    result = await session.execute(statement)
    memories = list(result.scalars().all())
    if mark_recalled:
        for memory in memories:
            memory.last_recalled_at = utc_now()
        await session.flush()
    return memories


async def maybe_extract_memory(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    message_id: uuid.UUID,
    content: str,
) -> MemoryItem | None:
    normalized = content.strip().lower()
    if len(normalized) < 12:
        return None
    if any(term in normalized for term in UNSAFE_MEMORY_TERMS):
        return None
    if not any(trigger in normalized for trigger in MEMORY_TRIGGERS):
        return None

    memory_content = _format_memory(content)
    if not memory_content:
        return None

    existing = await session.execute(
        select(MemoryItem).where(
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
            MemoryItem.content == memory_content,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return None

    preference_terms = ("favorite", "like", "love", "prefer")
    memory_type = "preference" if any(term in normalized for term in preference_terms) else "event"
    return await create_memory(
        session,
        user_id=user_id,
        character_id=character_id,
        content=memory_content,
        memory_type=memory_type,
        confidence=0.7,
        source_message_id=message_id,
    )


def memories_prompt_section(memories: list[MemoryItem]) -> str:
    if not memories:
        return "Relevant memories: none selected."
    lines = ["Relevant memories:"]
    for memory in memories:
        lines.append(
            f"- [{memory.memory_type}, confidence {memory.confidence:.1f}] {memory.content}"
        )
    return "\n".join(lines)


def _format_memory(content: str) -> str:
    cleaned = " ".join(content.strip().split())
    if len(cleaned) > 500:
        cleaned = cleaned[:497].rstrip() + "..."
    return cleaned
