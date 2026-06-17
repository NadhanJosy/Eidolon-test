from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user, require_conversation
from app.llm.factory import get_llm_provider
from app.models import User
from app.schemas import ChatRequest, ChatResponse, MessageOut
from app.services.chat import complete_assistant_message, prepare_user_message, run_chat

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/messages", response_model=ChatResponse)
async def chat_message(
    payload: ChatRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChatResponse:
    conversation = await require_conversation(payload.conversation_id, user, session)
    user_message, assistant_message = await run_chat(
        session,
        user=user,
        conversation=conversation,
        content=payload.content,
        requested_mode=payload.content_mode,
        provider=get_llm_provider(),
    )
    return ChatResponse(
        user_message=MessageOut.model_validate(user_message),
        assistant_message=MessageOut.model_validate(assistant_message),
    )


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    conversation = await require_conversation(payload.conversation_id, user, session)
    provider = get_llm_provider()

    async def event_stream():
        try:
            user_message, character, prompt = await prepare_user_message(
                session,
                user,
                conversation,
                payload.content,
                payload.content_mode,
            )
            await session.commit()
            await session.refresh(user_message)
            yield sse("message_start", {"user_message": dump_message(user_message)})

            chunks: list[str] = []
            async for chunk in provider.stream(prompt.prompt):
                chunks.append(chunk)
                yield sse("token", {"content": chunk})

            assistant_message = await complete_assistant_message(
                session,
                user=user,
                conversation=conversation,
                character=character,
                user_message=user_message,
                assistant_content="".join(chunks),
                provider=provider,
                prompt=prompt,
            )
            await session.commit()
            await session.refresh(assistant_message)
            yield sse("message_done", {"assistant_message": dump_message(assistant_message)})
        except Exception:  # noqa: BLE001 - streamed clients need a readable event
            await session.rollback()
            yield sse(
                "error",
                {"detail": "The backend could not finish that reply."},
            )
        finally:
            await session.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def dump_message(message) -> dict:
    return MessageOut.model_validate(message).model_dump(mode="json")
