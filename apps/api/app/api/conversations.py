from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user, require_conversation
from app.models import Conversation, Message, User
from app.schemas import (
    ConversationCreate,
    ConversationOut,
    DeleteResponse,
    MessageOut,
    MessageUpdate,
)
from app.services.chat import create_conversation
from app.services.safety import validate_user_content

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Conversation]:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.created_at)
    )
    return list(result.scalars().all())


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation_endpoint(
    payload: ConversationCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Conversation:
    conversation = await create_conversation(
        session,
        user,
        character_id=payload.character_id,
        title=payload.title,
    )
    await session.commit()
    await session.refresh(conversation)
    return conversation


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conversation_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Message]:
    await require_conversation(conversation_id, user, session)
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return list(result.scalars().all())


@router.get("/{conversation_id}/search", response_model=list[MessageOut])
async def search_messages(
    conversation_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str = Query(min_length=1, max_length=120),
    limit: int = Query(default=20, ge=1, le=50),
) -> list[Message]:
    await require_conversation(conversation_id, user, session)
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.content.ilike(f"%{q}%"))
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


@router.patch("/{conversation_id}/messages/{message_id}", response_model=MessageOut)
async def edit_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    payload: MessageUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Message:
    conversation = await require_conversation(conversation_id, user, session)
    validate_user_content(payload.content)
    result = await session.execute(
        select(Message).where(
            Message.id == message_id,
            Message.conversation_id == conversation.id,
            Message.role == "user",
        )
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=404, detail="Editable user message was not found.")
    message.content = payload.content
    message.metadata_json = {
        **(message.metadata_json or {}),
        "edited": True,
        "edit_note": "User edited this message after sending.",
    }
    await session.commit()
    await session.refresh(message)
    return message


@router.delete("/{conversation_id}/messages", response_model=DeleteResponse)
async def clear_conversation_messages(
    conversation_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeleteResponse:
    conversation = await require_conversation(conversation_id, user, session)
    result = await session.execute(
        delete(Message).where(Message.conversation_id == conversation.id)
    )
    await session.commit()
    return DeleteResponse(deleted=int(result.rowcount or 0))


@router.delete("/{conversation_id}", response_model=DeleteResponse)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeleteResponse:
    conversation = await require_conversation(conversation_id, user, session)
    await session.delete(conversation)
    await session.commit()
    return DeleteResponse(deleted=1)
