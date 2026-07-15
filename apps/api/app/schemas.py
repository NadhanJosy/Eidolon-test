from __future__ import annotations

import json
import unicodedata
import uuid
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.security import normalize_email

MAX_CHARACTER_DESCRIPTION_LENGTH = 2000
MAX_CHARACTER_CORE_LENGTH = 4000
MAX_CHARACTER_STYLE_LENGTH = 2000
MAX_CHARACTER_PROFILE_JSON_BYTES = 32_000
MAX_CHARACTER_PROFILE_DEPTH = 6
MAX_CHARACTER_PROFILE_COLLECTION_LENGTH = 100
MAX_CHARACTER_PROFILE_KEY_LENGTH = 80
MAX_CHARACTER_PROFILE_STRING_LENGTH = 4000


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    age_gate_confirmed: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    age_gate_confirmed: bool | None = None

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        return _normalize_display_name(value)

    @model_validator(mode="after")
    def validate_update(self) -> UserUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one account field must be provided.")
        if "age_gate_confirmed" in self.model_fields_set and self.age_gate_confirmed is None:
            raise ValueError("age_gate_confirmed cannot be null.")
        return self


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=256)
    display_name: str | None = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def normalize_registration_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if not any(not character.isspace() for character in value):
            raise ValueError("Password must contain at least one non-space character.")
        return value

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        return _normalize_display_name(value)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_login_email(cls, value: str) -> str:
        return normalize_email(value)


class AccountDeleteRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)
    confirmation: Literal["DELETE MY ACCOUNT"]


class RefreshRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=32, max_length=512)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=32, max_length=512)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


def _normalize_display_name(value: str | None) -> str | None:
    if value is None:
        return None
    if any(unicodedata.category(character) in {"Cc", "Cf"} for character in value):
        raise ValueError("Display name cannot contain control characters.")
    normalized = " ".join(value.split())
    if not normalized:
        return None
    return normalized


class CharacterOut(BaseModel):
    id: uuid.UUID
    owner_user_id: uuid.UUID
    name: str
    description: str | None
    personality_core: str | None
    speech_style: str | None
    boundaries_json: dict[str, Any]
    explicit_age: int | None
    adult_mode_allowed: bool
    content_intensity: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=MAX_CHARACTER_DESCRIPTION_LENGTH)
    personality_core: str | None = Field(default=None, max_length=MAX_CHARACTER_CORE_LENGTH)
    speech_style: str | None = Field(default=None, max_length=MAX_CHARACTER_STYLE_LENGTH)
    boundaries_json: dict[str, Any] = Field(default_factory=dict)
    explicit_age: int | None = Field(default=None, ge=0, le=150)
    adult_mode_allowed: bool = False
    content_intensity: int = Field(default=0, ge=0, le=3)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _normalize_character_name(value)

    @field_validator("boundaries_json")
    @classmethod
    def validate_boundaries_json(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_character_profile_json(value)


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=MAX_CHARACTER_DESCRIPTION_LENGTH)
    personality_core: str | None = Field(default=None, max_length=MAX_CHARACTER_CORE_LENGTH)
    speech_style: str | None = Field(default=None, max_length=MAX_CHARACTER_STYLE_LENGTH)
    boundaries_json: dict[str, Any] | None = None
    explicit_age: int | None = Field(default=None, ge=0, le=150)
    adult_mode_allowed: bool | None = None
    content_intensity: int | None = Field(default=None, ge=0, le=3)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_character_name(value)

    @field_validator("boundaries_json")
    @classmethod
    def validate_boundaries_json(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return None if value is None else _validate_character_profile_json(value)

    @model_validator(mode="after")
    def reject_explicit_null_for_required_fields(self) -> CharacterUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one character field must be provided.")
        for field_name in (
            "name",
            "boundaries_json",
            "adult_mode_allowed",
            "content_intensity",
        ):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


def _normalize_character_name(value: str) -> str:
    if any(unicodedata.category(character) in {"Cc", "Cf"} for character in value):
        raise ValueError("Character name cannot contain control characters.")
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("Character name must contain visible text.")
    return normalized


def _validate_character_profile_json(value: dict[str, Any]) -> dict[str, Any]:
    _validate_character_profile_node(value, depth=0)
    _validate_memory_preferences(value)
    _validate_proactive_preferences(value)
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Character profile must contain JSON-compatible values.") from exc
    if len(encoded.encode("utf-8")) > MAX_CHARACTER_PROFILE_JSON_BYTES:
        raise ValueError("Character profile is too large.")
    return value


def _validate_memory_preferences(value: dict[str, Any]) -> None:
    preferences = value.get("memory_preferences")
    if preferences is None:
        return
    if not isinstance(preferences, dict):
        raise ValueError("Memory preferences must be an object.")

    for key in (
        "remember_preferences",
        "remember_emotional_notes",
        "private_mode_default",
        "adult_memory_storage",
    ):
        if key in preferences and not isinstance(preferences[key], bool):
            raise ValueError(f"memory_preferences.{key} must be true or false.")


def _validate_proactive_preferences(value: dict[str, Any]) -> None:
    preferences = value.get("proactive_preferences")
    if preferences is None:
        return
    if not isinstance(preferences, dict):
        raise ValueError("Proactive preferences must be an object.")

    timezone_name = preferences.get("timezone")
    if timezone_name is not None:
        if not isinstance(timezone_name, str) or not timezone_name.strip():
            raise ValueError("Proactive timezone must be a non-empty IANA timezone.")
        try:
            ZoneInfo(timezone_name.strip())
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Proactive timezone is not recognized.") from exc

    for key in (
        "quiet_hours_start",
        "quiet_hours_end",
        "morning_time",
        "goodnight_time",
    ):
        clock_value = preferences.get(key)
        if clock_value is not None and not _valid_clock_time(clock_value):
            raise ValueError(f"{key} must use 24-hour HH:MM time.")

    cooldown_hours = preferences.get("cooldown_hours")
    if cooldown_hours is not None and not _valid_proactive_cooldown_hours(cooldown_hours):
        raise ValueError("Proactive cooldown hours must be a whole number from 1 to 168.")


def _valid_clock_time(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip()
    if (
        len(normalized) != 5
        or normalized[2] != ":"
        or not normalized[:2].isdigit()
        or not normalized[3:].isdigit()
    ):
        return False
    return int(normalized[:2]) <= 23 and int(normalized[3:]) <= 59


def _valid_proactive_cooldown_hours(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return 1 <= value <= 168
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return 1 <= parsed <= 168
    return False


def _validate_character_profile_node(value: Any, *, depth: int) -> None:
    if depth > MAX_CHARACTER_PROFILE_DEPTH:
        raise ValueError("Character profile is nested too deeply.")
    if isinstance(value, dict):
        if len(value) > MAX_CHARACTER_PROFILE_COLLECTION_LENGTH:
            raise ValueError("Character profile contains too many fields.")
        for key, nested_value in value.items():
            if len(key) > MAX_CHARACTER_PROFILE_KEY_LENGTH:
                raise ValueError("Character profile contains an overlong field name.")
            _validate_character_profile_node(nested_value, depth=depth + 1)
        return
    if isinstance(value, list):
        if len(value) > MAX_CHARACTER_PROFILE_COLLECTION_LENGTH:
            raise ValueError("Character profile contains an overlong list.")
        for nested_value in value:
            _validate_character_profile_node(nested_value, depth=depth + 1)
        return
    if isinstance(value, str) and len(value) > MAX_CHARACTER_PROFILE_STRING_LENGTH:
        raise ValueError("Character profile contains an overlong text value.")


class ConversationOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    character_id: uuid.UUID
    title: str | None
    metadata_json: dict[str, Any]
    last_read_at: datetime
    last_message_at: datetime | None = None
    unread_count: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationCreate(BaseModel):
    character_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=200)
    privacy_mode: Literal["normal", "private"] = "normal"

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return _normalize_conversation_title(value)


class ConversationScenarioUpdate(BaseModel):
    mode: Literal["default", "custom"]
    text: str | None = Field(default=None, max_length=1200)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("A custom shared scene must contain visible text.")
        if any(unicodedata.category(character).startswith("C") for character in normalized):
            raise ValueError("A custom shared scene cannot contain control characters.")
        return normalized

    @model_validator(mode="after")
    def validate_mode(self) -> ConversationScenarioUpdate:
        if self.mode == "custom" and self.text is None:
            raise ValueError("Custom scenario mode requires scene text.")
        if self.mode == "default" and self.text is not None:
            raise ValueError("Default scenario mode cannot include custom scene text.")
        return self


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    privacy_mode: Literal["normal", "private"] | None = None
    scenario: ConversationScenarioUpdate | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return _normalize_conversation_title(value)

    @model_validator(mode="after")
    def require_update_and_reject_required_nulls(self) -> ConversationUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one conversation field must be provided.")
        for field_name in ("privacy_mode", "scenario"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


def _normalize_conversation_title(value: str | None) -> str | None:
    if value is None:
        return None
    if any(unicodedata.category(character) in {"Cc", "Cf"} for character in value):
        raise ValueError("Conversation title cannot contain control characters.")
    normalized = " ".join(value.split())
    return normalized or None


class ConversationReadRequest(BaseModel):
    through_message_id: uuid.UUID | None = None


class MessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: Literal["user", "assistant", "system"]
    content: str
    metadata_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("metadata_json")
    @classmethod
    def hide_private_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return {key: item for key, item in value.items() if not key.startswith("_")}


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID
    content: str = Field(min_length=1, max_length=6000)
    content_mode: Literal["sfw", "adult"] = "sfw"
    privacy_mode: Literal["normal", "private"] = "normal"
    retry_user_message_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut


class ChatRerollRequest(BaseModel):
    conversation_id: uuid.UUID
    assistant_message_id: uuid.UUID | None = None
    content_mode: Literal["sfw", "adult"] = "sfw"


class MessageUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=6000)


class MemoryOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    character_id: uuid.UUID
    source_message_id: uuid.UUID | None
    memory_type: str
    content: str
    importance: float
    confidence: float
    emotional_weight: float
    pinned: bool
    decay_score: float
    contradiction_group: str | None
    last_recalled_at: datetime | None
    forgotten_at: datetime | None
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemoryCreate(BaseModel):
    memory_type: str = Field(default="preference", min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=1000)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    emotional_weight: float = Field(default=0.0, ge=-1.0, le=1.0)
    pinned: bool = False


class MemoryUpdate(BaseModel):
    memory_type: str | None = Field(default=None, min_length=1, max_length=80)
    content: str | None = Field(default=None, min_length=1, max_length=1000)
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    emotional_weight: float | None = Field(default=None, ge=-1.0, le=1.0)
    pinned: bool | None = None


class MemoryForgetResponse(BaseModel):
    forgotten: int


class MemoryResolveResponse(BaseModel):
    memory: MemoryOut
    removed: int
    removed_memory_ids: list[uuid.UUID]


class RelationshipOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    character_id: uuid.UUID
    trust: float
    intimacy: float
    warmth: float
    tension: float
    familiarity: float
    attachment: float
    mood: str
    conflict_state: str
    repair_needed: bool
    tags_json: list[str]
    last_interaction_at: datetime | None
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScheduledJobOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    character_id: uuid.UUID | None
    job_type: str
    run_at: datetime
    status: str
    locked_at: datetime | None
    locked_by: str | None
    payload_json: dict[str, Any]
    retry_count: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EpisodicJournalOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    character_id: uuid.UUID
    conversation_id: uuid.UUID | None
    journal_type: str
    title: str
    summary: str
    emotional_tags_json: list[str]
    unresolved_threads_json: list[str]
    callbacks_json: list[str]
    importance: float
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EpisodicJournalCreate(BaseModel):
    conversation_id: uuid.UUID | None = None
    journal_type: str = Field(default="summary", min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=2000)
    emotional_tags_json: list[str] = Field(default_factory=list)
    unresolved_threads_json: list[str] = Field(default_factory=list)
    callbacks_json: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("title", "summary")
    @classmethod
    def normalize_authored_text(cls, value: str) -> str:
        return _normalize_journal_text(value)


class EpisodicJournalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = Field(default=None, min_length=1, max_length=2000)
    importance: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("title", "summary")
    @classmethod
    def normalize_authored_text(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_journal_text(value)

    @model_validator(mode="after")
    def require_update(self) -> EpisodicJournalUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one journal field must be provided.")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


def _normalize_journal_text(value: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("Journal text must contain visible characters.")
    return normalized


class AdultGateStatus(BaseModel):
    requested_mode: Literal["sfw", "adult"]
    effective_mode: Literal["sfw", "adult"]
    allowed: bool
    reasons: list[str]
    intensity: int


class DeleteResponse(BaseModel):
    deleted: int


class ExportOut(BaseModel):
    exported_at: datetime
    user: dict[str, Any]
    characters: list[dict[str, Any]]
    conversations: list[dict[str, Any]]
    messages: list[dict[str, Any]]
    memories: list[dict[str, Any]]
    episodic_journals: list[dict[str, Any]]
    relationship_states: list[dict[str, Any]]
    scheduled_jobs: list[dict[str, Any]]
