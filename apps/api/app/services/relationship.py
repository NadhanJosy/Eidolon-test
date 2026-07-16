from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.companion.emotion import (
    apply_emotional_turn,
    emotional_mood,
    project_emotional_state,
    read_emotional_state,
)
from app.companion.perception import infer_turn_perception
from app.models import MemoryItem, Message, RelationshipState, ScheduledJob, utc_now
from app.services.embedding import text_embedding
from app.services.jobs import create_job

POSITIVE_WORDS = ("thanks", "thank you", "kind", "glad", "happy", "appreciate", "good")
REPAIR_WORDS = ("sorry", "apologize", "my fault")
CONFLICT_WORDS = ("angry", "upset", "hate", "annoyed", "frustrated")
VULNERABLE_WORDS = ("afraid", "lonely", "worried", "sad", "miss", "trust")
RELATIONSHIP_MILESTONES = (
    {
        "id": "first_warmth",
        "field": "warmth",
        "threshold": 1.0,
        "summary": "A warmer rhythm has started to form.",
        "memory": "A warmer rhythm has started to form between the user and character.",
        "tags": ["milestone", "warm"],
    },
    {
        "id": "trust_seed",
        "field": "trust",
        "threshold": 0.5,
        "summary": "A first seed of trust has taken hold.",
        "memory": "A first seed of trust has taken hold in the relationship.",
        "tags": ["milestone", "trust"],
    },
    {
        "id": "steady_rhythm",
        "field": "familiarity",
        "threshold": 1.0,
        "summary": "The conversation has begun to feel like a recurring rhythm.",
        "memory": "The conversation has begun to feel like a recurring rhythm.",
        "tags": ["milestone", "rhythm"],
    },
    {
        "id": "repair_arc",
        "field": "trust",
        "threshold": 0.25,
        "summary": "A repair moment was handled gently enough to matter.",
        "memory": "A repair moment was handled gently enough to matter.",
        "tags": ["milestone", "repair"],
        "requires_tag": "repair",
    },
)
RELATIONSHIP_CHANGE_LABELS = (
    ("trust", "Trust"),
    ("intimacy", "Closeness"),
    ("warmth", "Warmth"),
    ("tension", "Tension"),
    ("familiarity", "Rhythm"),
    ("attachment", "Attachment"),
)
RELATIONSHIP_EFFECT_VERSION = "relationship_effect_v1"
RELATIONSHIP_METRIC_BOUNDS = {
    "trust": (-100.0, 100.0),
    "intimacy": (0.0, 100.0),
    "warmth": (-100.0, 100.0),
    "tension": (0.0, 100.0),
    "familiarity": (0.0, 100.0),
    "attachment": (0.0, 100.0),
}
RELATIONSHIP_EFFECT_KEYS = tuple(RELATIONSHIP_METRIC_BOUNDS)


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
        return state

    state = RelationshipState(
        user_id=user_id,
        character_id=character_id,
        trust=0.0,
        intimacy=0.0,
        warmth=0.0,
        tension=0.0,
        familiarity=0.0,
        attachment=0.0,
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
    apply_relationship_decay(state, utc_now())
    await session.flush()
    return state


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
) -> tuple[RelationshipState, dict[str, object]]:
    state = await get_or_create_relationship(session, user_id, character_id)
    apply_relationship_decay(state, utc_now())
    normalized = content.lower()
    before = _snapshot(state)
    before_values = _snapshot_values(before)
    tags: set[str] = set(state.tags_json or [])
    tags_before = set(tags)
    repair_needed_before = state.repair_needed
    conflict_state_before = state.conflict_state
    mood_before = state.mood
    emotional_state_before = dict(state.emotional_state_json or {})
    metadata_before = state.metadata_json if isinstance(state.metadata_json, dict) else {}
    evidence_before = _evidence_counts(metadata_before.get("evidence_counts"))

    state.familiarity = clamp(state.familiarity + 0.2, 0, 100)
    if len(content) > 120:
        state.intimacy = clamp(state.intimacy + 0.1, 0, 100)
        tags.add("long-form")
    if any(word in normalized for word in VULNERABLE_WORDS):
        state.trust = clamp(state.trust + 0.05, -100, 100)
        state.intimacy = clamp(state.intimacy + 0.15, 0, 100)
        tags.add("vulnerable")
    if any(word in normalized for word in POSITIVE_WORDS):
        state.warmth = clamp(state.warmth + 0.3, -100, 100)
        state.trust = clamp(state.trust + 0.1, -100, 100)
        tags.add("warm")
    if any(word in normalized for word in REPAIR_WORDS):
        state.tension = clamp(state.tension - 0.5, 0, 100)
        state.trust = clamp(state.trust + 0.1, -100, 100)
        state.repair_needed = False
        tags.add("repair")
    if any(word in normalized for word in CONFLICT_WORDS):
        state.tension = clamp(state.tension + 0.5, 0, 100)
        state.warmth = clamp(state.warmth - 0.2, -100, 100)
        state.repair_needed = True
        tags.add("tension")

    state.attachment = clamp(state.attachment + 0.02, 0, 100)
    state.conflict_state = _conflict_state(state)
    perception = infer_turn_perception(content, recent_messages=[], journals=[])
    if any(word in normalized for word in CONFLICT_WORDS) and not perception.conflict_signal:
        perception = replace(perception, conflict_signal=True)
    emotion = apply_emotional_turn(state, perception, now=utc_now())
    state.mood = emotional_mood(emotion, repair_needed=state.repair_needed)
    state.tags_json = sorted(tags)[-8:]
    state.last_interaction_at = utc_now()
    recent_changes = _recent_changes(before, state, state.last_interaction_at)
    timeline_event = {
        "at": state.last_interaction_at.isoformat(),
        "kind": "message_update",
        "summary": _event_summary(before, state),
        "tags": sorted(tags),
    }
    if source_message_id is not None:
        timeline_event["source_message_id"] = str(source_message_id)
    state.metadata_json = _append_timeline_event(
        state.metadata_json or {},
        timeline_event,
    )
    state.metadata_json = {
        **(state.metadata_json or {}),
        "recent_changes": recent_changes,
        "recent_change_summary": _recent_change_summary(recent_changes),
        "evidence_counts": _updated_evidence_counts(
            evidence_before,
            content=content,
            normalized=normalized,
        ),
    }
    milestone_ids = await _maybe_create_milestones(
        session,
        state,
        before,
        tags,
        source_message_id=source_message_id,
    )
    effect = _relationship_effect_metadata(
        state,
        before_values=before_values,
        tags_before=tags_before,
        repair_needed_before=repair_needed_before,
        conflict_state_before=conflict_state_before,
        mood_before=mood_before,
        emotional_state_before=emotional_state_before,
        evidence_counts_before=evidence_before,
        applied_at=state.last_interaction_at,
        source_message_id=source_message_id,
        milestone_ids=milestone_ids,
    )
    await ensure_relationship_decay_job(session, user_id, character_id)
    await session.flush()
    return state, effect


async def refine_relationship_from_evidence(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    source_message: Message,
    signals: tuple[str, ...],
    confidence: float,
) -> bool:
    metadata = dict(source_message.metadata_json or {})
    if metadata.get("relationship_cognition_version") == "relationship_cognition_v1":
        return False
    effect = metadata.get("relationship_effect")
    if not isinstance(effect, dict) or effect.get("version") != RELATIONSHIP_EFFECT_VERSION:
        return False
    if confidence < 0.62 or not signals:
        source_message.metadata_json = {
            **metadata,
            "relationship_cognition_version": "relationship_cognition_v1",
        }
        return False

    state = await get_or_create_relationship(session, user_id, character_id)
    before = _snapshot(state)
    scale = clamp((confidence - 0.5) * 1.6, 0.2, 1.0)
    signal_deltas: dict[str, dict[str, float]] = {
        "boundary_assertion": {"trust": 0.02},
        "conflict": {"tension": 0.25, "warmth": -0.08},
        "gratitude": {"warmth": 0.10, "trust": 0.04},
        "play": {"familiarity": 0.08, "warmth": 0.05},
        "reliability": {"trust": 0.12},
        "repair_attempt": {"tension": -0.25, "trust": 0.05},
        "shared_ritual": {"familiarity": 0.12, "attachment": 0.03},
        "support": {"warmth": 0.06},
        "vulnerability": {"trust": 0.06, "intimacy": 0.12},
    }
    for signal in dict.fromkeys(signals):
        for key, delta in signal_deltas.get(signal, {}).items():
            minimum, maximum = RELATIONSHIP_METRIC_BOUNDS[key]
            setattr(
                state,
                key,
                clamp(float(getattr(state, key)) + (delta * scale), minimum, maximum),
            )
    if "conflict" in signals:
        state.repair_needed = True
    elif "repair_attempt" in signals and state.tension < 1.0:
        state.repair_needed = False
    state.conflict_state = _conflict_state(state)
    state.tags_json = sorted(set(state.tags_json or {}) | set(signals))[-8:]
    state.last_interaction_at = utc_now()
    changes = _recent_changes(before, state, state.last_interaction_at)
    cognition_counts = _cognition_evidence_counts(
        (state.metadata_json or {}).get("cognition_evidence_counts")
    )
    for signal in dict.fromkeys(signals):
        cognition_counts[signal] = min(cognition_counts.get(signal, 0) + 1, 1_000_000)
    state.metadata_json = _append_timeline_event(
        state.metadata_json or {},
        {
            "at": state.last_interaction_at.isoformat(),
            "kind": "grounded_relationship_evidence",
            "summary": "The exchange added grounded relationship evidence.",
            "signals": list(dict.fromkeys(signals))[:6],
            "source_message_id": str(source_message.id),
        },
    )
    state.metadata_json = {
        **(state.metadata_json or {}),
        "cognition_evidence_counts": cognition_counts,
        "recent_changes": changes,
        "recent_change_summary": _recent_change_summary(changes),
    }

    existing_deltas = effect.get("deltas") if isinstance(effect.get("deltas"), dict) else {}
    after_values = _snapshot_values(_snapshot(state))
    before_values = _snapshot_values(before)
    merged_deltas: dict[str, float] = {}
    for key in RELATIONSHIP_EFFECT_KEYS:
        prior = existing_deltas.get(key)
        prior_value = float(prior) if isinstance(prior, int | float) else 0.0
        merged_deltas[key] = round(prior_value + after_values[key] - before_values[key], 3)
    added_tags = set(_metadata_list(effect.get("added_tags"))) | set(signals)
    source_message.metadata_json = {
        **metadata,
        "relationship_effect": {
            **effect,
            "deltas": merged_deltas,
            "added_tags": sorted(added_tags),
            "repair_needed_after": state.repair_needed,
            "conflict_state_after": state.conflict_state,
            "mood_after": state.mood,
        },
        "relationship_cognition_version": "relationship_cognition_v1",
    }
    await session.flush()
    return any(change.get("key") != "steady" for change in changes)


async def reverse_relationship_message_effect(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    effect: object,
) -> bool:
    if not isinstance(effect, dict) or effect.get("version") != RELATIONSHIP_EFFECT_VERSION:
        return False
    deltas = effect.get("deltas")
    if not isinstance(deltas, dict):
        return False

    parsed_deltas: dict[str, float] = {}
    for key in RELATIONSHIP_EFFECT_KEYS:
        value = deltas.get(key)
        if not isinstance(value, int | float):
            return False
        parsed_deltas[key] = float(value)

    state = await get_or_create_relationship(session, user_id, character_id)
    for key, delta in parsed_deltas.items():
        minimum, maximum = RELATIONSHIP_METRIC_BOUNDS[key]
        current = float(getattr(state, key))
        setattr(state, key, clamp(current - delta, minimum, maximum))

    tags = set(state.tags_json or [])
    added_tags = _metadata_list(effect.get("added_tags"))
    tags.difference_update(added_tags)
    state.tags_json = sorted(tags)[-8:]

    repair_needed_before = effect.get("repair_needed_before")
    if isinstance(repair_needed_before, bool):
        state.repair_needed = repair_needed_before

    source_message_id = _effect_source_message_id(effect)
    milestone_ids = set(_metadata_list(effect.get("milestone_ids")))
    if source_message_id is not None:
        state.metadata_json = _remove_relationship_effect_entries(
            state.metadata_json or {},
            source_message_id=source_message_id,
            milestone_ids=milestone_ids,
        )
        await _delete_relationship_milestone_memories(
            session,
            user_id=user_id,
            character_id=character_id,
            source_message_id=source_message_id,
        )

    state.conflict_state = _conflict_state(state)
    emotional_before = effect.get("emotional_state_before")
    if isinstance(emotional_before, dict):
        state.emotional_state_json = emotional_before
    evidence_before = effect.get("evidence_counts_before")
    if isinstance(evidence_before, dict):
        state.metadata_json = {
            **(state.metadata_json or {}),
            "evidence_counts": _evidence_counts(evidence_before),
        }
    emotion = read_emotional_state(state)
    state.mood = emotional_mood(emotion, repair_needed=state.repair_needed)
    state.metadata_json = {
        **(state.metadata_json or {}),
        "recent_changes": [
            {
                "at": utc_now().isoformat(),
                "key": "edit_recalculation",
                "label": "Recalculated",
                "direction": "flat",
                "magnitude": "subtle",
                "delta": 0.0,
                "summary": "The latest edited turn was recalculated for relationship continuity.",
            }
        ],
        "recent_change_summary": "The latest edited turn was recalculated.",
    }
    await session.flush()
    return True


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
    days = max((now - state.last_interaction_at).total_seconds() / 86400, 0)
    if days < 1:
        return state
    before = _snapshot(state)
    state.tension = clamp(state.tension - (0.4 * days), 0, 100)
    if state.warmth > 0:
        state.warmth = clamp(state.warmth - (0.12 * days), -100, 100)
    elif state.warmth < 0:
        state.warmth = clamp(state.warmth + (0.12 * days), -100, 100)
    state.attachment = clamp(state.attachment - (0.03 * days), 0, 100)
    state.conflict_state = _conflict_state(state)
    state.mood = emotional_mood(emotion, repair_needed=state.repair_needed)
    tags = set(state.tags_json or [])
    if days >= 3:
        tags.add("absence")
    state.tags_json = sorted(tags)[-8:]
    if _snapshot(state) != before:
        state.metadata_json = _append_timeline_event(
            state.metadata_json or {},
            {
                "at": now.isoformat(),
                "kind": "decay",
                "summary": f"{days:.1f} days passed; warmth and tension drifted toward baseline.",
                "tags": ["absence"] if days >= 3 else [],
            },
        )
    return state


def relationship_summary(state: RelationshipState | None) -> str:
    if state is None:
        return "Relationship state: new connection, no established pattern yet."
    return (
        "Relationship state: "
        f"familiarity {state.familiarity:.1f}/100, "
        f"trust {state.trust:.1f}/100, "
        f"warmth {state.warmth:.1f}/100, "
        f"tension {state.tension:.1f}/100, "
        f"intimacy {state.intimacy:.1f}/100, "
        f"attachment {state.attachment:.1f}/100, "
        f"mood {state.mood}, conflict {state.conflict_state}, "
        f"repair needed {state.repair_needed}."
    )


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _conflict_state(state: RelationshipState) -> str:
    if state.repair_needed or state.tension >= 20:
        return "strained"
    if state.tension >= 5:
        return "watchful"
    return "clear"


def _mood(state: RelationshipState) -> str:
    if state.tension >= 20:
        return "tense"
    if state.warmth >= 15:
        return "warm"
    if state.warmth <= -10:
        return "guarded"
    if state.intimacy >= 20:
        return "close"
    return "steady"


def _snapshot(state: RelationshipState) -> tuple[float, float, float, float, float, float]:
    return (
        round(state.trust, 3),
        round(state.intimacy, 3),
        round(state.warmth, 3),
        round(state.tension, 3),
        round(state.familiarity, 3),
        round(state.attachment, 3),
    )


async def _maybe_create_milestones(
    session: AsyncSession,
    state: RelationshipState,
    before: tuple[float, float, float, float, float, float],
    tags: set[str],
    *,
    source_message_id: uuid.UUID | None = None,
) -> list[str]:
    metadata = state.metadata_json if isinstance(state.metadata_json, dict) else {}
    seen = set(_metadata_list(metadata.get("milestones")))
    created: list[str] = []
    now = state.last_interaction_at or utc_now()
    for milestone in RELATIONSHIP_MILESTONES:
        milestone_id = str(milestone["id"])
        required_tag = milestone.get("requires_tag")
        if milestone_id in seen:
            continue
        if isinstance(required_tag, str) and required_tag not in tags:
            continue
        if not _crossed_milestone(before, state, milestone):
            continue
        event = {
            "at": now.isoformat(),
            "kind": "milestone",
            "milestone_id": milestone_id,
            "summary": milestone["summary"],
            "tags": milestone["tags"],
        }
        if source_message_id is not None:
            event["source_message_id"] = str(source_message_id)
        state.metadata_json = _append_timeline_event(state.metadata_json or {}, event)
        await _create_milestone_memory(
            session,
            state,
            milestone,
            now,
            source_message_id=source_message_id,
        )
        seen.add(milestone_id)
        created.append(milestone_id)
    if created:
        state.metadata_json = {
            **(state.metadata_json or {}),
            "milestones": sorted(seen),
        }
    return created


async def _create_milestone_memory(
    session: AsyncSession,
    state: RelationshipState,
    milestone: dict,
    now: datetime,
    *,
    source_message_id: uuid.UUID | None = None,
) -> None:
    milestone_id = str(milestone["id"])
    metadata = {
        "source": "relationship_milestone",
        "milestone_id": milestone_id,
        "created_at": now.isoformat(),
    }
    if source_message_id is not None:
        metadata["source_message_id"] = str(source_message_id)
    memory = MemoryItem(
        user_id=state.user_id,
        character_id=state.character_id,
        source_message_id=None,
        memory_type="relationship_milestone",
        content=str(milestone["memory"]),
        importance=0.75,
        confidence=0.85,
        emotional_weight=0.45,
        pinned=False,
        embedding=text_embedding(str(milestone["memory"])),
        decay_score=0.0,
        contradiction_group=None,
        metadata_json=metadata,
    )
    session.add(memory)


def _crossed_milestone(
    before: tuple[float, float, float, float, float, float],
    state: RelationshipState,
    milestone: dict,
) -> bool:
    field = milestone.get("field")
    threshold = float(milestone.get("threshold", 0))
    before_values = _snapshot_values(before)
    before_value = before_values.get(str(field), 0.0)
    after_value = float(getattr(state, str(field), 0.0))
    return before_value < threshold <= after_value


def _snapshot_values(snapshot: tuple[float, float, float, float, float, float]) -> dict[str, float]:
    labels = ("trust", "intimacy", "warmth", "tension", "familiarity", "attachment")
    return dict(zip(labels, snapshot, strict=True))


def _relationship_effect_metadata(
    state: RelationshipState,
    *,
    before_values: dict[str, float],
    tags_before: set[str],
    repair_needed_before: bool,
    conflict_state_before: str,
    mood_before: str,
    emotional_state_before: dict[str, object],
    evidence_counts_before: dict[str, int],
    applied_at: datetime,
    source_message_id: uuid.UUID | None,
    milestone_ids: list[str],
) -> dict[str, object]:
    after_values = _snapshot_values(_snapshot(state))
    deltas = {
        key: round(after_values[key] - before_values[key], 3) for key in RELATIONSHIP_EFFECT_KEYS
    }
    metadata: dict[str, object] = {
        "version": RELATIONSHIP_EFFECT_VERSION,
        "applied_at": applied_at.isoformat(),
        "deltas": deltas,
        "added_tags": sorted(set(state.tags_json or []) - tags_before),
        "repair_needed_before": repair_needed_before,
        "repair_needed_after": state.repair_needed,
        "conflict_state_before": conflict_state_before,
        "conflict_state_after": state.conflict_state,
        "mood_before": mood_before,
        "mood_after": state.mood,
        "emotional_state_before": emotional_state_before,
        "evidence_counts_before": evidence_counts_before,
        "milestone_ids": milestone_ids,
    }
    if source_message_id is not None:
        metadata["source_message_id"] = str(source_message_id)
    return metadata


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


def _append_timeline_event(metadata: dict, event: dict) -> dict:
    timeline = list(metadata.get("timeline", []))
    timeline.append(event)
    return {**metadata, "timeline": timeline[-40:]}


def _event_summary(
    before: tuple[float, float, float, float, float, float],
    state: RelationshipState,
) -> str:
    after = _snapshot(state)
    labels = ("trust", "intimacy", "warmth", "tension", "familiarity", "attachment")
    changes = [
        f"{label} {after_value - before_value:+.2f}"
        for label, before_value, after_value in zip(labels, before, after, strict=True)
        if round(after_value - before_value, 3) != 0
    ]
    return ", ".join(changes) if changes else "Relationship state held steady."


def _recent_changes(
    before: tuple[float, float, float, float, float, float],
    state: RelationshipState,
    changed_at: datetime,
) -> list[dict[str, object]]:
    before_values = _snapshot_values(before)
    after_values = _snapshot_values(_snapshot(state))
    changes: list[dict[str, object]] = []
    for key, label in RELATIONSHIP_CHANGE_LABELS:
        before_value = before_values[key]
        after_value = after_values[key]
        delta = round(after_value - before_value, 3)
        if delta == 0:
            continue
        changes.append(
            {
                "at": changed_at.isoformat(),
                "key": key,
                "label": label,
                "direction": "up" if delta > 0 else "down",
                "magnitude": _change_magnitude(delta),
                "delta": delta,
                "summary": _change_summary(key, delta, state),
            }
        )
    if not changes:
        return [
            {
                "at": changed_at.isoformat(),
                "key": "steady",
                "label": "Steady",
                "direction": "flat",
                "magnitude": "subtle",
                "delta": 0.0,
                "summary": "The connection held steady through this exchange.",
            }
        ]
    return changes[:4]


def _change_magnitude(delta: float) -> str:
    absolute = abs(delta)
    if absolute >= 0.5:
        return "clear"
    if absolute >= 0.15:
        return "small"
    return "subtle"


def _change_summary(key: str, delta: float, state: RelationshipState) -> str:
    went_up = delta > 0
    if key == "trust":
        return "Trust opened a little." if went_up else "Trust pulled back a little."
    if key == "intimacy":
        return (
            "The exchange carried a little more closeness."
            if went_up
            else ("Closeness eased back a little.")
        )
    if key == "warmth":
        return "Warmth rose after this turn." if went_up else "Warmth cooled slightly."
    if key == "tension":
        if went_up:
            return "Tension rose; the next reply should move carefully."
        return "Tension eased a little."
    if key == "familiarity":
        return (
            "The rhythm became a little more familiar."
            if went_up
            else ("The rhythm softened a little.")
        )
    if key == "attachment":
        return (
            "The thread became a little more sticky."
            if went_up
            else ("Attachment loosened a little.")
        )
    if state.repair_needed:
        return "Repair is still the most important signal."
    return "The relationship shifted slightly."


def _recent_change_summary(changes: list[dict[str, object]]) -> str:
    summaries = [
        str(change.get("summary"))
        for change in changes[:2]
        if isinstance(change.get("summary"), str)
    ]
    return " ".join(summaries) if summaries else "The relationship held steady."


def _evidence_counts(value: object) -> dict[str, int]:
    source = value if isinstance(value, dict) else {}
    return {
        key: _bounded_evidence_count(source.get(key))
        for key in ("exchanges", "meaningful_events", "repairs", "conflicts")
    }


def _updated_evidence_counts(
    before: dict[str, int],
    *,
    content: str,
    normalized: str,
) -> dict[str, int]:
    updated = dict(before)
    updated["exchanges"] = min(updated["exchanges"] + 1, 1_000_000)
    meaningful = (
        len(content) > 120
        or any(word in normalized for word in (*POSITIVE_WORDS, *VULNERABLE_WORDS))
        or any(marker in normalized for marker in ("remember", "promise", "milestone"))
    )
    if meaningful:
        updated["meaningful_events"] = min(updated["meaningful_events"] + 1, 1_000_000)
    if any(word in normalized for word in REPAIR_WORDS):
        updated["repairs"] = min(updated["repairs"] + 1, 1_000_000)
    if any(word in normalized for word in CONFLICT_WORDS):
        updated["conflicts"] = min(updated["conflicts"] + 1, 1_000_000)
    return updated


def _bounded_evidence_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, min(value, 1_000_000))


def _cognition_evidence_counts(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key)[:40]: _bounded_evidence_count(count)
        for key, count in value.items()
        if isinstance(key, str)
    }
