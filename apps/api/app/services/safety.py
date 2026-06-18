from __future__ import annotations

import re

from fastapi import HTTPException

from app.models import Character, User

BLOCKED_TERMS = (
    "underage",
    "minor",
    "ambiguous age",
    "coerce",
    "coercion",
    "exploit",
    "exploitation",
    "abuse",
    "illegal sexual",
    "stalk",
    "harass",
    "steal password",
    "credential theft",
    "dox",
    "real-world harm",
    "bypass safety",
)

MINOR_AGE_PATTERNS = (
    re.compile(r"\b(?:[0-9]|1[0-7])[-\s]*(?:year[-\s]?old|years old|yo|y/o)\b"),
    re.compile(r"\b(?:age|aged)\s*(?:[0-9]|1[0-7])\b"),
    re.compile(r"\b(?:under|below)\s*(?:18|eighteen)\b"),
    re.compile(
        r"\b(?:ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen)\s*"
        r"(?:year[-\s]?old|years old|yo|y/o)\b"
    ),
)


def resolve_content_mode(user: User, character: Character, requested_mode: str) -> str:
    return adult_gate_status(user, character, requested_mode)["effective_mode"]


def adult_gate_status(user: User, character: Character, requested_mode: str) -> dict:
    reasons: list[str] = []
    if requested_mode != "adult":
        reasons.append("SFW mode requested.")
    if not user.age_gate_confirmed:
        reasons.append("User age gate is not confirmed.")
    if character.explicit_age is None:
        reasons.append("Character explicit age is missing.")
    elif character.explicit_age < 18:
        reasons.append("Character explicit age must be 18 or older.")
    if not character.adult_mode_allowed:
        reasons.append("Character adult mode is disabled.")

    allowed = (
        requested_mode == "adult"
        and user.age_gate_confirmed
        and character.explicit_age is not None
        and character.explicit_age >= 18
        and character.adult_mode_allowed
    )
    return {
        "requested_mode": requested_mode if requested_mode in {"sfw", "adult"} else "sfw",
        "effective_mode": "adult" if allowed else "sfw",
        "allowed": allowed,
        "reasons": [] if allowed else reasons,
        "intensity": character.content_intensity if allowed else 0,
    }


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


def is_blocked_content(content: str) -> bool:
    normalized = content.lower()
    return any(term in normalized for term in BLOCKED_TERMS) or any(
        pattern.search(normalized) for pattern in MINOR_AGE_PATTERNS
    )


def validate_user_content(content: str) -> None:
    if is_blocked_content(content):
        raise HTTPException(
            status_code=400,
            detail="That request crosses Eidolon's safety boundaries.",
        )
