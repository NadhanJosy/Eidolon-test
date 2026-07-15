from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import bindparam, delete, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.types import Vector
from app.models import MemoryItem, utc_now
from app.services.embedding import (
    EMBEDDING_DIMENSIONS,
    coerce_embedding,
    cosine_similarity,
    text_embedding,
)
from app.services.relationship import clamp
from app.services.safety import is_blocked_content

MEMORY_TRIGGERS = (
    "remember that ",
    "remember when ",
    "please remember ",
    "my favorite ",
    "my name is ",
    "my pronouns are ",
    "i like ",
    "i love ",
    "i prefer ",
    "i don't like ",
    "i hate ",
    "i work as ",
    "i live in ",
    "i am from ",
    "i'm from ",
    "i feel ",
    "i felt ",
    "i promise ",
    "we promised ",
    "you promised ",
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
CONTRADICTION_METADATA_KEYS = {
    "contradiction_checked_at",
    "contradiction_status",
    "contradicts_memory_id",
    "contradicts_memory_ids",
    "contradicted_by_memory_id",
    "contradicted_by_memory_ids",
    "supersedes_memory_id",
    "supersedes_memory_ids",
}


class MemoryConflictResolutionError(ValueError):
    """Raised when a memory cannot be used to resolve an active conflict."""


class MemoryCaptureError(ValueError):
    """Raised when a selected message cannot be stored as durable memory."""


@dataclass(frozen=True)
class MemoryCandidateDecision:
    accepted: bool
    reason: str
    memory_type: str | None = None
    content: str | None = None
    importance: float = 0.0
    confidence: float = 0.0
    emotional_weight: float = 0.0
    trigger: str | None = None

    def to_metadata(self) -> dict[str, object]:
        metadata: dict[str, object] = {
            "accepted": self.accepted,
            "reason": self.reason,
        }
        if self.memory_type is not None:
            metadata["memory_type"] = self.memory_type
        if self.trigger is not None:
            metadata["trigger"] = self.trigger
        if self.accepted:
            metadata["importance"] = round(self.importance, 3)
            metadata["confidence"] = round(self.confidence, 3)
            metadata["emotional_weight"] = round(self.emotional_weight, 3)
        return metadata


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
    extraction_metadata: dict[str, object] | None = None,
    memory_source: str | None = None,
    capture_metadata: dict[str, object] | None = None,
    merge_similar: bool = True,
) -> MemoryItem:
    memory_content = _format_memory(content)
    contradiction_group, polarity = _contradiction_key(memory_content)
    metadata = {"source": memory_source or ("manual" if source_message_id is None else "extracted")}
    if extraction_metadata is not None:
        metadata["extraction"] = extraction_metadata
    if capture_metadata is not None:
        metadata["capture"] = capture_metadata
    source_message_ids = _source_message_ids({}, None, source_message_id)
    if source_message_ids:
        metadata["source_message_ids"] = source_message_ids
    if polarity:
        metadata["polarity"] = polarity

    existing = None
    if merge_similar:
        existing = await _find_merge_candidate(
            session,
            user_id=user_id,
            character_id=character_id,
            content=memory_content,
            memory_type=memory_type,
            contradiction_group=contradiction_group,
            polarity=polarity,
        )
    if existing is not None:
        if existing.forgotten_at is not None:
            _restore_memory_state(existing, reason="relearned")
        old_group = existing.contradiction_group
        merged_content = _best_memory_content(existing.content, memory_content)
        merged_group, merged_polarity = _contradiction_key(merged_content)
        merged_metadata = _without_contradiction_metadata(existing.metadata_json or {})
        if merged_polarity:
            merged_metadata["polarity"] = merged_polarity
        else:
            merged_metadata.pop("polarity", None)
        existing.memory_type = memory_type
        existing.content = merged_content
        existing.embedding = text_embedding(merged_content)
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
        existing.contradiction_group = merged_group
        if extraction_metadata is not None:
            merged_metadata["extraction"] = extraction_metadata
        if memory_source is not None:
            merged_metadata["source"] = memory_source
        if capture_metadata is not None:
            merged_metadata["capture"] = capture_metadata
        source_message_ids = _source_message_ids(
            merged_metadata,
            existing.source_message_id,
            source_message_id,
        )
        if source_message_ids:
            merged_metadata["source_message_ids"] = source_message_ids
        existing.metadata_json = {
            **merged_metadata,
            "merged_count": int((existing.metadata_json or {}).get("merged_count", 0)) + 1,
            "last_merged_at": utc_now().isoformat(),
        }
        await session.flush()
        await _refresh_contradiction_group(
            session,
            user_id=user_id,
            character_id=character_id,
            contradiction_group=old_group,
        )
        if merged_group != old_group:
            await _refresh_contradiction_group(
                session,
                user_id=user_id,
                character_id=character_id,
                contradiction_group=merged_group,
            )
        return existing

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
        embedding=text_embedding(memory_content),
        decay_score=0.0,
        contradiction_group=contradiction_group,
        metadata_json=metadata,
    )
    session.add(memory)
    await session.flush()
    await _refresh_contradiction_group(
        session,
        user_id=user_id,
        character_id=character_id,
        contradiction_group=contradiction_group,
    )
    return memory


async def remember_message_as_memory(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    message_id: uuid.UUID,
    content: str,
    source_role: str,
) -> MemoryItem:
    decision = analyze_user_saved_memory(content, source_role=source_role)
    existing = await _find_memory_by_source_message(
        session,
        user_id=user_id,
        character_id=character_id,
        message_id=message_id,
    )
    if existing is not None:
        if existing.forgotten_at is not None:
            _restore_memory_state(existing, reason="remembered_by_user")
        source_ids = _source_message_ids(
            existing.metadata_json or {},
            existing.source_message_id,
            None,
        )
        if (existing.metadata_json or {}).get("source") == "user_saved" and str(
            message_id
        ) in source_ids:
            return existing
        await update_memory(
            session,
            existing,
            memory_type=decision.memory_type,
            content=decision.content,
        )
        _mark_memory_user_saved(
            existing,
            message_id=message_id,
            source_role=source_role,
            decision=decision,
        )
        await session.flush()
        return existing

    return await create_memory(
        session,
        user_id=user_id,
        character_id=character_id,
        content=decision.content or content,
        memory_type=decision.memory_type or "event",
        importance=decision.importance,
        confidence=decision.confidence,
        emotional_weight=decision.emotional_weight,
        pinned=True,
        source_message_id=message_id,
        memory_source="user_saved",
        capture_metadata={
            "reason": "user_saved",
            "source_role": source_role,
            "captured_at": utc_now().isoformat(),
        },
        merge_similar=False,
    )


def analyze_user_saved_memory(
    content: str,
    *,
    source_role: str,
) -> MemoryCandidateDecision:
    if source_role not in {"user", "assistant"}:
        raise MemoryCaptureError("Only user or companion messages can be remembered.")

    memory_content = _format_memory(content)
    if not memory_content:
        raise MemoryCaptureError("An empty message cannot be remembered.")

    normalized = content.strip().lower()
    if any(term in normalized for term in UNSAFE_MEMORY_TERMS):
        raise MemoryCaptureError("That line may contain private credential data and was not saved.")
    if is_blocked_content(content):
        raise MemoryCaptureError("That line crosses durable-memory safety boundaries.")

    automatic = analyze_memory_candidate(content)
    if automatic.accepted:
        return MemoryCandidateDecision(
            accepted=True,
            reason="user_saved",
            memory_type=automatic.memory_type,
            content=automatic.content or memory_content,
            importance=max(automatic.importance, 0.65),
            confidence=max(automatic.confidence, 0.9),
            emotional_weight=automatic.emotional_weight,
            trigger=automatic.trigger,
        )

    return MemoryCandidateDecision(
        accepted=True,
        reason="user_saved",
        memory_type="event" if source_role == "user" else "shared_moment",
        content=memory_content,
        importance=0.65,
        confidence=0.9 if source_role == "user" else 0.85,
        emotional_weight=0.15 if source_role == "user" else 0.2,
    )


async def retrieve_memories(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    query: str = "",
    limit: int = 5,
    mark_recalled: bool = True,
) -> list[MemoryItem]:
    now = utc_now()
    query_embedding = text_embedding(query) if query.strip() else None
    if query_embedding is not None and not any(query_embedding):
        query_embedding = None
    recent_statement = (
        select(MemoryItem)
        .where(
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
            MemoryItem.forgotten_at.is_(None),
        )
        .order_by(desc(MemoryItem.pinned), desc(MemoryItem.updated_at), MemoryItem.id.asc())
        .limit(100)
    )
    recent_result = await session.execute(recent_statement)
    candidates_by_id = {memory.id: memory for memory in recent_result.scalars().all()}
    if query_embedding is not None:
        query_vector = bindparam(
            "memory_query_embedding",
            value=query_embedding,
            type_=Vector(EMBEDDING_DIMENSIONS),
        )
        vector_distance = MemoryItem.embedding.op("<=>")(query_vector)
        semantic_statement = (
            select(MemoryItem)
            .where(
                MemoryItem.user_id == user_id,
                MemoryItem.character_id == character_id,
                MemoryItem.forgotten_at.is_(None),
                MemoryItem.embedding.is_not(None),
            )
            .order_by(vector_distance.asc(), desc(MemoryItem.updated_at), MemoryItem.id.asc())
            .limit(50)
        )
        semantic_result = await session.execute(semantic_statement)
        for memory in semantic_result.scalars().all():
            candidates_by_id.setdefault(memory.id, memory)
    candidates = list(candidates_by_id.values())
    terms = _query_terms(query)
    candidate_embeddings: dict[uuid.UUID, list[float]] = {}
    backfilled_embedding = False
    for memory in candidates:
        embedding = coerce_embedding(memory.embedding)
        if embedding is None:
            embedding = text_embedding(memory.content)
            memory.embedding = embedding
            backfilled_embedding = True
        candidate_embeddings[memory.id] = embedding
    memories = sorted(
        candidates,
        key=lambda memory: _memory_score(
            memory,
            terms,
            query,
            now,
            query_embedding=query_embedding,
            memory_embedding=candidate_embeddings.get(memory.id),
        ),
        reverse=True,
    )[:limit]
    if mark_recalled:
        for memory in memories:
            memory.last_recalled_at = now
            memory.decay_score = clamp(memory.decay_score - 0.05, 0.0, 1.0)
    if mark_recalled or backfilled_embedding:
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
        old_group = memory.contradiction_group
        memory.content = _format_memory(content)
        memory.embedding = text_embedding(memory.content)
        contradiction_group, polarity = _contradiction_key(memory.content)
        memory.contradiction_group = contradiction_group
        metadata = _without_contradiction_metadata(memory.metadata_json or {})
        if polarity:
            metadata["polarity"] = polarity
        else:
            metadata.pop("polarity", None)
        memory.metadata_json = {**metadata, "edited_at": utc_now().isoformat()}
    if importance is not None:
        memory.importance = importance
    if confidence is not None:
        memory.confidence = confidence
    if emotional_weight is not None:
        memory.emotional_weight = emotional_weight
    if pinned is not None:
        memory.pinned = pinned
    await session.flush()
    if content is not None:
        await _refresh_contradiction_group(
            session,
            user_id=memory.user_id,
            character_id=memory.character_id,
            contradiction_group=old_group,
        )
        if memory.contradiction_group != old_group:
            await _refresh_contradiction_group(
                session,
                user_id=memory.user_id,
                character_id=memory.character_id,
                contradiction_group=memory.contradiction_group,
            )
    return memory


async def delete_memory(session: AsyncSession, memory: MemoryItem) -> None:
    user_id = memory.user_id
    character_id = memory.character_id
    contradiction_group = memory.contradiction_group
    await session.delete(memory)
    await session.flush()
    await _refresh_contradiction_group(
        session,
        user_id=user_id,
        character_id=character_id,
        contradiction_group=contradiction_group,
    )


async def forget_memory(
    session: AsyncSession,
    memory: MemoryItem,
    *,
    reason: str = "forgotten_by_user",
) -> bool:
    if memory.forgotten_at is not None:
        return False
    contradiction_group = memory.contradiction_group
    _forget_memory_state(memory, reason=reason)
    await session.flush()
    await _refresh_contradiction_group(
        session,
        user_id=memory.user_id,
        character_id=memory.character_id,
        contradiction_group=contradiction_group,
    )
    return True


async def restore_memory(session: AsyncSession, memory: MemoryItem) -> bool:
    if memory.forgotten_at is None:
        return False
    _restore_memory_state(memory, reason="restored_by_user")
    await session.flush()
    await _refresh_contradiction_group(
        session,
        user_id=memory.user_id,
        character_id=memory.character_id,
        contradiction_group=memory.contradiction_group,
    )
    return True


async def remove_message_source_memories(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    message_id: uuid.UUID,
) -> int:
    result = await session.execute(
        select(MemoryItem).where(
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
            or_(
                MemoryItem.source_message_id == message_id,
                MemoryItem.metadata_json.contains({"source_message_ids": [str(message_id)]}),
            ),
        )
    )
    memories = list(result.scalars().all())
    removed = 0
    affected_groups: set[str | None] = set()
    edited_source = str(message_id)
    now = utc_now().isoformat()

    for memory in memories:
        metadata = dict(memory.metadata_json or {})
        source_ids = _source_message_ids(metadata, memory.source_message_id, None)
        remaining_source_ids = [source_id for source_id in source_ids if source_id != edited_source]
        if not remaining_source_ids:
            affected_groups.add(memory.contradiction_group)
            await session.delete(memory)
            removed += 1
            continue

        if memory.source_message_id == message_id:
            memory.source_message_id = _first_valid_uuid(remaining_source_ids)
        metadata["source_message_ids"] = remaining_source_ids[:24]
        edited_sources = _metadata_string_list(metadata.get("edited_source_message_ids"))
        if edited_source not in edited_sources:
            edited_sources.append(edited_source)
        metadata["edited_source_message_ids"] = edited_sources[-24:]
        metadata["source_edited_at"] = now
        memory.metadata_json = metadata

    await session.flush()
    for contradiction_group in affected_groups:
        await _refresh_contradiction_group(
            session,
            user_id=user_id,
            character_id=character_id,
            contradiction_group=contradiction_group,
        )
    return removed


async def resolve_memory_conflict(
    session: AsyncSession,
    memory: MemoryItem,
) -> tuple[MemoryItem, list[uuid.UUID]]:
    if memory.forgotten_at is not None:
        raise MemoryConflictResolutionError("Restore this memory before resolving its conflict.")
    contradiction_group = memory.contradiction_group
    selected_polarity = _memory_polarity(memory)
    if contradiction_group is None or selected_polarity is None:
        raise MemoryConflictResolutionError("This memory does not have an active conflict.")

    result = await session.execute(
        select(MemoryItem)
        .where(
            MemoryItem.user_id == memory.user_id,
            MemoryItem.character_id == memory.character_id,
            MemoryItem.contradiction_group == contradiction_group,
            MemoryItem.forgotten_at.is_(None),
        )
        .order_by(MemoryItem.created_at.asc(), MemoryItem.id.asc())
    )
    group_memories = list(result.scalars().all())
    opposing = [
        item
        for item in group_memories
        if item.id != memory.id and _memory_polarity(item) not in {None, selected_polarity}
    ]
    if not opposing:
        raise MemoryConflictResolutionError("This memory does not have an active conflict.")

    removed_ids = [item.id for item in opposing]
    now = utc_now()
    for item in opposing:
        await session.delete(item)

    metadata = _without_contradiction_metadata(memory.metadata_json or {})
    metadata["polarity"] = selected_polarity
    metadata["resolved_conflict_at"] = now.isoformat()
    metadata["resolution"] = "kept_by_user"
    metadata["removed_conflicting_memory_ids"] = [str(item_id) for item_id in removed_ids]
    memory.metadata_json = metadata
    memory.confidence = clamp(max(memory.confidence, 0.88), 0.0, 1.0)
    memory.importance = clamp(max(memory.importance, 0.65), 0.0, 1.0)
    memory.decay_score = clamp(memory.decay_score - 0.2, 0.0, 1.0)
    memory.pinned = True
    await session.flush()
    await _refresh_contradiction_group(
        session,
        user_id=memory.user_id,
        character_id=memory.character_id,
        contradiction_group=contradiction_group,
    )
    return memory, removed_ids


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
            MemoryItem.forgotten_at.is_(None),
        )
    )
    forgotten = 0
    for memory in result.scalars().all():
        _apply_decay(memory, now)
        if memory.decay_score >= 1.0 or memory.confidence - memory.decay_score <= 0.1:
            if await forget_memory(session, memory, reason="faded_by_decay"):
                forgotten += 1
    await session.flush()
    return forgotten


async def maybe_extract_memory(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    message_id: uuid.UUID,
    content: str,
    memory_preferences: dict[str, object] | None = None,
) -> MemoryItem | None:
    decision = analyze_memory_candidate(content, memory_preferences=memory_preferences)
    if not decision.accepted:
        return None
    return await create_memory(
        session,
        user_id=user_id,
        character_id=character_id,
        content=decision.content or content,
        memory_type=decision.memory_type or "event",
        importance=decision.importance,
        confidence=decision.confidence,
        emotional_weight=decision.emotional_weight,
        source_message_id=message_id,
        extraction_metadata=decision.to_metadata(),
    )


def analyze_memory_candidate(
    content: str,
    *,
    memory_preferences: dict[str, object] | None = None,
) -> MemoryCandidateDecision:
    normalized = content.strip().lower()
    if len(normalized) < 12:
        return MemoryCandidateDecision(accepted=False, reason="too_short")
    if any(term in normalized for term in UNSAFE_MEMORY_TERMS):
        return MemoryCandidateDecision(accepted=False, reason="unsafe_term")
    if is_blocked_content(content):
        return MemoryCandidateDecision(accepted=False, reason="blocked_content")
    trigger = _memory_trigger(normalized)
    if trigger is None:
        return MemoryCandidateDecision(accepted=False, reason="no_trigger")

    memory_content = _format_memory(content)
    if not memory_content:
        return MemoryCandidateDecision(accepted=False, reason="empty_content")

    memory_type = _candidate_memory_type(normalized)
    if not memory_type_allowed_by_preferences(memory_type, memory_preferences or {}):
        return MemoryCandidateDecision(
            accepted=False,
            reason="disabled_by_preferences",
            memory_type=memory_type,
            trigger=trigger,
        )
    importance, confidence, emotional_weight = _candidate_scores(memory_type, normalized)
    return MemoryCandidateDecision(
        accepted=True,
        reason="accepted",
        memory_type=memory_type,
        content=memory_content,
        importance=importance,
        confidence=confidence,
        emotional_weight=emotional_weight,
        trigger=trigger,
    )


def memory_preferences_from_boundaries(boundaries_json: object) -> dict[str, object]:
    if not isinstance(boundaries_json, dict):
        return {}
    preferences = boundaries_json.get("memory_preferences")
    if isinstance(preferences, dict):
        return preferences
    return {}


def memory_type_allowed_by_preferences(
    memory_type: str,
    memory_preferences: dict[str, object],
) -> bool:
    if memory_type == "preference" and memory_preferences.get("remember_preferences") is False:
        return False
    if (
        memory_type in {"event", "inside_joke", "promise", "relationship_milestone"}
        and memory_preferences.get("remember_emotional_notes") is False
    ):
        return False
    return True


def memories_prompt_section(memories: list[MemoryItem]) -> str:
    active_memories = [memory for memory in memories if memory.forgotten_at is None]
    if not active_memories:
        return "Relevant memories: none selected."
    lines = ["Relevant memories:"]
    for memory in active_memories:
        pin = ", pinned" if memory.pinned else ""
        lines.append(
            f"- [{memory.memory_type}, confidence {memory.confidence:.1f}, "
            f"importance {memory.importance:.1f}{pin}] {memory.content}"
        )
    return "\n".join(lines)


def _candidate_memory_type(normalized_content: str) -> str:
    preference_terms = ("favorite", "like", "love", "prefer")
    boundary_terms = ("boundary", "please don't", "do not")
    fact_terms = (
        "my name is ",
        "my pronouns are ",
        "i work as ",
        "i live in ",
        "i am from ",
        "i'm from ",
        "call me ",
    )
    promise_terms = ("i promise ", "we promised ", "you promised ")
    emotional_event_terms = ("i feel ", "i felt ")
    if "inside joke" in normalized_content:
        return "inside_joke"
    if any(term in normalized_content for term in boundary_terms):
        return "boundary"
    if any(term in normalized_content for term in promise_terms):
        return "promise"
    if any(term in normalized_content for term in fact_terms):
        return "user_fact"
    if any(term in normalized_content for term in preference_terms):
        return "preference"
    if any(term in normalized_content for term in emotional_event_terms):
        return "event"
    return "event"


def _memory_trigger(normalized_content: str) -> str | None:
    for trigger in MEMORY_TRIGGERS:
        if trigger in normalized_content:
            return trigger.strip()
    return None


def _candidate_scores(memory_type: str, normalized_content: str) -> tuple[float, float, float]:
    if memory_type == "boundary":
        return 0.72, 0.82, 0.0
    if memory_type == "inside_joke":
        return 0.68, 0.74, 0.35
    if memory_type == "promise":
        return 0.7, 0.78, 0.2
    if memory_type == "user_fact":
        return 0.58, 0.78, 0.05
    if memory_type == "event":
        return 0.52, 0.68, 0.25
    if "favorite" in normalized_content or "prefer" in normalized_content:
        return 0.5, 0.78, 0.05
    return 0.45, 0.72, 0.0


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
    *,
    query_embedding: list[float] | None,
    memory_embedding: list[float] | None,
) -> float:
    content_terms = _query_terms(memory.content)
    keyword_score = 0.0
    if terms:
        keyword_score = len(terms & content_terms) / max(len(terms), 1)
    vector_score = max(cosine_similarity(query_embedding, memory_embedding), 0.0)
    age_days = max((now - memory.created_at).total_seconds() / 86400, 0)
    recency_score = 1 / (1 + age_days / 14)
    relationship_relevance = 0.0
    if any(marker in query.lower() for marker in ("we ", "remember", "talked", "joke")):
        if memory.memory_type in {"event", "inside_joke", "relationship_milestone"}:
            relationship_relevance = 0.15
    metadata = memory.metadata_json or {}
    contradiction_penalty = 0.0
    if metadata.get("contradiction_status") == "conflicts":
        contradiction_penalty += 0.08
    if metadata.get("contradicted_by_memory_id"):
        contradiction_penalty += 0.12
    elif metadata.get("contradicts_memory_id"):
        contradiction_penalty += 0.05
    return (
        keyword_score * 0.34
        + vector_score * 0.4
        + memory.importance * 0.2
        + memory.confidence * 0.18
        + abs(memory.emotional_weight) * 0.08
        + recency_score * 0.1
        + relationship_relevance
        + (0.2 if memory.pinned else 0)
        - memory.decay_score * 0.25
        - contradiction_penalty
    )


async def _find_memory_by_source_message(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    message_id: uuid.UUID,
) -> MemoryItem | None:
    result = await session.execute(
        select(MemoryItem)
        .where(
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
            or_(
                MemoryItem.source_message_id == message_id,
                MemoryItem.metadata_json.contains({"source_message_ids": [str(message_id)]}),
            ),
        )
        .order_by(
            MemoryItem.forgotten_at.asc().nullsfirst(),
            MemoryItem.updated_at.desc(),
            MemoryItem.id.asc(),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


def _mark_memory_user_saved(
    memory: MemoryItem,
    *,
    message_id: uuid.UUID,
    source_role: str,
    decision: MemoryCandidateDecision,
) -> None:
    metadata = dict(memory.metadata_json or {})
    metadata["source"] = "user_saved"
    metadata["capture"] = {
        "reason": "user_saved",
        "source_role": source_role,
        "captured_at": utc_now().isoformat(),
    }
    metadata["source_message_ids"] = _source_message_ids(
        metadata,
        memory.source_message_id,
        message_id,
    )
    memory.metadata_json = metadata
    memory.source_message_id = memory.source_message_id or message_id
    memory.importance = clamp(max(memory.importance, decision.importance), 0.0, 1.0)
    memory.confidence = clamp(max(memory.confidence, decision.confidence), 0.0, 1.0)
    if abs(decision.emotional_weight) > abs(memory.emotional_weight):
        memory.emotional_weight = decision.emotional_weight
    memory.decay_score = 0.0
    memory.pinned = True


def _source_message_ids(
    metadata: dict[str, object],
    primary_message_id: uuid.UUID | None,
    incoming_message_id: uuid.UUID | None,
) -> list[str]:
    source_ids: list[str] = []
    stored_ids = metadata.get("source_message_ids")
    if isinstance(stored_ids, list):
        for value in stored_ids:
            if isinstance(value, str) and value and value not in source_ids:
                source_ids.append(value)
    for message_id in (primary_message_id, incoming_message_id):
        if message_id is None:
            continue
        value = str(message_id)
        if value not in source_ids:
            source_ids.append(value)
    return source_ids[:24]


def _metadata_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]


def _first_valid_uuid(values: list[str]) -> uuid.UUID | None:
    for value in values:
        try:
            return uuid.UUID(value)
        except ValueError:
            continue
    return None


async def _find_merge_candidate(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    content: str,
    memory_type: str,
    contradiction_group: str | None,
    polarity: str | None,
) -> MemoryItem | None:
    result = await session.execute(
        select(MemoryItem)
        .where(
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
            MemoryItem.memory_type == memory_type,
        )
        .order_by(
            MemoryItem.forgotten_at.asc().nullsfirst(),
            MemoryItem.updated_at.desc(),
            MemoryItem.id.asc(),
        )
        .limit(50)
    )
    normalized = _normalized_content(content)
    new_terms = _query_terms(content)
    for memory in result.scalars().all():
        existing_polarity = (memory.metadata_json or {}).get("polarity")
        if (
            contradiction_group
            and memory.contradiction_group == contradiction_group
            and polarity
            and existing_polarity
            and existing_polarity != polarity
        ):
            continue
        if _normalized_content(memory.content) == normalized:
            return memory
        existing_terms = _query_terms(memory.content)
        if new_terms and existing_terms:
            overlap = len(new_terms & existing_terms) / len(new_terms | existing_terms)
            if overlap >= 0.72:
                return memory
    return None


async def _refresh_contradiction_group(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    contradiction_group: str | None,
) -> None:
    if contradiction_group is None:
        return
    result = await session.execute(
        select(MemoryItem)
        .where(
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
            MemoryItem.contradiction_group == contradiction_group,
            MemoryItem.forgotten_at.is_(None),
        )
        .order_by(MemoryItem.created_at.asc(), MemoryItem.id.asc())
    )
    memories = list(result.scalars().all())
    if not memories:
        return

    checked_at = utc_now().isoformat()
    for memory in memories:
        metadata = _without_contradiction_metadata(memory.metadata_json or {})
        polarity = metadata.get("polarity")
        if not polarity:
            group, polarity = _contradiction_key(memory.content)
            if group == contradiction_group and polarity:
                metadata["polarity"] = polarity
        if not polarity:
            memory.metadata_json = metadata
            continue

        opposing = [
            other
            for other in memories
            if other.id != memory.id and (other.metadata_json or {}).get("polarity") != polarity
        ]
        opposing = [
            other for other in opposing if (other.metadata_json or {}).get("polarity") is not None
        ]
        if opposing:
            opposing_ids = [str(other.id) for other in opposing]
            newer_ids = [
                str(other.id)
                for other in opposing
                if _memory_order_key(other) > _memory_order_key(memory)
            ]
            older_ids = [
                str(other.id)
                for other in opposing
                if _memory_order_key(other) < _memory_order_key(memory)
            ]
            metadata["contradiction_status"] = "conflicts"
            metadata["contradiction_checked_at"] = checked_at
            metadata["contradicts_memory_ids"] = opposing_ids
            metadata["contradicts_memory_id"] = opposing_ids[0]
            if newer_ids:
                metadata["contradicted_by_memory_ids"] = newer_ids
                metadata["contradicted_by_memory_id"] = newer_ids[-1]
            if older_ids:
                metadata["supersedes_memory_ids"] = older_ids
                metadata["supersedes_memory_id"] = older_ids[-1]
        memory.metadata_json = metadata
    await session.flush()


def _forget_memory_state(memory: MemoryItem, *, reason: str) -> None:
    now = utc_now()
    metadata = _without_contradiction_metadata(memory.metadata_json or {})
    history = _forget_history(metadata.get("forget_history"))
    history.append({"forgotten_at": now.isoformat(), "reason": reason[:80]})
    metadata["forget_history"] = history[-8:]
    metadata["last_forget_reason"] = reason[:80]
    memory.metadata_json = metadata
    memory.forgotten_at = now


def _restore_memory_state(memory: MemoryItem, *, reason: str) -> None:
    now = utc_now()
    metadata = dict(memory.metadata_json or {})
    metadata["last_restored_at"] = now.isoformat()
    metadata["last_restore_reason"] = reason[:80]
    memory.metadata_json = metadata
    memory.forgotten_at = None
    memory.decay_score = 0.0 if reason != "restored_by_user" else min(memory.decay_score, 0.6)


def _forget_history(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    history: list[dict[str, str]] = []
    for item in value[-8:]:
        if not isinstance(item, dict):
            continue
        forgotten_at = item.get("forgotten_at")
        reason = item.get("reason")
        if isinstance(forgotten_at, str) and isinstance(reason, str):
            history.append(
                {
                    "forgotten_at": forgotten_at[:64],
                    "reason": reason[:80],
                }
            )
    return history


def _without_contradiction_metadata(metadata: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in metadata.items() if key not in CONTRADICTION_METADATA_KEYS}


def _memory_polarity(memory: MemoryItem) -> str | None:
    metadata = memory.metadata_json or {}
    polarity = metadata.get("polarity")
    if polarity in {"positive", "negative"}:
        return str(polarity)
    contradiction_group, derived_polarity = _contradiction_key(memory.content)
    if contradiction_group == memory.contradiction_group:
        return derived_polarity
    return None


def _memory_order_key(memory: MemoryItem) -> tuple[datetime, str]:
    return memory.created_at, str(memory.id)


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
