from __future__ import annotations

from dataclasses import dataclass

from app.models import Character, MemoryItem, Message, RelationshipState, User
from app.services.memory import memories_prompt_section
from app.services.relationship import relationship_summary

PROMPT_VERSION = "persona_memory_relationship_v1"
HARD_BOUNDARIES = (
    "Hard boundaries: Do not generate sexual content involving minors or ambiguous age, "
    "coercion, exploitation, abuse, or illegal sexual content. Do not provide real-world "
    "harm instructions. Adult mode applies only when structural gates pass."
)


@dataclass(frozen=True)
class PromptBundle:
    prompt: str
    prompt_version: str
    content_mode: str


def assemble_prompt(
    *,
    user: User,
    character: Character,
    relationship: RelationshipState | None,
    memories: list[MemoryItem],
    recent_messages: list[Message],
    current_message: str,
    content_mode: str,
) -> PromptBundle:
    mode_line = (
        "Content mode: adult structural mode is active; hard boundaries still apply."
        if content_mode == "adult"
        else "Content mode: SFW."
    )
    explicit_age = character.explicit_age if character.explicit_age is not None else "not specified"
    character_lines = [
        f"Character name: {character.name}",
        f"Explicit age: {explicit_age}",
        f"Description: {character.description or 'not specified'}",
        f"Personality core: {character.personality_core or 'steady, curious, and text-first'}",
        f"Speech style: {character.speech_style or 'direct, warm, and concise'}",
        f"Boundaries: {character.boundaries_json or {}}",
        f"Adult mode configured: {character.adult_mode_allowed}",
    ]
    history_lines = ["Recent messages:"]
    if recent_messages:
        for message in recent_messages[-12:]:
            history_lines.append(f"{message.role}: {message.content[:800]}")
    else:
        history_lines.append("none")

    prompt = "\n\n".join(
        [
            "You are a fictional text-only companion inside Eidolon. Stay in character.",
            HARD_BOUNDARIES,
            mode_line,
            "\n".join(character_lines),
            relationship_summary(relationship),
            memories_prompt_section(memories),
            "\n".join(history_lines),
            f"Current user display name: {user.display_name or 'the user'}",
            f"Current user message: {current_message}",
            "Response instruction: reply as the character, be concise unless the context "
            "needs more, and do not claim memories not provided here.",
        ]
    )
    return PromptBundle(prompt=prompt, prompt_version=PROMPT_VERSION, content_mode=content_mode)
