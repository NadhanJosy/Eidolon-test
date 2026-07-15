from __future__ import annotations

import asyncio
import json
import logging
import uuid
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user, require_conversation
from app.llm.base import (
    LLMGeneration,
    LLMProviderUnavailable,
    TokenUsage,
    public_provider_failure_detail,
)
from app.llm.factory import get_llm_provider
from app.models import User
from app.schemas import ChatRequest, ChatRerollRequest, ChatResponse, MessageOut
from app.services.chat import (
    ChatTurnCancelled,
    complete_assistant_message,
    mark_user_message_generation_failed,
    prepare_retry_user_message,
    prepare_user_message,
    record_prompt_context,
    reroll_assistant_message,
    run_chat,
)
from app.services.diagnostics import record_generation_error
from app.services.scheduler import run_post_chat_job

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/messages", response_model=ChatResponse)
async def chat_message(
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChatResponse:
    if payload.retry_user_message_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Retry incomplete replies through streaming chat.",
        )
    conversation = await require_conversation(payload.conversation_id, user, session)
    provider = get_llm_provider()
    user_id = user.id
    character_id = conversation.character_id
    conversation_id = conversation.id
    try:
        user_message, assistant_message = await run_chat(
            session,
            user=user,
            conversation=conversation,
            content=payload.content,
            requested_mode=payload.content_mode,
            requested_privacy_mode=payload.privacy_mode,
            provider=provider,
        )
    except LLMProviderUnavailable as exc:
        await session.rollback()
        await record_generation_error(
            user_id=user_id,
            character_id=character_id,
            conversation_id=conversation_id,
            operation="message",
            code=diagnostic_code(exc),
            provider=provider.name,
        )
        raise HTTPException(
            status_code=provider_http_status(exc),
            detail=public_provider_failure_detail(exc),
        ) from exc
    except ChatTurnCancelled as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    queue_post_chat_background(background_tasks, assistant_message)
    return ChatResponse(
        user_message=MessageOut.model_validate(user_message),
        assistant_message=MessageOut.model_validate(assistant_message),
    )


@router.post("/reroll", response_model=MessageOut)
async def chat_reroll(
    payload: ChatRerollRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MessageOut:
    conversation = await require_conversation(payload.conversation_id, user, session)
    provider = get_llm_provider()
    user_id = user.id
    character_id = conversation.character_id
    conversation_id = conversation.id
    try:
        message = await reroll_assistant_message(
            session,
            user=user,
            conversation=conversation,
            assistant_message_id=payload.assistant_message_id,
            requested_mode=payload.content_mode,
            provider=provider,
        )
    except LLMProviderUnavailable as exc:
        await session.rollback()
        await record_generation_error(
            user_id=user_id,
            character_id=character_id,
            conversation_id=conversation_id,
            operation="reroll",
            code=diagnostic_code(exc),
            provider=provider.name,
        )
        raise HTTPException(
            status_code=provider_http_status(exc),
            detail=public_provider_failure_detail(exc),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - keep provider defects out of logs/responses
        await session.rollback()
        await record_generation_error(
            user_id=user_id,
            character_id=character_id,
            conversation_id=conversation_id,
            operation="reroll",
            code="generation_failed",
            provider=provider.name,
        )
        raise HTTPException(
            status_code=503,
            detail="The backend could not create an alternate reply. The existing reply is safe.",
        ) from exc
    return MessageOut.model_validate(message)


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    conversation = await require_conversation(payload.conversation_id, user, session)
    provider = get_llm_provider()
    user_id = user.id
    character_id = conversation.character_id
    conversation_id = conversation.id

    async def event_stream():
        user_message_id = None
        try:
            if payload.retry_user_message_id is not None:
                user_message, character, prompt = await prepare_retry_user_message(
                    session,
                    user=user,
                    conversation=conversation,
                    user_message_id=payload.retry_user_message_id,
                    content=payload.content,
                )
            else:
                user_message, character, prompt = await prepare_user_message(
                    session,
                    user,
                    conversation,
                    payload.content,
                    payload.content_mode,
                    payload.privacy_mode,
                )
            user_message_id = user_message.id
            record_prompt_context(
                user_message,
                prompt=prompt,
                provider_name=provider.name,
                generation_kind="stream",
            )
            await session.commit()
            await session.refresh(user_message)
            yield sse(
                "message_start",
                {
                    "user_message": dump_message(user_message),
                    "retry": payload.retry_user_message_id is not None,
                },
            )

            chunks: list[str] = []
            generation_started = perf_counter()
            first_token_ms = None
            generation_provider = provider.name
            generation_model = provider.model
            finish_reason = None
            usage = TokenUsage()
            async for event in provider.stream(prompt.prompt):
                generation_provider = event.provider or generation_provider
                generation_model = event.model or generation_model
                if event.finish_reason is not None:
                    finish_reason = event.finish_reason
                if event.usage != TokenUsage():
                    usage = event.usage
                if not event.content:
                    continue
                if first_token_ms is None:
                    first_token_ms = elapsed_ms(generation_started)
                chunks.append(event.content)
                yield sse("token", {"content": event.content})

            generation = LLMGeneration(
                content="".join(chunks),
                provider=generation_provider,
                model=generation_model,
                finish_reason=finish_reason,
                usage=usage,
            )

            assistant_message = await complete_assistant_message(
                session,
                user=user,
                conversation=conversation,
                character=character,
                user_message=user_message,
                assistant_content=generation.content,
                provider=provider,
                prompt=prompt,
                generation=generation,
                latency_ms=elapsed_ms(generation_started),
                first_token_ms=first_token_ms,
            )
            await session.commit()
            await session.refresh(assistant_message)
            yield sse("message_done", {"assistant_message": dump_message(assistant_message)})
            job_id = post_chat_job_id(assistant_message)
            if job_id is not None:
                await run_post_chat_job(job_id)
        except asyncio.CancelledError:
            await session.rollback()
            await mark_user_message_generation_failed(
                session,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                failure_type="cancelled",
                cancelled=True,
            )
            await session.commit()
            raise
        except LLMProviderUnavailable as exc:
            await session.rollback()
            await mark_user_message_generation_failed(
                session,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                failure_type=exc.failure_type,
            )
            await session.commit()
            await record_generation_error(
                user_id=user_id,
                character_id=character_id,
                conversation_id=conversation_id,
                operation="stream",
                code=diagnostic_code(exc),
                provider=provider.name,
            )
            logger.warning(
                "Text provider failed during streamed reply (%s).",
                exc.failure_type,
            )
            yield sse(
                "error",
                {
                    "detail": public_provider_failure_detail(exc),
                    "failure_type": exc.failure_type,
                    "retryable": exc.retryable,
                    "user_message_id": str(user_message_id) if user_message_id else None,
                },
            )
        except ChatTurnCancelled as exc:
            await session.rollback()
            yield sse("error", {"detail": str(exc)})
        except HTTPException as exc:
            await session.rollback()
            yield sse("error", {"detail": str(exc.detail)})
        except Exception:  # noqa: BLE001 - streamed clients need a readable event
            await session.rollback()
            await mark_user_message_generation_failed(
                session,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                failure_type="provider_unavailable",
            )
            await session.commit()
            await record_generation_error(
                user_id=user_id,
                character_id=character_id,
                conversation_id=conversation_id,
                operation="stream",
                code="generation_failed",
                provider=provider.name,
            )
            logger.warning("Streamed reply generation failed unexpectedly.")
            yield sse(
                "error",
                {
                    "detail": "The backend could not finish that reply. Your message was saved.",
                    "failure_type": "provider_unavailable",
                    "retryable": True,
                    "user_message_id": str(user_message_id) if user_message_id else None,
                },
            )
        finally:
            await session.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def dump_message(message) -> dict:
    return MessageOut.model_validate(message).model_dump(mode="json")


def elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))


def diagnostic_code(exc: LLMProviderUnavailable) -> str:
    if exc.failure_type in {
        "authentication",
        "context_overflow",
        "malformed_response",
        "model_unavailable",
        "quota_exhausted",
        "rate_limited",
        "refusal",
        "timeout",
    }:
        return exc.failure_type
    return "provider_unavailable"


def provider_http_status(exc: LLMProviderUnavailable) -> int:
    if exc.failure_type in {"authentication", "model_unavailable"}:
        return 503
    if exc.failure_type in {"context_overflow", "refusal"}:
        return 422
    if exc.failure_type in {"quota_exhausted", "rate_limited"}:
        return 429
    if exc.failure_type == "timeout":
        return 504
    return 503


def queue_post_chat_background(background_tasks: BackgroundTasks, message) -> None:
    job_id = post_chat_job_id(message)
    if job_id is not None:
        background_tasks.add_task(run_post_chat_job, job_id)


def post_chat_job_id(message) -> uuid.UUID | None:
    metadata = message.metadata_json if isinstance(message.metadata_json, dict) else {}
    value = metadata.get("post_chat_job_id")
    if not isinstance(value, str):
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None
