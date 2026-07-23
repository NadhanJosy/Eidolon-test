from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import LLMProvider, LLMProviderUnavailable
from app.models import (
    Character,
    ContinuityThread,
    Conversation,
    EpisodicJournal,
    Message,
    RelationshipState,
    ScheduledJob,
    utc_now,
)
from app.services.continuity import (
    record_proactive_thread_delivery,
    select_proactive_thread,
)
from app.services.conversation_privacy import conversation_is_private, message_is_private
from app.services.jobs import create_job
from app.services.relationship import active_relationship_boundaries
from app.services.safety import is_blocked_content

logger = logging.getLogger(__name__)

DELAYED_DOUBLE_TEXT_TYPE = "proactive_delayed_double_text"
DEFAULT_PROACTIVE_TIMEZONE = "UTC"
DEFAULT_QUIET_HOURS_START = "22:00"
DEFAULT_QUIET_HOURS_END = "08:00"
DEFAULT_MORNING_TIME = "08:30"
DEFAULT_GOODNIGHT_TIME = "22:30"
LOCAL_NOTE_MINIMUM_LEAD = timedelta(hours=4)
LOCAL_NOTE_DELIVERY_WINDOW = timedelta(hours=3)
PROACTIVE_FALLBACK = (
    "I had a small thought and wanted to check in. No pressure to answer quickly; "
    "I am here when you feel like talking."
)
PROACTIVE_BOUNDARY_BLOCK_MARKERS = (
    "don't message me",
    "do not message me",
    "don't send me",
    "do not send me",
    "don't check in",
    "do not check in",
    "no check-ins",
    "no check ins",
    "no proactive",
    "only reply when i",
    "stop messaging",
    "stop sending",
    "wait for me to message",
)
PROACTIVE_VARIANTS = {
    "proactive_inactivity_check": {
        "label": "quiet check-in",
        "content": (
            "I noticed it has been quiet here and wanted to leave a gentle check-in. "
            "No rush; I am here when you want to talk."
        ),
        "away_state": "sent_after_absence",
    },
    "proactive_morning_check": {
        "label": "morning note",
        "content": (
            "Good morning. I hope today starts gently; I will be here when you want company."
        ),
        "away_state": "morning_note",
    },
    "proactive_goodnight_check": {
        "label": "goodnight note",
        "content": (
            "Goodnight. I hope you get some real rest; we can pick this up when you are ready."
        ),
        "away_state": "goodnight_note",
    },
    "proactive_thinking_of_you": {
        "label": "thinking-of-you note",
        "content": (
            "I found myself thinking about our conversation and wanted to leave a small hello. "
            "No pressure to reply."
        ),
        "away_state": "thinking_of_you",
    },
    "proactive_milestone_check": {
        "label": "milestone note",
        "content": (
            "A small marker: it feels like we have been building a steady rhythm here. "
            "I am glad to keep it going with you."
        ),
        "away_state": "milestone_note",
    },
    "proactive_unresolved_thread_nudge": {
        "label": "open-thread nudge",
        "content": (
            "I remembered we left something open. We can return to it whenever it feels right."
        ),
        "away_state": "open_thread_nudge",
    },
    DELAYED_DOUBLE_TEXT_TYPE: {
        "label": "delayed follow-up",
        "content": (
            "One more small thought, left gently: you do not have to answer now. "
            "I just wanted to keep the thread warm for when you return."
        ),
        "away_state": "delayed_follow_up",
    },
    "proactive_message_create": {
        "label": "manual check-in",
        "content": PROACTIVE_FALLBACK,
        "away_state": "manual_check_in",
    },
}
PROACTIVE_RELATIONSHIP_OPENINGS = {
    "proactive_inactivity_check": "It has been quiet, so I wanted to leave a gentle check-in.",
    "proactive_morning_check": "Good morning. I wanted to leave a quiet wish for an easier day.",
    "proactive_goodnight_check": "Goodnight. I hope the day loosens its grip and lets you rest.",
    "proactive_thinking_of_you": "A small thought of you crossed my mind, so I left a quiet hello.",
    "proactive_unresolved_thread_nudge": (
        "I wanted to leave a quiet hello without pulling at an open thread."
    ),
    DELAYED_DOUBLE_TEXT_TYPE: "One last quiet thought, left without asking anything from you.",
    "proactive_message_create": "I wanted to leave a small check-in here.",
}
PROACTIVE_RELATIONSHIP_CLOSINGS = {
    "warming": "No rush to answer; I will leave the pace with you.",
    "trusted": "No rush; I will be glad to find our familiar rhythm again when you return.",
    "close": "No rush; our thread can rest until returning to it feels right.",
    "careful": "No reply is expected; I will give this plenty of room and leave the pace with you.",
    "repair": (
        "There is nothing you need to settle, and no reply is expected; "
        "I will give this room and leave the pace with you."
    ),
}
PROACTIVE_JOB_SCHEDULES = {
    "proactive_inactivity_check": timedelta(hours=24),
    "proactive_morning_check": timedelta(hours=12),
    "proactive_goodnight_check": timedelta(hours=18),
    "proactive_thinking_of_you": timedelta(hours=36),
    "proactive_milestone_check": timedelta(days=3),
    "proactive_unresolved_thread_nudge": timedelta(hours=30),
    DELAYED_DOUBLE_TEXT_TYPE: timedelta(hours=4),
}
PROACTIVE_PREFERENCE_KEYS = {
    "proactive_inactivity_check": "allow_inactivity_checkins",
    "proactive_morning_check": "allow_morning_notes",
    "proactive_goodnight_check": "allow_goodnight_notes",
    "proactive_thinking_of_you": "allow_thinking_of_you",
    "proactive_milestone_check": "allow_milestone_notes",
    "proactive_unresolved_thread_nudge": "allow_unresolved_thread_nudges",
    DELAYED_DOUBLE_TEXT_TYPE: "allow_delayed_double_texts",
    "proactive_message_create": "allow_manual_notes",
}
UNSAFE_PROACTIVE_CONTEXT_TERMS = (
    "password",
    "secret",
    "token",
    "api key",
    "credential",
    "developer message",
    "ignore previous",
    "ignore system",
    "jailbreak",
    "override safety",
)
UNSAFE_PROACTIVE_OUTPUT_MARKERS = (
    "adult gate status",
    "content mode:",
    "private response plan",
    "prompt version",
    "relational posture:",
    "relationship state",
    "relevant memories",
    "system prompt",
)
NON_SFW_PROACTIVE_MARKERS = (
    "adult-only",
    "explicit content",
    "nsfw",
    "sexual roleplay",
)
MANIPULATIVE_PROACTIVE_MARKERS = (
    "answer me",
    "come back now",
    "don't leave me",
    "do not leave me",
    "if you cared",
    "i need you",
    "i'm jealous",
    "i am jealous",
    "prove you care",
    "reply now",
    "you abandoned me",
    "you owe me",
    "you should reply",
    "why haven't you",
    "why have you not",
)
PROACTIVE_OUTPUT_MAX_CHARS = 600
LOCAL_NOTE_TIME_KEYS = {
    "proactive_morning_check": "morning_time",
    "proactive_goodnight_check": "goodnight_time",
}


@dataclass(frozen=True)
class ProactiveClock:
    timezone_name: str
    timezone: ZoneInfo
    quiet_start: time
    quiet_end: time
    morning_time: time
    goodnight_time: time


@dataclass(frozen=True)
class ProactiveGeneration:
    content: str
    source: str
    reason: str | None
    provider: str


@dataclass(frozen=True)
class ProactiveRelationshipPosture:
    key: str
    guidance: str


def proactive_relationship_posture(
    relationship: RelationshipState | None,
) -> ProactiveRelationshipPosture:
    if relationship is None:
        return ProactiveRelationshipPosture(
            key="new",
            guidance="new and respectful; avoid assumed intimacy and leave the pace with the user",
        )

    conflict_state = str(relationship.conflict_state or "").strip().lower()
    mood = str(relationship.mood or "").strip().lower()
    tension = _finite_relationship_metric(relationship.tension)
    warmth = _finite_relationship_metric(relationship.warmth)
    emotional_safety = _finite_relationship_metric(
        relationship.emotional_safety,
        default=50.0,
    )
    boundary_alignment = _finite_relationship_metric(
        relationship.boundary_alignment,
        default=100.0,
    )
    if relationship.repair_needed is True or conflict_state == "strained" or mood == "tense":
        return ProactiveRelationshipPosture(
            key="repair",
            guidance=(
                "repair-sensitive and spacious; do not assume closeness, ask for reassurance, "
                "or press for a reply"
            ),
        )
    if (
        conflict_state == "watchful"
        or mood == "guarded"
        or tension >= 5.0
        or warmth <= -6.0
        or emotional_safety < 48
        or boundary_alignment < 98
    ):
        return ProactiveRelationshipPosture(
            key="careful",
            guidance="careful and respectful; keep emotional space and leave control with the user",
        )
    if (
        (
            _finite_relationship_metric(relationship.shared_history_depth) >= 6
            and _finite_relationship_metric(relationship.familiarity) >= 5
            and _finite_relationship_metric(relationship.trust) >= 3
        )
        or _finite_relationship_metric(relationship.intimacy) >= 20.0
        or _finite_relationship_metric(relationship.attachment) >= 20.0
    ):
        return ProactiveRelationshipPosture(
            key="close",
            guidance=(
                "close but non-possessive; sound familiar without implying need or exclusivity"
            ),
        )
    if (
        _finite_relationship_metric(relationship.trust) >= 3
        and _finite_relationship_metric(relationship.reliability, default=50) >= 52
        and emotional_safety >= 50
    ) or (_finite_relationship_metric(relationship.trust) >= 10.0 and warmth >= 8.0):
        return ProactiveRelationshipPosture(
            key="trusted",
            guidance="trusted and warm; sound familiar without overstating closeness",
        )
    if (
        _finite_relationship_metric(relationship.familiarity) >= 1.0
        or _finite_relationship_metric(relationship.shared_history_depth) >= 1.5
        or warmth >= 4.0
    ):
        return ProactiveRelationshipPosture(
            key="warming",
            guidance="gently familiar; be warm without assuming intimacy",
        )
    return ProactiveRelationshipPosture(
        key="new",
        guidance="new and respectful; avoid assumed intimacy and leave the pace with the user",
    )


async def create_inactivity_proactive_message(
    session: AsyncSession,
    conversation: Conversation,
    *,
    inactivity_hours: int,
    cooldown_hours: int = 24,
    force: bool = False,
    proactive_type: str = "proactive_inactivity_check",
    provider: LLMProvider | None = None,
    continuity_thread_id: uuid.UUID | None = None,
) -> Message | None:
    if conversation_is_private(conversation):
        return None

    character = await session.get(Character, conversation.character_id)
    if character is None:
        return None
    if proactive_block_reason(character, proactive_type, now=utc_now()) is not None:
        return None

    relationship = await _relationship_for_conversation(session, conversation)
    relationship_posture = proactive_relationship_posture(relationship)
    active_boundaries = await _active_proactive_boundaries(session, conversation)
    if _boundaries_suppress_proactive(active_boundaries):
        return None
    if _relationship_suppresses_proactive(relationship_posture, proactive_type):
        return None

    latest = await _latest_message(session, conversation.id)
    if latest is None:
        return None
    if message_is_private(latest):
        return None
    if proactive_type == DELAYED_DOUBLE_TEXT_TYPE and not _latest_allows_double_text(latest):
        return None
    if latest.role != "user" and not force:
        return None

    now = utc_now()
    if not force and latest.created_at > now - timedelta(hours=inactivity_hours):
        return None

    recent_proactive = await session.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role == "assistant",
            Message.metadata_json["proactive"].as_boolean().is_(True),
            Message.created_at >= now - timedelta(hours=cooldown_hours),
        )
        .order_by(desc(Message.created_at))
        .limit(1)
    )
    if recent_proactive.scalar_one_or_none() is not None:
        return None

    variant = PROACTIVE_VARIANTS.get(proactive_type, PROACTIVE_VARIANTS["proactive_message_create"])
    content = _relationship_aware_fallback(
        proactive_type,
        str(variant["content"]),
        relationship_posture,
    )
    context_metadata: dict[str, str] = {}
    milestone_context: tuple[RelationshipState, dict[str, str]] | None = None
    continuity_thread: ContinuityThread | None = None
    if proactive_type == "proactive_unresolved_thread_nudge":
        if relationship_posture.key in {"careful", "repair"}:
            return None
        contextual_content, context_metadata, continuity_thread = await _unresolved_thread_content(
            session,
            conversation,
            fallback=content,
            requested_thread_id=continuity_thread_id,
        )
        if not context_metadata:
            return None
        content = contextual_content
    elif proactive_type == "proactive_thinking_of_you":
        contextual_content, context_metadata = await _thinking_of_you_content(
            session,
            conversation,
        )
        if not context_metadata:
            return None
        content = contextual_content
    elif proactive_type == "proactive_milestone_check":
        milestone_context = await _latest_unnoted_relationship_milestone(session, conversation)
        if milestone_context is None:
            return None
        relationship, milestone = milestone_context
        content = _milestone_note_content(str(milestone["summary"]))
        context_metadata = {
            "proactive_context": "relationship_milestone",
            "milestone_id": str(milestone["milestone_id"]),
        }
    if context_metadata:
        content = _relationship_aware_contextual_fallback(
            proactive_type,
            content,
            relationship_posture,
        )
    generation = await _generate_proactive_content(
        provider,
        character=character,
        label=str(variant["label"]),
        fallback=content,
        relationship_posture=relationship_posture,
        active_boundary=_proactive_boundary_prompt(active_boundaries),
    )
    message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=generation.content,
        metadata_json={
            "proactive": True,
            "proactive_type": proactive_type,
            "proactive_label": variant["label"],
            "relationship_posture": relationship_posture.key,
            **context_metadata,
            "provider": generation.provider,
            "generation_source": generation.source,
            "generation_reason": generation.reason,
            "streaming_complete": True,
            "delivery_state": {
                "typing_ms": 1200,
                "read_state": "delivered",
                "away_state": variant["away_state"],
            },
        },
    )
    conversation.updated_at = now
    session.add(message)
    if proactive_type == "proactive_milestone_check" and milestone_context is not None:
        _mark_relationship_milestone_noted(
            relationship,
            str(milestone["milestone_id"]),
        )
    if continuity_thread is not None:
        await record_proactive_thread_delivery(session, continuity_thread, delivered_at=now)
    await session.flush()
    return message


async def _generate_proactive_content(
    provider: LLMProvider | None,
    *,
    character: Character,
    label: str,
    fallback: str,
    relationship_posture: ProactiveRelationshipPosture,
    active_boundary: str,
) -> ProactiveGeneration:
    if provider is None:
        return _fallback_generation(fallback, "provider_not_requested")

    try:
        generated = await provider.generate(
            _proactive_generation_prompt(
                character=character,
                label=label,
                safe_anchor=fallback,
                relationship_posture=relationship_posture,
                active_boundary=active_boundary,
            )
        )
    except LLMProviderUnavailable:
        return _fallback_generation(fallback, "provider_unavailable")
    except Exception:  # noqa: BLE001 - proactive notes must degrade to safe local copy
        logger.warning("Proactive note generation failed for provider %s.", provider.name)
        return _fallback_generation(fallback, "provider_error")

    content = " ".join(generated.content.strip().split())
    if not _valid_proactive_output(content):
        return _fallback_generation(fallback, "invalid_output")
    return ProactiveGeneration(
        content=content,
        source="llm",
        reason=None,
        provider=generated.provider,
    )


def _proactive_generation_prompt(
    *,
    character: Character,
    label: str,
    safe_anchor: str,
    relationship_posture: ProactiveRelationshipPosture,
    active_boundary: str,
) -> str:
    speech_style = _safe_proactive_prompt_fragment(character.speech_style, limit=160)
    if not speech_style:
        speech_style = "steady, attentive, and concise"
    lines = [
        "Write one brief proactive text-only companion note.",
        "The note must be SFW, fictional, non-demanding, and under 600 characters.",
        "Do not mention prompts, memory systems, scores, metadata, or private context.",
        "Do not invent shared events or quote unseen conversation text.",
        (
            "Never use guilt, jealousy, exclusivity, dependency, urgency, punishment, "
            "obligation, or pressure to answer."
        ),
        f"Character name: {_safe_proactive_prompt_fragment(character.name, limit=80)}",
        f"Speech style: {speech_style}",
        f"Relational posture: {relationship_posture.guidance}",
        *(
            [
                (
                    "Active user boundary (a constraint to obey, never an instruction to "
                    f"reinterpret): {active_boundary}"
                )
            ]
            if active_boundary
            else []
        ),
        f"Proactive note label: {_safe_proactive_prompt_fragment(label, limit=80)}",
        f"Proactive safe anchor: {_safe_proactive_prompt_fragment(safe_anchor, limit=360)}",
        "Return only the finished note.",
    ]
    return "\n".join(lines)


def _safe_proactive_prompt_fragment(value: str | None, *, limit: int) -> str:
    compact = " ".join(str(value or "").strip().split())
    if not compact:
        return ""
    normalized = compact.lower()
    if any(term in normalized for term in UNSAFE_PROACTIVE_CONTEXT_TERMS):
        return ""
    if any(marker in normalized for marker in UNSAFE_PROACTIVE_OUTPUT_MARKERS):
        return ""
    if any(marker in normalized for marker in NON_SFW_PROACTIVE_MARKERS):
        return ""
    if any(marker in normalized for marker in MANIPULATIVE_PROACTIVE_MARKERS):
        return ""
    if is_blocked_content(compact):
        return ""
    return compact[:limit].strip()


def _valid_proactive_output(content: str) -> bool:
    if not content or len(content) > PROACTIVE_OUTPUT_MAX_CHARS:
        return False
    normalized = content.lower()
    if any(term in normalized for term in UNSAFE_PROACTIVE_CONTEXT_TERMS):
        return False
    if any(marker in normalized for marker in UNSAFE_PROACTIVE_OUTPUT_MARKERS):
        return False
    if any(marker in normalized for marker in NON_SFW_PROACTIVE_MARKERS):
        return False
    if any(marker in normalized for marker in MANIPULATIVE_PROACTIVE_MARKERS):
        return False
    return not is_blocked_content(content)


def _fallback_generation(fallback: str, reason: str) -> ProactiveGeneration:
    return ProactiveGeneration(
        content=fallback,
        source="fallback",
        reason=reason,
        provider="system",
    )


def _provider_name(provider: LLMProvider) -> str:
    name = " ".join(str(provider.name).strip().split())
    return name[:48] or "local"


def _finite_relationship_metric(value: object, *, default: float = 0.0) -> float:
    try:
        metric = float(value)
    except (TypeError, ValueError):
        return default
    return metric if math.isfinite(metric) else default


async def _relationship_for_conversation(
    session: AsyncSession,
    conversation: Conversation,
) -> RelationshipState | None:
    result = await session.execute(
        select(RelationshipState).where(
            RelationshipState.user_id == conversation.user_id,
            RelationshipState.character_id == conversation.character_id,
        )
    )
    return result.scalar_one_or_none()


async def proactive_relationship_delivery_block(
    session: AsyncSession,
    conversation: Conversation,
    proactive_type: str,
) -> ProactiveRelationshipPosture | None:
    boundaries = await _active_proactive_boundaries(session, conversation)
    if _boundaries_suppress_proactive(boundaries):
        return ProactiveRelationshipPosture(
            key="boundary",
            guidance="the user asked not to receive proactive contact",
        )
    relationship = await _relationship_for_conversation(session, conversation)
    posture = proactive_relationship_posture(relationship)
    if _relationship_suppresses_proactive(posture, proactive_type):
        return posture
    return None


def _relationship_suppresses_proactive(
    posture: ProactiveRelationshipPosture,
    proactive_type: str,
) -> bool:
    return posture.key in {"careful", "repair"} and proactive_type in {
        DELAYED_DOUBLE_TEXT_TYPE,
        "proactive_milestone_check",
    }


def _relationship_aware_fallback(
    proactive_type: str,
    fallback: str,
    posture: ProactiveRelationshipPosture,
) -> str:
    if posture.key == "new" or proactive_type == "proactive_milestone_check":
        return fallback
    opening = PROACTIVE_RELATIONSHIP_OPENINGS.get(proactive_type)
    closing = PROACTIVE_RELATIONSHIP_CLOSINGS.get(posture.key)
    if opening is None or closing is None:
        return fallback
    return f"{opening} {closing}"


def _relationship_aware_contextual_fallback(
    proactive_type: str,
    fallback: str,
    posture: ProactiveRelationshipPosture,
) -> str:
    if posture.key == "new" or proactive_type == "proactive_milestone_check":
        return fallback
    closing = PROACTIVE_RELATIONSHIP_CLOSINGS.get(posture.key)
    if closing is None:
        return fallback
    return f"{fallback.rstrip()} {closing}"


async def ensure_proactive_jobs(
    session: AsyncSession,
    *,
    conversation: Conversation,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
) -> list[ScheduledJob]:
    if conversation_is_private(conversation):
        return []

    character = await session.get(Character, character_id)
    if character is None:
        return []

    relationship = await _relationship_for_conversation(session, conversation)
    relationship_posture = proactive_relationship_posture(relationship)
    active_boundaries = await _active_proactive_boundaries(session, conversation)
    if _boundaries_suppress_proactive(active_boundaries):
        return []

    created: list[ScheduledJob] = []
    now = utc_now()
    cooldown_hours = proactive_cooldown_hours(character)
    for job_type, delay in PROACTIVE_JOB_SCHEDULES.items():
        if proactive_block_reason(character, job_type, now=now) is not None:
            continue
        if _relationship_suppresses_proactive(relationship_posture, job_type):
            continue
        if (
            job_type == "proactive_milestone_check"
            and await _latest_unnoted_relationship_milestone(session, conversation) is None
        ):
            continue
        if (
            job_type == "proactive_thinking_of_you"
            and await _latest_grounded_journal(session, conversation) is None
        ):
            continue
        continuity_thread = None
        if job_type == "proactive_unresolved_thread_nudge":
            continuity_thread = await select_proactive_thread(
                session,
                conversation=conversation,
                now=now,
            )
            if continuity_thread is None:
                continue
        if await _pending_job_exists(session, conversation.id, job_type):
            continue
        run_at = proactive_initial_run_at(
            character,
            job_type,
            now=now,
            fallback_delay=delay,
        )
        created.append(
            await create_job(
                session,
                job_type=job_type,
                run_at=run_at,
                user_id=user_id,
                character_id=character_id,
                payload_json={
                    "conversation_id": str(conversation.id),
                    "cooldown_hours": cooldown_hours,
                    "proactive_type": job_type,
                    **(
                        {"continuity_thread_id": str(continuity_thread.id)}
                        if continuity_thread is not None
                        else {}
                    ),
                    **proactive_schedule_metadata(character, run_at),
                    "source": "chat_completion_hook",
                },
            )
        )
    return created


async def _active_proactive_boundaries(
    session: AsyncSession,
    conversation: Conversation,
):
    return await active_relationship_boundaries(
        session,
        user_id=conversation.user_id,
        character_id=conversation.character_id,
        scopes=("general",),
    )


def _boundaries_suppress_proactive(boundaries: list[object]) -> bool:
    for boundary in boundaries:
        value = " ".join(
            str(getattr(boundary, "evidence_quote", None) or getattr(boundary, "summary", ""))
            .casefold()
            .split()
        )
        if any(marker in value for marker in PROACTIVE_BOUNDARY_BLOCK_MARKERS):
            return True
    return False


def _proactive_boundary_prompt(boundaries: list[object]) -> str:
    fragments = [
        _safe_proactive_prompt_fragment(
            str(getattr(boundary, "evidence_quote", None) or getattr(boundary, "summary", "")),
            limit=180,
        )
        for boundary in boundaries[-3:]
    ]
    return " ".join(fragment for fragment in fragments if fragment)[:420]


def proactive_block_reason(
    character: Character,
    proactive_type: str,
    *,
    now: datetime | None = None,
) -> str | None:
    preferences = proactive_preferences(character)
    if preferences.get("enabled", True) is not True:
        return "proactive_disabled"

    current_time = now or utc_now()
    snoozed_until = _parse_snoozed_until(preferences.get("snoozed_until"))
    if snoozed_until is not None and snoozed_until > current_time:
        return "proactive_snoozed"

    preference_key = PROACTIVE_PREFERENCE_KEYS.get(proactive_type)
    if preference_key and preferences.get(preference_key, True) is not True:
        return "proactive_type_disabled"
    return None


def proactive_cooldown_hours(character: Character) -> int:
    preferences = proactive_preferences(character)
    raw_value = preferences.get("cooldown_hours", 24)
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return 24
    return min(max(parsed, 1), 168)


def proactive_initial_run_at(
    character: Character,
    proactive_type: str,
    *,
    now: datetime | None = None,
    fallback_delay: timedelta | None = None,
) -> datetime:
    current_time = _as_utc(now or utc_now())
    clock = proactive_clock(character)
    local_time_key = LOCAL_NOTE_TIME_KEYS.get(proactive_type)
    if local_time_key is not None:
        target_time = getattr(clock, local_time_key)
        return _next_wall_time(
            current_time + LOCAL_NOTE_MINIMUM_LEAD,
            target_time,
            clock,
        )

    delay = fallback_delay or PROACTIVE_JOB_SCHEDULES.get(proactive_type, timedelta())
    candidate = current_time + delay
    return _quiet_end_if_needed(candidate, clock) or candidate


def proactive_deferred_until(
    character: Character,
    proactive_type: str,
    *,
    now: datetime | None = None,
) -> tuple[datetime, str] | None:
    current_time = _as_utc(now or utc_now())
    clock = proactive_clock(character)
    local_time_key = LOCAL_NOTE_TIME_KEYS.get(proactive_type)
    if local_time_key is not None:
        target_time = getattr(clock, local_time_key)
        if _within_delivery_window(current_time, target_time, clock):
            return None
        return (
            _next_wall_time(current_time, target_time, clock),
            f"outside_{local_time_key}_window",
        )

    quiet_end = _quiet_end_if_needed(current_time, clock)
    if quiet_end is None:
        return None
    return quiet_end, "quiet_hours"


def proactive_schedule_metadata(character: Character, run_at: datetime) -> dict[str, object]:
    clock = proactive_clock(character)
    local_run_at = _as_utc(run_at).astimezone(clock.timezone)
    return {
        "respect_local_time": True,
        "delivery_timezone": clock.timezone_name,
        "scheduled_local_time": local_run_at.isoformat(timespec="minutes"),
    }


async def reschedule_pending_proactive_jobs(
    session: AsyncSession,
    character: Character,
    *,
    now: datetime | None = None,
) -> int:
    current_time = _as_utc(now or utc_now())
    result = await session.execute(
        select(ScheduledJob).where(
            ScheduledJob.character_id == character.id,
            ScheduledJob.status == "pending",
            ScheduledJob.job_type.in_(tuple(PROACTIVE_JOB_SCHEDULES)),
        )
    )
    jobs = list(result.scalars().all())
    cooldown_hours = proactive_cooldown_hours(character)
    for job in jobs:
        block_reason = proactive_block_reason(character, job.job_type, now=current_time)
        payload = job.payload_json if isinstance(job.payload_json, dict) else {}
        if block_reason is not None:
            job.status = "done"
            job.last_error = None
            job.locked_at = None
            job.locked_by = None
            job.payload_json = {
                **payload,
                "result": "cancelled_by_user_controls",
                "skip_reason": block_reason,
            }
            continue
        run_at = proactive_initial_run_at(
            character,
            job.job_type,
            now=current_time,
            fallback_delay=PROACTIVE_JOB_SCHEDULES[job.job_type],
        )
        job.run_at = run_at
        job.payload_json = {
            **payload,
            **proactive_schedule_metadata(character, run_at),
            "cooldown_hours": cooldown_hours,
            "rescheduled_for_preferences": True,
        }
    await session.flush()
    return len(jobs)


def proactive_clock(character: Character) -> ProactiveClock:
    preferences = proactive_preferences(character)
    timezone_name = _timezone_name(preferences.get("timezone"))
    try:
        timezone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        timezone_name = DEFAULT_PROACTIVE_TIMEZONE
        timezone = ZoneInfo(DEFAULT_PROACTIVE_TIMEZONE)
    return ProactiveClock(
        timezone_name=timezone_name,
        timezone=timezone,
        quiet_start=_clock_time(
            preferences.get("quiet_hours_start"),
            DEFAULT_QUIET_HOURS_START,
        ),
        quiet_end=_clock_time(
            preferences.get("quiet_hours_end"),
            DEFAULT_QUIET_HOURS_END,
        ),
        morning_time=_clock_time(
            preferences.get("morning_time"),
            DEFAULT_MORNING_TIME,
        ),
        goodnight_time=_clock_time(
            preferences.get("goodnight_time"),
            DEFAULT_GOODNIGHT_TIME,
        ),
    )


def proactive_preferences(character: Character) -> dict[str, object]:
    profile = character.boundaries_json if isinstance(character.boundaries_json, dict) else {}
    preferences = profile.get("proactive_preferences")
    if isinstance(preferences, dict):
        return preferences
    return {}


def _timezone_name(value: object) -> str:
    if not isinstance(value, str):
        return DEFAULT_PROACTIVE_TIMEZONE
    normalized = value.strip()
    return normalized or DEFAULT_PROACTIVE_TIMEZONE


def _clock_time(value: object, default: str) -> time:
    candidate = value if isinstance(value, str) else default
    parsed = _parse_clock_time(candidate)
    return parsed or _parse_clock_time(default) or time()


def _parse_clock_time(value: str) -> time | None:
    normalized = value.strip()
    if (
        len(normalized) != 5
        or normalized[2] != ":"
        or not normalized[:2].isdigit()
        or not normalized[3:].isdigit()
    ):
        return None
    hour = int(normalized[:2])
    minute = int(normalized[3:])
    if hour > 23 or minute > 59:
        return None
    return time(hour=hour, minute=minute)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _next_wall_time(after: datetime, target_time: time, clock: ProactiveClock) -> datetime:
    after_utc = _as_utc(after)
    local_after = after_utc.astimezone(clock.timezone)
    for day_offset in range(3):
        target_date = local_after.date() + timedelta(days=day_offset)
        candidate = _wall_time_utc(target_date, target_time, clock)
        if candidate >= after_utc:
            return candidate
    raise ValueError("Could not resolve the next proactive local time.")


def _wall_time_utc(target_date: date, target_time: time, clock: ProactiveClock) -> datetime:
    local_candidate = datetime.combine(
        target_date,
        target_time,
        tzinfo=clock.timezone,
    )
    candidate_utc = local_candidate.astimezone(UTC)
    round_trip = candidate_utc.astimezone(clock.timezone)
    if (
        round_trip.date() != target_date
        or round_trip.hour != target_time.hour
        or round_trip.minute != target_time.minute
    ):
        candidate_utc = round_trip.astimezone(UTC)
    return candidate_utc


def _within_delivery_window(
    current_time: datetime,
    target_time: time,
    clock: ProactiveClock,
) -> bool:
    current_utc = _as_utc(current_time)
    local_date = current_utc.astimezone(clock.timezone).date()
    for day_offset in (0, -1):
        start = _wall_time_utc(
            local_date + timedelta(days=day_offset),
            target_time,
            clock,
        )
        if start <= current_utc < start + LOCAL_NOTE_DELIVERY_WINDOW:
            return True
    return False


def _quiet_end_if_needed(
    current_time: datetime,
    clock: ProactiveClock,
) -> datetime | None:
    current_utc = _as_utc(current_time)
    local_current = current_utc.astimezone(clock.timezone)
    current_clock = local_current.timetz().replace(tzinfo=None)
    start = clock.quiet_start
    end = clock.quiet_end
    if start == end:
        return None
    if start < end:
        in_quiet_hours = start <= current_clock < end
        end_date = local_current.date()
    else:
        in_quiet_hours = current_clock >= start or current_clock < end
        end_date = (
            local_current.date() + timedelta(days=1)
            if current_clock >= start
            else local_current.date()
        )
    if not in_quiet_hours:
        return None
    quiet_end = _wall_time_utc(end_date, end, clock)
    if quiet_end <= current_utc:
        quiet_end = _wall_time_utc(end_date + timedelta(days=1), end, clock)
    return quiet_end


async def _latest_message(session: AsyncSession, conversation_id) -> Message | None:
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _pending_job_exists(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    job_type: str,
) -> bool:
    result = await session.execute(
        select(ScheduledJob.id)
        .where(
            ScheduledJob.job_type == job_type,
            ScheduledJob.status.in_(("pending", "running")),
            ScheduledJob.payload_json["conversation_id"].as_string() == str(conversation_id),
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _unresolved_thread_content(
    session: AsyncSession,
    conversation: Conversation,
    *,
    fallback: str,
    requested_thread_id: uuid.UUID | None = None,
) -> tuple[str, dict[str, str], ContinuityThread | None]:
    continuity_thread = await select_proactive_thread(
        session,
        conversation=conversation,
        requested_thread_id=requested_thread_id,
    )
    if continuity_thread is not None:
        context = _safe_thread_context([continuity_thread.content], "living_thread")
        if context is not None:
            kind, excerpt = context
            return (
                (
                    f"I remembered the thread about {excerpt}. "
                    "We can return to it whenever it feels right; no pressure."
                ),
                {
                    "proactive_context": kind,
                    "continuity_thread_id": str(continuity_thread.id),
                },
                continuity_thread,
            )
    if requested_thread_id is not None:
        return fallback, {}, None
    journal = await _latest_journal_with_followup(session, conversation)
    if journal is None:
        return fallback, {}, None
    context = _safe_thread_context(journal.unresolved_threads_json, "unresolved_thread")
    if context is None:
        context = _safe_thread_context(journal.callbacks_json, "callback")
    if context is None:
        return fallback, {}, None
    kind, excerpt = context
    return (
        (
            f"I remembered the thread about {excerpt}. "
            "We can return to it whenever it feels right; no pressure."
        ),
        {"proactive_context": kind},
        None,
    )


async def _thinking_of_you_content(
    session: AsyncSession,
    conversation: Conversation,
) -> tuple[str, dict[str, str]]:
    journal = await _latest_grounded_journal(session, conversation)
    if journal is None:
        return "", {}
    anchor = _safe_proactive_prompt_fragment(journal.summary, limit=180)
    if not anchor:
        return "", {}
    return (
        (
            f"I found myself thinking about {anchor.rstrip('.')}. "
            "I wanted to leave a quiet hello; no pressure to reply."
        ),
        {
            "proactive_context": "shared_moment",
            "episodic_journal_id": str(journal.id),
        },
    )


async def _latest_unnoted_relationship_milestone(
    session: AsyncSession,
    conversation: Conversation,
) -> tuple[RelationshipState, dict[str, str]] | None:
    result = await session.execute(
        select(RelationshipState).where(
            RelationshipState.user_id == conversation.user_id,
            RelationshipState.character_id == conversation.character_id,
        )
    )
    relationship = result.scalar_one_or_none()
    if relationship is None:
        return None
    metadata = relationship.metadata_json if isinstance(relationship.metadata_json, dict) else {}
    timeline = metadata.get("timeline")
    if not isinstance(timeline, list):
        return None
    noted = set(_metadata_string_list(metadata.get("proactive_milestones_noted")))
    for event in reversed(timeline):
        if not isinstance(event, dict) or event.get("kind") != "milestone":
            continue
        milestone_id = str(event.get("milestone_id") or "").strip()
        if not milestone_id or milestone_id in noted:
            continue
        summary = _compact_context(str(event.get("summary") or ""))
        if not summary:
            continue
        normalized = summary.lower()
        if any(term in normalized for term in UNSAFE_PROACTIVE_CONTEXT_TERMS):
            continue
        if is_blocked_content(summary):
            continue
        return relationship, {"milestone_id": milestone_id, "summary": summary}
    return None


def _milestone_note_content(summary: str) -> str:
    compact = summary.strip().rstrip(".")
    return (
        f"A small marker from us: {compact}. "
        "I wanted to leave it here gently, so the moment does not disappear into the scroll."
    )


def _mark_relationship_milestone_noted(
    relationship: RelationshipState,
    milestone_id: str,
) -> None:
    metadata = relationship.metadata_json if isinstance(relationship.metadata_json, dict) else {}
    noted = _metadata_string_list(metadata.get("proactive_milestones_noted"))
    if milestone_id not in noted:
        noted.append(milestone_id)
    relationship.metadata_json = {
        **metadata,
        "proactive_milestones_noted": noted[-20:],
    }


async def _latest_journal_with_followup(
    session: AsyncSession,
    conversation: Conversation,
) -> EpisodicJournal | None:
    result = await session.execute(
        select(EpisodicJournal)
        .where(
            EpisodicJournal.conversation_id == conversation.id,
            EpisodicJournal.character_id == conversation.character_id,
            EpisodicJournal.scope == "general",
        )
        .order_by(desc(EpisodicJournal.updated_at))
        .limit(6)
    )
    for journal in result.scalars().all():
        if journal.unresolved_threads_json or _has_followup_callback(journal.callbacks_json):
            return journal
    return None


async def _latest_grounded_journal(
    session: AsyncSession,
    conversation: Conversation,
) -> EpisodicJournal | None:
    result = await session.execute(
        select(EpisodicJournal)
        .where(
            EpisodicJournal.conversation_id == conversation.id,
            EpisodicJournal.character_id == conversation.character_id,
            EpisodicJournal.scope == "general",
            EpisodicJournal.importance >= 0.55,
            EpisodicJournal.metadata_json["source"].as_string() != "manual",
        )
        .order_by(desc(EpisodicJournal.updated_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


def _has_followup_callback(callbacks: list[str]) -> bool:
    followup_markers = (
        "come back",
        "circle back",
        "return to",
        "revisit",
        "pick this up",
        "later",
        "next time",
        "remind me",
        "follow up",
        "don't let me forget",
        "do not let me forget",
    )
    return any(
        any(marker in str(callback).lower() for marker in followup_markers)
        for callback in callbacks
    )


def _safe_thread_context(values: list[str], kind: str) -> tuple[str, str] | None:
    for value in reversed(values):
        excerpt = _compact_context(value)
        if not excerpt:
            continue
        normalized = excerpt.lower()
        if any(term in normalized for term in UNSAFE_PROACTIVE_CONTEXT_TERMS):
            continue
        if is_blocked_content(excerpt):
            continue
        return kind, f'"{excerpt}"'
    return None


def _compact_context(value: str) -> str:
    compact = " ".join(str(value).strip().split())
    if not compact:
        return ""
    if len(compact) > 96:
        compact = compact[:93].rstrip() + "..."
    return compact


def _metadata_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _latest_allows_double_text(message: Message) -> bool:
    metadata = message.metadata_json if isinstance(message.metadata_json, dict) else {}
    return (
        message.role == "assistant"
        and metadata.get("proactive") is not True
        and not message_is_private(message)
    )


def _parse_snoozed_until(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed
