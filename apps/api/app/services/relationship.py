from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.companion.emotion import (
    apply_emotional_turn,
    emotional_mood,
    project_emotional_state,
    read_emotional_state,
)
from app.companion.perception import infer_turn_perception
from app.models import (
    EpisodicJournal,
    EpisodicJournalSource,
    MemoryItem,
    Message,
    RelationshipEvent,
    RelationshipState,
    ScheduledJob,
    utc_now,
)
from app.services.embedding import text_embedding
from app.services.jobs import create_job

RELATIONSHIP_EFFECT_VERSION = "relationship_effect_v2"
SUPPORTED_EFFECT_VERSIONS = {"relationship_effect_v1", RELATIONSHIP_EFFECT_VERSION}
RELATIONSHIP_COGNITION_VERSION = "relationship_cognition_v2"

RELATIONSHIP_METRIC_BOUNDS: dict[str, tuple[float, float]] = {
    "trust": (-100.0, 100.0),
    "intimacy": (0.0, 100.0),
    "warmth": (-100.0, 100.0),
    "tension": (0.0, 100.0),
    "familiarity": (0.0, 100.0),
    "attachment": (0.0, 100.0),
    "emotional_safety": (0.0, 100.0),
    "reliability": (0.0, 100.0),
    "reciprocity": (0.0, 100.0),
    "repair_progress": (0.0, 100.0),
    "boundary_alignment": (0.0, 100.0),
    "shared_history_depth": (0.0, 100.0),
}
RELATIONSHIP_EFFECT_KEYS = tuple(RELATIONSHIP_METRIC_BOUNDS)
RELATIONSHIP_BASELINES: dict[str, float] = {
    "trust": 0.0,
    "intimacy": 0.0,
    "warmth": 0.0,
    "tension": 0.0,
    "familiarity": 0.0,
    "attachment": 0.0,
    "emotional_safety": 50.0,
    "reliability": 50.0,
    "reciprocity": 0.0,
    "repair_progress": 0.0,
    "boundary_alignment": 100.0,
    "shared_history_depth": 0.0,
}
RELATIONSHIP_EVENT_TYPES = {
    "support",
    "vulnerability",
    "promise",
    "consistency",
    "promise_broken",
    "conflict",
    "apology",
    "boundary_set",
    "boundary_violation",
    "boundary_revoked",
    "repair",
    "humor",
    "ritual",
    "milestone",
    "absence",
    "return",
    "reset",
}
BOUNDARY_EVENT_TYPES = {"boundary_set", "boundary_revoked", "boundary_violation"}
DURABLE_BOUNDARY_EVENT_TYPES = {"boundary_set", "boundary_revoked"}
EVENT_BASE_DELTAS: dict[str, dict[str, float]] = {
    "support": {
        "trust": 0.45,
        "warmth": 0.75,
        "familiarity": 0.20,
        "emotional_safety": 0.65,
        "reciprocity": 0.35,
    },
    "vulnerability": {
        "trust": 0.85,
        "intimacy": 0.70,
        "emotional_safety": 0.45,
        "reciprocity": 0.55,
    },
    "promise": {
        "trust": 0.10,
        "reliability": 0.10,
        "shared_history_depth": 0.25,
    },
    "consistency": {
        "trust": 0.65,
        "reliability": 1.00,
        "emotional_safety": 0.35,
    },
    "promise_broken": {
        "trust": -1.00,
        "reliability": -1.60,
        "emotional_safety": -0.70,
        "tension": 0.80,
    },
    "conflict": {
        "trust": -0.25,
        "warmth": -0.55,
        "tension": 1.25,
        "emotional_safety": -0.90,
    },
    "apology": {
        "trust": 0.25,
        "tension": -0.65,
        "emotional_safety": 0.35,
        "repair_progress": 2.50,
    },
    "boundary_set": {"trust": 0.10},
    "boundary_violation": {
        "trust": -1.60,
        "warmth": -0.80,
        "tension": 2.00,
        "emotional_safety": -2.20,
        "boundary_alignment": -4.00,
    },
    "boundary_revoked": {},
    "repair": {
        "trust": 0.45,
        "warmth": 0.25,
        "tension": -1.00,
        "emotional_safety": 0.80,
        "repair_progress": 4.00,
    },
    "humor": {
        "warmth": 0.40,
        "familiarity": 0.45,
        "reciprocity": 0.20,
    },
    "ritual": {
        "familiarity": 0.55,
        "reciprocity": 0.30,
        "shared_history_depth": 0.85,
    },
    "milestone": {},
    "absence": {},
    "return": {},
    "reset": {},
}
EVENT_SUMMARIES = {
    "support": "Care or appreciation was expressed clearly.",
    "vulnerability": "Something personally meaningful was entrusted to the relationship.",
    "promise": "A future intention became part of the shared context.",
    "consistency": "Follow-through added evidence of reliability.",
    "promise_broken": "A missed expectation made reliability feel less certain.",
    "conflict": "A disagreement or hurt became important to address.",
    "apology": "An apology opened a path toward repair.",
    "boundary_set": "A boundary was stated and is now authoritative.",
    "boundary_violation": "A stated limit may not have been respected.",
    "boundary_revoked": "A previously stated boundary was explicitly changed.",
    "repair": "A concrete repair attempt moved the relationship forward.",
    "humor": "Shared humor added to the relationship's familiar language.",
    "ritual": "A recurring shared ritual became more meaningful.",
    "milestone": "A meaningful relationship milestone was reached.",
    "absence": "Time passed without changing the relationship's earned foundations.",
    "return": "The conversation resumed after time apart, without obligation or guilt.",
    "reset": "The relationship's current interpretation was reset by the user.",
}
RELATIONSHIP_MILESTONES = (
    {
        "id": "first_warmth",
        "field": "warmth",
        "threshold": 1.0,
        "title": "A warmer rhythm",
        "summary": "A warmer rhythm has started to form.",
        "memory": "A warmer rhythm has started to form between the user and character.",
        "tags": ["milestone", "warm"],
    },
    {
        "id": "trust_seed",
        "field": "trust",
        "threshold": 0.6,
        "title": "A seed of trust",
        "summary": "A first seed of trust has taken hold.",
        "memory": "A first seed of trust has taken hold in the relationship.",
        "tags": ["milestone", "trust"],
    },
    {
        "id": "steady_rhythm",
        "field": "familiarity",
        "threshold": 1.0,
        "title": "A recurring rhythm",
        "summary": "The conversation has begun to feel like a recurring rhythm.",
        "memory": "The conversation has begun to feel like a recurring rhythm.",
        "tags": ["milestone", "rhythm"],
    },
    {
        "id": "shared_history",
        "field": "shared_history_depth",
        "threshold": 1.5,
        "title": "Shared history",
        "summary": "Specific shared history is beginning to carry forward.",
        "memory": "Specific shared history is beginning to carry forward.",
        "tags": ["milestone", "shared-history"],
    },
    {
        "id": "repair_arc",
        "field": "repair_progress",
        "threshold": 2.0,
        "title": "A meaningful repair",
        "summary": "A repair moment was handled gently enough to matter.",
        "memory": "A repair moment was handled gently enough to matter.",
        "tags": ["milestone", "repair"],
        "requires_event": {"apology", "repair"},
    },
)

POSITIVE_MARKERS = (
    "thank you",
    "thanks for",
    "i appreciate",
    "that helped",
    "you helped",
    "that meant a lot",
)
VULNERABILITY_MARKERS = (
    "i'm afraid",
    "i am afraid",
    "i feel lonely",
    "i'm worried",
    "i am worried",
    "i feel ashamed",
    "this is hard to say",
    "i trust you with",
)
CONFLICT_MARKERS = (
    "i'm angry",
    "i am angry",
    "i'm upset",
    "i am upset",
    "i hate that",
    "i'm frustrated",
    "i am frustrated",
    "you hurt me",
)
APOLOGY_MARKERS = ("i'm sorry", "i am sorry", "i apologize", "my fault")
REPAIR_MARKERS = (
    "can we repair",
    "can we work through",
    "i want to make this right",
    "let's try again",
    "let us try again",
)
PROMISE_MARKERS = ("i promise", "i will remember to", "i'll remember to")
CONSISTENCY_MARKERS = (
    "you remembered",
    "you kept your promise",
    "you followed through",
    "you've been consistent",
    "you have been consistent",
)
BROKEN_PROMISE_MARKERS = (
    "you forgot",
    "you broke your promise",
    "you said you would",
    "you didn't follow through",
    "you did not follow through",
)
HUMOR_MARKERS = ("inside joke", "our joke", "running joke", "you made me laugh")
RITUAL_MARKERS = (
    "our ritual",
    "our routine",
    "every morning we",
    "every night we",
    "we always do this",
)
BOUNDARY_SET_MARKERS = (
    "please don't",
    "please do not",
    "don't call me",
    "do not call me",
    "i'm not comfortable with",
    "i am not comfortable with",
    "my boundary",
    "stop ",
    "no more ",
)
BOUNDARY_VIOLATION_MARKERS = (
    "i asked you not to",
    "you crossed my boundary",
    "you ignored my boundary",
    "you didn't stop",
    "you did not stop",
)
BOUNDARY_REVOKE_MARKERS = (
    "that boundary no longer applies",
    "i changed my mind about that boundary",
    "you can call me that now",
)


@dataclass(frozen=True)
class RelationshipEvidence:
    event_type: str
    summary: str
    evidence_quote: str | None
    confidence: float
    significance: float
    boundary_key: str | None = None
    origin: str = "deterministic"


@dataclass(frozen=True)
class RelationshipPlanContext:
    current_state: str
    recent_change: str
    unresolved_tension: str
    active_boundary: str
    familiarity: str
    initiative: str


async def get_or_create_relationship(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
) -> RelationshipState:
    result = await session.execute(
        select(RelationshipState).where(
            RelationshipState.user_id == user_id,
            RelationshipState.character_id == character_id,
        )
    )
    state = result.scalar_one_or_none()
    if state is not None:
        _ensure_state_defaults(state)
        return state

    state = RelationshipState(
        user_id=user_id,
        character_id=character_id,
        **RELATIONSHIP_BASELINES,
        mood="steady",
        conflict_state="clear",
        repair_needed=False,
        emotional_state_json={},
        tags_json=[],
        metadata_json={},
    )
    session.add(state)
    await session.flush()
    return state


async def get_current_relationship(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
) -> RelationshipState:
    state = await get_or_create_relationship(session, user_id, character_id)
    now = utc_now()
    await _record_absence_if_needed(session, state, now=now)
    apply_relationship_decay(state, now)
    _update_public_facets(state)
    await session.flush()
    return state


async def _record_absence_if_needed(
    session: AsyncSession,
    state: RelationshipState,
    *,
    now: datetime,
) -> None:
    if state.last_interaction_at is None or now - state.last_interaction_at < timedelta(days=3):
        return
    gap_days = max((now - state.last_interaction_at).days, 3)
    await _record_relationship_event(
        session,
        state=state,
        evidence=RelationshipEvidence(
            event_type="absence",
            summary=EVENT_SUMMARIES["absence"],
            evidence_quote=None,
            confidence=1.0,
            significance=clamp(gap_days / 30, 0.3, 1.0),
            origin="elapsed_time",
        ),
        source_message_id=None,
        scope="general",
        occurred_at=now,
    )


async def update_relationship_from_message(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    content: str,
) -> RelationshipState:
    state, _effect = await update_relationship_from_message_with_effect(
        session,
        user_id,
        character_id,
        content,
    )
    return state


async def update_relationship_from_message_with_effect(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    content: str,
    *,
    source_message_id: uuid.UUID | None = None,
    scope: str = "general",
    boundary_only: bool = False,
) -> tuple[RelationshipState, dict[str, object]]:
    state = await get_or_create_relationship(session, user_id, character_id)
    now = utc_now()
    previous_interaction = state.last_interaction_at
    if scope == "general":
        apply_relationship_decay(state, now)
    before_values = _snapshot_values(state)
    tags_before = set(state.tags_json or [])
    repair_needed_before = state.repair_needed
    conflict_state_before = state.conflict_state
    mood_before = state.mood
    emotional_state_before = dict(state.emotional_state_json or {})

    evidence = _detect_message_evidence(
        content,
        previous_interaction=previous_interaction,
        now=now,
        boundary_only=boundary_only or scope == "adult",
    )
    event_ids: list[str] = []
    event_types: set[str] = set()
    for item in evidence:
        event, created = await _record_relationship_event(
            session,
            state=state,
            evidence=item,
            source_message_id=source_message_id,
            scope=scope,
            occurred_at=now,
        )
        if created:
            event_ids.append(str(event.id))
            event_types.add(event.event_type)

    if scope == "general":
        perception = infer_turn_perception(content, recent_messages=[], journals=[])
        if "conflict" in event_types and not perception.conflict_signal:
            perception = replace(perception, conflict_signal=True)
        emotion = apply_emotional_turn(state, perception, now=now)
        state.mood = emotional_mood(emotion, repair_needed=state.repair_needed)
        state.last_interaction_at = now
        milestone_ids, milestone_event_ids = await _maybe_create_milestones(
            session,
            state,
            before_values,
            event_types,
            source_message_id=source_message_id,
            occurred_at=now,
        )
        event_ids.extend(milestone_event_ids)
    else:
        milestone_ids = []

    if scope == "general":
        await _refresh_relationship_derived_state(session, state)
        changes = _recent_changes(before_values, state, now)
        state.metadata_json = {
            **(state.metadata_json or {}),
            "recent_changes": changes,
            "recent_change_summary": _recent_change_summary(changes),
            "evidence_counts": await _evidence_counts_for_state(session, state),
        }
        _update_public_facets(state)
    effect = _relationship_effect_metadata(
        state,
        scope=scope,
        before_values=before_values,
        tags_before=tags_before,
        repair_needed_before=repair_needed_before,
        conflict_state_before=conflict_state_before,
        mood_before=mood_before,
        emotional_state_before=emotional_state_before,
        applied_at=now,
        source_message_id=source_message_id,
        event_ids=event_ids,
        milestone_ids=milestone_ids,
    )
    if scope == "general":
        await ensure_relationship_decay_job(session, user_id, character_id)
    await session.flush()
    return state, effect


async def refine_relationship_from_evidence(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    source_message: Message,
    evidence: tuple[dict[str, object], ...] = (),
) -> bool:
    metadata = dict(source_message.metadata_json or {})
    if metadata.get("relationship_cognition_version") == RELATIONSHIP_COGNITION_VERSION:
        return False
    effect = metadata.get("relationship_effect")
    if not isinstance(effect, dict) or effect.get("version") != RELATIONSHIP_EFFECT_VERSION:
        return False

    proposals = _grounded_cognition_evidence(
        source_message.content,
        evidence=evidence,
    )
    if not proposals:
        source_message.metadata_json = {
            **metadata,
            "relationship_cognition_version": RELATIONSHIP_COGNITION_VERSION,
        }
        return False

    state = await get_or_create_relationship(session, user_id, character_id)
    before_values = _snapshot_values(state)
    new_event_ids: list[str] = []
    new_types: set[str] = set()
    for proposal in proposals:
        event, created = await _record_relationship_event(
            session,
            state=state,
            evidence=proposal,
            source_message_id=source_message.id,
            scope="general",
            occurred_at=utc_now(),
        )
        if created:
            new_event_ids.append(str(event.id))
            new_types.add(event.event_type)
    if not new_event_ids:
        source_message.metadata_json = {
            **metadata,
            "relationship_cognition_version": RELATIONSHIP_COGNITION_VERSION,
        }
        return False

    milestone_ids, milestone_event_ids = await _maybe_create_milestones(
        session,
        state,
        before_values,
        new_types,
        source_message_id=source_message.id,
        occurred_at=utc_now(),
    )
    new_event_ids.extend(milestone_event_ids)
    await _refresh_relationship_derived_state(session, state)
    changes = _recent_changes(before_values, state, utc_now())
    state.metadata_json = {
        **(state.metadata_json or {}),
        "recent_changes": changes,
        "recent_change_summary": _recent_change_summary(changes),
        "evidence_counts": await _evidence_counts_for_state(session, state),
    }
    _update_public_facets(state)

    prior_ids = _metadata_list(effect.get("event_ids"))
    prior_milestones = _metadata_list(effect.get("milestone_ids"))
    effect_before = effect.get("before_values")
    effect_before_values = (
        {
            key: float(effect_before[key])
            for key in RELATIONSHIP_EFFECT_KEYS
            if isinstance(effect_before, dict) and isinstance(effect_before.get(key), int | float)
        }
        if isinstance(effect_before, dict)
        else {}
    )
    if len(effect_before_values) != len(RELATIONSHIP_EFFECT_KEYS):
        prior_deltas = effect.get("deltas")
        effect_before_values = {
            key: _snapshot_values(state)[key]
            - (
                float(prior_deltas[key])
                if isinstance(prior_deltas, dict) and isinstance(prior_deltas.get(key), int | float)
                else 0.0
            )
            for key in RELATIONSHIP_EFFECT_KEYS
        }
    source_message.metadata_json = {
        **metadata,
        "relationship_effect": {
            **effect,
            "deltas": _deltas_from(effect_before_values, state),
            "event_ids": list(dict.fromkeys([*prior_ids, *new_event_ids])),
            "milestone_ids": list(dict.fromkeys([*prior_milestones, *milestone_ids])),
            "repair_needed_after": state.repair_needed,
            "conflict_state_after": state.conflict_state,
            "mood_after": state.mood,
        },
        "relationship_cognition_version": RELATIONSHIP_COGNITION_VERSION,
    }
    await session.flush()
    return True


async def reverse_relationship_message_effect(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    effect: object,
) -> bool:
    if not isinstance(effect, dict) or effect.get("version") not in SUPPORTED_EFFECT_VERSIONS:
        return False
    state = await get_or_create_relationship(session, user_id, character_id)
    effect_scope = effect.get("scope")
    event_ids = [_optional_uuid(value) for value in _metadata_list(effect.get("event_ids"))]
    event_ids = [value for value in event_ids if value is not None]
    reversed_from_events = False
    events: list[RelationshipEvent] = []
    if event_ids:
        result = await session.execute(
            select(RelationshipEvent).where(
                RelationshipEvent.id.in_(event_ids),
                RelationshipEvent.user_id == user_id,
                RelationshipEvent.character_id == character_id,
            )
        )
        events = list(result.scalars().all())
        for event in events:
            if event.affects_current_state:
                _reverse_event_deltas(state, event.dimension_deltas_json)
                reversed_from_events = True
            await _delete_linked_milestone(session, event)
            await session.delete(event)
    if effect_scope == "adult" and all(event.scope == "adult" for event in events):
        await session.flush()
        return True

    if not reversed_from_events:
        deltas = effect.get("deltas")
        if not isinstance(deltas, dict):
            return False
        for key in RELATIONSHIP_EFFECT_KEYS:
            value = deltas.get(key)
            if not isinstance(value, int | float):
                if effect.get("version") == "relationship_effect_v1" and key not in deltas:
                    continue
                return False
            minimum, maximum = RELATIONSHIP_METRIC_BOUNDS[key]
            setattr(state, key, clamp(float(getattr(state, key)) - float(value), minimum, maximum))

    emotional_before = effect.get("emotional_state_before")
    if isinstance(emotional_before, dict):
        state.emotional_state_json = emotional_before
    source_message_id = _effect_source_message_id(effect)
    if source_message_id is not None:
        state.metadata_json = _remove_relationship_effect_entries(
            state.metadata_json or {},
            source_message_id=source_message_id,
            milestone_ids=set(_metadata_list(effect.get("milestone_ids"))),
        )
        await _delete_relationship_milestone_memories(
            session,
            user_id=user_id,
            character_id=character_id,
            source_message_id=source_message_id,
        )
    await _refresh_relationship_derived_state(session, state)
    state.mood = emotional_mood(read_emotional_state(state), repair_needed=state.repair_needed)
    state.metadata_json = {
        **(state.metadata_json or {}),
        "recent_changes": [
            {
                "at": utc_now().isoformat(),
                "key": "edit_recalculation",
                "label": "Recalculated",
                "direction": "flat",
                "magnitude": "subtle",
                "summary": "The edited turn was recalculated from its remaining evidence.",
            }
        ],
        "recent_change_summary": "The edited turn was recalculated from its remaining evidence.",
        "evidence_counts": await _evidence_counts_for_state(session, state),
    }
    _update_public_facets(state)
    await session.flush()
    return True


async def list_relationship_events(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    scopes: tuple[str, ...] = ("general",),
    limit: int = 200,
) -> list[RelationshipEvent]:
    result = await session.execute(
        select(RelationshipEvent)
        .where(
            RelationshipEvent.user_id == user_id,
            RelationshipEvent.character_id == character_id,
            RelationshipEvent.scope.in_(scopes),
        )
        .order_by(desc(RelationshipEvent.occurred_at), desc(RelationshipEvent.created_at))
        .limit(max(1, min(limit, 200)))
    )
    return list(result.scalars().all())


async def active_relationship_boundaries(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    scopes: tuple[str, ...] = ("general",),
) -> list[RelationshipEvent]:
    result = await session.execute(
        select(RelationshipEvent)
        .where(
            RelationshipEvent.user_id == user_id,
            RelationshipEvent.character_id == character_id,
            RelationshipEvent.scope.in_(scopes),
            RelationshipEvent.event_type.in_(("boundary_set", "boundary_revoked")),
        )
        .order_by(RelationshipEvent.occurred_at, RelationshipEvent.created_at)
    )
    active: dict[str, RelationshipEvent] = {}
    for event in result.scalars().all():
        key = _event_boundary_key(event)
        if event.event_type == "boundary_set":
            active[key] = event
        else:
            removed = active.pop(key, None)
            if removed is None and len(active) == 1:
                active.pop(next(iter(active)))
    return list(active.values())


def relationship_event_public_dict(
    event: RelationshipEvent,
    *,
    active_boundary_ids: set[uuid.UUID] | None = None,
) -> dict[str, object]:
    metadata = event.metadata_json if isinstance(event.metadata_json, dict) else {}
    return {
        "id": event.id,
        "character_id": event.character_id,
        "source_message_id": event.source_message_id,
        "linked_moment_id": event.journal_id,
        "scope": event.scope,
        "event_type": event.event_type,
        "summary": event.summary,
        "evidence_excerpt": (_compact(event.evidence_quote, 240) if event.evidence_quote else None),
        "significance": _significance_label(event.significance),
        "is_boundary_active": bool(
            active_boundary_ids is not None and event.id in active_boundary_ids
        ),
        "occurred_at": event.occurred_at,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
        "corrected": bool(metadata.get("correction_history")),
    }


async def correct_relationship_event(
    session: AsyncSession,
    *,
    event: RelationshipEvent,
    state: RelationshipState,
    summary: str | None,
    event_type: str | None,
) -> RelationshipEvent:
    next_type = event_type or event.event_type
    system_event_types = {"milestone", "absence", "return", "reset"}
    if next_type not in RELATIONSHIP_EVENT_TYPES or (
        event_type is not None
        and (next_type in system_event_types or event.event_type in system_event_types)
    ):
        raise ValueError("That relationship event type cannot be selected.")
    previous = {
        "at": utc_now().isoformat(),
        "event_type": event.event_type,
        "summary": event.summary,
    }
    previous_event_type = event.event_type
    was_active = event.affects_current_state
    if was_active:
        _reverse_event_deltas(state, event.dimension_deltas_json)
    event.event_type = next_type
    if summary is not None:
        event.summary = _compact(summary, 500)
        if event.journal_id is not None:
            journal = await session.get(EpisodicJournal, event.journal_id)
            if journal is not None:
                journal.summary = event.summary
        if event.memory_id is not None:
            memory = await session.get(MemoryItem, event.memory_id)
            if memory is not None:
                memory.content = event.summary
                memory.embedding = text_embedding(event.summary)
    metadata = dict(event.metadata_json or {})
    dimension_reset_history = metadata.get("dimension_reset_history")
    dimension_reset_history = (
        dimension_reset_history if isinstance(dimension_reset_history, list) else []
    )
    reset_dimensions = {
        str(dimension)
        for reset in dimension_reset_history
        if isinstance(reset, dict)
        for dimension in reset.get("dimensions", [])
        if isinstance(dimension, str)
    }
    evidence = RelationshipEvidence(
        event_type=event.event_type,
        summary=event.summary,
        evidence_quote=event.evidence_quote,
        confidence=event.confidence,
        significance=event.significance,
        boundary_key=_event_boundary_key(event),
        origin="user_correction",
    )
    recalculated_deltas = _calculated_event_deltas(evidence) if event.scope == "general" else {}
    recalculated_deltas = {
        dimension: delta
        for dimension, delta in recalculated_deltas.items()
        if dimension not in reset_dimensions
    }
    event.dimension_deltas_json = (
        _bounded_event_deltas(state, recalculated_deltas)
        if event.scope == "general"
        else recalculated_deltas
    )
    event.affects_current_state = bool(
        event.scope == "general"
        and previous_event_type not in system_event_types
        and event.dimension_deltas_json
    )
    if event.affects_current_state:
        _apply_event_deltas(state, event.dimension_deltas_json)
    history = metadata.get("correction_history")
    history = list(history) if isinstance(history, list) else []
    history.append(previous)
    event.metadata_json = {
        **metadata,
        "origin": "user_correction",
        "boundary_key": evidence.boundary_key,
        "correction_history": history[-10:],
    }
    if event.scope == "general":
        await _refresh_relationship_derived_state(session, state)
        _record_manual_change(state, "A meaningful moment was corrected by the user.")
        _update_public_facets(state)
    await session.flush()
    return event


async def delete_relationship_event(
    session: AsyncSession,
    *,
    event: RelationshipEvent,
    state: RelationshipState,
) -> None:
    if event.affects_current_state:
        _reverse_event_deltas(state, event.dimension_deltas_json)
    await _delete_linked_milestone(session, event)
    await session.delete(event)
    await session.flush()
    if event.scope == "general":
        await _refresh_relationship_derived_state(session, state)
        _record_manual_change(state, "A meaningful moment was removed by the user.")
        state.metadata_json = {
            **(state.metadata_json or {}),
            "evidence_counts": await _evidence_counts_for_state(session, state),
        }
        _update_public_facets(state)


async def reset_relationship(
    session: AsyncSession,
    *,
    state: RelationshipState,
    mode: str,
    dimensions: tuple[str, ...] | None = None,
) -> RelationshipState:
    if mode not in {"dimensions", "restart"}:
        raise ValueError("Relationship reset mode must be dimensions or restart.")
    if mode == "restart" and dimensions is not None:
        raise ValueError("A relationship restart does not accept individual dimensions.")
    selected_dimensions = (
        tuple(RELATIONSHIP_EFFECT_KEYS)
        if mode == "restart" or dimensions is None
        else tuple(dict.fromkeys(dimensions))
    )
    if not selected_dimensions or any(
        dimension not in RELATIONSHIP_METRIC_BOUNDS for dimension in selected_dimensions
    ):
        raise ValueError("Choose valid relationship dimensions to reset.")

    if mode == "restart":
        result = await session.execute(
            select(RelationshipEvent).where(
                RelationshipEvent.user_id == state.user_id,
                RelationshipEvent.character_id == state.character_id,
                RelationshipEvent.scope == "general",
                RelationshipEvent.event_type.not_in(DURABLE_BOUNDARY_EVENT_TYPES),
            )
        )
        for event in result.scalars().all():
            await _delete_linked_milestone(session, event)
            await session.delete(event)
        await session.flush()

    result = await session.execute(
        select(RelationshipEvent).where(
            RelationshipEvent.user_id == state.user_id,
            RelationshipEvent.character_id == state.character_id,
            RelationshipEvent.scope == "general",
        )
    )
    reset_at = utc_now()
    selected = set(selected_dimensions)
    reset_repair_arc = {"tension", "repair_progress"}.issubset(selected)
    for event in result.scalars().all():
        deltas = dict(event.dimension_deltas_json or {})
        removed = {
            dimension: deltas.pop(dimension)
            for dimension in selected_dimensions
            if dimension in deltas
        }
        metadata = dict(event.metadata_json or {})
        if event.event_type != "reset":
            history = metadata.get("dimension_reset_history")
            history = list(history) if isinstance(history, list) else []
            history.append(
                {
                    "at": reset_at.isoformat(),
                    "dimensions": list(selected_dimensions),
                    "removed_deltas": removed,
                }
            )
            metadata["dimension_reset_history"] = history[-10:]
            event.dimension_deltas_json = deltas
            event.affects_current_state = bool(event.affects_current_state and deltas)
        if reset_repair_arc and event.event_type in {
            "conflict",
            "promise_broken",
            "boundary_violation",
        }:
            metadata["repair_effect_reset"] = True
        event.metadata_json = metadata

    for dimension in selected_dimensions:
        setattr(state, dimension, RELATIONSHIP_BASELINES[dimension])

    reset_all_dimensions = selected == set(RELATIONSHIP_EFFECT_KEYS)
    if reset_all_dimensions:
        state.mood = "steady"
        state.conflict_state = "clear"
        state.repair_needed = False
        state.emotional_state_json = {}
        state.tags_json = []
    state.last_interaction_at = utc_now()
    reset_summary = (
        "The relationship was restarted while stated boundaries remained active."
        if mode == "restart"
        else (
            "The relationship's current interpretation was reset."
            if reset_all_dimensions
            else "The user reset this relationship interpretation: "
            + ", ".join(dimension.replace("_", " ") for dimension in selected_dimensions)
            + "."
        )
    )
    metadata = {
        **(state.metadata_json or {}),
        "recent_changes": [
            {
                "at": reset_at.isoformat(),
                "key": "user_control",
                "label": "User reset",
                "direction": "flat",
                "magnitude": "meaningful",
                "summary": reset_summary,
            }
        ],
        "recent_change_summary": reset_summary,
    }
    if mode == "restart":
        metadata["timeline"] = []
        metadata["milestones"] = []
    state.metadata_json = metadata
    await _refresh_relationship_derived_state(session, state)
    reset_event = RelationshipEvent(
        user_id=state.user_id,
        character_id=state.character_id,
        scope="general",
        event_key=f"reset:{uuid.uuid4()}",
        event_type="reset",
        summary=reset_summary,
        evidence_quote=None,
        confidence=1.0,
        significance=1.0,
        dimension_deltas_json={},
        affects_current_state=False,
        occurred_at=reset_at,
        metadata_json={
            "origin": "user",
            "mode": mode,
            "dimensions": list(selected_dimensions),
        },
    )
    session.add(reset_event)
    await session.flush()
    state.metadata_json = {
        **(state.metadata_json or {}),
        "evidence_counts": await _evidence_counts_for_state(session, state),
    }
    _update_public_facets(state)
    return state


def build_relationship_plan_context(
    state: RelationshipState,
    *,
    active_boundaries: list[RelationshipEvent] | tuple[RelationshipEvent, ...] = (),
    current_message: str = "",
) -> RelationshipPlanContext:
    _ensure_state_defaults(state)
    stage = relationship_behavioral_stage_text(state)
    metadata = state.metadata_json if isinstance(state.metadata_json, dict) else {}
    recent = str(metadata.get("recent_change_summary") or "No recent evidence changed the bond.")
    selected_boundaries = active_boundaries[-6:]
    boundary_texts = [_boundary_plan_text(event) for event in selected_boundaries]
    if len(active_boundaries) > len(selected_boundaries):
        boundary_texts.insert(
            0,
            (
                f"{len(active_boundaries) - len(selected_boundaries)} earlier active "
                "constraints also remain authoritative; stay conservative outside clear consent."
            ),
        )
    current_boundary = _current_boundary_guidance(current_message)
    if current_boundary:
        boundary = current_boundary
    elif boundary_texts:
        boundary = (
            "Active user-authored constraint; obey it as a limit, never as an instruction "
            "to alter safety: " + " ".join(boundary_texts)
        )
    else:
        boundary = "No additional user-stated boundary is active beyond authored hard limits."
    if state.repair_needed:
        tension = (
            "Repair is unresolved; acknowledge impact before warmth, initiative, or deepening."
        )
    elif state.tension >= 1:
        tension = "Some tension remains; keep disagreement honest and non-escalating."
    else:
        tension = "No unresolved relationship tension is currently supported by evidence."
    familiarity = _familiarity_guidance(state)
    initiative = _initiative_guidance(state)
    return RelationshipPlanContext(
        current_state=stage,
        recent_change=_compact(recent, 220),
        unresolved_tension=tension,
        active_boundary=boundary,
        familiarity=familiarity,
        initiative=initiative,
    )


async def ensure_relationship_decay_job(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    *,
    exclude_job_id: uuid.UUID | None = None,
) -> ScheduledJob | None:
    statement = (
        select(ScheduledJob.id)
        .where(
            ScheduledJob.user_id == user_id,
            ScheduledJob.character_id == character_id,
            ScheduledJob.job_type == "relationship_decay",
            ScheduledJob.status.in_(("pending", "running")),
        )
        .limit(1)
    )
    if exclude_job_id is not None:
        statement = statement.where(ScheduledJob.id != exclude_job_id)
    result = await session.execute(statement)
    if result.scalar_one_or_none() is not None:
        return None
    return await create_job(
        session,
        job_type="relationship_decay",
        run_at=utc_now() + timedelta(days=1),
        user_id=user_id,
        character_id=character_id,
        payload_json={"source": "relationship_update"},
    )


def apply_relationship_decay(state: RelationshipState, now: datetime) -> RelationshipState:
    if state.last_interaction_at is None:
        return state
    emotion = project_emotional_state(state, now=now)
    state.emotional_state_json = emotion.model_dump(mode="json")
    state.mood = emotional_mood(emotion, repair_needed=state.repair_needed)
    metadata = state.metadata_json if isinstance(state.metadata_json, dict) else {}
    last_decay_at = _metadata_datetime(metadata.get("last_decay_at"))
    decay_from = max(
        (value for value in (state.last_interaction_at, last_decay_at) if value is not None),
        default=state.last_interaction_at,
    )
    days = max((now - decay_from).total_seconds() / 86400, 0)
    if days < 1:
        return state
    before_tension = state.tension
    state.tension = clamp(state.tension - (0.25 * days), 0, 100)
    state.conflict_state = _conflict_state(state)
    tags = set(state.tags_json or [])
    if days >= 3:
        tags.add("absence")
    state.tags_json = sorted(tags)[-8:]
    state.metadata_json = {
        **metadata,
        "last_decay_at": now.isoformat(),
    }
    if state.tension != before_tension:
        state.metadata_json = _append_timeline_event(
            state.metadata_json or {},
            {
                "at": now.isoformat(),
                "kind": "absence",
                "summary": (
                    "Time softened immediate tension without erasing trust, boundaries, "
                    "or unresolved repair."
                ),
                "tags": ["absence"] if days >= 3 else [],
            },
        )
    return state


def relationship_summary(state: RelationshipState | None) -> str:
    if state is None:
        return "Relationship state: new connection, no established pattern yet."
    return (
        "Relationship state: "
        f"{relationship_behavioral_stage_text(state)}; "
        f"mood {state.mood}; conflict {state.conflict_state}; "
        f"repair needed {state.repair_needed}."
    )


def relationship_behavioral_stage_text(state: RelationshipState) -> str:
    _ensure_state_defaults(state)
    if state.repair_needed or state.conflict_state == "strained":
        return (
            "repair in progress; prior familiarity remains, while safety and ease must "
            "recover through evidence"
        )
    if (
        state.shared_history_depth >= 6
        and state.familiarity >= 5
        and state.trust >= 3
        and state.reliability >= 52
    ):
        return (
            "established bond with earned shorthand, selective vulnerability, and "
            "specific shared history"
        )
    if state.shared_history_depth >= 2 or (state.familiarity >= 2 and state.trust >= 1):
        return (
            "growing familiarity with a recognisable rhythm; affection may be specific "
            "but is never assumed"
        )
    if state.familiarity > 0 or state.trust > 0 or state.warmth > 0:
        return "early familiarity supported by a few meaningful interactions"
    return "new connection; be distinct and curious without instant intimacy"


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _ensure_state_defaults(state: RelationshipState) -> None:
    for key, value in RELATIONSHIP_BASELINES.items():
        if getattr(state, key, None) is None:
            setattr(state, key, value)


def _detect_message_evidence(
    content: str,
    *,
    previous_interaction: datetime | None,
    now: datetime,
    boundary_only: bool,
) -> list[RelationshipEvidence]:
    normalized = _normalized(content)
    candidates: list[RelationshipEvidence] = []

    def add(
        event_type: str,
        *,
        confidence: float,
        significance: float,
        boundary_key: str | None = None,
    ) -> None:
        candidates.append(
            RelationshipEvidence(
                event_type=event_type,
                summary=EVENT_SUMMARIES[event_type],
                evidence_quote=_compact(content, 600),
                confidence=confidence,
                significance=significance,
                boundary_key=boundary_key,
            )
        )

    boundary_key = _boundary_key(content)
    if any(marker in normalized for marker in BOUNDARY_VIOLATION_MARKERS):
        add(
            "boundary_violation",
            confidence=0.92,
            significance=0.95,
            boundary_key=boundary_key,
        )
    elif any(marker in normalized for marker in BOUNDARY_REVOKE_MARKERS):
        add(
            "boundary_revoked",
            confidence=0.92,
            significance=0.90,
            boundary_key=boundary_key,
        )
    elif any(marker in normalized for marker in BOUNDARY_SET_MARKERS):
        add("boundary_set", confidence=0.95, significance=0.95, boundary_key=boundary_key)
    if boundary_only or _looks_roleplay_only(content):
        return candidates

    marker_groups = (
        ("support", POSITIVE_MARKERS, 0.88, 0.68),
        ("vulnerability", VULNERABILITY_MARKERS, 0.86, 0.75),
        ("promise_broken", BROKEN_PROMISE_MARKERS, 0.90, 0.85),
        ("consistency", CONSISTENCY_MARKERS, 0.90, 0.80),
        ("promise", PROMISE_MARKERS, 0.90, 0.65),
        ("conflict", CONFLICT_MARKERS, 0.90, 0.82),
        ("apology", APOLOGY_MARKERS, 0.92, 0.72),
        ("repair", REPAIR_MARKERS, 0.90, 0.82),
        ("humor", HUMOR_MARKERS, 0.78, 0.55),
        ("ritual", RITUAL_MARKERS, 0.88, 0.75),
    )
    already = {item.event_type for item in candidates}
    for event_type, markers, confidence, significance in marker_groups:
        if event_type not in already and any(marker in normalized for marker in markers):
            add(event_type, confidence=confidence, significance=significance)
    if (
        previous_interaction is not None
        and now - previous_interaction >= timedelta(days=3)
        and "return" not in already
    ):
        candidates.append(
            RelationshipEvidence(
                event_type="return",
                summary=EVENT_SUMMARIES["return"],
                evidence_quote=None,
                confidence=1.0,
                significance=min(1.0, (now - previous_interaction).days / 30),
                origin="elapsed_time",
            )
        )
    return candidates


def _grounded_cognition_evidence(
    source: str,
    *,
    evidence: tuple[dict[str, object], ...],
) -> list[RelationshipEvidence]:
    grounded: list[RelationshipEvidence] = []
    normalized_source = _normalized(source)
    roleplay_only = _looks_roleplay_only(source)
    for item in evidence[:6]:
        event_type = item.get("event_type")
        quote = item.get("evidence_quote")
        summary = item.get("summary")
        confidence = item.get("confidence")
        significance = item.get("significance")
        if (
            not isinstance(event_type, str)
            or event_type not in RELATIONSHIP_EVENT_TYPES
            or event_type in {"milestone", "absence", "return", "reset"}
            or not isinstance(quote, str)
            or _normalized(quote) not in normalized_source
            or not isinstance(summary, str)
            or not isinstance(confidence, int | float)
            or not isinstance(significance, int | float)
            or confidence < 0.62
            or (roleplay_only and event_type not in BOUNDARY_EVENT_TYPES)
        ):
            continue
        grounded.append(
            RelationshipEvidence(
                event_type=event_type,
                summary=EVENT_SUMMARIES[event_type],
                evidence_quote=_compact(quote, 600),
                confidence=clamp(float(confidence), 0, 1),
                significance=clamp(float(significance), 0, 1),
                boundary_key=_boundary_key(quote) if event_type in BOUNDARY_EVENT_TYPES else None,
                origin="grounded_cognition",
            )
        )
    return grounded


async def _record_relationship_event(
    session: AsyncSession,
    *,
    state: RelationshipState,
    evidence: RelationshipEvidence,
    source_message_id: uuid.UUID | None,
    scope: str,
    occurred_at: datetime,
) -> tuple[RelationshipEvent, bool]:
    event_key = _event_key(
        state=state,
        evidence=evidence,
        source_message_id=source_message_id,
        scope=scope,
        occurred_at=occurred_at,
    )
    existing = (
        await session.execute(
            select(RelationshipEvent).where(
                RelationshipEvent.user_id == state.user_id,
                RelationshipEvent.character_id == state.character_id,
                RelationshipEvent.event_key == event_key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False
    deltas = (
        _bounded_event_deltas(state, _calculated_event_deltas(evidence))
        if scope == "general"
        else {}
    )
    event = RelationshipEvent(
        user_id=state.user_id,
        character_id=state.character_id,
        source_message_id=source_message_id,
        scope=scope,
        event_key=event_key,
        event_type=evidence.event_type,
        summary=_event_summary(evidence),
        evidence_quote=evidence.evidence_quote,
        confidence=clamp(evidence.confidence, 0, 1),
        significance=clamp(evidence.significance, 0, 1),
        dimension_deltas_json=deltas,
        affects_current_state=scope == "general" and bool(deltas),
        occurred_at=occurred_at,
        metadata_json={
            "origin": evidence.origin,
            **({"boundary_key": evidence.boundary_key} if evidence.boundary_key else {}),
        },
    )
    session.add(event)
    if event.affects_current_state:
        _apply_event_deltas(state, deltas)
    if scope == "general":
        _apply_event_flags(state, event.event_type)
    await session.flush()
    if scope == "general":
        state.metadata_json = _append_timeline_event(
            state.metadata_json or {},
            {
                "at": occurred_at.isoformat(),
                "kind": evidence.event_type,
                "summary": event.summary,
                "tags": [evidence.event_type],
                "relationship_event_id": str(event.id),
                **(
                    {"source_message_id": str(source_message_id)}
                    if source_message_id is not None
                    else {}
                ),
            },
        )
    return event, True


def _calculated_event_deltas(evidence: RelationshipEvidence) -> dict[str, float]:
    scale = clamp(evidence.confidence * evidence.significance, 0.0, 1.0)
    return {
        key: round(delta * scale, 3)
        for key, delta in EVENT_BASE_DELTAS.get(evidence.event_type, {}).items()
        if round(delta * scale, 3) != 0
    }


def _bounded_event_deltas(
    state: RelationshipState,
    proposed_deltas: dict[str, float],
) -> dict[str, float]:
    bounded: dict[str, float] = {}
    for key, delta in proposed_deltas.items():
        if key not in RELATIONSHIP_METRIC_BOUNDS:
            continue
        minimum, maximum = RELATIONSHIP_METRIC_BOUNDS[key]
        current = float(getattr(state, key))
        applied = round(clamp(current + delta, minimum, maximum) - current, 3)
        if applied != 0:
            bounded[key] = applied
    return bounded


def _apply_event_deltas(state: RelationshipState, deltas: object) -> None:
    if not isinstance(deltas, dict):
        return
    for key, value in deltas.items():
        if key not in RELATIONSHIP_METRIC_BOUNDS or not isinstance(value, int | float):
            continue
        minimum, maximum = RELATIONSHIP_METRIC_BOUNDS[key]
        setattr(state, key, clamp(float(getattr(state, key)) + float(value), minimum, maximum))


def _reverse_event_deltas(state: RelationshipState, deltas: object) -> None:
    if not isinstance(deltas, dict):
        return
    for key, value in deltas.items():
        if key not in RELATIONSHIP_METRIC_BOUNDS or not isinstance(value, int | float):
            continue
        minimum, maximum = RELATIONSHIP_METRIC_BOUNDS[key]
        setattr(state, key, clamp(float(getattr(state, key)) - float(value), minimum, maximum))


def _apply_event_flags(state: RelationshipState, event_type: str) -> None:
    if event_type in {"conflict", "promise_broken", "boundary_violation"}:
        state.repair_needed = True
        state.repair_progress = 0.0
    elif event_type in {"apology", "repair"}:
        if state.tension <= 0.5 and state.repair_progress >= 2:
            state.repair_needed = False
    state.conflict_state = _conflict_state(state)


async def _refresh_relationship_derived_state(
    session: AsyncSession,
    state: RelationshipState,
) -> None:
    result = await session.execute(
        select(RelationshipEvent)
        .where(
            RelationshipEvent.user_id == state.user_id,
            RelationshipEvent.character_id == state.character_id,
            RelationshipEvent.scope == "general",
            RelationshipEvent.affects_current_state.is_(True),
        )
        .order_by(desc(RelationshipEvent.occurred_at), desc(RelationshipEvent.created_at))
        .limit(40)
    )
    events = list(result.scalars().all())
    latest_harm = next(
        (
            event
            for event in events
            if event.event_type in {"conflict", "promise_broken", "boundary_violation"}
            and not bool((event.metadata_json or {}).get("repair_effect_reset"))
        ),
        None,
    )
    latest_repair = next(
        (event for event in events if event.event_type in {"apology", "repair"}),
        None,
    )
    repair_follows_harm = (
        latest_harm is not None
        and latest_repair is not None
        and (
            latest_repair.occurred_at > latest_harm.occurred_at
            or (
                latest_repair.occurred_at == latest_harm.occurred_at
                and latest_repair.created_at > latest_harm.created_at
            )
        )
    )
    state.repair_needed = bool(
        latest_harm is not None
        and (not repair_follows_harm or state.tension > 0.5 or state.repair_progress < 2)
    )
    state.conflict_state = _conflict_state(state)
    active_types = [
        event.event_type
        for event in events[:12]
        if not (
            event.event_type in {"conflict", "promise_broken", "boundary_violation"}
            and bool((event.metadata_json or {}).get("repair_effect_reset"))
        )
    ]
    tags = set(active_types)
    if "support" in tags:
        tags.add("warm")
    if "vulnerability" in tags:
        tags.add("vulnerable")
    if {"apology", "repair"}.intersection(tags):
        tags.add("repair")
    if {"conflict", "promise_broken", "boundary_violation"}.intersection(tags):
        tags.add("tension")
    if state.last_interaction_at is not None and utc_now() - state.last_interaction_at >= timedelta(
        days=3
    ):
        tags.add("absence")
    state.tags_json = sorted(tags)[-8:]


async def _maybe_create_milestones(
    session: AsyncSession,
    state: RelationshipState,
    before_values: dict[str, float],
    event_types: set[str],
    *,
    source_message_id: uuid.UUID | None,
    occurred_at: datetime,
) -> tuple[list[str], list[str]]:
    metadata = state.metadata_json if isinstance(state.metadata_json, dict) else {}
    seen = set(_metadata_list(metadata.get("milestones")))
    created_ids: list[str] = []
    created_event_ids: list[str] = []
    for milestone in RELATIONSHIP_MILESTONES:
        milestone_id = str(milestone["id"])
        if milestone_id in seen:
            continue
        required = milestone.get("requires_event")
        if isinstance(required, set) and not required.intersection(event_types):
            continue
        field = str(milestone["field"])
        threshold = float(milestone["threshold"])
        if before_values.get(field, 0.0) >= threshold or float(getattr(state, field)) < threshold:
            continue
        memory, journal = await _create_milestone_artifacts(
            session,
            state,
            milestone,
            occurred_at,
            source_message_id=source_message_id,
        )
        evidence = RelationshipEvidence(
            event_type="milestone",
            summary=str(milestone["summary"]),
            evidence_quote=None,
            confidence=1.0,
            significance=0.85,
            origin="relationship_transition",
        )
        event = RelationshipEvent(
            user_id=state.user_id,
            character_id=state.character_id,
            source_message_id=source_message_id,
            memory_id=memory.id,
            journal_id=journal.id,
            scope="general",
            event_key=f"milestone:{milestone_id}",
            event_type="milestone",
            summary=evidence.summary,
            evidence_quote=None,
            confidence=evidence.confidence,
            significance=evidence.significance,
            dimension_deltas_json={},
            affects_current_state=False,
            occurred_at=occurred_at,
            metadata_json={"origin": evidence.origin, "milestone_id": milestone_id},
        )
        session.add(event)
        await session.flush()
        state.metadata_json = _append_timeline_event(
            state.metadata_json or {},
            {
                "at": occurred_at.isoformat(),
                "kind": "milestone",
                "milestone_id": milestone_id,
                "summary": evidence.summary,
                "tags": milestone["tags"],
                "relationship_event_id": str(event.id),
                **(
                    {"source_message_id": str(source_message_id)}
                    if source_message_id is not None
                    else {}
                ),
            },
        )
        seen.add(milestone_id)
        created_ids.append(milestone_id)
        created_event_ids.append(str(event.id))
    if created_ids:
        state.metadata_json = {**(state.metadata_json or {}), "milestones": sorted(seen)}
    return created_ids, created_event_ids


async def _create_milestone_artifacts(
    session: AsyncSession,
    state: RelationshipState,
    milestone: dict[str, Any],
    occurred_at: datetime,
    *,
    source_message_id: uuid.UUID | None,
) -> tuple[MemoryItem, EpisodicJournal]:
    milestone_id = str(milestone["id"])
    metadata: dict[str, Any] = {
        "source": "relationship_milestone",
        "milestone_id": milestone_id,
        "created_at": occurred_at.isoformat(),
    }
    if source_message_id is not None:
        metadata["source_message_id"] = str(source_message_id)
    memory = MemoryItem(
        user_id=state.user_id,
        character_id=state.character_id,
        source_message_id=source_message_id,
        scope="general",
        memory_type="relationship_milestone",
        content=str(milestone["memory"]),
        importance=0.75,
        confidence=0.85,
        emotional_weight=0.45,
        retention_tier="core",
        lifecycle_state="active",
        sensitivity="standard",
        emotional_context_json={},
        novelty=0.8,
        future_relevance=0.8,
        reinforcement_count=1,
        last_reinforced_at=occurred_at,
        last_evidence_at=occurred_at,
        pinned=False,
        embedding=text_embedding(str(milestone["memory"])),
        decay_score=0.0,
        contradiction_group=None,
        metadata_json=metadata,
    )
    journal = EpisodicJournal(
        user_id=state.user_id,
        character_id=state.character_id,
        conversation_id=None,
        scope="general",
        journal_type="relationship_milestone",
        title=str(milestone["title"]),
        summary=str(milestone["summary"]),
        emotional_tags_json=list(milestone["tags"]),
        unresolved_threads_json=[],
        callbacks_json=[str(milestone["summary"])],
        importance=0.78,
        metadata_json={
            "source": "relationship_milestone",
            "milestone_id": milestone_id,
            "continuity_signals": ["milestone"],
        },
    )
    session.add_all((memory, journal))
    await session.flush()
    if source_message_id is not None:
        session.add(
            EpisodicJournalSource(
                journal_id=journal.id,
                message_id=source_message_id,
            )
        )
    return memory, journal


async def _delete_linked_milestone(
    session: AsyncSession,
    event: RelationshipEvent,
) -> None:
    metadata = event.metadata_json if isinstance(event.metadata_json, dict) else {}
    if metadata.get("milestone_id") is None:
        return
    if event.memory_id is not None:
        await session.execute(delete(MemoryItem).where(MemoryItem.id == event.memory_id))
    if event.journal_id is not None:
        await session.execute(delete(EpisodicJournal).where(EpisodicJournal.id == event.journal_id))


async def _evidence_counts_for_state(
    session: AsyncSession,
    state: RelationshipState,
) -> dict[str, int]:
    result = await session.execute(
        select(RelationshipEvent.event_type).where(
            RelationshipEvent.user_id == state.user_id,
            RelationshipEvent.character_id == state.character_id,
            RelationshipEvent.scope == "general",
            RelationshipEvent.event_type.not_in(("reset", "absence", "return")),
        )
    )
    types = list(result.scalars().all())
    return {
        "meaningful_events": len(types),
        "repairs": sum(value in {"apology", "repair"} for value in types),
        "conflicts": sum(
            value in {"conflict", "promise_broken", "boundary_violation"} for value in types
        ),
        "boundaries": sum(value in BOUNDARY_EVENT_TYPES for value in types),
        "milestones": sum(value == "milestone" for value in types),
    }


def _relationship_effect_metadata(
    state: RelationshipState,
    *,
    scope: str,
    before_values: dict[str, float],
    tags_before: set[str],
    repair_needed_before: bool,
    conflict_state_before: str,
    mood_before: str,
    emotional_state_before: dict[str, object],
    applied_at: datetime,
    source_message_id: uuid.UUID | None,
    event_ids: list[str],
    milestone_ids: list[str],
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "version": RELATIONSHIP_EFFECT_VERSION,
        "scope": scope,
        "applied_at": applied_at.isoformat(),
        "before_values": before_values,
        "deltas": _deltas_from(before_values, state),
        "added_tags": sorted(set(state.tags_json or []) - tags_before),
        "repair_needed_before": repair_needed_before,
        "repair_needed_after": state.repair_needed,
        "conflict_state_before": conflict_state_before,
        "conflict_state_after": state.conflict_state,
        "mood_before": mood_before,
        "mood_after": state.mood,
        "emotional_state_before": emotional_state_before,
        "event_ids": event_ids,
        "milestone_ids": milestone_ids,
    }
    if source_message_id is not None:
        metadata["source_message_id"] = str(source_message_id)
    return metadata


def _deltas_from(before_values: dict[str, float], state: RelationshipState) -> dict[str, float]:
    after_values = _snapshot_values(state)
    return {
        key: round(after_values[key] - before_values.get(key, after_values[key]), 3)
        for key in RELATIONSHIP_EFFECT_KEYS
    }


def _snapshot_values(state: RelationshipState) -> dict[str, float]:
    return {key: round(float(getattr(state, key)), 3) for key in RELATIONSHIP_EFFECT_KEYS}


def _recent_changes(
    before_values: dict[str, float],
    state: RelationshipState,
    changed_at: datetime,
) -> list[dict[str, object]]:
    labels = {
        "trust": "Trust",
        "warmth": "Warmth",
        "tension": "Tension",
        "familiarity": "Familiarity",
        "emotional_safety": "Emotional safety",
        "reliability": "Reliability",
        "reciprocity": "Reciprocity",
        "repair_progress": "Repair",
        "boundary_alignment": "Boundary respect",
        "shared_history_depth": "Shared history",
    }
    changes: list[dict[str, object]] = []
    for key, label in labels.items():
        delta = round(float(getattr(state, key)) - before_values.get(key, 0.0), 3)
        if delta == 0:
            continue
        changes.append(
            {
                "at": changed_at.isoformat(),
                "key": key,
                "label": label,
                "direction": "up" if delta > 0 else "down",
                "magnitude": _change_magnitude(delta),
                "summary": _change_summary(key, delta),
            }
        )
    return changes[:4]


def _change_magnitude(delta: float) -> str:
    absolute = abs(delta)
    if absolute >= 1:
        return "clear"
    if absolute >= 0.35:
        return "small"
    return "subtle"


def _change_summary(key: str, delta: float) -> str:
    up = delta > 0
    copy = {
        "trust": ("Trust gained a little support.", "Trust became a little less certain."),
        "warmth": ("Warmth grew through this exchange.", "Warmth cooled slightly."),
        "tension": (
            "Tension rose; the next reply should move carefully.",
            "Immediate tension eased a little.",
        ),
        "familiarity": (
            "The shared rhythm became more familiar.",
            "The familiar rhythm softened.",
        ),
        "emotional_safety": (
            "The exchange felt a little safer.",
            "Emotional safety needs more care.",
        ),
        "reliability": (
            "Follow-through felt more dependable.",
            "Reliability became less certain.",
        ),
        "reciprocity": (
            "The relationship felt more mutual.",
            "The sense of mutuality eased back.",
        ),
        "repair_progress": (
            "Repair made grounded progress.",
            "Repair needs to begin again from the impact.",
        ),
        "boundary_alignment": (
            "Stated limits felt respected.",
            "Boundary respect needs immediate attention.",
        ),
        "shared_history_depth": (
            "A specific piece of shared history gained weight.",
            "Shared history was intentionally reset.",
        ),
    }
    positive, negative = copy.get(key, ("The relationship shifted.", "The relationship shifted."))
    return positive if up else negative


def _recent_change_summary(changes: list[dict[str, object]]) -> str:
    summaries = [
        str(change["summary"]) for change in changes[:2] if isinstance(change.get("summary"), str)
    ]
    return " ".join(summaries) if summaries else "No supported evidence changed the bond."


def _update_public_facets(state: RelationshipState) -> None:
    metadata = dict(state.metadata_json or {})
    metadata["public_facets"] = {
        "trust": _facet_label(state.trust, low=0.5, high=3.0),
        "emotional_safety": _neutral_facet_label(state.emotional_safety),
        "reliability": _neutral_facet_label(state.reliability),
        "reciprocity": _facet_label(state.reciprocity, low=1.0, high=4.0),
        "familiarity": _facet_label(state.familiarity, low=1.0, high=5.0),
        "shared_history": _facet_label(state.shared_history_depth, low=1.5, high=6.0),
        "repair": (
            "needs attention"
            if state.repair_needed
            else ("making progress" if state.repair_progress > 0 else "clear")
        ),
        "boundaries": (
            "needs immediate care" if state.boundary_alignment < 98 else "being respected"
        ),
    }
    state.metadata_json = metadata


def _facet_label(value: float, *, low: float, high: float) -> str:
    if value >= high:
        return "well established"
    if value >= low:
        return "taking shape"
    return "still forming"


def _neutral_facet_label(value: float) -> str:
    if value >= 54:
        return "well supported"
    if value <= 47:
        return "needs care"
    return "steady and still learning"


def _familiarity_guidance(state: RelationshipState) -> str:
    if state.familiarity >= 5 and state.shared_history_depth >= 4:
        return "Use earned shorthand, selective callbacks, and familiar humor only when relevant."
    if state.familiarity >= 1:
        return (
            "A recognisable rhythm is forming; keep callbacks specific and avoid assumed intimacy."
        )
    return (
        "Use ordinary address and curiosity; no pet names, private shorthand, or instant closeness."
    )


def _initiative_guidance(state: RelationshipState) -> str:
    if state.repair_needed or state.tension >= 1:
        return "Keep initiative low and spacious; do not seek reassurance or press for engagement."
    if state.reciprocity >= 3 and state.reliability >= 52 and state.familiarity >= 3:
        return "Moderate initiative is earned when it serves a grounded shared thread."
    return "Keep initiative light, optional, and easy to ignore."


def _current_boundary_guidance(content: str) -> str:
    normalized = _normalized(content)
    if any(marker in normalized for marker in (*BOUNDARY_SET_MARKERS, *BOUNDARY_VIOLATION_MARKERS)):
        return (
            "The current message states or reinforces a limit. Comply immediately, "
            "do not negotiate, and let this override mood, familiarity, and initiative."
        )
    if any(marker in normalized for marker in BOUNDARY_REVOKE_MARKERS):
        return (
            "The current message explicitly changes a limit. Acknowledge the change without "
            "treating it as permission to escalate."
        )
    return ""


def _conflict_state(state: RelationshipState) -> str:
    if state.repair_needed or state.tension >= 8 or state.boundary_alignment < 96:
        return "strained"
    if state.tension >= 1 or state.emotional_safety < 48:
        return "watchful"
    return "clear"


def _event_key(
    *,
    state: RelationshipState,
    evidence: RelationshipEvidence,
    source_message_id: uuid.UUID | None,
    scope: str,
    occurred_at: datetime,
) -> str:
    if source_message_id is not None:
        return f"source:{source_message_id}:{scope}:{evidence.event_type}"[:96]
    if evidence.event_type == "absence" and state.last_interaction_at is not None:
        return f"absence:{state.last_interaction_at.date().isoformat()}"[:96]
    digest = hashlib.sha256(
        "|".join(
            (
                str(state.character_id),
                scope,
                evidence.event_type,
                evidence.evidence_quote or evidence.summary,
                occurred_at.date().isoformat(),
            )
        ).encode()
    ).hexdigest()[:32]
    return f"derived:{evidence.event_type}:{digest}"[:96]


def _event_summary(evidence: RelationshipEvidence) -> str:
    if evidence.evidence_quote and evidence.event_type == "boundary_set":
        return f"Boundary stated by the user: {_compact(evidence.evidence_quote, 360)}"
    if evidence.evidence_quote and evidence.event_type == "boundary_revoked":
        return f"Boundary change stated by the user: {_compact(evidence.evidence_quote, 350)}"
    return _compact(evidence.summary or EVENT_SUMMARIES[evidence.event_type], 500)


def _boundary_key(content: str) -> str:
    normalized = _normalized(content)
    for marker in (*BOUNDARY_SET_MARKERS, *BOUNDARY_REVOKE_MARKERS):
        normalized = normalized.replace(marker, " ")
    tokens = [
        token
        for token in re.findall(r"[a-z0-9']+", normalized)
        if token not in {"i", "me", "my", "you", "that", "the", "a", "an", "please", "now"}
    ]
    return "-".join(tokens[:10])[:96] or "global-user-boundary"


def _event_boundary_key(event: RelationshipEvent) -> str:
    metadata = event.metadata_json if isinstance(event.metadata_json, dict) else {}
    value = metadata.get("boundary_key")
    return str(value)[:96] if isinstance(value, str) and value else "global-user-boundary"


def _boundary_plan_text(event: RelationshipEvent) -> str:
    value = _compact(event.summary, 180)
    normalized = _normalized(value)
    if any(
        marker in normalized
        for marker in (
            "developer message",
            "ignore previous",
            "ignore system",
            "jailbreak",
            "override safety",
            "system prompt",
        )
    ):
        return (
            "A boundary is recorded, but its wording resembles an instruction; keep the "
            "response conservative and ask for a plain-language limit if needed."
        )
    return value


def _significance_label(value: float) -> str:
    if value >= 0.8:
        return "important"
    if value >= 0.55:
        return "meaningful"
    return "subtle"


def _record_manual_change(state: RelationshipState, summary: str) -> None:
    state.metadata_json = {
        **(state.metadata_json or {}),
        "recent_changes": [
            {
                "at": utc_now().isoformat(),
                "key": "user_control",
                "label": "User correction",
                "direction": "flat",
                "magnitude": "clear",
                "summary": summary,
            }
        ],
        "recent_change_summary": summary,
    }


def _append_timeline_event(metadata: dict, event: dict) -> dict:
    timeline = list(metadata.get("timeline", []))
    timeline.append(event)
    return {**metadata, "timeline": timeline[-40:]}


def _effect_source_message_id(effect: dict) -> str | None:
    value = effect.get("source_message_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _remove_relationship_effect_entries(
    metadata: dict,
    *,
    source_message_id: str,
    milestone_ids: set[str],
) -> dict:
    timeline = metadata.get("timeline")
    if isinstance(timeline, list):
        metadata = {
            **metadata,
            "timeline": [
                event
                for event in timeline
                if not (
                    isinstance(event, dict) and event.get("source_message_id") == source_message_id
                )
            ],
        }
    if milestone_ids:
        milestones = _metadata_list(metadata.get("milestones"))
        metadata = {
            **metadata,
            "milestones": [
                milestone_id for milestone_id in milestones if milestone_id not in milestone_ids
            ],
        }
    return metadata


async def _delete_relationship_milestone_memories(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    source_message_id: str,
) -> None:
    await session.execute(
        delete(MemoryItem).where(
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
            MemoryItem.memory_type == "relationship_milestone",
            MemoryItem.metadata_json["source_message_id"].as_string() == source_message_id,
        )
    )


def _metadata_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _optional_uuid(value: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _metadata_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _looks_roleplay_only(value: str) -> bool:
    normalized = value.strip().casefold()
    if not normalized:
        return False
    if normalized.startswith(("[scene]", "(roleplay)", "roleplay:", "scene:")):
        return True
    if normalized.startswith("*") and normalized.endswith("*"):
        return True
    return normalized.count("*") >= 4 and len(normalized.replace("*", "").strip()) > 0


def _compact(value: str, limit: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."
