from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, cast

from sqlalchemy import delete, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Character,
    ContinuityThread,
    Conversation,
    Message,
    RelationshipState,
    utc_now,
)
from app.services.conversation_privacy import conversation_is_private, message_is_private
from app.services.safety import is_blocked_content

ThreadKind = Literal["follow_up", "plan", "promise", "repair", "ritual"]
ThreadStatus = Literal["open", "resolved"]

THREAD_KINDS = {"follow_up", "plan", "promise", "repair", "ritual"}
THREAD_STATUSES = {"open", "resolved"}
AUTO_SOURCE = "explicit_user_language"
MANUAL_SOURCE = "manual"
MAX_THREAD_CONTENT = 600
PROACTIVE_THREAD_COOLDOWN = timedelta(days=14)

FOLLOW_UP_MARKERS = (
    "ask me about",
    "come back to",
    "circle back",
    "don't let me forget",
    "do not let me forget",
    "follow up",
    "let's revisit",
    "lets revisit",
    "pick this up",
    "remind me",
    "return to this",
    "talk about this later",
    "talk more later",
)
PROMISE_MARKERS = (
    "i promise",
    "we promise",
    "we promised",
    "you promised",
)
RITUAL_MARKERS = (
    "every morning",
    "every night",
    "every evening",
    "every week",
    "every weekend",
    "make this a ritual",
    "our ritual",
    "our routine",
)
FUTURE_MARKERS = (
    "after work",
    "later today",
    "next month",
    "next time",
    "next week",
    "this evening",
    "this weekend",
    "tomorrow",
)
FUTURE_ACTION_MARKERS = (
    "i am going to",
    "i plan to",
    "i'll",
    "i will",
    "i'm going to",
    "we are going to",
    "we'll",
    "we will",
)
CLOSURE_MARKERS = (
    "already did it",
    "cancel that",
    "don't remind me",
    "do not remind me",
    "forget that plan",
    "i did it",
    "i finished",
    "it is done",
    "it's done",
    "never mind about",
    "no need to follow up",
    "no need to remind me",
    "resolved now",
    "that's done",
    "we can drop that",
)
UNSAFE_RETENTION_TERMS = (
    "api key",
    "credential",
    "one-time code",
    "passcode",
    "password",
    "private key",
    "recovery code",
    "secret",
    "security code",
    "token",
)
WORD_PATTERN = re.compile(r"[a-z0-9']+")
STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "are",
    "back",
    "can",
    "come",
    "did",
    "don't",
    "for",
    "from",
    "going",
    "have",
    "into",
    "it's",
    "later",
    "let's",
    "more",
    "next",
    "not",
    "our",
    "pick",
    "remind",
    "return",
    "that",
    "the",
    "this",
    "tomorrow",
    "want",
    "will",
    "with",
    "you",
}


class ContinuityThreadError(ValueError):
    """Raised when a living thread cannot be stored safely."""


@dataclass(frozen=True)
class ThreadCandidateDecision:
    accepted: bool
    reason: str
    thread_kind: ThreadKind | None = None
    content: str | None = None
    salience: float = 0.0
    confidence: float = 0.0
    trigger: str | None = None

    def safe_metadata(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            **({"thread_kind": self.thread_kind} if self.thread_kind else {}),
            **({"trigger": self.trigger} if self.trigger else {}),
            "salience": round(self.salience, 3),
            "confidence": round(self.confidence, 3),
        }


@dataclass(frozen=True)
class ContinuitySyncResult:
    decision: ThreadCandidateDecision
    created_ids: tuple[uuid.UUID, ...] = ()
    refreshed_ids: tuple[uuid.UUID, ...] = ()
    resolved_ids: tuple[uuid.UUID, ...] = ()
    removed_source_count: int = 0

    def safe_metadata(self) -> dict[str, object]:
        return {
            "decision": self.decision.safe_metadata(),
            "created_count": len(self.created_ids),
            "refreshed_count": len(self.refreshed_ids),
            "resolved_count": len(self.resolved_ids),
            "removed_source_count": self.removed_source_count,
            "thread_ids": [
                str(thread_id)
                for thread_id in (*self.created_ids, *self.refreshed_ids, *self.resolved_ids)[:8]
            ],
        }


async def list_continuity_threads(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    status: Literal["open", "resolved", "all"] = "open",
    limit: int = 50,
) -> list[ContinuityThread]:
    statement = select(ContinuityThread).where(
        ContinuityThread.user_id == user_id,
        ContinuityThread.character_id == character_id,
    )
    if status != "all":
        statement = statement.where(ContinuityThread.status == status)
    result = await session.execute(
        statement.order_by(
            ContinuityThread.status,
            desc(ContinuityThread.salience),
            desc(ContinuityThread.updated_at),
        ).limit(max(1, min(limit, 100)))
    )
    return list(result.scalars().all())


async def create_continuity_thread(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    content: str,
    thread_kind: str = "follow_up",
    salience: float = 0.7,
    confidence: float = 1.0,
    conversation_id: uuid.UUID | None = None,
    source_message_id: uuid.UUID | None = None,
    source: str = MANUAL_SOURCE,
    metadata_json: dict[str, object] | None = None,
    merge_existing: bool = True,
) -> ContinuityThread:
    normalized_content = validate_thread_content(content)
    normalized_kind = validate_thread_kind(thread_kind)
    bounded_salience = _bounded_score(salience, default=0.7)
    bounded_confidence = _bounded_score(confidence, default=0.8)
    dedupe_key = thread_dedupe_key(normalized_content)
    if merge_existing:
        existing = await _matching_open_thread(
            session,
            user_id=user_id,
            character_id=character_id,
            content=normalized_content,
            dedupe_key=dedupe_key,
        )
        if existing is not None:
            metadata = existing.metadata_json if isinstance(existing.metadata_json, dict) else {}
            source_message_ids = _metadata_uuid_strings(metadata.get("source_message_ids"))
            if source_message_id is not None and str(source_message_id) not in source_message_ids:
                source_message_ids.append(str(source_message_id))
            existing.salience = max(existing.salience, bounded_salience)
            existing.confidence = max(existing.confidence, bounded_confidence)
            existing.last_referenced_at = utc_now()
            existing.updated_at = utc_now()
            existing.metadata_json = {
                **metadata,
                "source_message_ids": source_message_ids[-12:],
                "reference_count": _non_negative_int(metadata.get("reference_count")) + 1,
                "last_evidence_source": source,
            }
            await session.flush()
            return existing

    thread = ContinuityThread(
        user_id=user_id,
        character_id=character_id,
        conversation_id=conversation_id,
        source_message_id=source_message_id,
        thread_kind=normalized_kind,
        content=normalized_content,
        status="open",
        salience=bounded_salience,
        confidence=bounded_confidence,
        dedupe_key=dedupe_key,
        metadata_json={
            "source": source,
            "source_message_ids": [str(source_message_id)] if source_message_id else [],
            "reference_count": 0,
            "proactive_count": 0,
            **(metadata_json or {}),
        },
    )
    session.add(thread)
    await session.flush()
    return thread


async def update_continuity_thread(
    session: AsyncSession,
    thread: ContinuityThread,
    *,
    content: str | None = None,
    thread_kind: str | None = None,
    status: str | None = None,
    salience: float | None = None,
    resolution_source: str = "user_control",
) -> ContinuityThread:
    if content is not None:
        thread.content = validate_thread_content(content)
        thread.dedupe_key = thread_dedupe_key(thread.content)
    if thread_kind is not None:
        thread.thread_kind = validate_thread_kind(thread_kind)
    if salience is not None:
        thread.salience = _bounded_score(salience, default=thread.salience)
    if status is not None:
        normalized_status = validate_thread_status(status)
        if normalized_status != thread.status:
            now = utc_now()
            thread.status = normalized_status
            thread.resolved_at = now if normalized_status == "resolved" else None
            metadata = thread.metadata_json if isinstance(thread.metadata_json, dict) else {}
            thread.metadata_json = {
                **metadata,
                "last_status_source": resolution_source,
                "last_status_changed_at": now.isoformat(),
            }
    thread.updated_at = utc_now()
    await session.flush()
    return thread


async def delete_continuity_thread(
    session: AsyncSession,
    thread: ContinuityThread,
) -> None:
    await session.delete(thread)
    await session.flush()


async def sync_continuity_from_message(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character: Character,
    conversation: Conversation,
    message: Message,
) -> ContinuitySyncResult:
    removed_count = await remove_message_source_threads(
        session,
        user_id=user_id,
        character_id=character.id,
        message_id=message.id,
    )
    if (
        message.role != "user"
        or conversation_is_private(conversation)
        or message_is_private(message)
        or _message_is_adult(message)
        or not automatic_continuity_enabled(character)
    ):
        reason = "adult_turn" if _message_is_adult(message) else "private_or_disabled"
        return ContinuitySyncResult(
            decision=ThreadCandidateDecision(accepted=False, reason=reason),
            removed_source_count=removed_count,
        )

    relationship = await _relationship_state(session, user_id, character.id)
    open_threads = await list_continuity_threads(
        session,
        user_id=user_id,
        character_id=character.id,
        status="open",
        limit=100,
    )
    closure_matches = _closure_matches(message.content, open_threads, conversation.id)
    resolved_ids: list[uuid.UUID] = []
    if closure_matches:
        now = utc_now()
        for thread in closure_matches:
            await update_continuity_thread(
                session,
                thread,
                status="resolved",
                resolution_source="explicit_user_closure",
            )
            thread.last_referenced_at = now
            resolved_ids.append(thread.id)
        return ContinuitySyncResult(
            decision=ThreadCandidateDecision(accepted=False, reason="explicit_closure"),
            resolved_ids=tuple(resolved_ids),
            removed_source_count=removed_count,
        )

    decision = analyze_thread_candidate(
        message.content,
        repair_needed=bool(relationship and relationship.repair_needed),
    )
    created_ids: list[uuid.UUID] = []
    refreshed_ids: list[uuid.UUID] = []
    if decision.accepted and decision.content and decision.thread_kind:
        known_ids = {thread.id for thread in open_threads}
        thread = await create_continuity_thread(
            session,
            user_id=user_id,
            character_id=character.id,
            conversation_id=conversation.id,
            source_message_id=message.id,
            content=decision.content,
            thread_kind=decision.thread_kind,
            salience=decision.salience,
            confidence=decision.confidence,
            source=AUTO_SOURCE,
            metadata_json={
                "extraction": decision.safe_metadata(),
                "content_mode": "sfw",
            },
        )
        if thread.id in known_ids:
            refreshed_ids.append(thread.id)
        else:
            created_ids.append(thread.id)
    else:
        referenced = _referenced_threads(message.content, open_threads)
        now = utc_now()
        for thread in referenced:
            metadata = thread.metadata_json if isinstance(thread.metadata_json, dict) else {}
            thread.last_referenced_at = now
            thread.updated_at = now
            thread.metadata_json = {
                **metadata,
                "reference_count": _non_negative_int(metadata.get("reference_count")) + 1,
            }
            refreshed_ids.append(thread.id)
    await session.flush()
    return ContinuitySyncResult(
        decision=decision,
        created_ids=tuple(created_ids),
        refreshed_ids=tuple(refreshed_ids),
        removed_source_count=removed_count,
    )


def analyze_thread_candidate(
    content: str,
    *,
    repair_needed: bool = False,
) -> ThreadCandidateDecision:
    compact = _compact(content, MAX_THREAD_CONTENT)
    normalized = compact.casefold()
    if len(compact) < 12:
        return ThreadCandidateDecision(accepted=False, reason="too_short")
    if any(term in normalized for term in UNSAFE_RETENTION_TERMS):
        return ThreadCandidateDecision(accepted=False, reason="sensitive_content")
    if is_blocked_content(compact):
        return ThreadCandidateDecision(accepted=False, reason="blocked_content")
    if any(marker in normalized for marker in CLOSURE_MARKERS):
        return ThreadCandidateDecision(accepted=False, reason="explicit_closure")

    trigger = _first_marker(normalized, FOLLOW_UP_MARKERS)
    if trigger:
        kind: ThreadKind = "repair" if repair_needed else "follow_up"
        return ThreadCandidateDecision(
            accepted=True,
            reason="explicit_follow_up",
            thread_kind=kind,
            content=compact,
            salience=0.82 if repair_needed else 0.76,
            confidence=0.94,
            trigger=trigger,
        )

    trigger = _first_marker(normalized, PROMISE_MARKERS)
    if trigger:
        return ThreadCandidateDecision(
            accepted=True,
            reason="explicit_promise",
            thread_kind="promise",
            content=compact,
            salience=0.82,
            confidence=0.95,
            trigger=trigger,
        )

    trigger = _first_marker(normalized, RITUAL_MARKERS)
    if trigger:
        return ThreadCandidateDecision(
            accepted=True,
            reason="explicit_ritual",
            thread_kind="ritual",
            content=compact,
            salience=0.72,
            confidence=0.9,
            trigger=trigger,
        )

    future_marker = _first_marker(normalized, FUTURE_MARKERS)
    action_marker = _first_marker(normalized, FUTURE_ACTION_MARKERS)
    if future_marker and (action_marker or _has_first_person_reference(normalized)):
        return ThreadCandidateDecision(
            accepted=True,
            reason="grounded_future_plan",
            thread_kind="plan",
            content=compact,
            salience=0.66,
            confidence=0.82,
            trigger=future_marker,
        )

    return ThreadCandidateDecision(accepted=False, reason="no_explicit_thread")


async def retrieve_continuity_threads(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    query: str,
    conversation_id: uuid.UUID | None = None,
    limit: int = 4,
    mark_referenced: bool = True,
) -> list[ContinuityThread]:
    candidates = await list_continuity_threads(
        session,
        user_id=user_id,
        character_id=character_id,
        status="open",
        limit=100,
    )
    now = utc_now()
    query_terms = _thread_terms(query)
    relevant = [thread for thread in candidates if query_terms & _thread_terms(thread.content)]
    selected = sorted(
        relevant,
        key=lambda thread: _retrieval_score(
            thread,
            query_terms=query_terms,
            conversation_id=conversation_id,
            now=now,
        ),
        reverse=True,
    )[: max(0, min(limit, 8))]
    if mark_referenced:
        for thread in selected:
            metadata = thread.metadata_json if isinstance(thread.metadata_json, dict) else {}
            thread.last_referenced_at = now
            thread.metadata_json = {
                **metadata,
                "prompt_reference_count": _non_negative_int(metadata.get("prompt_reference_count"))
                + 1,
            }
        await session.flush()
    return selected


def continuity_prompt_items(threads: list[ContinuityThread]) -> list[str]:
    return [
        (
            f"{thread.thread_kind.replace('_', ' ')} explicitly left open by the user: "
            f'"{_compact(thread.content, 420)}". Use only when relevant; do not imply it '
            "was completed or promise an offline action."
        )
        for thread in threads
        if thread.status == "open"
    ]


async def select_proactive_thread(
    session: AsyncSession,
    *,
    conversation: Conversation,
    requested_thread_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> ContinuityThread | None:
    current_time = now or utc_now()
    conditions = [
        ContinuityThread.user_id == conversation.user_id,
        ContinuityThread.character_id == conversation.character_id,
        ContinuityThread.conversation_id == conversation.id,
        ContinuityThread.status == "open",
        or_(
            ContinuityThread.last_proactive_at.is_(None),
            ContinuityThread.last_proactive_at <= current_time - PROACTIVE_THREAD_COOLDOWN,
        ),
    ]
    if requested_thread_id is not None:
        conditions.append(ContinuityThread.id == requested_thread_id)
    result = await session.execute(
        select(ContinuityThread)
        .where(*conditions)
        .order_by(desc(ContinuityThread.salience), desc(ContinuityThread.updated_at))
        .limit(12)
    )
    for thread in result.scalars().all():
        if _safe_for_proactive(thread.content):
            return thread
    return None


async def record_proactive_thread_delivery(
    session: AsyncSession,
    thread: ContinuityThread,
    *,
    delivered_at: datetime | None = None,
) -> None:
    now = delivered_at or utc_now()
    metadata = thread.metadata_json if isinstance(thread.metadata_json, dict) else {}
    thread.last_proactive_at = now
    thread.last_referenced_at = now
    thread.updated_at = now
    thread.metadata_json = {
        **metadata,
        "proactive_count": _non_negative_int(metadata.get("proactive_count")) + 1,
    }
    await session.flush()


async def remove_message_source_threads(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    message_id: uuid.UUID,
) -> int:
    result = await session.execute(
        delete(ContinuityThread).where(
            ContinuityThread.user_id == user_id,
            ContinuityThread.character_id == character_id,
            ContinuityThread.source_message_id == message_id,
            ContinuityThread.metadata_json["source"].as_string() == AUTO_SOURCE,
        )
    )
    return int(result.rowcount or 0)


async def delete_conversation_threads(
    session: AsyncSession,
    conversation_id: uuid.UUID,
) -> int:
    result = await session.execute(
        delete(ContinuityThread).where(ContinuityThread.conversation_id == conversation_id)
    )
    return int(result.rowcount or 0)


def automatic_continuity_enabled(character: Character) -> bool:
    profile = character.boundaries_json if isinstance(character.boundaries_json, dict) else {}
    preferences = profile.get("memory_preferences")
    if not isinstance(preferences, dict):
        return True
    return (
        preferences.get("private_mode_default") is not True
        and preferences.get("remember_emotional_notes") is not False
    )


def validate_thread_content(content: str) -> str:
    compact = _compact(content, MAX_THREAD_CONTENT + 1)
    if not compact:
        raise ContinuityThreadError("A living thread needs visible text.")
    if len(compact) > MAX_THREAD_CONTENT:
        raise ContinuityThreadError(
            f"Keep living threads to {MAX_THREAD_CONTENT} characters or fewer."
        )
    normalized = compact.casefold()
    if any(term in normalized for term in UNSAFE_RETENTION_TERMS):
        raise ContinuityThreadError("Sensitive credentials cannot be kept as a living thread.")
    if is_blocked_content(compact):
        raise ContinuityThreadError("That thread crosses Eidolon's safety boundaries.")
    return compact


def validate_thread_kind(thread_kind: str) -> ThreadKind:
    normalized = str(thread_kind).strip().lower()
    if normalized not in THREAD_KINDS:
        raise ContinuityThreadError("Living thread kind is not supported.")
    return cast(ThreadKind, normalized)


def validate_thread_status(status: str) -> ThreadStatus:
    normalized = str(status).strip().lower()
    if normalized not in THREAD_STATUSES:
        raise ContinuityThreadError("Living thread status is not supported.")
    return cast(ThreadStatus, normalized)


def thread_dedupe_key(content: str) -> str:
    terms = sorted(_thread_terms(content))
    basis = " ".join(terms) or _compact(content, MAX_THREAD_CONTENT).casefold()
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


async def _matching_open_thread(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    content: str,
    dedupe_key: str,
) -> ContinuityThread | None:
    result = await session.execute(
        select(ContinuityThread).where(
            ContinuityThread.user_id == user_id,
            ContinuityThread.character_id == character_id,
            ContinuityThread.status == "open",
        )
    )
    content_terms = _thread_terms(content)
    best: ContinuityThread | None = None
    best_similarity = 0.0
    for thread in result.scalars().all():
        if thread.dedupe_key == dedupe_key:
            return thread
        similarity = _jaccard(content_terms, _thread_terms(thread.content))
        if similarity >= 0.72 and similarity > best_similarity:
            best = thread
            best_similarity = similarity
    return best


async def _relationship_state(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
) -> RelationshipState | None:
    result = await session.execute(
        select(RelationshipState).where(
            RelationshipState.user_id == user_id,
            RelationshipState.character_id == character_id,
        )
    )
    return result.scalar_one_or_none()


def _closure_matches(
    content: str,
    open_threads: list[ContinuityThread],
    conversation_id: uuid.UUID,
) -> list[ContinuityThread]:
    normalized = _compact(content, MAX_THREAD_CONTENT).casefold()
    if not any(marker in normalized for marker in CLOSURE_MARKERS):
        return []
    content_terms = _thread_terms(content)
    ranked = [
        (thread, _jaccard(content_terms, _thread_terms(thread.content))) for thread in open_threads
    ]
    explicit = [thread for thread, overlap in ranked if overlap >= 0.18]
    if explicit:
        return explicit[:2]
    local_threads = [thread for thread in open_threads if thread.conversation_id == conversation_id]
    if len(local_threads) == 1:
        return local_threads
    return []


def _referenced_threads(
    content: str,
    open_threads: list[ContinuityThread],
) -> list[ContinuityThread]:
    content_terms = _thread_terms(content)
    if not content_terms:
        return []
    ranked = sorted(
        (
            (thread, _jaccard(content_terms, _thread_terms(thread.content)))
            for thread in open_threads
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    return [thread for thread, overlap in ranked if overlap >= 0.28][:2]


def _retrieval_score(
    thread: ContinuityThread,
    *,
    query_terms: set[str],
    conversation_id: uuid.UUID | None,
    now: datetime,
) -> float:
    overlap = _jaccard(query_terms, _thread_terms(thread.content)) if query_terms else 0.0
    age_days = max((now - thread.updated_at).total_seconds() / 86_400, 0)
    recency = 1 / (1 + age_days / 21)
    local = 0.18 if conversation_id is not None and thread.conversation_id == conversation_id else 0
    kind_weight = 0.08 if thread.thread_kind in {"promise", "repair"} else 0
    return (
        (overlap * 0.48)
        + (thread.salience * 0.2)
        + (thread.confidence * 0.08)
        + (recency * 0.06)
        + local
        + kind_weight
    )


def _safe_for_proactive(content: str) -> bool:
    normalized = content.casefold()
    has_sensitive_term = any(term in normalized for term in UNSAFE_RETENTION_TERMS)
    return not has_sensitive_term and not is_blocked_content(content)


def _message_is_adult(message: Message) -> bool:
    metadata = message.metadata_json if isinstance(message.metadata_json, dict) else {}
    return metadata.get("content_mode") == "adult"


def _first_marker(value: str, markers: tuple[str, ...]) -> str | None:
    return next((marker for marker in markers if marker in value), None)


def _has_first_person_reference(value: str) -> bool:
    words = set(WORD_PATTERN.findall(value))
    return bool(words & {"i", "i'm", "i'll", "me", "my", "we", "we'll"})


def _thread_terms(value: str) -> set[str]:
    return {
        term
        for term in WORD_PATTERN.findall(value.casefold())
        if len(term) > 2 and term not in STOP_WORDS
    }


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _compact(value: str, limit: int) -> str:
    compact = " ".join(str(value).strip().split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _bounded_score(value: object, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed != parsed:
        return default
    return min(max(parsed, 0.0), 1.0)


def _non_negative_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _metadata_uuid_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    selected: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        try:
            normalized = str(uuid.UUID(item))
        except ValueError:
            continue
        if normalized not in selected:
            selected.append(normalized)
    return selected
