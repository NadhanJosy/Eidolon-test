from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RelationshipState, utc_now

POSITIVE_WORDS = ("thanks", "thank you", "kind", "glad", "happy", "appreciate", "good")
REPAIR_WORDS = ("sorry", "apologize", "my fault")
CONFLICT_WORDS = ("angry", "upset", "hate", "annoyed", "frustrated")


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
        metadata_json={},
    )
    session.add(state)
    await session.flush()
    return state


async def update_relationship_from_message(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    content: str,
) -> RelationshipState:
    state = await get_or_create_relationship(session, user_id, character_id)
    normalized = content.lower()

    state.familiarity = clamp(state.familiarity + 0.2, 0, 100)
    if len(content) > 120:
        state.intimacy = clamp(state.intimacy + 0.1, 0, 100)
    if any(word in normalized for word in POSITIVE_WORDS):
        state.warmth = clamp(state.warmth + 0.3, -100, 100)
        state.trust = clamp(state.trust + 0.1, -100, 100)
    if any(word in normalized for word in REPAIR_WORDS):
        state.tension = clamp(state.tension - 0.5, 0, 100)
        state.trust = clamp(state.trust + 0.1, -100, 100)
    if any(word in normalized for word in CONFLICT_WORDS):
        state.tension = clamp(state.tension + 0.5, 0, 100)
        state.warmth = clamp(state.warmth - 0.2, -100, 100)

    state.attachment = clamp(state.attachment + 0.02, 0, 100)
    state.last_interaction_at = utc_now()
    await session.flush()
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
        f"attachment {state.attachment:.1f}/100."
    )


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
