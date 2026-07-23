from __future__ import annotations

import asyncio
import json
import logging
import uuid
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.companion.quality import (
    checked_response,
    enforce_stream_chunk,
    evaluate_response,
    quality_requires_repair,
)
from app.db.session import get_session
from app.dependencies import get_current_user, require_conversation
from app.llm.base import (
    LLMGeneration,
    LLMProviderUnavailable,
    TokenUsage,
    public_provider_failure_detail,
)
from app.llm.factory import get_llm_provider
from app.models import Conversation, Message, ScheduledJob, User
from app.schemas import (
    ChatRequest,
    ChatRerollRequest,
    ChatResponse,
    ContinuityReceiptOut,
    MessageOut,
)
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
from app.services.generation import (
    StreamContextState,
    repair_checked_reply,
    stream_with_context_retry,
)
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


@router.get(
    "/turns/{assistant_message_id}/continuity",
    response_model=ContinuityReceiptOut,
)
async def turn_continuity_receipt(
    assistant_message_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ContinuityReceiptOut:
    result = await session.execute(
        select(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Message.id == assistant_message_id,
            Message.role == "assistant",
            Conversation.user_id == user.id,
        )
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=404, detail="Turn continuity was not found.")
    metadata = message.metadata_json if isinstance(message.metadata_json, dict) else {}
    receipt = metadata.get("continuity_receipt")
    if not isinstance(receipt, dict):
        return ContinuityReceiptOut(state="skipped")
    if receipt.get("state") == "pending":
        job_id = post_chat_job_id(message)
        job = await session.get(ScheduledJob, job_id) if job_id is not None else None
        if job is not None and job.user_id == user.id:
            payload_receipt = (job.payload_json or {}).get("continuity_receipt")
            if isinstance(payload_receipt, dict):
                receipt = payload_receipt
            elif job.status == "failed":
                receipt = {"state": "degraded"}
    return _validated_continuity_receipt(receipt)


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    background_tasks = BackgroundTasks()
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
                    provider=provider,
                )
            else:
                user_message, character, prompt = await prepare_user_message(
                    session,
                    user,
                    conversation,
                    payload.content,
                    payload.content_mode,
                    payload.privacy_mode,
                    provider,
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
            buffered_chunks: list[str] = []
            prelude_checked = False
            repair_attempted = False
            context_compacted = False
            stream_context_state = StreamContextState()
            initial_quality_violations: tuple[str, ...] = ()
            response_evaluation = None
            generation_started = perf_counter()
            first_token_ms = None
            generation_provider = provider.name
            generation_model = provider.model
            finish_reason = None
            usage = TokenUsage()
            stream = stream_with_context_retry(
                provider,
                prompt=prompt.prompt,
                state=stream_context_state,
            )
            async for event in stream:
                generation_provider = event.provider or generation_provider
                generation_model = event.model or generation_model
                if event.finish_reason is not None:
                    finish_reason = event.finish_reason
                if event.usage != TokenUsage():
                    usage = event.usage
                if not event.content:
                    continue
                chunks.append(event.content)
                candidate = "".join(chunks)
                enforce_stream_chunk(candidate, prompt.response_check_context)
                if not prelude_checked:
                    buffered_chunks.append(event.content)
                    if not _stream_prelude_ready(candidate, event.finish_reason):
                        continue
                    prelude_evaluation = evaluate_response(
                        candidate,
                        prompt.response_check_context,
                    )
                    if quality_requires_repair(prelude_evaluation):
                        initial_quality_violations = tuple(prelude_evaluation.violations[:8])
                        close_stream = getattr(stream, "aclose", None)
                        if callable(close_stream):
                            await close_stream()
                        repaired = await repair_checked_reply(
                            provider,
                            prompt=prompt.prompt,
                            context=prompt.response_check_context,
                            violations=initial_quality_violations,
                        )
                        prelude_checked = True
                        repair_attempted = True
                        context_compacted = repaired.context_compacted
                        response_evaluation = repaired.evaluation
                        generation_provider = repaired.generation.provider
                        generation_model = repaired.generation.model
                        finish_reason = repaired.generation.finish_reason
                        usage = repaired.generation.usage
                        chunks = [repaired.generation.content]
                        if first_token_ms is None:
                            first_token_ms = elapsed_ms(generation_started)
                        for repaired_chunk in _bounded_stream_chunks(repaired.generation.content):
                            yield sse("token", {"content": repaired_chunk})
                        break
                    prelude_checked = True
                    if first_token_ms is None:
                        first_token_ms = elapsed_ms(generation_started)
                    for buffered_chunk in buffered_chunks:
                        yield sse("token", {"content": buffered_chunk})
                    buffered_chunks.clear()
                    continue
                yield sse("token", {"content": event.content})

            if not prelude_checked and buffered_chunks:
                prelude_evaluation = evaluate_response(
                    "".join(chunks),
                    prompt.response_check_context,
                )
                if quality_requires_repair(prelude_evaluation):
                    initial_quality_violations = tuple(prelude_evaluation.violations[:8])
                    repaired = await repair_checked_reply(
                        provider,
                        prompt=prompt.prompt,
                        context=prompt.response_check_context,
                        violations=initial_quality_violations,
                    )
                    prelude_checked = True
                    repair_attempted = True
                    context_compacted = repaired.context_compacted
                    response_evaluation = repaired.evaluation
                    generation_provider = repaired.generation.provider
                    generation_model = repaired.generation.model
                    finish_reason = repaired.generation.finish_reason
                    usage = repaired.generation.usage
                    chunks = [repaired.generation.content]
                    if first_token_ms is None:
                        first_token_ms = elapsed_ms(generation_started)
                    for repaired_chunk in _bounded_stream_chunks(repaired.generation.content):
                        yield sse("token", {"content": repaired_chunk})
                else:
                    if first_token_ms is None:
                        first_token_ms = elapsed_ms(generation_started)
                    for buffered_chunk in buffered_chunks:
                        yield sse("token", {"content": buffered_chunk})

            generation = LLMGeneration(
                content="".join(chunks),
                provider=generation_provider,
                model=generation_model,
                finish_reason=finish_reason,
                usage=usage,
            )
            context_compacted = context_compacted or stream_context_state.compacted
            if response_evaluation is None:
                content, response_evaluation = checked_response(
                    generation.content,
                    prompt.response_check_context,
                    require_quality=True,
                )
                generation = LLMGeneration(
                    content=content,
                    provider=generation.provider,
                    model=generation.model,
                    finish_reason=generation.finish_reason,
                    usage=generation.usage,
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
                response_evaluation=response_evaluation,
                repair_attempted=repair_attempted,
                initial_quality_violations=initial_quality_violations,
                context_compacted=context_compacted,
            )
            await session.commit()
            await session.refresh(assistant_message)
            job_id = post_chat_job_id(assistant_message)
            if job_id is not None:
                background_tasks.add_task(run_post_chat_job, job_id)
            yield sse("message_done", {"assistant_message": dump_message(assistant_message)})
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
                response_check_violations=getattr(exc, "response_check_violations", ()),
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
        background=background_tasks,
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


def _stream_prelude_ready(content: str, finish_reason: str | None) -> bool:
    compact = content.rstrip()
    if finish_reason is not None:
        return True
    # Do not hold cancellation behind a sentence boundary when a provider pauses
    # after its first meaningful fragment.
    return len(compact) >= 12


def _bounded_stream_chunks(content: str, *, target_chars: int = 36) -> list[str]:
    words = content.split(" ")
    chunks: list[str] = []
    current: list[str] = []
    for index, word in enumerate(words):
        current.append(word)
        joined = " ".join(current)
        if len(joined) < target_chars and not word.endswith((".", "!", "?", ";")):
            continue
        suffix = " " if index < len(words) - 1 else ""
        chunks.append(f"{joined}{suffix}")
        current = []
    if current:
        chunks.append(" ".join(current))
    return chunks


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


def _validated_continuity_receipt(value: dict) -> ContinuityReceiptOut:
    state = value.get("state")
    if state not in {"pending", "ready", "degraded", "skipped"}:
        state = "degraded"
    memory_ids: list[uuid.UUID] = []
    raw_memory_ids = value.get("memory_ids")
    if isinstance(raw_memory_ids, list):
        for item in raw_memory_ids[:3]:
            try:
                memory_ids.append(uuid.UUID(str(item)))
            except ValueError:
                continue
    moment_id = None
    if value.get("moment_id") is not None:
        try:
            moment_id = uuid.UUID(str(value.get("moment_id")))
        except ValueError:
            pass
    allowed_labels = {"remembered", "reinforced", "corrected", "moment", "relationship"}
    raw_labels = value.get("change_labels")
    labels = (
        [item for item in raw_labels[:5] if isinstance(item, str) and item in allowed_labels]
        if isinstance(raw_labels, list)
        else []
    )
    return ContinuityReceiptOut(
        state=state,
        memory_ids=memory_ids,
        moment_id=moment_id,
        change_labels=labels,
    )
