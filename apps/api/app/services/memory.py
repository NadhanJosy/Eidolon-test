from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import bindparam, delete, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.types import Vector
from app.models import MemoryEntity, MemoryEntityLink, MemoryEvidence, MemoryItem, utc_now
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
    "my friend ",
    "my partner ",
    "my sister ",
    "my brother ",
    "i keep ",
    "i always struggle ",
    "our ritual ",
    "we call this ",
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
MEMORY_OPT_OUT_MARKERS = (
    "do not remember this",
    "don't remember this",
    "do not save this",
    "don't save this",
    "keep this out of memory",
    "this is off the record",
    "forget what i just said",
)
SENSITIVE_MEMORY_PATTERNS = (
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", re.I),
    re.compile(r"\b(?:\+?\d[\d ()-]{7,}\d)\b"),
    re.compile(r"\b(?:social security|bank account|routing number|credit card)\b", re.I),
    re.compile(r"\b(?:my home address|i live at|my address is)\b", re.I),
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
class MemoryMaintenanceResult:
    consolidated: int = 0
    faded: int = 0
    reviewed: int = 0


@dataclass(frozen=True)
class MemoryCandidateDecision:
    accepted: bool
    reason: str
    memory_type: str | None = None
    content: str | None = None
    importance: float = 0.0
    confidence: float = 0.0
    emotional_weight: float = 0.0
    novelty: float = 0.0
    future_relevance: float = 0.0
    retention_tier: str | None = None
    sensitivity: str = "standard"
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
            metadata["novelty"] = round(self.novelty, 3)
            metadata["future_relevance"] = round(self.future_relevance, 3)
            metadata["retention_tier"] = self.retention_tier or "normal"
            metadata["sensitivity"] = self.sensitivity
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
    scope: str = "general",
    claim_key: str | None = None,
    retrieval_facets: list[str] | None = None,
    retention_tier: str | None = None,
    sensitivity: str | None = None,
    novelty: float = 0.5,
    future_relevance: float = 0.5,
    emotional_context: dict[str, object] | None = None,
    linked_entities: list[tuple[str, str]] | None = None,
    evidence_actor: str | None = None,
) -> MemoryItem:
    if scope not in {"general", "adult"}:
        raise MemoryCaptureError("Memory scope must be general or adult.")
    memory_content = _validated_memory_content(content)
    selected_retention = _retention_tier(
        memory_type,
        importance=importance,
        pinned=pinned,
        requested=retention_tier,
    )
    selected_sensitivity = sensitivity or classify_memory_sensitivity(memory_content)
    if selected_sensitivity not in {"standard", "sensitive"}:
        raise MemoryCaptureError("Memory sensitivity must be standard or sensitive.")
    novelty = clamp(novelty, 0.0, 1.0)
    future_relevance = clamp(future_relevance, 0.0, 1.0)
    bounded_emotional_context = _bounded_emotional_context(emotional_context or {})
    facets = _bounded_facets(retrieval_facets or [])
    embedding_text = _embedding_text(memory_content, facets)
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
    if facets:
        metadata["retrieval_facets"] = facets

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
            scope=scope,
            claim_key=claim_key,
        )
    if existing is not None:
        was_forgotten = existing.forgotten_at is not None
        if was_forgotten:
            _restore_memory_state(existing, reason="relearned")
        old_group = existing.contradiction_group
        old_content = existing.content
        merged_content = _best_memory_content(existing.content, memory_content)
        merged_group, merged_polarity = _contradiction_key(merged_content)
        merged_metadata = _without_contradiction_metadata(existing.metadata_json or {})
        if merged_polarity:
            merged_metadata["polarity"] = merged_polarity
        else:
            merged_metadata.pop("polarity", None)
        existing.memory_type = memory_type
        existing.scope = scope
        existing.claim_key = existing.claim_key or claim_key
        existing.content = merged_content
        merged_facets = _bounded_facets(
            [*_metadata_string_list(merged_metadata.get("retrieval_facets")), *facets]
        )
        if merged_facets:
            merged_metadata["retrieval_facets"] = merged_facets
        existing.embedding = text_embedding(_embedding_text(merged_content, merged_facets))
        existing.importance = clamp(max(existing.importance, importance), 0.0, 1.0)
        existing.confidence = clamp(max(existing.confidence, confidence) + 0.03, 0.0, 1.0)
        existing.emotional_weight = clamp(
            (existing.emotional_weight + emotional_weight) / 2,
            -1.0,
            1.0,
        )
        existing.pinned = existing.pinned or pinned
        existing.retention_tier = _stronger_retention_tier(
            existing.retention_tier,
            selected_retention,
        )
        existing.sensitivity = (
            "sensitive"
            if "sensitive" in {existing.sensitivity, selected_sensitivity}
            else "standard"
        )
        existing.novelty = clamp((existing.novelty + novelty) / 2, 0.0, 1.0)
        existing.future_relevance = clamp(
            max(existing.future_relevance, future_relevance), 0.0, 1.0
        )
        existing.emotional_context_json = _merge_emotional_context(
            existing.emotional_context_json,
            bounded_emotional_context,
        )
        existing.reinforcement_count += 1
        existing.last_reinforced_at = utc_now()
        existing.last_evidence_at = utc_now()
        existing.lifecycle_state = "active"
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
        if was_forgotten:
            await _record_memory_evidence(
                session,
                existing,
                action="restored",
                actor="system",
                reason="relearned_from_new_evidence",
                source_message_id=source_message_id,
            )
        await _record_memory_evidence(
            session,
            existing,
            action="merged" if merged_content != old_content else "reinforced",
            actor=evidence_actor or ("user" if memory_source in {None, "manual"} else "system"),
            reason="repeated_grounded_evidence",
            source_message_id=source_message_id,
        )
        await _link_memory_entities(
            session,
            existing,
            linked_entities or _inferred_entities(existing.memory_type, existing.content, facets),
        )
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
        scope=scope,
        claim_key=claim_key,
        retention_tier=selected_retention,
        lifecycle_state="active",
        sensitivity=selected_sensitivity,
        memory_type=memory_type,
        content=memory_content,
        importance=importance,
        confidence=confidence,
        emotional_weight=emotional_weight,
        emotional_context_json=bounded_emotional_context,
        novelty=novelty,
        future_relevance=future_relevance,
        reinforcement_count=1,
        pinned=pinned,
        embedding=text_embedding(embedding_text),
        decay_score=0.0,
        last_reinforced_at=utc_now(),
        last_evidence_at=utc_now(),
        contradiction_group=contradiction_group,
        metadata_json=metadata,
    )
    session.add(memory)
    await session.flush()
    await _record_memory_evidence(
        session,
        memory,
        action="created",
        actor=evidence_actor
        or ("user" if memory_source in {None, "manual", "user_saved"} else "system"),
        reason=memory_source or "manual",
        source_message_id=source_message_id,
    )
    await _link_memory_entities(
        session,
        memory,
        linked_entities or _inferred_entities(memory_type, memory_content, facets),
    )
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
    scope: str = "general",
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
        await _record_memory_evidence(
            session,
            existing,
            action="reinforced",
            actor="user",
            reason="remembered_by_user",
            source_message_id=message_id,
        )
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
        novelty=decision.novelty,
        future_relevance=decision.future_relevance,
        retention_tier=decision.retention_tier,
        sensitivity=decision.sensitivity,
        pinned=True,
        source_message_id=message_id,
        memory_source="user_saved",
        capture_metadata={
            "reason": "user_saved",
            "source_role": source_role,
            "captured_at": utc_now().isoformat(),
        },
        merge_similar=False,
        scope=scope,
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
            novelty=automatic.novelty,
            future_relevance=max(automatic.future_relevance, 0.65),
            retention_tier="core",
            sensitivity=classify_memory_sensitivity(content),
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
        novelty=0.7,
        future_relevance=0.65,
        retention_tier="core",
        sensitivity=classify_memory_sensitivity(content),
    )


async def retrieve_memories(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    query: str = "",
    limit: int = 5,
    mark_recalled: bool = True,
    scopes: tuple[str, ...] = ("general",),
) -> list[MemoryItem]:
    allowed_scopes = tuple(scope for scope in scopes if scope in {"general", "adult"})
    if not allowed_scopes:
        return []
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
            MemoryItem.lifecycle_state == "active",
            MemoryItem.scope.in_(allowed_scopes),
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
                MemoryItem.lifecycle_state == "active",
                MemoryItem.scope.in_(allowed_scopes),
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
    if query.strip():
        candidates = [
            memory
            for memory in candidates
            if memory.sensitivity != "sensitive"
            or _sensitive_memory_query_matches(memory.content, query)
        ]
    entity_match_ids = await _entity_matching_memory_ids(
        session,
        candidates=candidates,
        query=query,
    )
    candidate_embeddings: dict[uuid.UUID, list[float]] = {}
    backfilled_embedding = False
    for memory in candidates:
        embedding = coerce_embedding(memory.embedding)
        if embedding is None:
            embedding = text_embedding(memory.content)
            memory.embedding = embedding
            backfilled_embedding = True
        candidate_embeddings[memory.id] = embedding
    scored = sorted(
        (
            (
                memory,
                _memory_score(
                    memory,
                    terms,
                    query,
                    now,
                    query_embedding=query_embedding,
                    memory_embedding=candidate_embeddings.get(memory.id),
                    entity_match=memory.id in entity_match_ids,
                ),
            )
            for memory in candidates
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    memories = _select_ranked_memories(
        scored,
        limit=limit,
        has_query=bool(terms or query_embedding is not None),
    )
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
    retention_tier: str | None = None,
) -> MemoryItem:
    before = _memory_snapshot(memory)
    if memory_type is not None:
        memory.memory_type = memory_type
    if content is not None:
        old_group = memory.contradiction_group
        memory.content = _validated_memory_content(content)
        memory.sensitivity = classify_memory_sensitivity(memory.content)
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
        if pinned:
            memory.retention_tier = "core"
        elif memory.retention_tier == "core" and memory.memory_type not in {
            "boundary",
            "relationship_milestone",
        }:
            memory.retention_tier = "normal"
    if retention_tier is not None:
        memory.retention_tier = _retention_tier(
            memory.memory_type,
            importance=memory.importance,
            pinned=memory.pinned,
            requested=retention_tier,
        )
    memory.lifecycle_state = "active" if memory.forgotten_at is None else memory.lifecycle_state
    memory.last_evidence_at = utc_now()
    await session.flush()
    await _record_memory_evidence(
        session,
        memory,
        action="edited",
        actor="user",
        reason="edited_by_user",
        source_message_id=None,
        snapshot=before,
    )
    if content is not None:
        await _link_memory_entities(
            session,
            memory,
            _inferred_entities(memory.memory_type, memory.content, []),
            replace=True,
        )
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
    await _delete_orphan_entities(session, user_id=user_id, character_id=character_id)
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
    before = _memory_snapshot(memory)
    _forget_memory_state(memory, reason=reason)
    await session.flush()
    await _record_memory_evidence(
        session,
        memory,
        action="forgotten",
        actor="user" if reason == "forgotten_by_user" else "system",
        reason=reason,
        source_message_id=None,
        snapshot=before,
    )
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
    if memory.lifecycle_state == "superseded":
        raise MemoryConflictResolutionError(
            "A superseded memory stays in correction history and cannot be restored directly."
        )
    before = _memory_snapshot(memory)
    _restore_memory_state(memory, reason="restored_by_user")
    await session.flush()
    await _record_memory_evidence(
        session,
        memory,
        action="restored",
        actor="user",
        reason="restored_by_user",
        source_message_id=None,
        snapshot=before,
    )
    await _refresh_contradiction_group(
        session,
        user_id=memory.user_id,
        character_id=memory.character_id,
        contradiction_group=memory.contradiction_group,
    )
    return True


async def supersede_memory(
    session: AsyncSession,
    memory: MemoryItem,
    *,
    replacement: MemoryItem,
    reason: str,
    source_message_id: uuid.UUID | None,
    actor: str = "system",
) -> None:
    before = _memory_snapshot(memory)
    _forget_memory_state(memory, reason=reason)
    memory.lifecycle_state = "superseded"
    memory.superseded_by_id = replacement.id
    memory.metadata_json = {
        **(memory.metadata_json or {}),
        "superseded_by_memory_id": str(replacement.id),
    }
    await session.flush()
    await _record_memory_evidence(
        session,
        memory,
        action="corrected",
        actor=actor,
        reason=reason,
        source_message_id=source_message_id,
        snapshot=before,
    )


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
            MemoryItem.lifecycle_state != "superseded",
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
    if removed:
        await _delete_orphan_entities(
            session,
            user_id=user_id,
            character_id=character_id,
        )
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
        await supersede_memory(
            session,
            item,
            replacement=memory,
            reason="superseded_by_user_resolution",
            source_message_id=None,
            actor="user",
        )

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
    memory.retention_tier = "core"
    memory.reinforcement_count += 1
    memory.last_reinforced_at = now
    await session.flush()
    await _record_memory_evidence(
        session,
        memory,
        action="resolved",
        actor="user",
        reason="kept_by_user",
        source_message_id=None,
    )
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
    await _delete_orphan_entities(session, user_id=user_id, character_id=character_id)
    return int(result.rowcount or 0)


async def clear_memory_category(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    *,
    category: str,
    scope: str = "general",
) -> int:
    memory_types = {
        "boundaries": {"boundary"},
        "people": {"person"},
        "preferences": {"interest", "preference", "routine", "user_fact"},
        "inside_jokes": {"inside_joke"},
        "moments": {"date", "event", "place", "shared_lore", "shared_moment"},
        "patterns": {
            "interest",
            "preference",
            "relationship_milestone",
            "routine",
            "theme",
            "user_fact",
        },
        "promises": {"boundary", "promise"},
    }.get(category)
    if not memory_types:
        raise MemoryCaptureError("Unknown memory category.")
    result = await session.execute(
        delete(MemoryItem).where(
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
            MemoryItem.scope == scope,
            MemoryItem.memory_type.in_(memory_types),
        )
    )
    await session.flush()
    await _delete_orphan_entities(session, user_id=user_id, character_id=character_id)
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
        if _memory_is_decay_protected(memory):
            memory.decay_score = min(memory.decay_score, 0.15)
            continue
        _apply_decay(memory, now)
        fade_threshold = 0.82 if memory.retention_tier == "transient" else 0.96
        durable_value = (
            memory.importance * 0.3
            + memory.confidence * 0.25
            + memory.future_relevance * 0.25
            + min(memory.reinforcement_count, 5) / 5 * 0.2
        )
        if (
            memory.confidence <= 0.1
            or durable_value < 0.22
            or (memory.decay_score >= fade_threshold and durable_value < 0.58)
        ):
            if await forget_memory(session, memory, reason="faded_by_decay"):
                forgotten += 1
    await session.flush()
    return forgotten


async def maintain_memories(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> MemoryMaintenanceResult:
    """Consolidate exact durable claims, then run tier-aware decay."""

    result = await session.execute(
        select(MemoryItem)
        .where(
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
            MemoryItem.forgotten_at.is_(None),
            MemoryItem.lifecycle_state == "active",
        )
        .order_by(MemoryItem.created_at.asc(), MemoryItem.id.asc())
    )
    memories = list(result.scalars().all())
    for memory in memories:
        if not _metadata_string_list((memory.metadata_json or {}).get("entity_keys")):
            await _link_memory_entities(
                session,
                memory,
                _inferred_entities(memory.memory_type, memory.content, []),
            )
    groups: dict[tuple[str, str], list[MemoryItem]] = {}
    for memory in memories:
        identity = memory.claim_key or f"exact:{_normalized_content(memory.content)}"
        groups.setdefault((memory.scope, identity), []).append(memory)

    consolidated = 0
    for group in groups.values():
        if (
            len(group) < 2
            or len({item.contradiction_group for item in group if item.contradiction_group}) > 1
        ):
            continue
        if any(
            (item.metadata_json or {}).get("contradiction_status") == "conflicts" for item in group
        ):
            continue
        keeper = max(
            group,
            key=lambda item: (
                item.pinned,
                item.retention_tier == "core",
                item.reinforcement_count,
                item.confidence,
                item.updated_at,
                str(item.id),
            ),
        )
        for duplicate in group:
            if duplicate.id == keeper.id:
                continue
            keeper.importance = max(keeper.importance, duplicate.importance)
            keeper.confidence = clamp(max(keeper.confidence, duplicate.confidence) + 0.02, 0.0, 1.0)
            keeper.future_relevance = max(keeper.future_relevance, duplicate.future_relevance)
            keeper.novelty = clamp((keeper.novelty + duplicate.novelty) / 2, 0.0, 1.0)
            keeper.reinforcement_count += max(duplicate.reinforcement_count, 1)
            keeper.last_reinforced_at = max(
                value
                for value in (keeper.last_reinforced_at, duplicate.last_reinforced_at, utc_now())
                if value is not None
            )
            keeper.last_evidence_at = max(
                value
                for value in (keeper.last_evidence_at, duplicate.last_evidence_at, utc_now())
                if value is not None
            )
            keeper.retention_tier = _stronger_retention_tier(
                keeper.retention_tier,
                duplicate.retention_tier,
            )
            keeper.metadata_json = _merged_source_metadata(keeper, duplicate)
            await _transfer_entity_links(session, source=duplicate, target=keeper)
            await session.delete(duplicate)
            consolidated += 1
        if consolidated:
            await session.flush()
            await _record_memory_evidence(
                session,
                keeper,
                action="merged",
                actor="system",
                reason="scheduled_consolidation",
                source_message_id=None,
            )

    faded = await forget_low_value_memories(
        session,
        user_id,
        character_id,
        now=now,
    )
    return MemoryMaintenanceResult(
        consolidated=consolidated,
        faded=faded,
        reviewed=len(memories),
    )


async def maybe_extract_memory(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    message_id: uuid.UUID,
    content: str,
    memory_preferences: dict[str, object] | None = None,
    scope: str = "general",
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
        novelty=decision.novelty,
        future_relevance=decision.future_relevance,
        retention_tier=decision.retention_tier,
        sensitivity=decision.sensitivity,
        source_message_id=message_id,
        extraction_metadata=decision.to_metadata(),
        scope=scope,
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
    if any(marker in normalized for marker in MEMORY_OPT_OUT_MARKERS):
        return MemoryCandidateDecision(accepted=False, reason="user_opted_out")
    if classify_memory_sensitivity(content) == "sensitive":
        return MemoryCandidateDecision(
            accepted=False,
            reason="sensitive_without_explicit_opt_in",
            sensitivity="sensitive",
        )
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
    novelty, future_relevance = _candidate_lifecycle_scores(memory_type, normalized)
    retention_tier = _retention_tier(
        memory_type,
        importance=importance,
        pinned=False,
        requested=None,
    )
    retention_tier = retention_tier_for_preferences(
        memory_type,
        retention_tier,
        memory_preferences or {},
    )
    return MemoryCandidateDecision(
        accepted=True,
        reason="accepted",
        memory_type=memory_type,
        content=memory_content,
        importance=importance,
        confidence=confidence,
        emotional_weight=emotional_weight,
        novelty=novelty,
        future_relevance=future_relevance,
        retention_tier=retention_tier,
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
        memory_type
        in {
            "event",
            "inside_joke",
            "promise",
            "relationship_milestone",
            "shared_lore",
            "theme",
        }
        and memory_preferences.get("remember_emotional_notes") is False
    ):
        return False
    return True


def retention_tier_for_preferences(
    memory_type: str,
    proposed: str,
    memory_preferences: dict[str, object],
) -> str:
    mode = memory_preferences.get("retention_mode", "balanced")
    if mode == "minimal":
        if memory_type in {"boundary", "relationship_milestone"}:
            return "core"
        return "transient" if memory_type in {"event", "theme", "shared_moment"} else "normal"
    if mode == "long_lived" and proposed == "transient":
        return "normal"
    return proposed if proposed in {"transient", "normal", "core"} else "normal"


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
    person_terms = (
        "my friend ",
        "my partner ",
        "my sister ",
        "my brother ",
        "my parent ",
    )
    theme_terms = ("i keep ", "i always struggle ", "this keeps happening")
    shared_lore_terms = ("our ritual ", "we call this ", "our story ")
    if "inside joke" in normalized_content:
        return "inside_joke"
    if any(term in normalized_content for term in shared_lore_terms):
        return "shared_lore"
    if any(term in normalized_content for term in person_terms):
        return "person"
    if any(term in normalized_content for term in theme_terms):
        return "theme"
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
    if memory_type == "person":
        return 0.62, 0.76, 0.12
    if memory_type == "theme":
        return 0.58, 0.68, 0.2
    if memory_type == "shared_lore":
        return 0.72, 0.78, 0.32
    if memory_type == "user_fact":
        return 0.58, 0.78, 0.05
    if memory_type == "event":
        return 0.52, 0.68, 0.25
    if "favorite" in normalized_content or "prefer" in normalized_content:
        return 0.5, 0.78, 0.05
    return 0.45, 0.72, 0.0


def _candidate_lifecycle_scores(memory_type: str, normalized_content: str) -> tuple[float, float]:
    novelty = 0.65
    future_relevance = {
        "boundary": 0.95,
        "date": 0.78,
        "inside_joke": 0.68,
        "person": 0.76,
        "place": 0.66,
        "preference": 0.72,
        "promise": 0.92,
        "routine": 0.86,
        "theme": 0.76,
        "user_fact": 0.8,
    }.get(memory_type, 0.55)
    if any(
        term in normalized_content for term in ("always", "every ", "next time", "please remember")
    ):
        future_relevance = max(future_relevance, 0.84)
    return novelty, future_relevance


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
    entity_match: bool,
) -> float:
    content_terms = _query_terms(memory.content)
    keyword_score = 0.0
    if terms:
        keyword_score = len(terms & content_terms) / max(len(terms), 1)
    vector_score = max(cosine_similarity(query_embedding, memory_embedding), 0.0)
    age_days = max((now - memory.created_at).total_seconds() / 86400, 0)
    recency_score = 1 / (1 + age_days / 14)
    reinforcement_score = min(memory.reinforcement_count, 6) / 6
    query_emotion = _query_emotional_weight(query)
    emotional_compatibility = 0.0
    if query_emotion and memory.emotional_weight:
        emotional_compatibility = max(
            0.0,
            1.0 - abs(query_emotion - memory.emotional_weight),
        )
    relationship_relevance = {
        "boundary": 0.18,
        "inside_joke": 0.16,
        "promise": 0.2,
        "relationship_milestone": 0.16,
        "shared_lore": 0.18,
        "shared_moment": 0.14,
    }.get(memory.memory_type, 0.04)
    if any(marker in query.lower() for marker in ("we ", "remember", "talked", "joke")):
        if memory.memory_type in {"event", "inside_joke", "relationship_milestone"}:
            relationship_relevance += 0.15
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
        + abs(memory.emotional_weight) * 0.04
        + emotional_compatibility * 0.1
        + memory.future_relevance * 0.12
        + reinforcement_score * 0.08
        + recency_score * (0.04 if memory.retention_tier == "core" else 0.08)
        + relationship_relevance
        + (0.24 if entity_match else 0)
        + (0.2 if memory.pinned else 0)
        + (0.08 if memory.retention_tier == "core" else 0)
        - memory.decay_score * 0.25
        - contradiction_penalty
    )


def _select_ranked_memories(
    ranked: list[tuple[MemoryItem, float]],
    *,
    limit: int,
    has_query: bool,
) -> list[MemoryItem]:
    selected: list[MemoryItem] = []
    seen_content: set[str] = set()
    contradiction_counts: dict[str, int] = {}
    for memory, score in ranked:
        if has_query and score < 0.42 and not memory.pinned:
            continue
        key = _normalized_content(memory.content)
        if not key or key in seen_content:
            continue
        group = memory.contradiction_group
        if group and contradiction_counts.get(group, 0) >= 2:
            continue
        selected.append(memory)
        seen_content.add(key)
        if group:
            contradiction_counts[group] = contradiction_counts.get(group, 0) + 1
        if len(selected) >= max(0, limit):
            break
    return selected


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
            MemoryItem.lifecycle_state != "superseded",
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
    memory.retention_tier = "core"
    memory.sensitivity = decision.sensitivity
    memory.future_relevance = max(memory.future_relevance, decision.future_relevance)
    memory.reinforcement_count += 1
    memory.last_reinforced_at = utc_now()
    memory.last_evidence_at = utc_now()


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
    scope: str,
    claim_key: str | None,
) -> MemoryItem | None:
    statement = select(MemoryItem).where(
        MemoryItem.user_id == user_id,
        MemoryItem.character_id == character_id,
        MemoryItem.scope == scope,
        MemoryItem.memory_type == memory_type,
        MemoryItem.lifecycle_state != "superseded",
    )
    if claim_key is not None:
        statement = statement.where(MemoryItem.claim_key == claim_key)
    result = await session.execute(
        statement.order_by(
            MemoryItem.forgotten_at.asc().nullsfirst(),
            MemoryItem.updated_at.desc(),
            MemoryItem.id.asc(),
        ).limit(50)
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
            MemoryItem.lifecycle_state == "active",
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
    memory.lifecycle_state = "forgotten"


def _restore_memory_state(memory: MemoryItem, *, reason: str) -> None:
    now = utc_now()
    metadata = dict(memory.metadata_json or {})
    metadata["last_restored_at"] = now.isoformat()
    metadata["last_restore_reason"] = reason[:80]
    memory.metadata_json = metadata
    memory.forgotten_at = None
    memory.lifecycle_state = "active"
    memory.superseded_by_id = None
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
    if _memory_is_decay_protected(memory):
        memory.decay_score = 0.0
        return
    last_anchor = max(
        value
        for value in (
            memory.last_recalled_at,
            memory.last_reinforced_at,
            memory.last_evidence_at,
            memory.updated_at,
            memory.created_at,
        )
        if value is not None
    )
    metadata = dict(memory.metadata_json or {})
    last_review = _metadata_datetime(metadata.get("last_decay_review_at"))
    total_age_days = max((now - last_anchor).total_seconds() / 86400, 0)
    previous_age_days = (
        max((last_review - last_anchor).total_seconds() / 86400, 0)
        if last_review is not None
        else 0.0
    )
    decay_days = max(total_age_days - 7, 0) - max(previous_age_days - 7, 0)
    tier_rate = {"transient": 0.022, "normal": 0.009, "core": 0.002}.get(
        memory.retention_tier,
        0.009,
    )
    protection = min(
        memory.importance * 0.25
        + memory.confidence * 0.2
        + memory.future_relevance * 0.2
        + min(memory.reinforcement_count, 5) * 0.05
        + abs(memory.emotional_weight) * 0.05,
        0.8,
    )
    decay_delta = max(decay_days, 0) * tier_rate * (1 - protection)
    memory.decay_score = clamp(memory.decay_score + decay_delta, 0.0, 1.0)
    metadata["last_decay_review_at"] = now.isoformat()
    memory.metadata_json = metadata


def _metadata_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def classify_memory_sensitivity(content: str) -> str:
    return (
        "sensitive"
        if any(pattern.search(content) for pattern in SENSITIVE_MEMORY_PATTERNS)
        else "standard"
    )


def _sensitive_memory_query_matches(content: str, query: str) -> bool:
    """Require an explicit sensitive category or exact value before recall."""

    content_categories = _sensitive_memory_categories(content)
    query_categories = _sensitive_memory_categories(query, include_query_markers=True)
    if content_categories & query_categories:
        return True

    normalized_query = query.casefold()
    return any(
        match.group(0).casefold() in normalized_query
        for pattern in SENSITIVE_MEMORY_PATTERNS[:2]
        for match in pattern.finditer(content)
    )


def _sensitive_memory_categories(
    value: str,
    *,
    include_query_markers: bool = False,
) -> set[str]:
    categories: set[str] = set()
    if not include_query_markers:
        if SENSITIVE_MEMORY_PATTERNS[0].search(value):
            categories.add("email")
        if SENSITIVE_MEMORY_PATTERNS[1].search(value):
            categories.add("phone")
        if SENSITIVE_MEMORY_PATTERNS[2].search(value):
            categories.add("financial")
        if SENSITIVE_MEMORY_PATTERNS[3].search(value):
            categories.add("address")
        return categories

    normalized = value.casefold()
    if re.search(r"\bmy (?:email|e-mail) address\b", normalized):
        categories.add("email")
    if re.search(r"\bmy (?:phone|telephone|mobile) number\b", normalized):
        categories.add("phone")
    if re.search(
        r"\bmy (?:bank account|routing number|credit card|financial details?)\b",
        normalized,
    ):
        categories.add("financial")
    if re.search(r"\b(?:my (?:home )?address|where do i live|where i live)\b", normalized):
        categories.add("address")
    return categories


def user_opted_out_of_memory(content: str) -> bool:
    normalized = content.casefold()
    return any(marker in normalized for marker in MEMORY_OPT_OUT_MARKERS)


def _retention_tier(
    memory_type: str,
    *,
    importance: float,
    pinned: bool,
    requested: str | None,
) -> str:
    if requested not in {None, "transient", "normal", "core"}:
        raise MemoryCaptureError("Memory retention must be transient, normal, or core.")
    if pinned or memory_type in {"boundary", "relationship_milestone"}:
        return "core"
    if requested is not None:
        return requested
    if memory_type in {"promise", "routine"} or importance >= 0.8:
        return "core"
    if memory_type in {"event", "theme"} and importance < 0.45:
        return "transient"
    return "normal"


def _stronger_retention_tier(left: str, right: str) -> str:
    order = {"transient": 0, "normal": 1, "core": 2}
    return max((left, right), key=lambda value: order.get(value, 1))


def _memory_is_decay_protected(memory: MemoryItem) -> bool:
    return bool(
        memory.pinned
        or memory.retention_tier == "core"
        or memory.memory_type in {"boundary", "relationship_milestone"}
        or (memory.reinforcement_count >= 3 and memory.confidence >= 0.82)
    )


def _query_emotional_weight(query: str) -> float:
    normalized = query.casefold()
    positive = ("happy", "glad", "excited", "proud", "relieved", "love")
    negative = ("sad", "hurt", "angry", "afraid", "anxious", "upset", "grief")
    if any(marker in normalized for marker in positive):
        return 0.65
    if any(marker in normalized for marker in negative):
        return -0.65
    return 0.0


def _bounded_emotional_context(value: dict[str, object]) -> dict[str, object]:
    context: dict[str, object] = {}
    for key in ("feeling", "meaning", "helped", "hurt", "resolution"):
        item = value.get(key)
        if isinstance(item, str) and item.strip():
            context[key] = " ".join(item.split())[:240]
    resolved = value.get("resolved")
    if isinstance(resolved, bool):
        context["resolved"] = resolved
    return context


def _merge_emotional_context(
    existing: object,
    incoming: dict[str, object],
) -> dict[str, object]:
    current = _bounded_emotional_context(existing if isinstance(existing, dict) else {})
    return {**current, **incoming}


def _memory_snapshot(memory: MemoryItem) -> dict[str, object]:
    return {
        "content": memory.content,
        "memory_type": memory.memory_type,
        "importance": round(memory.importance, 4),
        "confidence": round(memory.confidence, 4),
        "emotional_weight": round(memory.emotional_weight, 4),
        "retention_tier": memory.retention_tier,
        "lifecycle_state": memory.lifecycle_state,
        "reinforcement_count": memory.reinforcement_count,
        "pinned": memory.pinned,
    }


async def _record_memory_evidence(
    session: AsyncSession,
    memory: MemoryItem,
    *,
    action: str,
    actor: str,
    reason: str,
    source_message_id: uuid.UUID | None,
    snapshot: dict[str, object] | None = None,
) -> None:
    session.add(
        MemoryEvidence(
            memory_id=memory.id,
            source_message_id=source_message_id,
            action=action,
            actor=actor if actor in {"system", "user"} else "system",
            reason=" ".join(reason.split())[:120] or "unspecified",
            snapshot_json=snapshot or _memory_snapshot(memory),
        )
    )
    await session.flush()


def _inferred_entities(
    memory_type: str,
    content: str,
    facets: list[str],
) -> list[tuple[str, str]]:
    entity_type = {
        "date": "date",
        "person": "person",
        "place": "place",
        "routine": "routine",
    }.get(memory_type)
    values: list[tuple[str, str]] = []
    if entity_type:
        values.append((entity_type, _entity_name_for_memory(memory_type, content)))
    for facet in facets[:4]:
        values.append(("topic", facet))
    return values


def _entity_name_for_memory(memory_type: str, content: str) -> str:
    if memory_type == "person":
        match = re.search(
            r"\bmy\s+(?:friend|partner|sister|brother|parent)\s+([\w'-]{2,})",
            content,
            re.I,
        )
        if match:
            return match.group(1)
    if memory_type == "place":
        match = re.search(r"\b(?:live in|from|place is)\s+([^,.;!?]{2,80})", content, re.I)
        if match:
            return match.group(1).strip()
    if memory_type == "date":
        match = re.search(
            r"\b(?:\d{4}-\d{2}-\d{2}|(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:,\s*\d{4})?)\b",
            content,
            re.I,
        )
        if match:
            return match.group(0)
    return content


async def _link_memory_entities(
    session: AsyncSession,
    memory: MemoryItem,
    entities: list[tuple[str, str]],
    *,
    replace: bool = False,
) -> None:
    if replace:
        await session.execute(
            delete(MemoryEntityLink).where(MemoryEntityLink.memory_id == memory.id)
        )
    now = utc_now()
    seen: set[tuple[str, str]] = set()
    entity_keys: list[str] = []
    for raw_type, raw_name in entities[:8]:
        entity_type = (
            raw_type
            if raw_type in {"date", "person", "place", "project", "routine", "topic"}
            else "topic"
        )
        name = " ".join(str(raw_name).split())[:160]
        normalized_name = _normalized_content(name)[:160]
        identity = (entity_type, normalized_name)
        if len(normalized_name) < 2 or identity in seen:
            continue
        seen.add(identity)
        result = await session.execute(
            select(MemoryEntity).where(
                MemoryEntity.user_id == memory.user_id,
                MemoryEntity.character_id == memory.character_id,
                MemoryEntity.entity_type == entity_type,
                MemoryEntity.normalized_name == normalized_name,
            )
        )
        entity = result.scalar_one_or_none()
        if entity is None:
            entity = MemoryEntity(
                user_id=memory.user_id,
                character_id=memory.character_id,
                entity_type=entity_type,
                name=name,
                normalized_name=normalized_name,
                first_seen_at=now,
                last_seen_at=now,
                mention_count=1,
            )
            session.add(entity)
            await session.flush()
        else:
            entity.last_seen_at = now
            entity.mention_count += 1
        link = await session.get(
            MemoryEntityLink,
            {"memory_id": memory.id, "entity_id": entity.id},
        )
        if link is None:
            session.add(
                MemoryEntityLink(
                    memory_id=memory.id,
                    entity_id=entity.id,
                    relation="about",
                )
            )
        entity_keys.append(f"{entity_type}:{normalized_name}")
    if entity_keys:
        memory.metadata_json = {
            **(memory.metadata_json or {}),
            "entity_keys": entity_keys,
        }
    elif replace:
        metadata = dict(memory.metadata_json or {})
        metadata.pop("entity_keys", None)
        memory.metadata_json = metadata
    await session.flush()


async def _entity_matching_memory_ids(
    session: AsyncSession,
    *,
    candidates: list[MemoryItem],
    query: str,
) -> set[uuid.UUID]:
    if not candidates or not query.strip():
        return set()
    normalized_query = _normalized_content(query)
    rows = await session.execute(
        select(MemoryEntityLink.memory_id, MemoryEntity.normalized_name)
        .join(MemoryEntity, MemoryEntity.id == MemoryEntityLink.entity_id)
        .where(MemoryEntityLink.memory_id.in_([memory.id for memory in candidates]))
    )
    return {
        memory_id
        for memory_id, normalized_name in rows.all()
        if len(normalized_name) >= 2 and normalized_name in normalized_query
    }


async def _transfer_entity_links(
    session: AsyncSession,
    *,
    source: MemoryItem,
    target: MemoryItem,
) -> None:
    rows = await session.execute(
        select(MemoryEntityLink).where(MemoryEntityLink.memory_id == source.id)
    )
    for link in rows.scalars().all():
        existing = await session.get(
            MemoryEntityLink,
            {"memory_id": target.id, "entity_id": link.entity_id},
        )
        if existing is None:
            session.add(
                MemoryEntityLink(
                    memory_id=target.id,
                    entity_id=link.entity_id,
                    relation=link.relation,
                )
            )


async def _delete_orphan_entities(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
) -> None:
    await session.execute(
        delete(MemoryEntity).where(
            MemoryEntity.user_id == user_id,
            MemoryEntity.character_id == character_id,
            MemoryEntity.id.not_in(select(MemoryEntityLink.entity_id)),
        )
    )
    await session.flush()


def _merged_source_metadata(keeper: MemoryItem, duplicate: MemoryItem) -> dict[str, object]:
    metadata = dict(keeper.metadata_json or {})
    source_ids = _source_message_ids(
        metadata, keeper.source_message_id, duplicate.source_message_id
    )
    for source_id in _metadata_string_list(
        (duplicate.metadata_json or {}).get("source_message_ids")
    ):
        if source_id not in source_ids:
            source_ids.append(source_id)
    if source_ids:
        metadata["source_message_ids"] = source_ids[:24]
    metadata["consolidated_at"] = utc_now().isoformat()
    return metadata


def _bounded_facets(values: list[str]) -> list[str]:
    facets: list[str] = []
    for value in values:
        normalized = " ".join(str(value).strip().split())[:80]
        if normalized and normalized.casefold() not in {item.casefold() for item in facets}:
            facets.append(normalized)
        if len(facets) >= 8:
            break
    return facets


def _validated_memory_content(content: str) -> str:
    memory_content = _format_memory(content)
    if not memory_content:
        raise MemoryCaptureError("An empty memory cannot be saved.")
    normalized_content = memory_content.casefold()
    if any(term in normalized_content for term in UNSAFE_MEMORY_TERMS):
        raise MemoryCaptureError("That memory may contain private credential data.")
    if is_blocked_content(memory_content):
        raise MemoryCaptureError("That memory crosses durable-memory safety boundaries.")
    return memory_content


def _embedding_text(content: str, facets: list[str]) -> str:
    return " ".join((content, *facets)).strip()


def _format_memory(content: str) -> str:
    cleaned = " ".join(content.strip().split())
    if len(cleaned) > 500:
        cleaned = cleaned[:497].rstrip() + "..."
    return cleaned
