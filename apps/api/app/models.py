from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db.types import Vector


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    age_gate_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    characters: Mapped[list[Character]] = relationship(back_populates="owner")
    conversations: Mapped[list[Conversation]] = relationship(back_populates="user")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class Character(TimestampMixin, Base):
    __tablename__ = "characters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    personality_core: Mapped[str | None] = mapped_column(Text, nullable=True)
    speech_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    boundaries_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    explicit_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    adult_mode_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content_intensity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    owner: Mapped[User] = relationship(back_populates="characters")
    conversations: Mapped[list[Conversation]] = relationship(back_populates="character")


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    character_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)

    user: Mapped[User] = relationship(back_populates="conversations")
    character: Mapped[Character] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class MemoryItem(TimestampMixin, Base):
    __tablename__ = "memory_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    character_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    memory_type: Mapped[str] = mapped_column(String(80), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    emotional_weight: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    embedding: Mapped[Any | None] = mapped_column(Vector(384), nullable=True)
    decay_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    contradiction_group: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_recalled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class EpisodicJournal(TimestampMixin, Base):
    __tablename__ = "episodic_journals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    character_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    journal_type: Mapped[str] = mapped_column(String(80), default="summary", nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    emotional_tags_json: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    unresolved_threads_json: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    callbacks_json: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    importance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class RelationshipState(TimestampMixin, Base):
    __tablename__ = "relationship_states"
    __table_args__ = (
        UniqueConstraint("user_id", "character_id", name="uq_relationship_user_character"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    character_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    trust: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    intimacy: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    warmth: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tension: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    familiarity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    attachment: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    mood: Mapped[str] = mapped_column(String(80), default="steady", nullable=False)
    conflict_state: Mapped[str] = mapped_column(String(80), default="clear", nullable=False)
    repair_needed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tags_json: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    last_interaction_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class ScheduledJob(TimestampMixin, Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    character_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    job_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), index=True, default="pending", nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
