from __future__ import annotations

import logging
import os
import socket
import uuid
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import desc, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.session import AsyncSessionLocal
from app.llm.factory import get_llm_provider
from app.models import Character, Conversation, MemoryItem, Message, ScheduledJob, User, utc_now
from app.services.cognition import analyze_completed_turn, apply_cognition_report
from app.services.continuity import sync_continuity_from_message
from app.services.conversation_privacy import conversation_is_private, message_is_private
from app.services.jobs import (
    claim_due_jobs,
    create_job,
    mark_job_deferred,
    mark_job_done,
    mark_job_failed,
    mark_job_retry,
)
from app.services.journal import maybe_create_journal_from_conversation
from app.services.memory import (
    analyze_memory_candidate,
    maintain_memories,
    maybe_extract_memory,
    memory_preferences_from_boundaries,
)
from app.services.proactive import (
    LOCAL_NOTE_TIME_KEYS,
    PROACTIVE_JOB_SCHEDULES,
    create_inactivity_proactive_message,
    ensure_proactive_jobs,
    proactive_block_reason,
    proactive_deferred_until,
    proactive_relationship_delivery_block,
)
from app.services.proactive_presence import (
    PROACTIVE_DELIVERY_JOB,
    deliver_proactive_candidate,
    fail_candidate,
)
from app.services.relationship import (
    ensure_relationship_decay_job,
    get_current_relationship,
    refine_relationship_from_evidence,
)

logger = logging.getLogger(__name__)

PROACTIVE_JOB_TYPES = set(PROACTIVE_JOB_SCHEDULES) | {
    "proactive_message_create",
    PROACTIVE_DELIVERY_JOB,
}
SCHEDULER_ADVISORY_LOCK_KEY = 0x4549444F4C4F4E


class ScheduledJobDeferred(Exception):
    def __init__(self, *, run_at: datetime, reason: str) -> None:
        super().__init__(reason)
        self.run_at = run_at
        self.reason = reason


async def process_due_jobs(
    session: AsyncSession,
    *,
    worker_id: str,
    settings: Settings | None = None,
    limit: int | None = None,
) -> int:
    runtime_settings = settings or get_settings()
    jobs = await claim_due_jobs(
        session,
        worker_id=worker_id,
        limit=limit or runtime_settings.scheduler_job_limit,
    )
    for job in jobs:
        await _process_claimed_job(session, job, runtime_settings)
    return len(jobs)


async def process_job_by_id(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    settings: Settings | None = None,
) -> bool:
    runtime_settings = settings or get_settings()
    result = await session.execute(
        select(ScheduledJob)
        .where(ScheduledJob.id == job_id, ScheduledJob.status == "pending")
        .with_for_update(skip_locked=True)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return False
    job.status = "running"
    job.locked_at = utc_now()
    job.locked_by = _worker_id()
    await session.flush()
    await _process_claimed_job(session, job, runtime_settings)
    return True


async def run_post_chat_job(job_id: uuid.UUID) -> None:
    """Best-effort immediate processing; the durable pending row remains the fallback."""
    try:
        async with AsyncSessionLocal() as session:
            await process_job_by_id(session, job_id=job_id)
            await session.commit()
    except Exception:  # noqa: BLE001 - chat has already committed successfully
        logger.warning("Post-chat processing will be retried by the durable scheduler.")


def start_background_scheduler(settings: Settings | None = None) -> AsyncIOScheduler:
    runtime_settings = settings or get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _run_scheduler_tick,
        "interval",
        id="eidolon-postgres-jobs",
        seconds=runtime_settings.scheduler_interval_seconds,
        next_run_time=utc_now(),
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        kwargs={"settings": runtime_settings, "worker_id": _worker_id()},
    )
    scheduler.start()
    return scheduler


async def _run_scheduler_tick(*, settings: Settings, worker_id: str) -> None:
    try:
        async with AsyncSessionLocal() as session:
            if not await _acquire_scheduler_tick_lock(session):
                return
            await process_due_jobs(session, worker_id=worker_id, settings=settings)
            await session.commit()
    except Exception:  # noqa: BLE001 - background failures should not crash API startup
        logger.warning("Scheduler tick failed.")


async def _run_job(
    session: AsyncSession,
    job: ScheduledJob,
    settings: Settings,
) -> None:
    if job.job_type == "maintenance_noop":
        _merge_payload(job, {"result": "noop"})
        return
    if job.job_type == "memory_extract":
        await _run_memory_extract_job(session, job)
        return
    if job.job_type == "memory_maintenance":
        await _run_memory_maintenance_job(session, job)
        return
    if job.job_type == "chat_postprocess":
        await _run_chat_postprocess_job(session, job, settings)
        return
    if job.job_type in PROACTIVE_JOB_TYPES:
        await _run_proactive_job(session, job, settings)
        return
    if job.job_type == "relationship_decay":
        await _run_relationship_decay_job(session, job)
        return
    raise ValueError("Unsupported job type.")


async def _run_proactive_job(
    session: AsyncSession,
    job: ScheduledJob,
    settings: Settings,
) -> None:
    candidate_id = _optional_uuid((job.payload_json or {}).get("candidate_id"))
    if candidate_id is not None:
        result = await deliver_proactive_candidate(
            session,
            candidate_id=candidate_id,
            provider=get_llm_provider(settings),
        )
        if result.status == "deferred" and result.deferred_until is not None:
            raise ScheduledJobDeferred(
                run_at=result.deferred_until,
                reason=result.reason or "candidate_deferred",
            )
        _merge_payload(
            job,
            {
                "result": ("message_created" if result.status == "delivered" else result.status),
                "candidate_id": str(result.candidate.id),
                "candidate_state": result.candidate.state,
                "skip_reason": result.reason,
                "message_id": str(result.message.id) if result.message else None,
            },
        )
        return

    conversation = await _conversation_from_job(session, job)
    if conversation_is_private(conversation):
        _merge_payload(
            job,
            {
                "result": "skipped_private_conversation",
                "skip_reason": "conversation_private",
            },
        )
        return
    payload = job.payload_json or {}
    proactive_type = str(payload.get("proactive_type") or job.job_type)
    character = await session.get(Character, conversation.character_id)
    if character is None:
        raise ValueError("Character for scheduled job was not found.")
    now = utc_now()
    block_reason = proactive_block_reason(character, proactive_type, now=now)
    if block_reason is not None:
        _merge_payload(
            job,
            {
                "result": "skipped_by_user_controls",
                "skip_reason": block_reason,
                "proactive_type": proactive_type,
            },
        )
        return
    relationship_block = await proactive_relationship_delivery_block(
        session,
        conversation,
        proactive_type,
    )
    if relationship_block is not None:
        _merge_payload(
            job,
            {
                "result": "skipped_by_relationship_state",
                "skip_reason": f"relationship_{relationship_block.key}",
                "relationship_posture": relationship_block.key,
                "proactive_type": proactive_type,
            },
        )
        return
    if proactive_type in LOCAL_NOTE_TIME_KEYS or payload.get("respect_local_time") is True:
        deferred = proactive_deferred_until(character, proactive_type, now=now)
        if deferred is not None:
            run_at, reason = deferred
            raise ScheduledJobDeferred(run_at=run_at, reason=reason)
    latest_message = await _latest_conversation_message(session, conversation)
    if latest_message is not None and message_is_private(latest_message):
        _merge_payload(
            job,
            {
                "result": "skipped_private_turn",
                "skip_reason": "latest_turn_private",
                "proactive_type": proactive_type,
            },
        )
        return
    if _user_returned_after_job(job, latest_message):
        _merge_payload(
            job,
            {
                "result": "skipped_user_returned",
                "skip_reason": "user_returned",
                "proactive_type": proactive_type,
            },
        )
        return
    message = await create_inactivity_proactive_message(
        session,
        conversation,
        inactivity_hours=_positive_int(
            payload.get("inactivity_hours"),
            default=settings.proactive_inactivity_hours,
        ),
        cooldown_hours=_positive_int(
            payload.get("cooldown_hours"),
            default=settings.proactive_cooldown_hours,
        ),
        force=_bool_payload(payload.get("force"), default=True),
        proactive_type=proactive_type,
        provider=get_llm_provider(settings),
        continuity_thread_id=_optional_uuid(payload.get("continuity_thread_id")),
    )
    if message is None:
        _merge_payload(job, {"result": "skipped_by_cooldown_or_state"})
        return
    _merge_payload(
        job,
        {
            "result": "message_created",
            "defer_reason": None,
            "deferred_until": None,
            "message_id": str(message.id),
            "proactive_type": message.metadata_json.get("proactive_type"),
            "relationship_posture": message.metadata_json.get("relationship_posture"),
            "generation_source": message.metadata_json.get("generation_source"),
            "generation_reason": message.metadata_json.get("generation_reason"),
        },
    )


async def _run_memory_extract_job(session: AsyncSession, job: ScheduledJob) -> None:
    if job.user_id is None or job.character_id is None:
        raise ValueError("Memory extract job is missing user or character.")
    character = await session.get(Character, job.character_id)
    if character is None:
        raise ValueError("Character for memory extract job was not found.")
    memory_preferences = memory_preferences_from_boundaries(character.boundaries_json)
    messages = await _memory_extract_messages(session, job)
    extracted = 0
    skipped = 0
    accepted_types: dict[str, int] = {}
    skip_reasons: dict[str, int] = {}
    for message in messages:
        decision = analyze_memory_candidate(
            message.content,
            memory_preferences=memory_preferences,
        )
        memory = await maybe_extract_memory(
            session,
            user_id=job.user_id,
            character_id=job.character_id,
            message_id=message.id,
            content=message.content,
            memory_preferences=memory_preferences,
            scope=(
                "adult"
                if (message.metadata_json or {}).get("content_mode") == "adult"
                else "general"
            ),
        )
        if memory is None:
            skipped += 1
            _increment_count(skip_reasons, decision.reason)
        else:
            extracted += 1
            _increment_count(accepted_types, memory.memory_type)
    _merge_payload(
        job,
        {
            "result": "memory_extract_complete",
            "messages_checked": len(messages),
            "extracted_count": extracted,
            "skipped_count": skipped,
            "accepted_types": accepted_types,
            "skip_reasons": skip_reasons,
        },
    )


async def _run_chat_postprocess_job(
    session: AsyncSession,
    job: ScheduledJob,
    settings: Settings,
) -> None:
    if job.user_id is None or job.character_id is None:
        raise ValueError("Post-chat job is missing user or character.")
    conversation = await _conversation_from_job(session, job)
    character = await session.get(Character, job.character_id)
    user = await session.get(User, job.user_id)
    if character is None or user is None:
        raise ValueError("Post-chat job owner or character was not found.")
    payload = job.payload_json if isinstance(job.payload_json, dict) else {}
    source_message = await _message_from_job(session, job)
    assistant_message = await _assistant_from_job(session, job)
    scope = (
        "adult"
        if (source_message.metadata_json or {}).get("content_mode") == "adult"
        else "general"
    )
    cognition_allowed = payload.get("memory_allowed") is True and settings.cognition_mode != "off"
    analysis = None
    application = None
    relationship_changed = False
    if cognition_allowed and get_llm_provider(settings).name != "mock":
        selected_memories = await _selected_cognition_memories(
            session,
            source_message=source_message,
            user_id=user.id,
            character_id=character.id,
            scope=scope,
        )
        analysis = await analyze_completed_turn(
            provider=get_llm_provider(settings),
            user_message=source_message,
            assistant_message=assistant_message,
            recent_messages=await _recent_cognition_messages(
                session,
                conversation_id=conversation.id,
                source_message=source_message,
            ),
            selected_memories=selected_memories,
            mode=settings.cognition_mode,
            max_output_tokens=settings.cognition_max_output_tokens,
        )
        if analysis.report is not None:
            application = await apply_cognition_report(
                session,
                report=analysis.report,
                user_id=user.id,
                character_id=character.id,
                conversation_id=conversation.id,
                user_message=source_message,
                assistant_message=assistant_message,
                scope=scope,
                memory_preferences=memory_preferences_from_boundaries(character.boundaries_json),
            )
            if scope == "general":
                relationship_changed = await refine_relationship_from_evidence(
                    session,
                    user_id=user.id,
                    character_id=character.id,
                    source_message=source_message,
                    evidence=application.relationship_evidence,
                )

    deterministic_fallback = payload.get("memory_allowed") is True and (
        settings.cognition_mode == "off"
        or get_llm_provider(settings).name == "mock"
        or (analysis is not None and analysis.source == "degraded")
    )
    if deterministic_fallback:
        await _run_memory_extract_job(session, job)
    elif payload.get("memory_allowed") is not True:
        _merge_payload(
            job,
            {
                "memory_result": "skipped_by_privacy_or_profile",
                "messages_checked": 0,
                "extracted_count": 0,
            },
        )
    continuity_result = await sync_continuity_from_message(
        session,
        user_id=user.id,
        character=character,
        conversation=conversation,
        message=source_message,
    )
    journal = None
    if deterministic_fallback:
        journal = await maybe_create_journal_from_conversation(
            session,
            user=user,
            character=character,
            conversation=conversation,
        )
    if scope == "general":
        await ensure_proactive_jobs(
            session,
            conversation=conversation,
            user_id=user.id,
            character_id=character.id,
        )
    if payload.get("memory_allowed") is True:
        await ensure_memory_maintenance_job(
            session,
            user_id=user.id,
            character_id=character.id,
        )
    receipt_state = (
        "ready"
        if application is not None
        else "degraded"
        if analysis is not None and analysis.source == "degraded"
        else "skipped"
    )
    receipt_labels = list(application.change_labels if application else ())
    if relationship_changed and "relationship" not in receipt_labels:
        receipt_labels.append("relationship")
    receipt = {
        "state": receipt_state,
        "memory_ids": [
            str(memory_id) for memory_id in (application.memory_ids if application else ())
        ],
        "moment_id": str(application.moment_id) if application and application.moment_id else None,
        "change_labels": receipt_labels,
    }
    assistant_message.metadata_json = {
        **(assistant_message.metadata_json or {}),
        "continuity_receipt": receipt,
    }
    _merge_payload(
        job,
        {
            "result": "chat_postprocess_complete",
            "journal_id": (
                str(application.moment_id)
                if application is not None and application.moment_id is not None
                else str(journal.id)
                if journal is not None
                else None
            ),
            "continuity": continuity_result.safe_metadata(),
            "cognition_source": analysis.source if analysis is not None else "deterministic",
            "cognition_failure": analysis.failure_code if analysis is not None else None,
            "cognition_usage": _safe_token_usage(analysis.usage if analysis is not None else None),
            "continuity_receipt": receipt,
        },
    )


async def _run_memory_maintenance_job(session: AsyncSession, job: ScheduledJob) -> None:
    if job.user_id is None or job.character_id is None:
        raise ValueError("Memory maintenance job is missing user or character.")
    result = await maintain_memories(
        session,
        job.user_id,
        job.character_id,
    )
    _merge_payload(
        job,
        {
            "result": "memory_maintenance_complete",
            "reviewed_count": result.reviewed,
            "consolidated_count": result.consolidated,
            "faded_count": result.faded,
        },
    )
    await ensure_memory_maintenance_job(
        session,
        user_id=job.user_id,
        character_id=job.character_id,
        exclude_job_id=job.id,
    )


async def ensure_memory_maintenance_job(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    exclude_job_id: uuid.UUID | None = None,
) -> ScheduledJob:
    statement = (
        select(ScheduledJob)
        .where(
            ScheduledJob.user_id == user_id,
            ScheduledJob.character_id == character_id,
            ScheduledJob.job_type == "memory_maintenance",
            ScheduledJob.status.in_(("pending", "running")),
        )
        .order_by(ScheduledJob.run_at.asc(), ScheduledJob.id.asc())
        .limit(1)
    )
    if exclude_job_id is not None:
        statement = statement.where(ScheduledJob.id != exclude_job_id)
    existing = (await session.execute(statement)).scalar_one_or_none()
    if existing is not None:
        return existing
    return await create_job(
        session,
        job_type="memory_maintenance",
        run_at=utc_now() + timedelta(hours=24),
        user_id=user_id,
        character_id=character_id,
        payload_json={"reason": "living_memory_lifecycle"},
    )


async def _process_claimed_job(
    session: AsyncSession,
    job: ScheduledJob,
    settings: Settings,
) -> None:
    try:
        async with session.begin_nested():
            await _run_job(session, job, settings)
        await mark_job_done(session, job)
    except ScheduledJobDeferred as exc:
        payload = job.payload_json if isinstance(job.payload_json, dict) else {}
        raw_count = payload.get("deferred_count", 0)
        deferred_count = raw_count if isinstance(raw_count, int) and raw_count >= 0 else 0
        _merge_payload(
            job,
            {
                "result": "deferred_for_local_time",
                "defer_reason": exc.reason,
                "deferred_count": deferred_count + 1,
                "deferred_until": exc.run_at.isoformat(),
            },
        )
        await mark_job_deferred(session, job, run_at=exc.run_at)
    except ValueError as exc:
        await _mark_post_chat_receipt_degraded(session, job)
        await _mark_proactive_candidate_failed(session, job, "invalid_delivery_state")
        await mark_job_failed(session, job, str(exc))
    except Exception:  # noqa: BLE001 - failed job rows need safe, deterministic state
        logger.warning("Scheduled job %s failed unexpectedly.", job.id)
        if job.retry_count < settings.scheduler_max_retries:
            retry_delay = _retry_delay_seconds(job.retry_count, settings)
            await mark_job_retry(
                session,
                job,
                error="Transient job failure; retry scheduled.",
                run_at=utc_now() + timedelta(seconds=retry_delay),
            )
        else:
            await _mark_post_chat_receipt_degraded(session, job)
            await _mark_proactive_candidate_failed(session, job, "delivery_dead_lettered")
            await mark_job_failed(session, job, "Job failed during execution.")


async def _mark_proactive_candidate_failed(
    session: AsyncSession,
    job: ScheduledJob,
    reason_code: str,
) -> None:
    candidate_id = _optional_uuid((job.payload_json or {}).get("candidate_id"))
    if candidate_id is None:
        return
    from app.models import ProactiveCandidate

    candidate = await session.get(ProactiveCandidate, candidate_id)
    if candidate is None or candidate.state not in {"candidate", "scheduled", "generated"}:
        return
    await fail_candidate(session, candidate, reason_code)


async def _mark_post_chat_receipt_degraded(
    session: AsyncSession,
    job: ScheduledJob,
) -> None:
    if job.job_type != "chat_postprocess":
        return
    receipt = {
        "state": "degraded",
        "memory_ids": [],
        "moment_id": None,
        "change_labels": [],
    }
    _merge_payload(job, {"continuity_receipt": receipt})
    try:
        assistant_message = await _assistant_from_job(session, job)
    except ValueError:
        return
    assistant_message.metadata_json = {
        **(assistant_message.metadata_json or {}),
        "continuity_receipt": receipt,
    }


async def _run_relationship_decay_job(session: AsyncSession, job: ScheduledJob) -> None:
    if job.user_id is None or job.character_id is None:
        raise ValueError("Relationship decay job is missing user or character.")
    relationship = await get_current_relationship(session, job.user_id, job.character_id)
    timeline = (relationship.metadata_json or {}).get("timeline", [])
    _merge_payload(
        job,
        {
            "result": "relationship_decay_applied",
            "mood": relationship.mood,
            "conflict_state": relationship.conflict_state,
            "timeline_events": len(timeline),
        },
    )
    await ensure_relationship_decay_job(
        session,
        job.user_id,
        job.character_id,
        exclude_job_id=job.id,
    )


async def _conversation_from_job(
    session: AsyncSession,
    job: ScheduledJob,
) -> Conversation:
    conversation_id = _conversation_id(job)
    statement = select(Conversation).where(Conversation.id == conversation_id)
    if job.user_id is not None:
        statement = statement.where(Conversation.user_id == job.user_id)
    if job.character_id is not None:
        statement = statement.where(Conversation.character_id == job.character_id)
    result = await session.execute(statement)
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise ValueError("Conversation for scheduled job was not found.")
    return conversation


async def _latest_conversation_message(
    session: AsyncSession,
    conversation: Conversation,
) -> Message | None:
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(desc(Message.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


def _user_returned_after_job(job: ScheduledJob, latest_message: Message | None) -> bool:
    if latest_message is None or latest_message.role != "user":
        return False
    return latest_message.created_at > job.created_at


async def _memory_extract_messages(session: AsyncSession, job: ScheduledJob) -> list[Message]:
    payload = job.payload_json or {}
    if payload.get("message_id"):
        message = await _message_from_job(session, job)
        conversation = await _conversation_from_job(session, job)
        if conversation_is_private(conversation) or message_is_private(message):
            return []
        return [message]

    conversation = await _conversation_from_job(session, job)
    if conversation_is_private(conversation):
        return []
    limit = _positive_int(payload.get("limit"), default=20)
    message_privacy = Message.metadata_json["privacy_mode"].as_string()
    result = await session.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role == "user",
            or_(message_privacy.is_(None), message_privacy != "private"),
        )
        .order_by(desc(Message.created_at))
        .limit(min(limit, 50))
    )
    return list(reversed(result.scalars().all()))


async def _assistant_from_job(session: AsyncSession, job: ScheduledJob) -> Message:
    value = (job.payload_json or {}).get("assistant_message_id")
    try:
        assistant_message_id = uuid.UUID(str(value))
    except ValueError as exc:
        raise ValueError("Post-chat job is missing a valid assistant message.") from exc
    conversation_id = _conversation_id(job)
    result = await session.execute(
        select(Message).where(
            Message.id == assistant_message_id,
            Message.conversation_id == conversation_id,
            Message.role == "assistant",
        )
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise ValueError("Assistant message for post-chat cognition was not found.")
    return message


async def _recent_cognition_messages(
    session: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    source_message: Message,
) -> list[Message]:
    result = await session.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.created_at <= source_message.created_at,
            Message.role.in_(("user", "assistant")),
        )
        .order_by(desc(Message.created_at))
        .limit(8)
    )
    return [
        message for message in reversed(result.scalars().all()) if not message_is_private(message)
    ]


async def _selected_cognition_memories(
    session: AsyncSession,
    *,
    source_message: Message,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    scope: str,
) -> list[MemoryItem]:
    manifest = (source_message.metadata_json or {}).get("_prompt_context")
    raw_items = manifest.get("memory_items") if isinstance(manifest, dict) else None
    selected_ids: list[uuid.UUID] = []
    if isinstance(raw_items, list):
        for item in raw_items[:12]:
            if not isinstance(item, dict):
                continue
            value = item.get("id")
            try:
                selected_ids.append(uuid.UUID(str(value)))
            except ValueError:
                continue
    if not selected_ids:
        return []
    readable_scopes = ("general", "adult") if scope == "adult" else ("general",)
    result = await session.execute(
        select(MemoryItem).where(
            MemoryItem.id.in_(selected_ids),
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
            MemoryItem.scope.in_(readable_scopes),
            MemoryItem.forgotten_at.is_(None),
        )
    )
    by_id = {memory.id: memory for memory in result.scalars().all()}
    return [by_id[memory_id] for memory_id in selected_ids if memory_id in by_id]


def _safe_token_usage(usage) -> dict[str, int | None]:
    if usage is None:
        return {"input_tokens": None, "output_tokens": None, "total_tokens": None}
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
    }


async def _message_from_job(session: AsyncSession, job: ScheduledJob) -> Message:
    message_id = _message_id(job)
    conversation_id = _conversation_id(job)
    result = await session.execute(
        select(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Message.id == message_id,
            Message.conversation_id == conversation_id,
            Message.role == "user",
            Conversation.user_id == job.user_id,
            Conversation.character_id == job.character_id,
        )
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise ValueError("Message for memory extract job was not found.")
    return message


def _conversation_id(job: ScheduledJob) -> uuid.UUID:
    value = (job.payload_json or {}).get("conversation_id")
    if not value:
        raise ValueError("Scheduled job is missing conversation_id.")
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise ValueError("Scheduled job has an invalid conversation_id.") from exc


def _message_id(job: ScheduledJob) -> uuid.UUID:
    value = (job.payload_json or {}).get("message_id")
    if not value:
        raise ValueError("Memory extract job is missing message_id.")
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise ValueError("Memory extract job has an invalid message_id.") from exc


def _positive_int(value: object, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _bool_payload(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _optional_uuid(value: object) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _increment_count(counts: dict[str, int], key: str | None) -> None:
    label = key or "unknown"
    counts[label] = counts.get(label, 0) + 1


def _merge_payload(job: ScheduledJob, updates: dict[str, object]) -> None:
    job.payload_json = {**(job.payload_json or {}), **updates}


def _worker_id() -> str:
    return f"api:{socket.gethostname()}:{os.getpid()}"


async def _acquire_scheduler_tick_lock(session: AsyncSession) -> bool:
    result = await session.execute(
        text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
        {"lock_key": SCHEDULER_ADVISORY_LOCK_KEY},
    )
    return bool(result.scalar_one())


def _retry_delay_seconds(retry_count: int, settings: Settings) -> int:
    exponent = min(max(retry_count, 0), 8)
    return min(settings.scheduler_retry_base_seconds * (2**exponent), 86_400)
