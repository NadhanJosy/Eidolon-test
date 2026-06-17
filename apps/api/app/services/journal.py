from __future__ import annotations

import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Character, Conversation, EpisodicJournal, Message, User, utc_now
from app.services.relationship import clamp

EMOTIONAL_TAGS = {
    "warm": ("thanks", "thank you", "glad", "happy", "appreciate"),
    "repair": ("sorry", "apologize", "my fault"),
    "tension": ("angry", "upset", "hate", "frustrated"),
    "playful": ("joke", "funny", "laugh"),
    "reflective": ("remember", "thinking", "felt", "feel"),
}
CALLBACK_MARKERS = ("remember", "next time", "later", "inside joke", "remind me")


async def list_journals(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    *,
    limit: int = 20,
) -> list[EpisodicJournal]:
    result = await session.execute(
        select(EpisodicJournal)
        .where(EpisodicJournal.user_id == user_id, EpisodicJournal.character_id == character_id)
        .order_by(desc(EpisodicJournal.created_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def create_journal(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    *,
    title: str,
    summary: str,
    conversation_id: uuid.UUID | None = None,
    journal_type: str = "summary",
    emotional_tags_json: list[str] | None = None,
    unresolved_threads_json: list[str] | None = None,
    callbacks_json: list[str] | None = None,
    importance: float = 0.5,
    metadata_json: dict | None = None,
) -> EpisodicJournal:
    journal = EpisodicJournal(
        user_id=user_id,
        character_id=character_id,
        conversation_id=conversation_id,
        journal_type=journal_type,
        title=_compact(title, 200) or "Conversation note",
        summary=_compact(summary, 2000),
        emotional_tags_json=emotional_tags_json or [],
        unresolved_threads_json=unresolved_threads_json or [],
        callbacks_json=callbacks_json or [],
        importance=clamp(importance, 0.0, 1.0),
        metadata_json=metadata_json or {},
    )
    session.add(journal)
    await session.flush()
    return journal


async def maybe_create_journal_from_conversation(
    session: AsyncSession,
    *,
    user: User,
    character: Character,
    conversation: Conversation,
) -> EpisodicJournal | None:
    messages = await _recent_messages(session, conversation.id, limit=8)
    if len(messages) < 2:
        return None

    result = await session.execute(
        select(EpisodicJournal)
        .where(
            EpisodicJournal.user_id == user.id,
            EpisodicJournal.character_id == character.id,
            EpisodicJournal.conversation_id == conversation.id,
        )
        .order_by(desc(EpisodicJournal.updated_at))
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    summary = summarize_messages(messages)
    tags = _emotional_tags(messages)
    unresolved = _unresolved_threads(messages)
    callbacks = _callbacks(messages)
    importance = clamp(0.35 + (0.1 * len(tags)) + (0.1 if callbacks else 0), 0.0, 1.0)

    if existing is not None:
        existing.summary = summary
        existing.emotional_tags_json = tags
        existing.unresolved_threads_json = unresolved
        existing.callbacks_json = callbacks
        existing.importance = max(existing.importance, importance)
        existing.updated_at = utc_now()
        existing.metadata_json = {
            **(existing.metadata_json or {}),
            "message_count": len(messages),
            "updated_by": "deterministic_summarizer",
        }
        await session.flush()
        return existing

    title = _title_from_messages(messages, character.name)
    return await create_journal(
        session,
        user.id,
        character.id,
        conversation_id=conversation.id,
        title=title,
        summary=summary,
        journal_type="conversation_summary",
        emotional_tags_json=tags,
        unresolved_threads_json=unresolved,
        callbacks_json=callbacks,
        importance=importance,
        metadata_json={"message_count": len(messages), "created_by": "deterministic_summarizer"},
    )


def journals_prompt_section(journals: list[EpisodicJournal]) -> str:
    if not journals:
        return "Episodic journal: no selected entries."
    lines = ["Episodic journal:"]
    for journal in journals[:4]:
        tags = ", ".join(journal.emotional_tags_json[:3]) or "steady"
        lines.append(
            f"- [{journal.journal_type}, importance {journal.importance:.1f}, tags {tags}] "
            f"{journal.title}: {journal.summary}"
        )
        for callback in journal.callbacks_json[:2]:
            lines.append(f"  callback: {callback}")
        for thread in journal.unresolved_threads_json[:2]:
            lines.append(f"  unresolved: {thread}")
    return "\n".join(lines)


def summarize_messages(messages: list[Message]) -> str:
    user_points: list[str] = []
    assistant_points: list[str] = []
    redacted_adult = False
    for message in messages:
        if message.metadata_json.get("content_mode") == "adult":
            redacted_adult = True
            continue
        excerpt = _compact(message.content, 180)
        if not excerpt:
            continue
        if message.role == "user":
            user_points.append(excerpt)
        elif message.role == "assistant":
            assistant_points.append(excerpt)

    pieces: list[str] = []
    if user_points:
        pieces.append(f"User brought up: {' / '.join(user_points[-3:])}.")
    if assistant_points:
        pieces.append(f"Character responded around: {' / '.join(assistant_points[-2:])}.")
    if redacted_adult:
        pieces.append("A gated adult-mode exchange occurred; durable details were omitted.")
    return " ".join(pieces) or "A brief exchange with no durable summary yet."


async def _recent_messages(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    *,
    limit: int,
) -> list[Message]:
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


def _title_from_messages(messages: list[Message], character_name: str) -> str:
    for message in messages:
        if message.role == "user" and message.content.strip():
            return _compact(message.content, 72)
    return f"Conversation with {character_name}"


def _emotional_tags(messages: list[Message]) -> list[str]:
    text = " ".join(message.content.lower() for message in messages)
    return [
        tag for tag, markers in EMOTIONAL_TAGS.items() if any(marker in text for marker in markers)
    ]


def _unresolved_threads(messages: list[Message]) -> list[str]:
    threads: list[str] = []
    for message in messages:
        if message.role == "user" and "?" in message.content:
            threads.append(_compact(message.content, 160))
    return threads[-3:]


def _callbacks(messages: list[Message]) -> list[str]:
    callbacks: list[str] = []
    for message in messages:
        normalized = message.content.lower()
        if message.role == "user" and any(marker in normalized for marker in CALLBACK_MARKERS):
            callbacks.append(_compact(message.content, 160))
    return callbacks[-3:]


def _compact(value: str, limit: int) -> str:
    compact = " ".join(value.strip().split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."
