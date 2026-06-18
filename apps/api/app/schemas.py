from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    display_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class AccountDeleteRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)
    confirmation: Literal["DELETE MY ACCOUNT"]


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=32, max_length=512)


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


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
    description: str | None = None
    personality_core: str | None = None
    speech_style: str | None = None
    boundaries_json: dict[str, Any] = Field(default_factory=dict)
    explicit_age: int | None = Field(default=None, ge=0, le=150)
    adult_mode_allowed: bool = False
    content_intensity: int = Field(default=0, ge=0, le=3)


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    personality_core: str | None = None
    speech_style: str | None = None
    boundaries_json: dict[str, Any] | None = None
    explicit_age: int | None = Field(default=None, ge=0, le=150)
    adult_mode_allowed: bool | None = None
    content_intensity: int | None = Field(default=None, ge=0, le=3)


class ConversationOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    character_id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationCreate(BaseModel):
    character_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=200)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class MessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: Literal["user", "assistant", "system"]
    content: str
    metadata_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID
    content: str = Field(min_length=1, max_length=6000)
    content_mode: Literal["sfw", "adult"] = "sfw"


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
