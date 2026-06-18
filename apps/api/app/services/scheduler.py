from __future__ import annotations

import logging
import os
import socket
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.session import AsyncSessionLocal
from app.models import Conversation, Message, ScheduledJob, utc_now
from app.services.jobs import claim_due_jobs, mark_job_done, mark_job_failed
from app.services.memory import maybe_extract_memory
from app.services.proactive import (
    PROACTIVE_JOB_SCHEDULES,
    create_inactivity_proactive_message,
)
from app.services.relationship import ensure_relationship_decay_job, get_current_relationship

logger = logging.getLogger(__name__)

PROACTIVE_JOB_TYPES = set(PROACTIVE_JOB_SCHEDULES) | {"proactive_message_create"}


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
        try:
            await _run_job(session, job, runtime_settings)
            await mark_job_done(session, job)
        except ValueError as exc:
            await mark_job_failed(session, job, str(exc))
        except Exception:  # noqa: BLE001 - failed job rows need safe, deterministic state
            await mark_job_failed(session, job, "Job failed during execution.")
    return len(jobs)


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
    conversation = await _conversation_from_job(session, job)
    payload = job.payload_json or {}
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
        proactive_type=str(payload.get("proactive_type") or job.job_type),
    )
    if message is None:
        _merge_payload(job, {"result": "skipped_by_cooldown_or_state"})
        return
    _merge_payload(
        job,
        {
            "result": "message_created",
            "message_id": str(message.id),
            "proactive_type": message.metadata_json.get("proactive_type"),
        },
    )


async def _run_memory_extract_job(session: AsyncSession, job: ScheduledJob) -> None:
    if job.user_id is None or job.character_id is None:
        raise ValueError("Memory extract job is missing user or character.")
    messages = await _memory_extract_messages(session, job)
    extracted = 0
    skipped = 0
    for message in messages:
        memory = await maybe_extract_memory(
            session,
            user_id=job.user_id,
            character_id=job.character_id,
            message_id=message.id,
            content=message.content,
        )
        if memory is None:
            skipped += 1
        else:
            extracted += 1
    _merge_payload(
        job,
        {
            "result": "memory_extract_complete",
            "messages_checked": len(messages),
            "extracted_count": extracted,
            "skipped_count": skipped,
        },
    )


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


async def _memory_extract_messages(session: AsyncSession, job: ScheduledJob) -> list[Message]:
    payload = job.payload_json or {}
    if payload.get("message_id"):
        message = await _message_from_job(session, job)
        return [message]

    conversation = await _conversation_from_job(session, job)
    limit = _positive_int(payload.get("limit"), default=20)
    result = await session.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role == "user",
        )
        .order_by(desc(Message.created_at))
        .limit(min(limit, 50))
    )
    return list(reversed(result.scalars().all()))


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


def _merge_payload(job: ScheduledJob, updates: dict[str, object]) -> None:
    job.payload_json = {**(job.payload_json or {}), **updates}


def _worker_id() -> str:
    return f"api:{socket.gethostname()}:{os.getpid()}"
