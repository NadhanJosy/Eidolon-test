from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ScheduledJob, utc_now

STALE_JOB_LOCK_AFTER = timedelta(minutes=15)


async def create_job(
    session: AsyncSession,
    *,
    job_type: str,
    run_at: datetime,
    user_id: uuid.UUID | None = None,
    character_id: uuid.UUID | None = None,
    payload_json: dict | None = None,
    dedupe_key: str | None = None,
    expires_at: datetime | None = None,
) -> ScheduledJob:
    if dedupe_key is not None:
        existing = (
            await session.execute(
                select(ScheduledJob).where(ScheduledJob.dedupe_key == dedupe_key).limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
    job = ScheduledJob(
        user_id=user_id,
        character_id=character_id,
        job_type=job_type,
        run_at=run_at,
        status="pending",
        dedupe_key=dedupe_key,
        expires_at=expires_at,
        payload_json=payload_json or {},
        retry_count=0,
    )
    session.add(job)
    await session.flush()
    return job


async def claim_due_jobs(
    session: AsyncSession,
    *,
    worker_id: str,
    limit: int = 10,
) -> list[ScheduledJob]:
    now = utc_now()
    stale_before = now - STALE_JOB_LOCK_AFTER
    statement = (
        select(ScheduledJob)
        .where(
            ScheduledJob.run_at <= now,
            or_(
                ScheduledJob.status == "pending",
                (
                    (ScheduledJob.status == "running")
                    & (ScheduledJob.locked_at.is_not(None))
                    & (ScheduledJob.locked_at <= stale_before)
                ),
            ),
        )
        .order_by(ScheduledJob.run_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(statement)
    jobs = list(result.scalars().all())
    for job in jobs:
        if job.status == "running":
            job.retry_count += 1
            job.last_error = "Recovered a stale worker lock."
        job.status = "running"
        job.locked_at = now
        job.locked_by = worker_id
    await session.flush()
    return jobs


async def mark_job_done(session: AsyncSession, job: ScheduledJob) -> ScheduledJob:
    job.status = "done"
    job.last_error = None
    _clear_job_lock(job)
    await session.flush()
    return job


async def mark_job_failed(session: AsyncSession, job: ScheduledJob, error: str) -> ScheduledJob:
    job.status = "failed"
    job.retry_count += 1
    job.last_error = error[:1000]
    _clear_job_lock(job)
    await session.flush()
    return job


async def mark_job_cancelled(
    session: AsyncSession,
    job: ScheduledJob,
    *,
    reason: str,
) -> ScheduledJob:
    job.status = "cancelled"
    job.cancelled_at = utc_now()
    job.last_error = reason[:1000]
    _clear_job_lock(job)
    await session.flush()
    return job


async def mark_job_retry(
    session: AsyncSession,
    job: ScheduledJob,
    *,
    error: str,
    run_at: datetime,
) -> ScheduledJob:
    job.status = "pending"
    job.run_at = run_at
    job.retry_count += 1
    job.last_error = error[:1000]
    _clear_job_lock(job)
    await session.flush()
    return job


async def mark_job_deferred(
    session: AsyncSession,
    job: ScheduledJob,
    *,
    run_at: datetime,
) -> ScheduledJob:
    job.status = "pending"
    job.run_at = run_at
    job.last_error = None
    _clear_job_lock(job)
    await session.flush()
    return job


def _clear_job_lock(job: ScheduledJob) -> None:
    job.locked_at = None
    job.locked_by = None
