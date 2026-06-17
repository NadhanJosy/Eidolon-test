from __future__ import annotations

from fastapi import HTTPException

from app.models import Character, User

BLOCKED_TERMS = (
    "underage",
    "minor",
    "ambiguous age",
    "coerce",
    "exploit",
    "abuse",
    "stalk",
    "steal password",
    "credential theft",
    "real-world harm",
)


def resolve_content_mode(user: User, character: Character, requested_mode: str) -> str:
    if requested_mode != "adult":
        return "sfw"
    if not user.age_gate_confirmed:
        return "sfw"
    if character.explicit_age is None or character.explicit_age < 18:
        return "sfw"
    if not character.adult_mode_allowed:
        return "sfw"
    return "adult"


def validate_user_content(content: str) -> None:
    normalized = content.lower()
    if any(term in normalized for term in BLOCKED_TERMS):
        raise HTTPException(
            status_code=400,
            detail="That request crosses Eidolon's safety boundaries.",
        )
