from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from app.companion.domain import CharacterSoul
from app.models import Character


def character_soul(character: Character) -> CharacterSoul:
    stored = character.soul_json if isinstance(character.soul_json, dict) else {}
    legacy = character.boundaries_json if isinstance(character.boundaries_json, dict) else {}
    defaults = _legacy_soul_values(character, legacy)
    try:
        return CharacterSoul.model_validate({**defaults, **stored})
    except ValidationError:
        # Older or manually imported profiles fail closed to bounded legacy values.
        return CharacterSoul.model_validate(defaults)


def canonical_soul_json(
    value: Mapping[str, object] | CharacterSoul | None,
    *,
    character: Character | None = None,
) -> dict[str, object]:
    if isinstance(value, CharacterSoul):
        soul = value
    else:
        payload = dict(value or {})
        if character is not None:
            legacy = (
                character.boundaries_json if isinstance(character.boundaries_json, dict) else {}
            )
            payload = {**_legacy_soul_values(character, legacy), **payload}
        soul = CharacterSoul.model_validate(payload)
    return soul.model_dump(mode="json")


def compiled_soul_sections(
    character: Character,
    soul: CharacterSoul | None = None,
) -> tuple[str, ...]:
    """Compile stable prose modules; raw profile JSON never enters a prompt."""
    soul = soul or character_soul(character)
    relationship_path = soul.relationship_path
    if relationship_path == "custom" and soul.custom_relationship:
        relationship_path = f"custom: {soul.custom_relationship}"
    identity = "\n".join(
        (
            "Character identity, personality, style, and boundaries:",
            f"Character name: {_compact(character.name, 120)}",
            f"Identity: {_compact(soul.identity, 700)}",
            f"Worldview: {_compact(soul.worldview, 700)}",
            f"Temperament: {_compact(soul.temperament, 700)}",
            f"Values: {_compact(soul.values, 600)}",
            f"Relationship path: {_compact(relationship_path, 500)}",
        )
    )
    voice = "\n".join(
        (
            "Character voice and conversational texture:",
            f"Speech rhythm: {_compact(soul.speech_rhythm, 700)}",
            f"Speech style: {_compact(soul.speech_rhythm, 700)}",
            f"Humour: {_compact(soul.humour, 500)}",
            f"Habits: {_compact(soul.habits, 600)}",
            f"Emoji use: {soul.emoji_style}",
            f"Terms of address: {_compact(soul.terms_of_address, 500)}",
        )
    )
    relating = "\n".join(
        (
            "Character ways of relating:",
            f"Affection style: {_compact(soul.affection_style, 650)}",
            f"Conflict style: {_compact(soul.conflict_style, 650)}",
            f"Insecurities and imperfect edges: {_compact(soul.insecurities, 650)}",
            f"Initiative style: {_compact(soul.initiative_style, 650)}",
            f"Personal boundaries: {_compact(soul.boundaries, 750)}",
            "Remain recognisable. Do not flatten these traits into generic agreement, therapy, "
            "or constant reassurance.",
        )
    )
    return identity, voice, relating


def _legacy_soul_values(character: Character, profile: Mapping[str, object]) -> dict[str, object]:
    relationship_type = _mapping_text(profile, "relationship_type")
    personality = character.personality_core or ""
    speech_style = character.speech_style or ""
    description = character.description or ""
    return {
        "identity": description or f"{character.name} is a distinct private text companion.",
        "worldview": _mapping_text(profile, "worldview")
        or "Values honest attention, privacy, consent, and ordinary moments.",
        "temperament": personality
        or "Observant, grounded, patient, and capable of gentle friction.",
        "humour": _mapping_text(profile, "humor_style") or "Dry, understated, and never cruel.",
        "speech_rhythm": speech_style
        or "Plainspoken, varied, and comfortable with short replies and silence.",
        "affection_style": _mapping_text(profile, "affection_style")
        or "Warm through specificity; never assumes intimacy.",
        "conflict_style": _mapping_text(profile, "conflict_style")
        or "Direct without being punishing; owns mistakes and gives repair time.",
        "values": _mapping_text(profile, "values") or "Privacy, consent, honesty, and continuity.",
        "insecurities": _mapping_text(profile, "insecurities")
        or _mapping_text(profile, "flaws")
        or "Can become overly careful when the emotional stakes are unclear.",
        "habits": _mapping_text(profile, "habits")
        or "Notices small wording changes and unfinished threads.",
        "initiative_style": _mapping_text(profile, "initiative_style")
        or "Offers a contextual thought or activity when the moment has room for it.",
        "boundaries": _mapping_text(profile, "boundary_notes")
        or _mapping_text(profile, "default")
        or "Respects stated limits, consent, privacy, and all platform boundaries.",
        "emoji_style": _legacy_emoji_style(profile),
        "terms_of_address": _mapping_text(profile, "nicknames")
        or "Uses the chosen name; nicknames must be invited or earned gradually.",
        "relationship_path": _relationship_path(relationship_type),
        "custom_relationship": (
            relationship_type
            if relationship_type and _relationship_path(relationship_type) == "custom"
            else ""
        ),
    }


def _mapping_text(profile: Mapping[str, object], key: str) -> str:
    value = profile.get(key)
    return " ".join(value.split()) if isinstance(value, str) else ""


def _legacy_emoji_style(profile: Mapping[str, object]) -> str:
    value = _mapping_text(profile, "emoji_style").casefold()
    if value in {"none", "rare", "light", "expressive"}:
        return value
    return "rare"


def _relationship_path(value: str) -> str:
    normalized = value.casefold()
    if any(marker in normalized for marker in ("romantic", "partner", "slow-burn")):
        return "romantic"
    if any(marker in normalized for marker in ("friend", "confidant", "companion")):
        return "friendship"
    return "custom" if normalized else "friendship"


def _compact(value: str, limit: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."
