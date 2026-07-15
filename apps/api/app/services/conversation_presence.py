from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message
from app.schemas import ConversationOut


def conversation_summary_query() -> Select[tuple[Conversation, datetime | None, int]]:
    last_message_at = (
        select(func.max(Message.created_at))
        .where(Message.conversation_id == Conversation.id)
        .correlate(Conversation)
        .scalar_subquery()
    )
    unread_count = (
        select(func.count(Message.id))
        .where(
            Message.conversation_id == Conversation.id,
            Message.role == "assistant",
            Message.created_at > Conversation.last_read_at,
        )
        .correlate(Conversation)
        .scalar_subquery()
    )
    return select(
        Conversation,
        last_message_at.label("last_message_at"),
        unread_count.label("unread_count"),
    )


async def list_conversation_summaries(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> list[ConversationOut]:
    query = conversation_summary_query().where(Conversation.user_id == user_id)
    rows = (await session.execute(query)).all()
    summaries = [_conversation_out(*row) for row in rows]
    return sorted(
        summaries,
        key=lambda item: item.last_message_at or item.updated_at,
        reverse=True,
    )


async def get_conversation_summary(
    session: AsyncSession,
    conversation: Conversation,
) -> ConversationOut:
    row = (
        await session.execute(
            conversation_summary_query().where(Conversation.id == conversation.id)
        )
    ).one()
    return _conversation_out(*row)


async def advance_read_cursor(
    session: AsyncSession,
    conversation: Conversation,
    *,
    through_message_id: uuid.UUID | None,
) -> bool:
    if through_message_id is None:
        return True
    read_through_at = await session.scalar(
        select(Message.created_at).where(
            Message.id == through_message_id,
            Message.conversation_id == conversation.id,
            Message.role == "assistant",
        )
    )
    if read_through_at is None:
        return False
    await session.execute(
        update(Conversation)
        .where(Conversation.id == conversation.id)
        .values(
            last_read_at=func.greatest(
                Conversation.last_read_at,
                read_through_at,
            )
        )
        .execution_options(synchronize_session=False)
    )
    await session.flush()
    return True


def _conversation_out(
    conversation: Conversation,
    last_message_at: datetime | None,
    unread_count: int,
) -> ConversationOut:
    return ConversationOut.model_validate(conversation).model_copy(
        update={
            "last_message_at": last_message_at,
            "unread_count": max(0, int(unread_count)),
        }
    )
