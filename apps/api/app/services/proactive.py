from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message, ScheduledJob, utc_now
from app.services.jobs import create_job

PROACTIVE_FALLBACK = (
    "I had a small thought and wanted to check in. No pressure to answer quickly; "
    "I am here when you feel like talking."
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
    "proactive_message_create": {
        "label": "manual check-in",
        "content": PROACTIVE_FALLBACK,
        "away_state": "manual_check_in",
    },
}
PROACTIVE_JOB_SCHEDULES = {
    "proactive_inactivity_check": timedelta(hours=24),
    "proactive_morning_check": timedelta(hours=12),
    "proactive_goodnight_check": timedelta(hours=18),
    "proactive_thinking_of_you": timedelta(hours=36),
    "proactive_milestone_check": timedelta(days=3),
    "proactive_unresolved_thread_nudge": timedelta(hours=30),
}


async def create_inactivity_proactive_message(
    session: AsyncSession,
    conversation: Conversation,
    *,
    inactivity_hours: int,
    cooldown_hours: int = 24,
    force: bool = False,
    proactive_type: str = "proactive_inactivity_check",
) -> Message | None:
    latest = await _latest_message(session, conversation.id)
    if latest is None:
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
    message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=variant["content"],
        metadata_json={
            "proactive": True,
            "proactive_type": proactive_type,
            "proactive_label": variant["label"],
            "provider": "system",
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
    await session.flush()
    return message


async def ensure_proactive_jobs(
    session: AsyncSession,
    *,
    conversation: Conversation,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
) -> list[ScheduledJob]:
    created: list[ScheduledJob] = []
    now = utc_now()
    for job_type, delay in PROACTIVE_JOB_SCHEDULES.items():
        if await _pending_job_exists(session, conversation.id, job_type):
            continue
        created.append(
            await create_job(
                session,
                job_type=job_type,
                run_at=now + delay,
                user_id=user_id,
                character_id=character_id,
                payload_json={
                    "conversation_id": str(conversation.id),
                    "cooldown_hours": 24,
                    "proactive_type": job_type,
                    "source": "chat_completion_hook",
                },
            )
        )
    return created


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
