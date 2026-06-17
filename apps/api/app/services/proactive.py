from __future__ import annotations

from datetime import timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message, utc_now

PROACTIVE_FALLBACK = (
    "I had a small thought and wanted to check in. No pressure to answer quickly; "
    "I am here when you feel like talking."
)


async def create_inactivity_proactive_message(
    session: AsyncSession,
    conversation: Conversation,
    *,
    inactivity_hours: int,
    cooldown_hours: int = 24,
    force: bool = False,
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

    message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=PROACTIVE_FALLBACK,
        metadata_json={"proactive": True, "provider": "system", "streaming_complete": True},
    )
    conversation.updated_at = now
    session.add(message)
    await session.flush()
    return message


async def _latest_message(session: AsyncSession, conversation_id) -> Message | None:
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()
