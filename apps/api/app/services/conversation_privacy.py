from __future__ import annotations

from typing import Literal

from app.models import Conversation, Message

ConversationPrivacyMode = Literal["normal", "private"]

DEFAULT_CONVERSATION_PRIVACY_MODE: ConversationPrivacyMode = "normal"
PRIVATE_CONVERSATION_PRIVACY_MODE: ConversationPrivacyMode = "private"
VALID_CONVERSATION_PRIVACY_MODES = {
    DEFAULT_CONVERSATION_PRIVACY_MODE,
    PRIVATE_CONVERSATION_PRIVACY_MODE,
}
PRIVACY_EVENT_COPY: dict[ConversationPrivacyMode, tuple[str, str]] = {
    "private": (
        "Private room opened",
        (
            "Private room opened. New messages stay in this thread without shaping "
            "memory, journal, bond, or presence."
        ),
    ),
    "normal": (
        "Standard continuity resumed",
        (
            "Standard continuity resumed. Only new messages can shape memory, "
            "journal, bond, and presence."
        ),
    ),
}


def conversation_privacy_mode(conversation: Conversation) -> ConversationPrivacyMode:
    metadata = conversation.metadata_json if isinstance(conversation.metadata_json, dict) else {}
    mode = metadata.get("privacy_mode")
    if mode == PRIVATE_CONVERSATION_PRIVACY_MODE:
        return PRIVATE_CONVERSATION_PRIVACY_MODE
    return DEFAULT_CONVERSATION_PRIVACY_MODE


def conversation_is_private(conversation: Conversation) -> bool:
    return conversation_privacy_mode(conversation) == PRIVATE_CONVERSATION_PRIVACY_MODE


def message_privacy_mode(message: Message) -> ConversationPrivacyMode:
    metadata = message.metadata_json if isinstance(message.metadata_json, dict) else {}
    if metadata.get("privacy_mode") == PRIVATE_CONVERSATION_PRIVACY_MODE:
        return PRIVATE_CONVERSATION_PRIVACY_MODE
    return DEFAULT_CONVERSATION_PRIVACY_MODE


def message_is_private(message: Message) -> bool:
    return message_privacy_mode(message) == PRIVATE_CONVERSATION_PRIVACY_MODE


def resolve_turn_privacy_mode(
    conversation: Conversation,
    requested_mode: ConversationPrivacyMode,
) -> ConversationPrivacyMode:
    if requested_mode not in VALID_CONVERSATION_PRIVACY_MODES:
        raise ValueError("Unsupported turn privacy mode.")
    if conversation_is_private(conversation) or requested_mode == PRIVATE_CONVERSATION_PRIVACY_MODE:
        return PRIVATE_CONVERSATION_PRIVACY_MODE
    return DEFAULT_CONVERSATION_PRIVACY_MODE


def set_conversation_privacy_mode(
    conversation: Conversation,
    privacy_mode: ConversationPrivacyMode,
) -> None:
    if privacy_mode not in VALID_CONVERSATION_PRIVACY_MODES:
        raise ValueError("Unsupported conversation privacy mode.")
    metadata = conversation.metadata_json if isinstance(conversation.metadata_json, dict) else {}
    conversation.metadata_json = {
        **metadata,
        "privacy_mode": privacy_mode,
    }


def build_privacy_mode_event(
    conversation: Conversation,
    privacy_mode: ConversationPrivacyMode,
) -> Message:
    if privacy_mode not in VALID_CONVERSATION_PRIVACY_MODES:
        raise ValueError("Unsupported conversation privacy mode.")
    label, content = PRIVACY_EVENT_COPY[privacy_mode]
    return Message(
        conversation_id=conversation.id,
        role="system",
        content=content,
        metadata_json={
            "system_event": True,
            "event_type": "privacy_mode_changed",
            "event_label": label,
            "privacy_mode": privacy_mode,
            "content_mode": "sfw",
        },
    )
