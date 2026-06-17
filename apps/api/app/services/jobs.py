from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ScheduledJob, utc_now


async def create_job(
    session: AsyncSession,
    *,
    job_type: str,
    run_at: datetime,
    user_id: uuid.UUID | None = None,
    character_id: uuid.UUID | None = None,
    payload_json: dict | None = None,
) -> ScheduledJob:
    job = ScheduledJob(
        user_id=user_id,
        character_id=character_id,
        job_type=job_type,
        run_at=run_at,
        status="pending",
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
    statement = (
        select(ScheduledJob)
        .where(ScheduledJob.status == "pending", ScheduledJob.run_at <= utc_now())
        .order_by(ScheduledJob.run_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(statement)
    jobs = list(result.scalars().all())
    for job in jobs:
        job.status = "running"
        job.locked_at = utc_now()
        job.locked_by = worker_id
    await session.flush()
    return jobs


async def mark_job_done(session: AsyncSession, job: ScheduledJob) -> ScheduledJob:
    job.status = "done"
    job.last_error = None
    await session.flush()
    return job


async def mark_job_failed(session: AsyncSession, job: ScheduledJob, error: str) -> ScheduledJob:
    job.status = "failed"
    job.retry_count += 1
    job.last_error = error[:1000]
    await session.flush()
    return job
