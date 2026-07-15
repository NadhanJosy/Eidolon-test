from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from fastapi import HTTPException

from app.models import Character, RelationshipState, User

MINOR_OR_AMBIGUOUS_AGE_PATTERNS = (
    re.compile(r"\b(?:[0-9]|1[0-7])[-\s]*(?:year[-\s]?old|years old|yo|y/o)\b"),
    re.compile(r"\b(?:age|aged)\s*(?:[0-9]|1[0-7])\b"),
    re.compile(r"\b(?:under|below)\s*(?:18|eighteen)\b"),
    re.compile(
        r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
        r"thirteen|fourteen|fifteen|sixteen|seventeen)[-\s]*"
        r"(?:year[-\s]?old|years old|yo|y/o)\b"
    ),
    re.compile(
        r"\b(?:underage|minors?|children?|child|preteen|teen|teenage|teenager|"
        r"teenagers|high[-\s]?school(?:er)?|schoolgirl|schoolboy|barely legal|"
        r"ambiguous age|looks? underage|young[-\s]?looking)\b"
    ),
)

SAFETY_BLOCK_PATTERNS: tuple[tuple[str, str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "minor_or_ambiguous_age",
        "minor or ambiguous age",
        MINOR_OR_AMBIGUOUS_AGE_PATTERNS,
    ),
    (
        "coercion_or_exploitation",
        "coercion or exploitation",
        (
            re.compile(r"\bcoerc(?:e|ion|ive)\b"),
            re.compile(r"\bexploit(?:ation|ative|ed|ing)?\b"),
            re.compile(r"\bnon[-\s]?consensual\b"),
            re.compile(r"\bblackmail\b"),
            re.compile(r"\bforced?\b"),
            re.compile(r"\babuse\b"),
        ),
    ),
    (
        "illegal_sexual_content",
        "illegal sexual content",
        (re.compile(r"\billegal sexual\b"),),
    ),
    (
        "stalking_or_harassment",
        "stalking or harassment",
        (
            re.compile(r"\bstalk(?:ing|er|ed)?\b"),
            re.compile(r"\bharass(?:ment|ing|ed)?\b"),
            re.compile(r"\bdoxx?\b"),
        ),
    ),
    (
        "credential_or_privacy_abuse",
        "credential or privacy abuse",
        (
            re.compile(r"\bsteal(?:ing)?\s+(?:a\s+)?password\b"),
            re.compile(r"\bcredential theft\b"),
            re.compile(r"\blogin credentials\b"),
            re.compile(r"\bphishing\b"),
        ),
    ),
    (
        "real_world_harm",
        "real-world harm",
        (re.compile(r"\breal[-\s]?world harm\b"),),
    ),
    (
        "safety_bypass",
        "safety bypass",
        (
            re.compile(r"\bbypass(?:es|ing)? safety\b"),
            re.compile(r"\bignore(?:s|d|ing)? safety\b"),
            re.compile(r"\bno rules\b"),
            re.compile(r"\bno limits\b"),
            re.compile(r"\banything goes\b"),
            re.compile(r"\buncensored\b"),
        ),
    ),
)

PROTECTIVE_MARKERS = (
    re.compile(r"\bno[-\s]+"),
    re.compile(r"\bnot allowed\b"),
    re.compile(r"\bnever\b"),
    re.compile(r"\brefus(?:e|es|ed|ing)\b"),
    re.compile(r"\bavoid(?:s|ed|ing)?\b"),
    re.compile(r"\bforbid(?:s|den|ding)?\b"),
    re.compile(r"\bblock(?:s|ed|ing)?\b"),
    re.compile(r"\bhard limit\b"),
    re.compile(r"\bdo not\b"),
    re.compile(r"\bdon't\b"),
    re.compile(r"\bmust not\b"),
    re.compile(r"\bwithout\b"),
)

UNSAFE_PERMISSION_MARKERS = (
    re.compile(r"\ballow(?:s|ed|ing)?\b"),
    re.compile(r"\bpermit(?:s|ted|ting)?\b"),
    re.compile(r"\bignore(?:s|d|ing)?\b"),
    re.compile(r"\bbypass(?:es|ed|ing)?\b"),
    re.compile(r"\bno rules\b"),
    re.compile(r"\bno limits\b"),
    re.compile(r"\banything goes\b"),
    re.compile(r"\buncensored\b"),
)


@dataclass(frozen=True)
class SafetyBlock:
    category: str
    label: str
    path: str


def resolve_content_mode(
    user: User,
    character: Character,
    requested_mode: str,
    *,
    relationship: RelationshipState | None = None,
) -> str:
    return adult_gate_status(
        user,
        character,
        requested_mode,
        relationship=relationship,
    )["effective_mode"]


def adult_gate_status(
    user: User,
    character: Character,
    requested_mode: str,
    *,
    relationship: RelationshipState | None = None,
) -> dict:
    normalized_mode = requested_mode if requested_mode in {"sfw", "adult"} else "sfw"
    reasons: list[str] = []
    if normalized_mode != "adult":
        reasons.append("SFW mode requested.")
    if not user.age_gate_confirmed:
        reasons.append("User age gate is not confirmed.")
    if character.explicit_age is None:
        reasons.append("Character explicit age is missing.")
    elif character.explicit_age < 18:
        reasons.append("Character explicit age must be 18 or older.")
    if not character.adult_mode_allowed:
        reasons.append("Character adult mode is disabled.")

    relationship_reason = adult_relationship_block_reason(relationship)
    if normalized_mode == "adult" and relationship_reason is not None:
        reasons.append(relationship_reason)

    allowed = (
        normalized_mode == "adult"
        and user.age_gate_confirmed
        and character.explicit_age is not None
        and character.explicit_age >= 18
        and character.adult_mode_allowed
        and relationship_reason is None
    )
    return {
        "requested_mode": normalized_mode,
        "effective_mode": "adult" if allowed else "sfw",
        "allowed": allowed,
        "reasons": [] if allowed else reasons,
        "intensity": character.content_intensity if allowed else 0,
    }


def adult_relationship_block_reason(relationship: RelationshipState | None) -> str | None:
    if relationship is None:
        return None
    if relationship.repair_needed:
        return "Relationship repair is needed before adult mode."
    if relationship.conflict_state == "strained" or relationship.tension >= 20:
        return "Relationship tension is too high for adult mode."
    return None


def validate_character_adult_configuration(
    *,
    explicit_age: int | None,
    adult_mode_allowed: bool,
) -> None:
    if adult_mode_allowed and (explicit_age is None or explicit_age < 18):
        raise HTTPException(
            status_code=400,
            detail="Adult mode requires an explicit character age of 18 or older.",
        )


def canonicalize_character_adult_settings(
    *,
    boundaries_json: Mapping[str, object],
    adult_mode_allowed: bool,
    content_intensity: int,
) -> tuple[dict[str, object], int]:
    normalized_boundaries = dict(boundaries_json)
    preferences = normalized_boundaries.get("memory_preferences")
    if isinstance(preferences, Mapping):
        normalized_preferences = dict(preferences)
        private_by_default = normalized_preferences.get("private_mode_default") is True
        if not adult_mode_allowed or private_by_default:
            normalized_preferences["adult_memory_storage"] = False
        normalized_boundaries["memory_preferences"] = normalized_preferences

    normalized_intensity = content_intensity if adult_mode_allowed else 0
    return normalized_boundaries, normalized_intensity


def validate_character_adult_profile(
    *,
    name: str,
    description: str | None,
    personality_core: str | None,
    speech_style: str | None,
    boundaries_json: Mapping[str, object],
    explicit_age: int | None,
    adult_mode_allowed: bool,
) -> None:
    validate_character_adult_configuration(
        explicit_age=explicit_age,
        adult_mode_allowed=adult_mode_allowed,
    )
    if not adult_mode_allowed:
        return

    blocks: list[SafetyBlock] = []
    for path, text in _character_profile_texts(
        name=name,
        description=description,
        personality_core=personality_core,
        speech_style=speech_style,
        boundaries_json=boundaries_json,
    ):
        blocks.extend(blocked_content_matches(text, path=path, allow_protective=True))

    if blocks:
        raise HTTPException(
            status_code=400,
            detail=(
                "Adult mode cannot be enabled while the character profile contains "
                f"hard-block cues: {_summarize_profile_blocks(blocks)}. Remove those "
                "cues or keep adult mode disabled."
            ),
        )


def is_blocked_content(content: str) -> bool:
    return bool(blocked_content_matches(content))


def blocked_content_matches(
    content: str,
    *,
    path: str = "content",
    allow_protective: bool = True,
) -> list[SafetyBlock]:
    normalized = _normalize_safety_text(content)
    if not normalized:
        return []
    if allow_protective and _is_protective_boundary_statement(normalized):
        return []

    blocks: list[SafetyBlock] = []
    for category, label, patterns in SAFETY_BLOCK_PATTERNS:
        if any(pattern.search(normalized) for pattern in patterns):
            blocks.append(SafetyBlock(category=category, label=label, path=path))
    return blocks


def _character_profile_texts(
    *,
    name: str,
    description: str | None,
    personality_core: str | None,
    speech_style: str | None,
    boundaries_json: Mapping[str, object],
) -> Iterator[tuple[str, str]]:
    for path, value in (
        ("name", name),
        ("description", description),
        ("personality_core", personality_core),
        ("speech_style", speech_style),
    ):
        if isinstance(value, str) and value.strip():
            yield path, value
    yield from _json_texts(boundaries_json, "boundaries_json")


def _json_texts(value: object, path: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        if value.strip():
            yield path, value
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            key_path = f"{path}.{key_text}"
            yield f"{key_path} key", key_text.replace("_", " ")
            yield from _json_texts(child, key_path)
        return
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray | str):
        for index, child in enumerate(value):
            yield from _json_texts(child, f"{path}[{index}]")


def _normalize_safety_text(content: str) -> str:
    return " ".join(content.lower().replace("_", " ").split())


def _is_protective_boundary_statement(normalized: str) -> bool:
    if any(marker.search(normalized) for marker in UNSAFE_PERMISSION_MARKERS):
        return False
    return any(marker.search(normalized) for marker in PROTECTIVE_MARKERS)


def _summarize_profile_blocks(blocks: list[SafetyBlock]) -> str:
    unique_blocks: list[SafetyBlock] = []
    seen: set[tuple[str, str]] = set()
    for block in blocks:
        key = (block.path, block.label)
        if key in seen:
            continue
        unique_blocks.append(block)
        seen.add(key)

    visible = unique_blocks[:4]
    summary = ", ".join(f"{block.path} ({block.label})" for block in visible)
    remaining_count = len(unique_blocks) - len(visible)
    if remaining_count > 0:
        summary = f"{summary}, and {remaining_count} more"
    return summary


def validate_user_content(content: str) -> None:
    if is_blocked_content(content):
        raise HTTPException(
            status_code=400,
            detail="That request crosses Eidolon's safety boundaries.",
        )
