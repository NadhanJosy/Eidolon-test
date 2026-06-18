from __future__ import annotations

import re
import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MemoryItem, utc_now
from app.services.relationship import clamp
from app.services.safety import is_blocked_content

MEMORY_TRIGGERS = (
    "remember that ",
    "remember when ",
    "my favorite ",
    "i like ",
    "i love ",
    "i prefer ",
    "i don't like ",
    "i hate ",
    "call me ",
    "my boundary ",
    "please don't ",
    "inside joke",
)
UNSAFE_MEMORY_TERMS = (
    "password",
    "secret",
    "token",
    "api key",
    "underage",
    "minor",
    "ambiguous age",
    "coerce",
    "exploit",
    "credential",
)
STOP_WORDS = {
    "about",
    "after",
    "again",
    "that",
    "this",
    "with",
    "have",
    "from",
    "they",
    "them",
    "your",
    "just",
    "like",
    "love",
    "prefer",
    "remember",
}
POSITIVE_MEMORY_RE = re.compile(r"\bi (like|love|prefer|enjoy)\s+(?P<object>.+)", re.I)
NEGATIVE_MEMORY_RE = re.compile(r"\bi (do not like|don't like|hate|dislike)\s+(?P<object>.+)", re.I)


async def create_memory(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    content: str,
    memory_type: str = "preference",
    importance: float = 0.5,
    confidence: float = 0.8,
    emotional_weight: float = 0.0,
    pinned: bool = False,
    source_message_id: uuid.UUID | None = None,
) -> MemoryItem:
    memory_content = _format_memory(content)
    contradiction_group, polarity = _contradiction_key(memory_content)
    metadata = {"source": "manual" if source_message_id is None else "extracted"}
    if polarity:
        metadata["polarity"] = polarity

    existing = await _find_merge_candidate(
        session,
        user_id=user_id,
        character_id=character_id,
        content=memory_content,
        memory_type=memory_type,
    )
    if existing is not None:
        existing.memory_type = memory_type
        existing.content = _best_memory_content(existing.content, memory_content)
        existing.importance = clamp(max(existing.importance, importance), 0.0, 1.0)
        existing.confidence = clamp(max(existing.confidence, confidence) + 0.03, 0.0, 1.0)
        existing.emotional_weight = clamp(
            (existing.emotional_weight + emotional_weight) / 2,
            -1.0,
            1.0,
        )
        existing.pinned = existing.pinned or pinned
        existing.source_message_id = existing.source_message_id or source_message_id
        existing.decay_score = clamp(existing.decay_score - 0.1, 0.0, 1.0)
        existing.metadata_json = {
            **(existing.metadata_json or {}),
            "merged_count": int((existing.metadata_json or {}).get("merged_count", 0)) + 1,
            "last_merged_at": utc_now().isoformat(),
        }
        await session.flush()
        return existing

    contradiction_metadata = await _contradiction_metadata(
        session,
        user_id=user_id,
        character_id=character_id,
        contradiction_group=contradiction_group,
        polarity=polarity,
    )
    memory = MemoryItem(
        user_id=user_id,
        character_id=character_id,
        source_message_id=source_message_id,
        memory_type=memory_type,
        content=memory_content,
        importance=importance,
        confidence=confidence,
        emotional_weight=emotional_weight,
        pinned=pinned,
        embedding=None,
        decay_score=0.0,
        contradiction_group=contradiction_group,
        metadata_json={**metadata, **contradiction_metadata},
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
    now = utc_now()
    statement = (
        select(MemoryItem)
        .where(
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
        )
        .limit(100)
    )
    result = await session.execute(statement)
    candidates = list(result.scalars().all())
    terms = _query_terms(query)
    memories = sorted(
        candidates,
        key=lambda memory: _memory_score(memory, terms, query, now),
        reverse=True,
    )[:limit]
    if mark_recalled:
        for memory in memories:
            memory.last_recalled_at = now
            memory.decay_score = clamp(memory.decay_score - 0.05, 0.0, 1.0)
        await session.flush()
    return memories


async def update_memory(
    session: AsyncSession,
    memory: MemoryItem,
    *,
    memory_type: str | None = None,
    content: str | None = None,
    importance: float | None = None,
    confidence: float | None = None,
    emotional_weight: float | None = None,
    pinned: bool | None = None,
) -> MemoryItem:
    if memory_type is not None:
        memory.memory_type = memory_type
    if content is not None:
        memory.content = _format_memory(content)
        contradiction_group, polarity = _contradiction_key(memory.content)
        memory.contradiction_group = contradiction_group
        memory.metadata_json = {
            **(memory.metadata_json or {}),
            "polarity": polarity,
            "edited_at": utc_now().isoformat(),
        }
    if importance is not None:
        memory.importance = importance
    if confidence is not None:
        memory.confidence = confidence
    if emotional_weight is not None:
        memory.emotional_weight = emotional_weight
    if pinned is not None:
        memory.pinned = pinned
    await session.flush()
    return memory


async def delete_memory(session: AsyncSession, memory: MemoryItem) -> None:
    await session.delete(memory)
    await session.flush()


async def clear_memories(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
) -> int:
    result = await session.execute(
        delete(MemoryItem).where(
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
        )
    )
    await session.flush()
    return int(result.rowcount or 0)


async def forget_low_value_memories(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> int:
    now = now or utc_now()
    result = await session.execute(
        select(MemoryItem).where(
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
            MemoryItem.pinned.is_(False),
        )
    )
    forgotten = 0
    for memory in result.scalars().all():
        _apply_decay(memory, now)
        if memory.decay_score >= 1.0 or memory.confidence - memory.decay_score <= 0.1:
            await session.delete(memory)
            forgotten += 1
    await session.flush()
    return forgotten


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
    if any(term in normalized for term in UNSAFE_MEMORY_TERMS) or is_blocked_content(content):
        return None
    if not any(trigger in normalized for trigger in MEMORY_TRIGGERS):
        return None

    memory_content = _format_memory(content)
    if not memory_content:
        return None

    preference_terms = ("favorite", "like", "love", "prefer")
    boundary_terms = ("boundary", "please don't", "do not")
    if "inside joke" in normalized:
        memory_type = "inside_joke"
    elif any(term in normalized for term in boundary_terms):
        memory_type = "boundary"
    elif any(term in normalized for term in preference_terms):
        memory_type = "preference"
    else:
        memory_type = "event"
    return await create_memory(
        session,
        user_id=user_id,
        character_id=character_id,
        content=memory_content,
        memory_type=memory_type,
        importance=0.6 if memory_type in {"boundary", "inside_joke"} else 0.45,
        confidence=0.7,
        emotional_weight=0.25 if memory_type in {"inside_joke", "event"} else 0.0,
        source_message_id=message_id,
    )


def memories_prompt_section(memories: list[MemoryItem]) -> str:
    if not memories:
        return "Relevant memories: none selected."
    lines = ["Relevant memories:"]
    for memory in memories:
        pin = ", pinned" if memory.pinned else ""
        lines.append(
            f"- [{memory.memory_type}, confidence {memory.confidence:.1f}, "
            f"importance {memory.importance:.1f}{pin}] {memory.content}"
        )
    return "\n".join(lines)


def _query_terms(query: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-z0-9']+", query.lower())
        if len(term) > 2 and term not in STOP_WORDS
    }


def _memory_score(
    memory: MemoryItem,
    terms: set[str],
    query: str,
    now: datetime,
) -> float:
    content_terms = _query_terms(memory.content)
    keyword_score = 0.0
    if terms:
        keyword_score = len(terms & content_terms) / max(len(terms), 1)
    age_days = max((now - memory.created_at).total_seconds() / 86400, 0)
    recency_score = 1 / (1 + age_days / 14)
    relationship_relevance = 0.0
    if any(marker in query.lower() for marker in ("we ", "remember", "talked", "joke")):
        if memory.memory_type in {"event", "inside_joke", "relationship_milestone"}:
            relationship_relevance = 0.15
    contradiction_penalty = 0.15 if (memory.metadata_json or {}).get("contradicts_memory_id") else 0
    return (
        keyword_score * 0.34
        + memory.importance * 0.2
        + memory.confidence * 0.18
        + max(memory.emotional_weight, 0) * 0.08
        + recency_score * 0.1
        + relationship_relevance
        + (0.2 if memory.pinned else 0)
        - memory.decay_score * 0.25
        - contradiction_penalty
    )


async def _find_merge_candidate(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    content: str,
    memory_type: str,
) -> MemoryItem | None:
    result = await session.execute(
        select(MemoryItem)
        .where(
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
            MemoryItem.memory_type == memory_type,
        )
        .limit(50)
    )
    normalized = _normalized_content(content)
    new_terms = _query_terms(content)
    for memory in result.scalars().all():
        if _normalized_content(memory.content) == normalized:
            return memory
        existing_terms = _query_terms(memory.content)
        if new_terms and existing_terms:
            overlap = len(new_terms & existing_terms) / len(new_terms | existing_terms)
            if overlap >= 0.72:
                return memory
    return None


async def _contradiction_metadata(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    contradiction_group: str | None,
    polarity: str | None,
) -> dict[str, str]:
    if contradiction_group is None or polarity is None:
        return {}
    result = await session.execute(
        select(MemoryItem)
        .where(
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
            MemoryItem.contradiction_group == contradiction_group,
        )
        .order_by(MemoryItem.created_at.desc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        return {}
    existing_polarity = (existing.metadata_json or {}).get("polarity")
    if existing_polarity and existing_polarity != polarity:
        return {"contradicts_memory_id": str(existing.id)}
    return {}


def _contradiction_key(content: str) -> tuple[str | None, str | None]:
    normalized = " ".join(content.lower().split())
    positive = POSITIVE_MEMORY_RE.search(normalized)
    negative = NEGATIVE_MEMORY_RE.search(normalized)
    if positive:
        return f"preference:{_clean_contradiction_object(positive.group('object'))}", "positive"
    if negative:
        return f"preference:{_clean_contradiction_object(negative.group('object'))}", "negative"
    return None, None


def _clean_contradiction_object(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s'-]", "", value.lower())
    words = [word for word in cleaned.split() if word not in STOP_WORDS]
    return "-".join(words[:8])[:100]


def _best_memory_content(existing: str, incoming: str) -> str:
    if len(incoming) > len(existing) and len(incoming) <= 500:
        return incoming
    return existing


def _normalized_content(content: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", content.lower()))


def _apply_decay(memory: MemoryItem, now: datetime) -> None:
    if memory.pinned:
        memory.decay_score = 0.0
        return
    last_anchor = memory.last_recalled_at or memory.updated_at or memory.created_at
    age_days = max((now - last_anchor).total_seconds() / 86400, 0)
    decay_delta = age_days * 0.015
    protection = (memory.importance * 0.006) + (memory.confidence * 0.004)
    memory.decay_score = clamp(memory.decay_score + decay_delta - protection, 0.0, 1.0)


def _format_memory(content: str) -> str:
    cleaned = " ".join(content.strip().split())
    if len(cleaned) > 500:
        cleaned = cleaned[:497].rstrip() + "..."
    return cleaned
