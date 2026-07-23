from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Literal

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import LLMProvider
from app.models import (
    Character,
    ContinuityThread,
    Conversation,
    EpisodicJournal,
    MemoryItem,
    Message,
    ProactiveCandidate,
    ProactiveCandidateEvent,
    RelationshipEvent,
    RelationshipState,
    ScheduledJob,
    utc_now,
)
from app.services.continuity import select_proactive_thread
from app.services.conversation_privacy import conversation_is_private, message_is_private
from app.services.jobs import create_job
from app.services.memory import classify_memory_sensitivity
from app.services.proactive import (
    DELAYED_DOUBLE_TEXT_TYPE,
    PROACTIVE_JOB_SCHEDULES,
    create_inactivity_proactive_message,
    proactive_block_reason,
    proactive_cooldown_hours,
    proactive_deferred_until,
    proactive_initial_run_at,
    proactive_preferences,
    proactive_relationship_delivery_block,
    proactive_relationship_posture,
    proactive_schedule_metadata,
)

CandidateType = Literal[
    "follow_up",
    "check_in",
    "reminder",
    "callback",
    "milestone",
    "routine",
    "return",
    "suggestion",
    "queued_thought",
]

PROACTIVE_DELIVERY_JOB = "proactive_delivery"
VISIBLE_STATES = ("delivered", "opened", "dismissed", "replied")
PENDING_STATES = ("candidate", "scheduled", "generated")
TERMINAL_STATES = ("dismissed", "replied", "cancelled", "failed", "expired")
ALL_STATES = (
    "candidate",
    "scheduled",
    "generated",
    "delivered",
    "opened",
    "dismissed",
    "replied",
    "cancelled",
    "failed",
    "expired",
)
REMINDER_MARKERS = (
    "remind me",
    "don't let me forget",
    "do not let me forget",
)
TEMPORAL_MARKERS = (
    "after work",
    "later today",
    "this evening",
    "tomorrow",
    "next week",
    "this weekend",
    " on monday",
    " on tuesday",
    " on wednesday",
    " on thursday",
    " on friday",
    " on saturday",
    " on sunday",
)
CONTEXT_RATIONALES = {
    "follow_up": "An explicitly saved conversation thread is still open.",
    "check_in": "A meaningful shared thread may benefit from a restrained follow-up.",
    "reminder": "The user explicitly asked to be reminded about an open thread.",
    "callback": "A grounded shared moment contains a useful callback.",
    "milestone": "A meaningful relationship milestone has not yet been acknowledged.",
    "routine": "An explicitly saved routine is eligible at the user’s local time.",
    "return": "The user returned after an absence before an outbound note was sent.",
    "suggestion": "An explicitly saved plan supports a contextual suggestion.",
    "queued_thought": "An open thread supports one concise follow-up thought.",
}
JOB_TO_CANDIDATE: dict[str, CandidateType] = {
    "proactive_inactivity_check": "check_in",
    "proactive_morning_check": "routine",
    "proactive_goodnight_check": "routine",
    "proactive_thinking_of_you": "callback",
    "proactive_milestone_check": "milestone",
    "proactive_unresolved_thread_nudge": "follow_up",
    DELAYED_DOUBLE_TEXT_TYPE: "queued_thought",
    "proactive_message_create": "check_in",
}
FREQUENCY_POLICY = {
    "minimal": {"threshold": 0.72, "daily_cap": 1, "preference": 0.55},
    "balanced": {"threshold": 0.58, "daily_cap": 2, "preference": 0.75},
    "frequent": {"threshold": 0.50, "daily_cap": 3, "preference": 0.95},
}
SENSITIVE_PROACTIVE_RE = re.compile(
    r"\b(?:abuse|assault|crisis|diagnos(?:is|ed)|doctor|grief|hospital|"
    r"medication|panic attack|prescription|self[- ]harm|suicid(?:e|al)|"
    r"surgery|therap(?:ist|y)|trauma)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CandidateEvidence:
    source: str
    candidate_type: CandidateType
    source_message_id: uuid.UUID | None = None
    memory_id: uuid.UUID | None = None
    journal_id: uuid.UUID | None = None
    continuity_thread_id: uuid.UUID | None = None
    relationship_event_id: uuid.UUID | None = None
    source_version: str = ""
    sensitivity: Literal["standard", "sensitive"] = "standard"
    confidence: float = 0.7
    urgency: float = 0.35
    importance: float = 0.5
    emotional_weight: float = 0.0
    unresolved: float = 0.0
    routine_fit: float = 0.0
    evidence_supported: bool = False
    required_source: str = "message"
    milestone_id: str | None = None
    temporal_text: str | None = None


@dataclass(frozen=True)
class CandidateDeliveryResult:
    status: Literal["delivered", "suppressed", "deferred", "already_terminal"]
    candidate: ProactiveCandidate
    message: Message | None = None
    reason: str | None = None
    deferred_until: datetime | None = None


async def ensure_proactive_candidates(
    session: AsyncSession,
    *,
    conversation: Conversation,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    now: datetime | None = None,
) -> list[ProactiveCandidate]:
    """Create idempotent candidates and durable delivery jobs from all eligible sources."""
    if conversation_is_private(conversation):
        return []
    character = await session.get(Character, character_id)
    if character is None or character.owner_user_id != user_id:
        return []
    contact_block = await proactive_relationship_delivery_block(
        session,
        conversation,
        "proactive_inactivity_check",
    )
    if contact_block is not None and contact_block.key == "boundary":
        await cancel_pending_for_character(
            session,
            character_id=character.id,
            reason_code="relationship_boundary",
        )
        return []

    current_time = _as_utc(now or utc_now())
    latest = await _latest_stateful_message(session, conversation.id)
    if latest is None or message_is_private(latest) or _message_is_adult(latest):
        return []
    thread = await select_proactive_thread(
        session,
        conversation=conversation,
        now=current_time,
    )
    journal = await _latest_general_journal(session, conversation)
    relationship = await _relationship_state(session, conversation)
    milestone = await _unnoted_milestone(session, conversation, relationship)

    candidate_plans: list[tuple[str, CandidateEvidence]] = []
    if thread is not None:
        thread_type = _thread_candidate_type(
            thread,
            "proactive_unresolved_thread_nudge",
        )
        if thread_type == "routine":
            normalized_thread = thread.content.casefold()
            thread_job_type = (
                "proactive_morning_check"
                if "morning" in normalized_thread
                else "proactive_goodnight_check"
                if "night" in normalized_thread or "evening" in normalized_thread
                else "proactive_unresolved_thread_nudge"
            )
        else:
            thread_job_type = "proactive_unresolved_thread_nudge"
        candidate_plans.append(
            (
                thread_job_type,
                _candidate_evidence(
                    thread_job_type,
                    latest=latest,
                    thread=thread,
                    journal=None,
                    milestone=None,
                ),
            )
        )
    if journal is not None:
        journal_job_type = (
            DELAYED_DOUBLE_TEXT_TYPE
            if latest.role == "assistant" and journal.callbacks_json
            else "proactive_thinking_of_you"
        )
        candidate_plans.append(
            (
                journal_job_type,
                _candidate_evidence(
                    journal_job_type,
                    latest=latest,
                    thread=None,
                    journal=journal,
                    milestone=None,
                ),
            )
        )
    if milestone is not None:
        candidate_plans.append(
            (
                "proactive_milestone_check",
                _candidate_evidence(
                    "proactive_milestone_check",
                    latest=latest,
                    thread=None,
                    journal=None,
                    milestone=milestone,
                ),
            )
        )

    created: list[ProactiveCandidate] = []
    for job_type, evidence in candidate_plans:
        if proactive_block_reason(character, job_type, now=current_time) is not None:
            continue
        if (
            await proactive_relationship_delivery_block(
                session,
                conversation,
                job_type,
            )
            is not None
        ):
            continue
        if not evidence.evidence_supported:
            continue
        run_at = _candidate_run_at(
            character,
            job_type=job_type,
            evidence=evidence,
            now=current_time,
            fallback_delay=PROACTIVE_JOB_SCHEDULES[job_type],
        )
        candidate = await _create_candidate_once(
            session,
            user_id=user_id,
            character=character,
            conversation=conversation,
            job_type=job_type,
            evidence=evidence,
            run_at=run_at,
            now=current_time,
        )
        if candidate is None:
            continue
        created.append(candidate)
        await _schedule_candidate_job(
            session,
            candidate=candidate,
            job_type=job_type,
            character=character,
        )
    return created


async def deliver_proactive_candidate(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    provider: LLMProvider | None,
    now: datetime | None = None,
) -> CandidateDeliveryResult:
    current_time = _as_utc(now or utc_now())
    candidate = (
        await session.execute(
            select(ProactiveCandidate)
            .where(ProactiveCandidate.id == candidate_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if candidate is None:
        raise ValueError("Proactive candidate was not found.")
    if candidate.state not in PENDING_STATES:
        return CandidateDeliveryResult(status="already_terminal", candidate=candidate)

    character = await session.get(Character, candidate.character_id)
    conversation = await session.get(Conversation, candidate.conversation_id)
    if (
        character is None
        or conversation is None
        or character.owner_user_id != candidate.user_id
        or conversation.user_id != candidate.user_id
        or conversation.character_id != candidate.character_id
    ):
        await cancel_candidate(session, candidate, "source_scope_changed", now=current_time)
        return _suppressed(candidate, "source_scope_changed")
    if candidate.expires_at <= current_time:
        await transition_candidate(
            session,
            candidate,
            "expired",
            "candidate_expired",
            now=current_time,
        )
        return _suppressed(candidate, "candidate_expired")
    if conversation_is_private(conversation) or candidate.sensitivity in {"adult", "private"}:
        await cancel_candidate(session, candidate, "privacy_block", now=current_time)
        return _suppressed(candidate, "privacy_block")
    if candidate.sensitivity == "sensitive" and candidate.candidate_type != "reminder":
        await cancel_candidate(
            session,
            candidate,
            "sensitive_source_suppressed",
            now=current_time,
        )
        return _suppressed(candidate, "sensitive_source_suppressed")

    constraints = _dict(candidate.delivery_constraints_json)
    job_type = str(constraints.get("proactive_type") or "")
    if job_type not in JOB_TO_CANDIDATE:
        await fail_candidate(session, candidate, "invalid_candidate_type", now=current_time)
        return _suppressed(candidate, "invalid_candidate_type")
    control_block = proactive_block_reason(character, job_type, now=current_time)
    if control_block == "proactive_snoozed":
        snoozed_until = _iso_datetime(proactive_preferences(character).get("snoozed_until"))
        if snoozed_until is not None and snoozed_until < candidate.expires_at:
            candidate.scheduled_for = snoozed_until
            await _record_event(
                session,
                candidate,
                from_state=candidate.state,
                to_state="scheduled",
                reason_code="proactive_snoozed",
                metadata={"deferred_until": snoozed_until.isoformat()},
            )
            return CandidateDeliveryResult(
                status="deferred",
                candidate=candidate,
                reason="proactive_snoozed",
                deferred_until=snoozed_until,
            )
    if control_block is not None:
        await cancel_candidate(session, candidate, control_block, now=current_time)
        return _suppressed(candidate, control_block)
    muted = _string_set(proactive_preferences(character).get("muted_categories"))
    if candidate.candidate_type in muted:
        await cancel_candidate(session, candidate, "category_muted", now=current_time)
        return _suppressed(candidate, "category_muted")
    if not await _source_still_valid(session, candidate):
        await cancel_candidate(session, candidate, "source_stale_or_deleted", now=current_time)
        return _suppressed(candidate, "source_stale_or_deleted")
    if constraints.get("evidence_supported") is not True:
        await cancel_candidate(session, candidate, "insufficient_context", now=current_time)
        return _suppressed(candidate, "insufficient_context")

    latest = await _latest_stateful_message(session, conversation.id)
    if latest is None or message_is_private(latest) or _message_is_adult(latest):
        await cancel_candidate(session, candidate, "current_context_ineligible", now=current_time)
        return _suppressed(candidate, "current_context_ineligible")
    if latest.role == "user" and latest.created_at > candidate.created_at:
        await transition_candidate(
            session,
            candidate,
            "replied",
            "user_returned_before_delivery",
            now=current_time,
        )
        return _suppressed(candidate, "user_returned_before_delivery")

    relationship_block = await proactive_relationship_delivery_block(
        session,
        conversation,
        job_type,
    )
    if relationship_block is not None:
        reason = f"relationship_{relationship_block.key}"
        await cancel_candidate(session, candidate, reason, now=current_time)
        return _suppressed(candidate, reason)

    deferred = proactive_deferred_until(character, job_type, now=current_time)
    if deferred is not None:
        deferred_until, reason = deferred
        if deferred_until >= candidate.expires_at:
            await transition_candidate(
                session,
                candidate,
                "expired",
                "quiet_hours_exceeded_expiry",
                now=current_time,
            )
            return _suppressed(candidate, "quiet_hours_exceeded_expiry")
        candidate.scheduled_for = deferred_until
        await _record_event(
            session,
            candidate,
            from_state=candidate.state,
            to_state="scheduled",
            reason_code=reason,
            metadata={"deferred_until": deferred_until.isoformat()},
        )
        return CandidateDeliveryResult(
            status="deferred",
            candidate=candidate,
            reason=reason,
            deferred_until=deferred_until,
        )

    score, factors, threshold, block = await score_candidate(
        session,
        candidate=candidate,
        character=character,
        conversation=conversation,
        relationship=await _relationship_state(session, conversation),
        now=current_time,
    )
    candidate.relevance_score = score
    candidate.score_factors_json = factors
    if block is not None or score < threshold:
        reason = block or "low_relevance"
        await cancel_candidate(session, candidate, reason, now=current_time)
        return _suppressed(candidate, reason)

    message = await create_inactivity_proactive_message(
        session,
        conversation,
        inactivity_hours=1,
        cooldown_hours=proactive_cooldown_hours(character),
        force=True,
        proactive_type=job_type,
        provider=provider,
        continuity_thread_id=candidate.continuity_thread_id,
        reject_user_returns_after=candidate.created_at,
    )
    if message is None:
        await cancel_candidate(session, candidate, "delivery_recheck_suppressed", now=current_time)
        return _suppressed(candidate, "delivery_recheck_suppressed")

    message.metadata_json = {
        **(message.metadata_json or {}),
        "proactive_candidate_id": str(candidate.id),
        "initiative_kind": candidate.initiative_kind,
        "proactive_origin": candidate.candidate_type,
        "proactive_rationale": candidate.rationale,
    }
    candidate.message_id = message.id
    candidate.generated_at = current_time
    await transition_candidate(
        session,
        candidate,
        "generated",
        "generation_completed",
        now=current_time,
        metadata={
            "generation_source": str(
                (message.metadata_json or {}).get("generation_source") or "unknown"
            )[:40]
        },
    )
    candidate.delivered_at = current_time
    await transition_candidate(
        session,
        candidate,
        "delivered",
        "in_app_delivery",
        now=current_time,
    )
    await session.flush()
    return CandidateDeliveryResult(
        status="delivered",
        candidate=candidate,
        message=message,
    )


async def score_candidate(
    session: AsyncSession,
    *,
    candidate: ProactiveCandidate,
    character: Character,
    conversation: Conversation,
    relationship: RelationshipState | None,
    now: datetime,
) -> tuple[float, dict[str, float | int | str], float, str | None]:
    preferences = proactive_preferences(character)
    frequency = str(preferences.get("frequency") or "balanced")
    policy = FREQUENCY_POLICY.get(frequency, FREQUENCY_POLICY["balanced"])
    cooldown_hours = proactive_cooldown_hours(character)
    local_day_start = _local_day_start(character, now)
    delivered_today = int(
        (
            await session.execute(
                select(func.count(ProactiveCandidate.id)).where(
                    ProactiveCandidate.character_id == character.id,
                    ProactiveCandidate.state.in_(VISIBLE_STATES),
                    ProactiveCandidate.delivered_at >= local_day_start,
                )
            )
        ).scalar_one()
    )
    configured_cap = _bounded_int(
        preferences.get("daily_cap"),
        default=int(policy["daily_cap"]),
        minimum=1,
        maximum=3,
    )
    latest_delivery = (
        await session.execute(
            select(ProactiveCandidate.delivered_at)
            .where(
                ProactiveCandidate.character_id == character.id,
                ProactiveCandidate.delivered_at.is_not(None),
                ProactiveCandidate.id != candidate.id,
            )
            .order_by(desc(ProactiveCandidate.delivered_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    cooldown_remaining = 0.0
    if latest_delivery is not None:
        cooldown_end = latest_delivery + timedelta(hours=cooldown_hours)
        cooldown_remaining = max(0.0, (cooldown_end - now).total_seconds() / 3600)
    if delivered_today >= configured_cap:
        block = "daily_cap_reached"
    elif cooldown_remaining > 0:
        block = "cooldown_active"
    else:
        block = None

    initial = _dict(candidate.score_factors_json)
    source_age_hours = max(0.0, (now - candidate.created_at).total_seconds() / 3600)
    recency = max(0.0, 1.0 - source_age_hours / 168)
    importance = _bounded_float(initial.get("importance"), 0.5)
    emotional_weight = _bounded_float(initial.get("emotional_weight"), 0.0)
    unresolved = _bounded_float(initial.get("unresolved"), 0.0)
    routine_fit = _bounded_float(initial.get("routine_fit"), 0.0)
    relationship_fit = {
        "new": 0.55,
        "warming": 0.72,
        "trusted": 0.86,
        "close": 0.92,
        "careful": 0.35,
        "repair": 0.15,
    }.get(proactive_relationship_posture(relationship).key, 0.5)
    frequency_fit = max(0.0, 1.0 - delivered_today / max(configured_cap, 1))
    score = (
        recency * 0.13
        + importance * 0.18
        + emotional_weight * 0.08
        + unresolved * 0.18
        + float(policy["preference"]) * 0.12
        + routine_fit * 0.08
        + relationship_fit * 0.12
        + frequency_fit * 0.07
        + candidate.urgency * 0.04
    )
    score = round(min(max(score, 0.0), 1.0), 4)
    factors: dict[str, float | int | str] = {
        "recency": round(recency, 4),
        "importance": importance,
        "emotional_weight": emotional_weight,
        "unresolved": unresolved,
        "preference": float(policy["preference"]),
        "routine": routine_fit,
        "local_time": 1.0,
        "relationship": relationship_fit,
        "frequency": round(frequency_fit, 4),
        "urgency": candidate.urgency,
        "delivered_today": delivered_today,
        "daily_cap": configured_cap,
        "frequency_mode": frequency,
    }
    threshold = float(policy["threshold"])
    if candidate.candidate_type in {"milestone", "reminder"}:
        threshold = max(0.45, threshold - 0.04)
    return score, factors, threshold, block


async def transition_candidate(
    session: AsyncSession,
    candidate: ProactiveCandidate,
    to_state: str,
    reason_code: str,
    *,
    now: datetime | None = None,
    metadata: dict[str, object] | None = None,
) -> ProactiveCandidate:
    previous = candidate.state
    current_time = _as_utc(now or utc_now())
    candidate.state = to_state
    candidate.updated_at = current_time
    if to_state == "opened":
        candidate.opened_at = current_time
    elif to_state == "dismissed":
        candidate.dismissed_at = current_time
    elif to_state == "replied":
        candidate.replied_at = current_time
    elif to_state == "cancelled":
        candidate.cancelled_at = current_time
        candidate.failure_code = reason_code[:80]
    elif to_state == "failed":
        candidate.failed_at = current_time
        candidate.failure_code = reason_code[:80]
    await _record_event(
        session,
        candidate,
        from_state=previous,
        to_state=to_state,
        reason_code=reason_code,
        metadata=metadata,
    )
    await session.flush()
    return candidate


async def cancel_candidate(
    session: AsyncSession,
    candidate: ProactiveCandidate,
    reason_code: str,
    *,
    now: datetime | None = None,
) -> ProactiveCandidate:
    return await transition_candidate(
        session,
        candidate,
        "cancelled",
        reason_code,
        now=now,
    )


async def fail_candidate(
    session: AsyncSession,
    candidate: ProactiveCandidate,
    reason_code: str,
    *,
    now: datetime | None = None,
) -> ProactiveCandidate:
    return await transition_candidate(
        session,
        candidate,
        "failed",
        reason_code,
        now=now,
    )


async def mark_candidate_opened(
    session: AsyncSession,
    candidate: ProactiveCandidate,
) -> ProactiveCandidate:
    if candidate.state == "delivered":
        await transition_candidate(session, candidate, "opened", "opened_in_inbox")
    return candidate


async def mark_candidates_opened_through(
    session: AsyncSession,
    *,
    conversation: Conversation,
) -> int:
    result = await session.execute(
        select(ProactiveCandidate)
        .join(Message, Message.id == ProactiveCandidate.message_id)
        .where(
            ProactiveCandidate.conversation_id == conversation.id,
            ProactiveCandidate.state == "delivered",
            Message.created_at <= conversation.last_read_at,
        )
        .with_for_update(skip_locked=True)
    )
    candidates = list(result.scalars().all())
    for candidate in candidates:
        await transition_candidate(
            session,
            candidate,
            "opened",
            "conversation_read",
            now=conversation.last_read_at,
        )
    return len(candidates)


async def mark_candidate_dismissed(
    session: AsyncSession,
    candidate: ProactiveCandidate,
    *,
    feedback: str | None,
) -> ProactiveCandidate:
    if candidate.state not in {"delivered", "opened"}:
        return candidate
    candidate.dismissal_feedback = feedback
    return await transition_candidate(
        session,
        candidate,
        "dismissed",
        f"dismissed_{feedback}" if feedback else "dismissed",
    )


async def mark_delivered_candidates_replied(
    session: AsyncSession,
    *,
    conversation: Conversation,
    user_message: Message,
) -> int:
    delivered_result = await session.execute(
        select(ProactiveCandidate)
        .where(
            ProactiveCandidate.conversation_id == conversation.id,
            ProactiveCandidate.state.in_(("delivered", "opened")),
            ProactiveCandidate.delivered_at <= user_message.created_at,
        )
        .with_for_update(skip_locked=True)
    )
    delivered = list(delivered_result.scalars().all())
    for candidate in delivered:
        await transition_candidate(
            session,
            candidate,
            "replied",
            "user_replied_in_conversation",
            now=user_message.created_at,
        )
    pending_result = await session.execute(
        select(ProactiveCandidate)
        .where(
            ProactiveCandidate.conversation_id == conversation.id,
            ProactiveCandidate.state.in_(PENDING_STATES),
            ProactiveCandidate.created_at <= user_message.created_at,
        )
        .with_for_update(skip_locked=True)
    )
    pending = list(pending_result.scalars().all())
    for candidate in pending:
        await transition_candidate(
            session,
            candidate,
            "replied",
            "user_returned_before_delivery",
            now=user_message.created_at,
        )
        jobs = (
            await session.execute(
                select(ScheduledJob)
                .where(
                    ScheduledJob.status.in_(("pending", "running")),
                    ScheduledJob.payload_json["candidate_id"].as_string() == str(candidate.id),
                )
                .with_for_update(skip_locked=True)
            )
        ).scalars()
        for job in jobs:
            job.status = "cancelled"
            job.cancelled_at = user_message.created_at
            job.locked_at = None
            job.locked_by = None
            job.last_error = "User returned before delivery."
    if pending:
        await _record_return_candidate(
            session,
            conversation=conversation,
            user_message=user_message,
            superseded_count=len(pending),
        )
        user_message.metadata_json = {
            **_dict(user_message.metadata_json),
            "return_context": {
                "pending_notes_cancelled": len(pending),
                "source": "proactive_presence",
            },
        }
    return len(delivered) + len(pending)


async def cancel_pending_for_character(
    session: AsyncSession,
    *,
    character_id: uuid.UUID,
    reason_code: str,
    candidate_type: str | None = None,
    conversation_id: uuid.UUID | None = None,
    continuity_thread_id: uuid.UUID | None = None,
    journal_id: uuid.UUID | None = None,
    memory_id: uuid.UUID | None = None,
) -> int:
    statement = select(ProactiveCandidate).where(
        ProactiveCandidate.character_id == character_id,
        ProactiveCandidate.state.in_(PENDING_STATES),
    )
    if candidate_type is not None:
        statement = statement.where(ProactiveCandidate.candidate_type == candidate_type)
    if conversation_id is not None:
        statement = statement.where(ProactiveCandidate.conversation_id == conversation_id)
    if continuity_thread_id is not None:
        statement = statement.where(ProactiveCandidate.continuity_thread_id == continuity_thread_id)
    if journal_id is not None:
        statement = statement.where(ProactiveCandidate.journal_id == journal_id)
    if memory_id is not None:
        statement = statement.where(ProactiveCandidate.memory_id == memory_id)
    candidates = list((await session.execute(statement.with_for_update())).scalars().all())
    for candidate in candidates:
        await cancel_candidate(session, candidate, reason_code)
        await cancel_candidate_delivery_jobs(
            session,
            candidate,
            reason_code=reason_code,
        )
    await session.flush()
    return len(candidates)


async def cancel_candidate_delivery_jobs(
    session: AsyncSession,
    candidate: ProactiveCandidate,
    *,
    reason_code: str,
) -> int:
    jobs = list(
        (
            await session.execute(
                select(ScheduledJob)
                .where(
                    ScheduledJob.status.in_(("pending", "running")),
                    ScheduledJob.payload_json["candidate_id"].as_string() == str(candidate.id),
                )
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    now = utc_now()
    for job in jobs:
        job.status = "cancelled"
        job.cancelled_at = now
        job.locked_at = None
        job.locked_by = None
        job.last_error = reason_code[:1000]
    await session.flush()
    return len(jobs)


def notification_preview(_character: Character) -> str:
    """Never include profile text, evidence, message prose, or sensitive context."""
    return "New companion note"


async def _record_return_candidate(
    session: AsyncSession,
    *,
    conversation: Conversation,
    user_message: Message,
    superseded_count: int,
) -> None:
    key = hashlib.sha256(f"return:{user_message.id}".encode()).hexdigest()
    existing = (
        await session.execute(
            select(ProactiveCandidate.id).where(
                ProactiveCandidate.user_id == conversation.user_id,
                ProactiveCandidate.idempotency_key == key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    character = await session.get(Character, conversation.character_id)
    if character is None:
        return
    candidate = ProactiveCandidate(
        user_id=conversation.user_id,
        character_id=conversation.character_id,
        conversation_id=conversation.id,
        source_message_id=user_message.id,
        candidate_type="return",
        initiative_kind="companion",
        source="user_return",
        rationale=CONTEXT_RATIONALES["return"],
        confidence=1.0,
        urgency=0.0,
        relevance_score=1.0,
        sensitivity="standard",
        state="candidate",
        idempotency_key=key,
        scheduled_for=None,
        expires_at=user_message.created_at + timedelta(days=1),
        notification_preview=notification_preview(character),
        delivery_constraints_json={"channel": "in_app", "outbound": False},
        score_factors_json={"superseded_count": superseded_count},
    )
    session.add(candidate)
    await session.flush()
    await _record_event(
        session,
        candidate,
        from_state=None,
        to_state="candidate",
        reason_code="user_return_detected",
        metadata={"superseded_count": superseded_count},
    )
    await transition_candidate(
        session,
        candidate,
        "replied",
        "continued_in_live_chat",
        now=user_message.created_at,
    )


def public_candidate(candidate: ProactiveCandidate, *, include_message: Message | None) -> dict:
    message_preview = None
    if include_message is not None and candidate.state in VISIBLE_STATES:
        message_preview = include_message.content
    return {
        "id": candidate.id,
        "character_id": candidate.character_id,
        "conversation_id": candidate.conversation_id,
        "message_id": candidate.message_id,
        "candidate_type": candidate.candidate_type,
        "initiative_kind": candidate.initiative_kind,
        "rationale": candidate.rationale,
        "state": candidate.state,
        "scheduled_for": candidate.scheduled_for,
        "expires_at": candidate.expires_at,
        "delivered_at": candidate.delivered_at,
        "opened_at": candidate.opened_at,
        "notification_preview": candidate.notification_preview,
        "message_preview": message_preview,
        "dismissal_feedback": candidate.dismissal_feedback,
        "created_at": candidate.created_at,
        "updated_at": candidate.updated_at,
    }


async def _create_candidate_once(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character: Character,
    conversation: Conversation,
    job_type: str,
    evidence: CandidateEvidence,
    run_at: datetime,
    now: datetime,
) -> ProactiveCandidate | None:
    idempotency_key = _candidate_key(
        conversation.id,
        job_type,
        evidence,
    )
    existing = (
        await session.execute(
            select(ProactiveCandidate).where(
                ProactiveCandidate.user_id == user_id,
                ProactiveCandidate.idempotency_key == idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None
    expires_at = _candidate_expiry(evidence.candidate_type, run_at)
    candidate = ProactiveCandidate(
        user_id=user_id,
        character_id=character.id,
        conversation_id=conversation.id,
        source_message_id=evidence.source_message_id,
        memory_id=evidence.memory_id,
        journal_id=evidence.journal_id,
        continuity_thread_id=evidence.continuity_thread_id,
        relationship_event_id=evidence.relationship_event_id,
        candidate_type=evidence.candidate_type,
        initiative_kind=("reminder" if evidence.candidate_type == "reminder" else "companion"),
        source=evidence.source,
        rationale=CONTEXT_RATIONALES[evidence.candidate_type],
        confidence=_bounded_float(evidence.confidence, 0.7),
        urgency=_bounded_float(evidence.urgency, 0.35),
        relevance_score=0.0,
        sensitivity=evidence.sensitivity,
        state="candidate",
        idempotency_key=idempotency_key,
        scheduled_for=run_at,
        expires_at=expires_at,
        notification_preview=notification_preview(character),
        delivery_constraints_json={
            "channel": "in_app",
            "proactive_type": job_type,
            "required_source": evidence.required_source,
            "source_version": evidence.source_version,
            "evidence_supported": evidence.evidence_supported,
            **({"milestone_id": evidence.milestone_id} if evidence.milestone_id else {}),
        },
        score_factors_json={
            "importance": evidence.importance,
            "emotional_weight": evidence.emotional_weight,
            "unresolved": evidence.unresolved,
            "routine_fit": evidence.routine_fit,
        },
    )
    try:
        async with session.begin_nested():
            session.add(candidate)
            await session.flush()
            await _record_event(
                session,
                candidate,
                from_state=None,
                to_state="candidate",
                reason_code="evidence_collected",
                metadata={"source": evidence.source},
            )
            await session.flush()
    except IntegrityError:
        return None
    return candidate


async def _schedule_candidate_job(
    session: AsyncSession,
    *,
    candidate: ProactiveCandidate,
    job_type: str,
    character: Character,
) -> ScheduledJob:
    candidate.state = "scheduled"
    await _record_event(
        session,
        candidate,
        from_state="candidate",
        to_state="scheduled",
        reason_code="delivery_eligible_after",
        metadata={"scheduled_for": candidate.scheduled_for.isoformat()},
    )
    await session.flush()
    return await create_job(
        session,
        job_type=PROACTIVE_DELIVERY_JOB,
        run_at=candidate.scheduled_for or utc_now(),
        user_id=candidate.user_id,
        character_id=candidate.character_id,
        dedupe_key=f"proactive-delivery:{candidate.id}",
        expires_at=candidate.expires_at,
        payload_json={
            "candidate_id": str(candidate.id),
            "conversation_id": str(candidate.conversation_id),
            "proactive_type": job_type,
            "source": "proactive_candidate_pipeline",
            **proactive_schedule_metadata(
                character,
                candidate.scheduled_for or utc_now(),
            ),
        },
    )


def _candidate_evidence(
    job_type: str,
    *,
    latest: Message,
    thread: ContinuityThread | None,
    journal: EpisodicJournal | None,
    milestone: tuple[str, RelationshipEvent | None] | None,
) -> CandidateEvidence:
    candidate_type = JOB_TO_CANDIDATE[job_type]
    source_version = _source_fingerprint(latest.content, _message_is_adult(latest))
    common = {
        "source_message_id": latest.id,
        "source_version": source_version,
        "confidence": 0.58,
        "importance": 0.35,
        "required_source": "message",
    }
    if job_type == "proactive_milestone_check" and milestone is not None:
        milestone_id, event = milestone
        return CandidateEvidence(
            source="relationship_milestone",
            candidate_type="milestone",
            relationship_event_id=event.id if event else None,
            source_version=milestone_id,
            confidence=event.confidence if event else 0.8,
            urgency=0.25,
            importance=max(event.significance, 0.75) if event else 0.82,
            emotional_weight=0.5,
            evidence_supported=True,
            required_source="relationship_milestone",
            milestone_id=milestone_id,
        )
    if job_type == "proactive_thinking_of_you" and journal is not None:
        candidate_type: CandidateType = (
            "callback" if journal.callbacks_json or journal.unresolved_threads_json else "check_in"
        )
        return CandidateEvidence(
            source="episodic_journal",
            candidate_type=candidate_type,
            journal_id=journal.id,
            source_version=_journal_source_version(journal),
            sensitivity=_proactive_sensitivity(
                journal.summary,
                *journal.unresolved_threads_json,
                *journal.callbacks_json,
            ),
            confidence=0.76,
            urgency=0.22,
            importance=_bounded_float(journal.importance, 0.6),
            emotional_weight=min(1.0, len(journal.emotional_tags_json) * 0.18),
            unresolved=0.45 if journal.callbacks_json else 0.0,
            evidence_supported=True,
            required_source="journal",
        )
    if job_type == DELAYED_DOUBLE_TEXT_TYPE and journal is not None:
        return CandidateEvidence(
            source="episodic_callback",
            candidate_type="queued_thought",
            journal_id=journal.id,
            source_version=_journal_source_version(journal),
            sensitivity=_proactive_sensitivity(
                journal.summary,
                *journal.unresolved_threads_json,
                *journal.callbacks_json,
            ),
            confidence=0.72,
            urgency=0.3,
            importance=_bounded_float(journal.importance, 0.6),
            emotional_weight=min(1.0, len(journal.emotional_tags_json) * 0.18),
            unresolved=0.7,
            evidence_supported=bool(journal.callbacks_json),
            required_source="journal",
        )
    if thread is not None:
        candidate_type = _thread_candidate_type(thread, job_type)
        routine_fit = 0.9 if thread.thread_kind == "ritual" else 0.0
        supported = job_type in {
            "proactive_inactivity_check",
            "proactive_morning_check",
            "proactive_goodnight_check",
            "proactive_unresolved_thread_nudge",
            DELAYED_DOUBLE_TEXT_TYPE,
        } and (
            job_type not in {"proactive_morning_check", "proactive_goodnight_check"}
            or thread.thread_kind == "ritual"
        )
        return CandidateEvidence(
            source="continuity_thread",
            candidate_type=candidate_type,
            source_message_id=thread.source_message_id,
            continuity_thread_id=thread.id,
            source_version=_thread_source_version(thread),
            sensitivity=_proactive_sensitivity(thread.content),
            confidence=_bounded_float(thread.confidence, 0.75),
            urgency=0.62 if candidate_type == "reminder" else 0.38,
            importance=_bounded_float(thread.salience, 0.65),
            unresolved=1.0,
            routine_fit=routine_fit,
            evidence_supported=supported,
            required_source="continuity_thread",
            temporal_text=thread.content,
        )
    return CandidateEvidence(
        source="recent_conversation",
        candidate_type=candidate_type,
        evidence_supported=False,
        **common,
    )


def _thread_candidate_type(thread: ContinuityThread, job_type: str) -> CandidateType:
    normalized = thread.content.casefold()
    if any(marker in normalized for marker in REMINDER_MARKERS) and any(
        marker in normalized for marker in TEMPORAL_MARKERS
    ):
        return "reminder"
    if thread.thread_kind == "ritual":
        return "routine"
    if thread.thread_kind == "plan":
        return "suggestion"
    if job_type == DELAYED_DOUBLE_TEXT_TYPE:
        return "queued_thought"
    return "follow_up"


def _candidate_run_at(
    character: Character,
    *,
    job_type: str,
    evidence: CandidateEvidence,
    now: datetime,
    fallback_delay: timedelta,
) -> datetime:
    if evidence.candidate_type == "reminder" and evidence.continuity_thread_id is not None:
        parsed = _reminder_due_at(character, evidence.temporal_text or "", now)
        if parsed is not None:
            return parsed
    return proactive_initial_run_at(
        character,
        job_type,
        now=now,
        fallback_delay=fallback_delay,
    )


async def _source_still_valid(
    session: AsyncSession,
    candidate: ProactiveCandidate,
) -> bool:
    constraints = _dict(candidate.delivery_constraints_json)
    required = constraints.get("required_source")
    source_version = constraints.get("source_version")
    if required == "continuity_thread":
        if candidate.continuity_thread_id is None:
            return False
        thread = await session.get(ContinuityThread, candidate.continuity_thread_id)
        return bool(
            thread
            and thread.user_id == candidate.user_id
            and thread.character_id == candidate.character_id
            and thread.status == "open"
            and (
                not isinstance(source_version, str)
                or source_version == _thread_source_version(thread)
            )
        )
    if required == "journal":
        if candidate.journal_id is None:
            return False
        journal = await session.get(EpisodicJournal, candidate.journal_id)
        return bool(
            journal
            and journal.user_id == candidate.user_id
            and journal.character_id == candidate.character_id
            and journal.scope == "general"
            and (
                not isinstance(source_version, str)
                or source_version == _journal_source_version(journal)
            )
        )
    if required == "memory":
        if candidate.memory_id is None:
            return False
        memory = await session.get(MemoryItem, candidate.memory_id)
        return bool(
            memory
            and memory.user_id == candidate.user_id
            and memory.character_id == candidate.character_id
            and memory.scope == "general"
            and memory.lifecycle_state == "active"
            and memory.sensitivity == "standard"
            and (
                not isinstance(source_version, str)
                or source_version == memory_source_version(memory)
            )
        )
    if required == "relationship_milestone":
        if candidate.relationship_event_id is None:
            return False
        event = await session.get(RelationshipEvent, candidate.relationship_event_id)
        relationship = await _relationship_state_by_ids(
            session,
            candidate.user_id,
            candidate.character_id,
        )
        milestone_id = str(constraints.get("milestone_id") or "")
        if (
            not milestone_id
            or relationship is None
            or event is None
            or event.user_id != candidate.user_id
            or event.character_id != candidate.character_id
            or event.scope != "general"
            or event.event_type != "milestone"
            or _dict(event.metadata_json).get("milestone_id") != milestone_id
        ):
            return False
        metadata = _dict(relationship.metadata_json)
        noted = _string_set(metadata.get("proactive_milestones_noted"))
        return milestone_id not in noted
    if candidate.source_message_id is None:
        return False
    message = await session.get(Message, candidate.source_message_id)
    return bool(
        message
        and message.conversation_id == candidate.conversation_id
        and not message_is_private(message)
        and not _message_is_adult(message)
        and (
            not isinstance(source_version, str)
            or source_version == _source_fingerprint(message.content, _message_is_adult(message))
        )
    )


def memory_source_version(memory: MemoryItem) -> str:
    return _source_fingerprint(
        memory.content,
        memory.scope,
        memory.lifecycle_state,
        memory.sensitivity,
        memory.memory_type,
        memory.importance,
        memory.confidence,
        memory.emotional_weight,
    )


def _thread_source_version(thread: ContinuityThread) -> str:
    return _source_fingerprint(
        thread.content,
        thread.thread_kind,
        thread.status,
        thread.salience,
        thread.confidence,
    )


def _journal_source_version(journal: EpisodicJournal) -> str:
    return _source_fingerprint(
        journal.scope,
        journal.journal_type,
        journal.title,
        journal.summary,
        journal.emotional_tags_json,
        journal.unresolved_threads_json,
        journal.callbacks_json,
        journal.importance,
    )


def _source_fingerprint(*parts: object) -> str:
    serialized = json.dumps(parts, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _proactive_sensitivity(*values: str) -> Literal["standard", "sensitive"]:
    combined = " ".join(value for value in values if isinstance(value, str))
    if classify_memory_sensitivity(combined) == "sensitive":
        return "sensitive"
    return "sensitive" if SENSITIVE_PROACTIVE_RE.search(combined) else "standard"


async def _record_event(
    session: AsyncSession,
    candidate: ProactiveCandidate,
    *,
    from_state: str | None,
    to_state: str,
    reason_code: str,
    metadata: dict[str, object] | None = None,
) -> None:
    session.add(
        ProactiveCandidateEvent(
            candidate_id=candidate.id,
            from_state=from_state,
            to_state=to_state,
            reason_code=reason_code[:80],
            metadata_json=metadata or {},
        )
    )


async def _latest_stateful_message(
    session: AsyncSession,
    conversation_id: uuid.UUID,
) -> Message | None:
    return (
        await session.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role.in_(("user", "assistant")),
            )
            .order_by(desc(Message.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()


async def _latest_general_journal(
    session: AsyncSession,
    conversation: Conversation,
) -> EpisodicJournal | None:
    return (
        await session.execute(
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
    ).scalar_one_or_none()


async def _relationship_state(
    session: AsyncSession,
    conversation: Conversation,
) -> RelationshipState | None:
    return await _relationship_state_by_ids(
        session,
        conversation.user_id,
        conversation.character_id,
    )


async def _relationship_state_by_ids(
    session: AsyncSession,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
) -> RelationshipState | None:
    return (
        await session.execute(
            select(RelationshipState).where(
                RelationshipState.user_id == user_id,
                RelationshipState.character_id == character_id,
            )
        )
    ).scalar_one_or_none()


async def _unnoted_milestone(
    session: AsyncSession,
    conversation: Conversation,
    relationship: RelationshipState | None,
) -> tuple[str, RelationshipEvent | None] | None:
    if relationship is None:
        return None
    metadata = _dict(relationship.metadata_json)
    timeline = metadata.get("timeline")
    if not isinstance(timeline, list):
        return None
    noted = _string_set(metadata.get("proactive_milestones_noted"))
    for item in reversed(timeline):
        if not isinstance(item, dict) or item.get("kind") != "milestone":
            continue
        milestone_id = str(item.get("milestone_id") or "").strip()
        if not milestone_id or milestone_id in noted:
            continue
        event = None
        raw_event_id = item.get("relationship_event_id")
        if isinstance(raw_event_id, str):
            try:
                event = await session.get(RelationshipEvent, uuid.UUID(raw_event_id))
            except ValueError:
                event = None
        if (
            event is None
            or event.user_id != conversation.user_id
            or event.character_id != conversation.character_id
            or event.scope != "general"
            or event.event_type != "milestone"
            or _dict(event.metadata_json).get("milestone_id") != milestone_id
        ):
            event = (
                await session.execute(
                    select(RelationshipEvent)
                    .where(
                        RelationshipEvent.user_id == conversation.user_id,
                        RelationshipEvent.character_id == conversation.character_id,
                        RelationshipEvent.scope == "general",
                        RelationshipEvent.event_type == "milestone",
                        RelationshipEvent.metadata_json["milestone_id"].as_string() == milestone_id,
                    )
                    .order_by(desc(RelationshipEvent.occurred_at))
                    .limit(1)
                )
            ).scalar_one_or_none()
        if event is not None:
            return milestone_id, event
    return None


def _candidate_key(
    conversation_id: uuid.UUID,
    job_type: str,
    evidence: CandidateEvidence,
) -> str:
    source_id = (
        evidence.continuity_thread_id
        or evidence.journal_id
        or evidence.relationship_event_id
        or evidence.source_message_id
        or conversation_id
    )
    material = (
        f"{conversation_id}:{job_type}:{source_id}:{evidence.source_version}:"
        f"{evidence.candidate_type}"
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _candidate_expiry(candidate_type: str, run_at: datetime) -> datetime:
    lifespan = {
        "check_in": timedelta(days=2),
        "queued_thought": timedelta(days=1),
        "routine": timedelta(hours=8),
        "reminder": timedelta(days=7),
        "milestone": timedelta(days=7),
        "callback": timedelta(days=4),
        "follow_up": timedelta(days=5),
        "suggestion": timedelta(days=4),
        "return": timedelta(days=1),
    }.get(candidate_type, timedelta(days=2))
    return run_at + lifespan


def _local_day_start(character: Character, now: datetime) -> datetime:
    from app.services.proactive import proactive_clock

    clock = proactive_clock(character)
    local_now = now.astimezone(clock.timezone)
    local_start = datetime.combine(local_now.date(), time(), tzinfo=clock.timezone)
    return local_start.astimezone(UTC)


def _reminder_due_at(
    character: Character,
    content: str,
    now: datetime,
) -> datetime | None:
    from app.services.proactive import proactive_clock

    normalized = " ".join(content.casefold().split())
    if not normalized:
        return None
    clock = proactive_clock(character)
    local_now = now.astimezone(clock.timezone)
    target_date = local_now.date()
    default_hour = 10
    default_minute = 0

    if "tomorrow" in normalized:
        target_date += timedelta(days=1)
    elif "next week" in normalized:
        target_date += timedelta(days=7)
    elif "this weekend" in normalized:
        days_until_saturday = (5 - local_now.weekday()) % 7
        target_date += timedelta(days=days_until_saturday or 7)
    elif "this evening" in normalized or "after work" in normalized:
        default_hour = 18
        if local_now.hour >= default_hour:
            target_date += timedelta(days=1)
    elif "later today" in normalized:
        return now + timedelta(hours=4)
    else:
        weekdays = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        matched_weekday = next(
            (value for label, value in weekdays.items() if f" on {label}" in normalized),
            None,
        )
        if matched_weekday is not None:
            day_delta = (matched_weekday - local_now.weekday()) % 7
            target_date += timedelta(days=day_delta or 7)

    clock_match = re.search(
        r"\b(?:at|around)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b",
        normalized,
    )
    if clock_match:
        hour = int(clock_match.group(1))
        minute = int(clock_match.group(2) or "0")
        meridiem = clock_match.group(3)
        if minute > 59 or hour > (12 if meridiem else 23) or hour == 0 and meridiem:
            return None
        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        default_hour = hour
        default_minute = minute

    local_due = datetime.combine(
        target_date,
        time(default_hour, default_minute),
        tzinfo=clock.timezone,
    )
    due = local_due.astimezone(UTC)
    if due <= now:
        due = (local_due + timedelta(days=1)).astimezone(UTC)
    return due


def _message_is_adult(message: Message) -> bool:
    return _dict(message.metadata_json).get("content_mode") == "adult"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed) if parsed.tzinfo is not None else None


def _dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _string_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item).strip() for item in value if isinstance(item, str) and str(item).strip()}


def _bounded_float(value: object, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, 0.0), 1.0)


def _bounded_int(
    value: object,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


def _suppressed(candidate: ProactiveCandidate, reason: str) -> CandidateDeliveryResult:
    return CandidateDeliveryResult(
        status="suppressed",
        candidate=candidate,
        reason=reason,
    )
