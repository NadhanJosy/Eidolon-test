from __future__ import annotations

import uuid

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Character, Conversation, EpisodicJournal, Message, User, utc_now
from app.services.conversation_privacy import message_is_private
from app.services.relationship import clamp

EMOTIONAL_TAGS = {
    "warm": ("thanks", "thank you", "glad", "happy", "appreciate"),
    "repair": ("sorry", "apologize", "my fault"),
    "tension": ("angry", "upset", "hate", "frustrated"),
    "playful": ("joke", "funny", "laugh"),
    "reflective": ("remember", "thinking", "felt", "feel"),
    "inside_joke": ("inside joke", "our joke", "running joke"),
    "anniversary": ("anniversary", "a year since", "years since", "months since"),
    "shared_moment": ("shared moment", "moment we shared", "made this together"),
    "shared_reference": ("remember when", "our ritual", "our thing", "shared reference"),
    "milestone": ("first time", "milestone", "we did it", "we made it"),
}
CALLBACK_MARKERS = ("remember", "next time", "later", "inside joke", "remind me")
PROMISE_MARKERS = ("i promise", "we promise", "we promised", "you promised")
OPEN_THREAD_MARKERS = (
    "come back to",
    "circle back",
    "return to",
    "revisit",
    "pick this up",
    "talk about this later",
    "talk more later",
    "next time",
    "remind me",
    "follow up",
    "don't let me forget",
    "do not let me forget",
    "hold onto this",
)
REPAIR_ARC_MARKERS = ("sorry", "apologize", "my fault", "repair", "make it right")
ANNIVERSARY_MARKERS = (
    "anniversary",
    "one year since",
    "a year since",
    "years since",
    "one month since",
    "months since",
)
INSIDE_JOKE_MARKERS = (
    "inside joke",
    "our joke",
    "running joke",
    "still makes me laugh",
    "you always tease me about",
)
MILESTONE_MARKERS = (
    "first time",
    "milestone",
    "we did it",
    "we made it",
    "made it through",
    "finally",
)
SHARED_MOMENT_MARKERS = (
    "shared moment",
    "moment we shared",
    "this moment with you",
    "made this together",
    "did this together",
    "that day together",
    "that night together",
)
SHARED_REFERENCE_MARKERS = (
    "remember when",
    "that time",
    "our ritual",
    "our thing",
    "shared reference",
)
SIGNAL_LABELS = {
    "repair_arc": "repair arc",
    "anniversary": "anniversary",
    "inside_joke": "inside joke",
    "milestone": "milestone",
    "shared_moment": "shared moment",
    "shared_reference": "shared reference",
    "callback_request": "callback request",
    "open_thread": "open thread",
    "adult_redacted": "adult redacted",
    "steady_exchange": "steady exchange",
}
DETERMINISTIC_JOURNAL_SOURCE = "deterministic_summarizer"
MANUAL_JOURNAL_SOURCE = "manual"
JOURNAL_TYPE_BY_SIGNAL = {
    "repair_arc": "repair_arc",
    "anniversary": "anniversary",
    "inside_joke": "inside_joke",
    "milestone": "milestone",
    "shared_moment": "shared_moment",
    "shared_reference": "shared_reference",
    "callback_request": "callback",
    "open_thread": "open_thread",
    "adult_redacted": "adult_redacted",
}


class JournalMutationError(ValueError):
    """Raised when a transcript-owned episode is mutated as a personal note."""


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


def journal_is_manual(journal: EpisodicJournal) -> bool:
    metadata = journal.metadata_json if isinstance(journal.metadata_json, dict) else {}
    return metadata.get("source") == MANUAL_JOURNAL_SOURCE


async def update_manual_journal(
    session: AsyncSession,
    journal: EpisodicJournal,
    *,
    title: str | None = None,
    summary: str | None = None,
    importance: float | None = None,
) -> EpisodicJournal:
    if not journal_is_manual(journal):
        raise JournalMutationError(
            "Generated episodes follow their conversation. Edit the transcript instead."
        )
    if title is not None:
        journal.title = _compact(title, 200)
    if summary is not None:
        journal.summary = _compact(summary, 2000)
    if importance is not None:
        journal.importance = clamp(importance, 0.0, 1.0)
    journal.metadata_json = {
        **(journal.metadata_json or {}),
        "edited_by_user_at": utc_now().isoformat(),
    }
    await session.flush()
    return journal


async def delete_manual_journal(
    session: AsyncSession,
    journal: EpisodicJournal,
) -> None:
    if not journal_is_manual(journal):
        raise JournalMutationError(
            "Generated episodes follow their conversation. Clear or edit that conversation instead."
        )
    await session.delete(journal)
    await session.flush()


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
            or_(
                EpisodicJournal.metadata_json["source"].as_string() == DETERMINISTIC_JOURNAL_SOURCE,
                EpisodicJournal.metadata_json["created_by"].as_string()
                == DETERMINISTIC_JOURNAL_SOURCE,
            ),
        )
        .order_by(desc(EpisodicJournal.updated_at))
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    summary = summarize_messages(messages)
    tags = _emotional_tags(messages)
    unresolved = _unresolved_threads(messages)
    callbacks = _callbacks(messages)
    redacted_adult = _has_redacted_adult_message(messages)
    continuity = _continuity_metadata(messages, tags, unresolved, callbacks, redacted_adult)
    journal_type = _journal_type_from_continuity(continuity)
    signal_count = len(
        [
            signal
            for signal in continuity["continuity_signals"]
            if signal not in {"steady_exchange", "adult_redacted"}
        ]
    )
    importance = clamp(
        0.35 + (0.1 * len(tags)) + (0.1 if callbacks else 0) + (0.08 * signal_count),
        0.0,
        1.0,
    )

    if existing is not None:
        existing.summary = summary
        existing.journal_type = journal_type
        existing.emotional_tags_json = tags
        existing.unresolved_threads_json = unresolved
        existing.callbacks_json = callbacks
        existing.importance = max(existing.importance, importance)
        existing.updated_at = utc_now()
        existing.metadata_json = {
            **(existing.metadata_json or {}),
            "message_count": len(messages),
            "updated_by": "deterministic_summarizer",
            **continuity,
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
        journal_type=journal_type,
        emotional_tags_json=tags,
        unresolved_threads_json=unresolved,
        callbacks_json=callbacks,
        importance=importance,
        metadata_json={
            "source": DETERMINISTIC_JOURNAL_SOURCE,
            "message_count": len(messages),
            "created_by": DETERMINISTIC_JOURNAL_SOURCE,
            **continuity,
        },
    )


def journals_prompt_section(journals: list[EpisodicJournal]) -> str:
    if not journals:
        return "Episodic journal: no selected entries."
    lines = ["Episodic journal:"]
    for journal in journals[:4]:
        tags = ", ".join(journal.emotional_tags_json[:3]) or "steady"
        signals = ", ".join(journal_continuity_labels(journal)[:3])
        signal_text = f", signals {signals}" if signals else ""
        lines.append(
            f"- [{journal.journal_type}, importance {journal.importance:.1f}, "
            f"tags {tags}{signal_text}] "
            f"{journal.title}: {journal.summary}"
        )
        for note in journal_continuity_notes(journal)[:2]:
            lines.append(f"  continuity: {note}")
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
        if message_is_private(message):
            continue
        if _message_is_adult(message):
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
    message_privacy = Message.metadata_json["privacy_mode"].as_string()
    result = await session.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.role.in_(("user", "assistant")),
            or_(message_privacy.is_(None), message_privacy != "private"),
        )
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
    text = _safe_conversation_text(messages).lower()
    return [
        tag for tag, markers in EMOTIONAL_TAGS.items() if any(marker in text for marker in markers)
    ]


def _unresolved_threads(messages: list[Message]) -> list[str]:
    threads: list[str] = []
    latest_stateful_role = _latest_stateful_role(messages)
    latest_user_index = _latest_stateful_user_index(messages)
    for index, message in enumerate(messages):
        normalized = message.content.lower()
        if (
            message.role == "user"
            and _message_allows_durable_detail(message)
            and (
                any(marker in normalized for marker in OPEN_THREAD_MARKERS)
                or (
                    "?" in message.content
                    and latest_stateful_role == "user"
                    and index == latest_user_index
                )
            )
        ):
            threads.append(_compact(message.content, 160))
    return threads[-3:]


def _callbacks(messages: list[Message]) -> list[str]:
    callbacks: list[str] = []
    for message in messages:
        normalized = message.content.lower()
        if (
            message.role in {"user", "assistant"}
            and _message_allows_durable_detail(message)
            and (
                (
                    message.role == "user"
                    and any(marker in normalized for marker in CALLBACK_MARKERS)
                )
                or any(marker in normalized for marker in PROMISE_MARKERS)
            )
        ):
            callbacks.append(_compact(message.content, 160))
    return callbacks[-3:]


def _continuity_metadata(
    messages: list[Message],
    tags: list[str],
    unresolved: list[str],
    callbacks: list[str],
    redacted_adult: bool,
) -> dict[str, object]:
    safe_text = _safe_conversation_text(messages).lower()
    signals: list[str] = []
    notes: list[str] = []

    def add_signal(signal: str, note: str) -> None:
        if signal in signals:
            return
        signals.append(signal)
        notes.append(_compact(note, 220))

    if "repair" in tags or any(marker in safe_text for marker in REPAIR_ARC_MARKERS):
        add_signal("repair_arc", "Repair arc: prioritize accountability, steadiness, and space.")

    anniversary = _first_matching_user_excerpt(messages, ANNIVERSARY_MARKERS)
    if anniversary:
        add_signal(
            "anniversary",
            f"Anniversary: acknowledge the shared date without inventing details: {anniversary}",
        )

    inside_joke = _first_matching_user_excerpt(messages, INSIDE_JOKE_MARKERS)
    if inside_joke:
        add_signal(
            "inside_joke",
            f"Inside joke: preserve the exact playful reference: {inside_joke}",
        )

    if any(marker in safe_text for marker in MILESTONE_MARKERS):
        add_signal("milestone", "Milestone: treat this as meaningful shared progress.")

    shared_moment = _first_matching_user_excerpt(messages, SHARED_MOMENT_MARKERS)
    if shared_moment:
        add_signal(
            "shared_moment",
            f"Shared moment: keep this exchange emotionally specific: {shared_moment}",
        )

    shared_reference = _first_matching_user_excerpt(messages, SHARED_REFERENCE_MARKERS)
    if shared_reference:
        add_signal("shared_reference", f"Shared reference: {shared_reference}")

    if callbacks:
        add_signal("callback_request", f"Callback requested: {callbacks[-1]}")

    if unresolved:
        add_signal("open_thread", f"Open thread: {unresolved[-1]}")

    if redacted_adult and not signals:
        add_signal("adult_redacted", "Adult-mode episode redacted; do not infer durable details.")

    if not signals:
        add_signal("steady_exchange", "Steady exchange: keep continuity light and present-tense.")

    return {
        "episode_focus": signals[0],
        "continuity_signals": signals[:6],
        "continuity_notes": notes[:6],
        "redacted_adult": redacted_adult,
    }


def _journal_type_from_continuity(continuity: dict[str, object]) -> str:
    focus = continuity.get("episode_focus")
    if isinstance(focus, str):
        return JOURNAL_TYPE_BY_SIGNAL.get(focus, "conversation_summary")
    return "conversation_summary"


def journal_continuity_signals(journal: EpisodicJournal) -> list[str]:
    metadata = journal.metadata_json if isinstance(journal.metadata_json, dict) else {}
    raw_signals = metadata.get("continuity_signals")
    if not isinstance(raw_signals, list):
        return []
    signals: list[str] = []
    for signal in raw_signals:
        if isinstance(signal, str) and signal in SIGNAL_LABELS and signal not in signals:
            signals.append(signal)
    return signals


def journal_continuity_labels(journal: EpisodicJournal) -> list[str]:
    return [SIGNAL_LABELS[signal] for signal in journal_continuity_signals(journal)]


def journal_continuity_notes(journal: EpisodicJournal) -> list[str]:
    metadata = journal.metadata_json if isinstance(journal.metadata_json, dict) else {}
    raw_notes = metadata.get("continuity_notes")
    if not isinstance(raw_notes, list):
        return []
    notes: list[str] = []
    for note in raw_notes:
        if isinstance(note, str) and note.strip():
            notes.append(_compact(note, 220))
    return notes[:5]


def _first_matching_user_excerpt(messages: list[Message], markers: tuple[str, ...]) -> str:
    for message in messages:
        if message.role != "user" or not _message_allows_durable_detail(message):
            continue
        normalized = message.content.lower()
        if any(marker in normalized for marker in markers):
            return _compact(message.content, 160)
    return ""


def _latest_stateful_role(messages: list[Message]) -> str | None:
    for message in reversed(messages):
        if message.role in {"user", "assistant"} and _message_allows_durable_detail(message):
            return message.role
    return None


def _latest_stateful_user_index(messages: list[Message]) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if message.role == "user" and _message_allows_durable_detail(message):
            return index
    return None


def _safe_conversation_text(messages: list[Message]) -> str:
    return " ".join(
        message.content
        for message in messages
        if message.role in {"user", "assistant"} and _message_allows_durable_detail(message)
    )


def _has_redacted_adult_message(messages: list[Message]) -> bool:
    return any(
        _message_is_adult(message) and not message_is_private(message) for message in messages
    )


def _message_allows_durable_detail(message: Message) -> bool:
    return not message_is_private(message) and not _message_is_adult(message)


def _message_is_adult(message: Message) -> bool:
    metadata = message.metadata_json if isinstance(message.metadata_json, dict) else {}
    return metadata.get("content_mode") == "adult"


def _compact(value: str, limit: int) -> str:
    compact = " ".join(value.strip().split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."
