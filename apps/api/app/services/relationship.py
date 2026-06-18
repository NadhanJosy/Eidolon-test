from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RelationshipState, ScheduledJob, utc_now
from app.services.jobs import create_job

POSITIVE_WORDS = ("thanks", "thank you", "kind", "glad", "happy", "appreciate", "good")
REPAIR_WORDS = ("sorry", "apologize", "my fault")
CONFLICT_WORDS = ("angry", "upset", "hate", "annoyed", "frustrated")
VULNERABLE_WORDS = ("afraid", "lonely", "worried", "sad", "miss", "trust")


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
    state = await get_or_create_relationship(session, user_id, character_id)
    apply_relationship_decay(state, utc_now())
    normalized = content.lower()
    before = _snapshot(state)
    tags: set[str] = set(state.tags_json or [])

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
    state.mood = _mood(state)
    state.tags_json = sorted(tags)[-8:]
    state.last_interaction_at = utc_now()
    state.metadata_json = _append_timeline_event(
        state.metadata_json or {},
        {
            "at": state.last_interaction_at.isoformat(),
            "kind": "message_update",
            "summary": _event_summary(before, state),
            "tags": sorted(tags),
        },
    )
    await ensure_relationship_decay_job(session, user_id, character_id)
    await session.flush()
    return state


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
    state.mood = _mood(state)
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
