from __future__ import annotations

import math
from datetime import datetime

from pydantic import ValidationError

from app.companion.domain import EmotionalState, TurnPerception
from app.models import RelationshipState, utc_now

HALF_LIFE_HOURS = {
    "amusement": 6.0,
    "concern": 18.0,
    "warmth": 72.0,
    "hurt": 96.0,
    "guardedness": 48.0,
}


def read_emotional_state(state: RelationshipState) -> EmotionalState:
    value = state.emotional_state_json
    try:
        return EmotionalState.model_validate(value if isinstance(value, dict) else {})
    except ValidationError:
        return EmotionalState()


def project_emotional_state(
    state: RelationshipState,
    *,
    now: datetime | None = None,
) -> EmotionalState:
    current = read_emotional_state(state)
    now = now or utc_now()
    hours = max((now - current.updated_at).total_seconds() / 3600, 0.0)
    if hours <= 0:
        return current
    values = current.model_dump()
    for key, half_life in HALF_LIFE_HOURS.items():
        baseline = 0.12 if key == "warmth" else 0.0
        value = float(values[key])
        values[key] = baseline + (value - baseline) * math.pow(0.5, hours / half_life)
    values["repair_openness"] = 1.0 - (
        (1.0 - current.repair_openness) * math.pow(0.5, hours / 72.0)
    )
    values["updated_at"] = now
    if hours >= 24:
        values["cause_tags"] = current.cause_tags[-4:]
    return EmotionalState.model_validate(values)


def apply_emotional_turn(
    state: RelationshipState,
    perception: TurnPerception,
    *,
    now: datetime | None = None,
) -> EmotionalState:
    now = now or utc_now()
    current = project_emotional_state(state, now=now)
    values = current.model_dump()
    tags = list(current.cause_tags)

    if perception.intent == "celebrate" or perception.tone == "bright":
        _add(values, "amusement", 0.32)
        _add(values, "warmth", 0.18)
        tags.append("shared_joy")
    if perception.intent == "play" or perception.tone == "playful":
        _add(values, "amusement", 0.28)
        _add(values, "warmth", 0.1)
        tags.append("play")
    if perception.intent == "support" or perception.tone in {"anxious", "heavy"}:
        _add(values, "concern", 0.34)
        _add(values, "warmth", 0.08)
        tags.append("concern")
    if perception.conflict_signal:
        _add(values, "hurt", 0.38)
        _add(values, "guardedness", 0.34)
        _add(values, "warmth", -0.16)
        _add(values, "repair_openness", -0.3)
        tags.append("conflict")
    if perception.repair_signal:
        # Repair is real but gradual: one apology cannot erase accumulated hurt.
        _add(values, "hurt", -0.18)
        _add(values, "guardedness", -0.16)
        _add(values, "warmth", 0.12)
        _add(values, "repair_openness", 0.24)
        tags.append("repair_attempt")
    if perception.tone == "tender":
        _add(values, "warmth", 0.12)
        tags.append("tenderness")

    values["cause_tags"] = _dedupe(tags)[-8:]
    values["updated_at"] = now
    updated = EmotionalState.model_validate(values)
    state.emotional_state_json = updated.model_dump(mode="json")
    return updated


def emotional_posture(emotion: EmotionalState, *, repair_needed: bool) -> str:
    conflict_still_resolving = "conflict" in emotion.cause_tags and emotion.hurt >= 0.12
    if repair_needed or emotion.hurt >= 0.42 or conflict_still_resolving:
        if emotion.repair_openness >= 0.55:
            return "hurt but open to careful repair; do not pretend everything is already fine"
        return "hurt and guarded; stay restrained, honest, and non-punishing"
    if emotion.guardedness >= 0.38:
        return "guarded and measured; allow space without becoming cold"
    if emotion.concern >= 0.38:
        return "quietly concerned; let care show through attention, not canned reassurance"
    if emotion.amusement >= 0.35:
        return "genuinely amused and a little playful"
    if emotion.warmth >= 0.34:
        return "warm and present without overclaiming closeness"
    return "steady, attentive, and emotionally available"


def emotional_mood(emotion: EmotionalState, *, repair_needed: bool) -> str:
    conflict_still_resolving = "conflict" in emotion.cause_tags and emotion.hurt >= 0.12
    if repair_needed or emotion.hurt >= 0.42 or conflict_still_resolving:
        return "hurt" if emotion.repair_openness >= 0.55 else "guarded"
    candidates = (
        (emotion.guardedness, "guarded"),
        (emotion.concern, "concerned"),
        (emotion.amusement, "amused"),
        (emotion.warmth, "warm"),
    )
    strongest, label = max(candidates)
    return label if strongest >= 0.34 else "steady"


def _add(values: dict[str, object], key: str, amount: float) -> None:
    current = float(values[key])
    values[key] = max(0.0, min(1.0, current + amount))


def _dedupe(values: list[str]) -> list[str]:
    selected: list[str] = []
    for value in values:
        if value and value not in selected:
            selected.append(value)
    return selected
