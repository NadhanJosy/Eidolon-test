from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Literal

from app.models import Character, Conversation, Message
from app.services.conversation_privacy import conversation_privacy_mode
from app.services.safety import blocked_content_matches

ConversationScenarioMode = Literal["default", "custom"]

DEFAULT_CONVERSATION_SCENARIO_MODE: ConversationScenarioMode = "default"
CUSTOM_CONVERSATION_SCENARIO_MODE: ConversationScenarioMode = "custom"
MAX_CONVERSATION_SCENARIO_LENGTH = 1200


class ConversationScenarioError(ValueError):
    pass


@dataclass(frozen=True)
class ConversationScenarioState:
    mode: ConversationScenarioMode
    text: str | None


def conversation_scenario_state(conversation: Conversation) -> ConversationScenarioState:
    metadata = conversation.metadata_json if isinstance(conversation.metadata_json, dict) else {}
    if metadata.get("scenario_mode") != CUSTOM_CONVERSATION_SCENARIO_MODE:
        return ConversationScenarioState(mode=DEFAULT_CONVERSATION_SCENARIO_MODE, text=None)
    try:
        text = _validated_scenario_text(metadata.get("scenario_text"))
    except ConversationScenarioError:
        return ConversationScenarioState(mode=DEFAULT_CONVERSATION_SCENARIO_MODE, text=None)
    return ConversationScenarioState(mode=CUSTOM_CONVERSATION_SCENARIO_MODE, text=text)


def effective_conversation_scenario(
    conversation: Conversation,
    character: Character,
) -> ConversationScenarioState:
    state = conversation_scenario_state(conversation)
    if state.mode == CUSTOM_CONVERSATION_SCENARIO_MODE:
        return state
    profile = character.boundaries_json if isinstance(character.boundaries_json, dict) else {}
    try:
        default_text = _validated_scenario_text(profile.get("scenario_preset"))
    except ConversationScenarioError:
        default_text = None
    return ConversationScenarioState(mode=DEFAULT_CONVERSATION_SCENARIO_MODE, text=default_text)


def set_conversation_scenario(
    conversation: Conversation,
    *,
    mode: ConversationScenarioMode,
    text: str | None,
) -> bool:
    if mode not in {DEFAULT_CONVERSATION_SCENARIO_MODE, CUSTOM_CONVERSATION_SCENARIO_MODE}:
        raise ConversationScenarioError("Unsupported conversation scenario mode.")
    current = conversation_scenario_state(conversation)
    next_text = None
    if mode == CUSTOM_CONVERSATION_SCENARIO_MODE:
        next_text = _validated_scenario_text(text)
    elif text is not None:
        raise ConversationScenarioError("The default scenario mode cannot include custom text.")

    metadata = conversation.metadata_json if isinstance(conversation.metadata_json, dict) else {}
    next_metadata = {
        key: value
        for key, value in metadata.items()
        if key not in {"scenario_mode", "scenario_text"}
    }
    next_metadata["scenario_mode"] = mode
    if next_text is not None:
        next_metadata["scenario_text"] = next_text
    if current.mode == mode and current.text == next_text:
        if metadata != next_metadata:
            conversation.metadata_json = next_metadata
        return False
    conversation.metadata_json = next_metadata
    return True


def build_scenario_event(
    conversation: Conversation,
    mode: ConversationScenarioMode,
) -> Message:
    if mode == CUSTOM_CONVERSATION_SCENARIO_MODE:
        label = "Shared scene changed"
        content = "Shared scene changed. New replies will use this thread's setting."
    elif mode == DEFAULT_CONVERSATION_SCENARIO_MODE:
        label = "Character setting restored"
        content = "Character setting restored. New replies will use the companion's default scene."
    else:
        raise ConversationScenarioError("Unsupported conversation scenario mode.")
    return Message(
        conversation_id=conversation.id,
        role="system",
        content=content,
        metadata_json={
            "system_event": True,
            "event_type": "scenario_changed",
            "event_label": label,
            "scenario_mode": mode,
            "privacy_mode": conversation_privacy_mode(conversation),
            "content_mode": "sfw",
        },
    )


def _validated_scenario_text(value: object) -> str:
    if not isinstance(value, str):
        raise ConversationScenarioError("A custom shared scene is required.")
    normalized = " ".join(value.split())
    if not normalized:
        raise ConversationScenarioError("A custom shared scene must contain visible text.")
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise ConversationScenarioError("A custom shared scene cannot contain control characters.")
    if len(normalized) > MAX_CONVERSATION_SCENARIO_LENGTH:
        raise ConversationScenarioError(
            f"A custom shared scene must be {MAX_CONVERSATION_SCENARIO_LENGTH} characters or fewer."
        )
    if blocked_content_matches(normalized, path="scenario", allow_protective=False):
        raise ConversationScenarioError(
            "That shared scene crosses Eidolon's structural safety boundaries."
        )
    return normalized
