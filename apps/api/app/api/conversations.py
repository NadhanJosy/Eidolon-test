from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user, require_character, require_conversation
from app.llm.base import SAFE_PROVIDER_UNAVAILABLE_DETAIL, LLMProviderUnavailable
from app.llm.factory import get_llm_provider
from app.models import (
    Character,
    Conversation,
    EpisodicJournal,
    Message,
    ScheduledJob,
    User,
    utc_now,
)
from app.schemas import (
    ChatResponse,
    ConversationCreate,
    ConversationOut,
    ConversationReadRequest,
    ConversationUpdate,
    DeleteResponse,
    MemoryOut,
    MessageOut,
    MessageUpdate,
)
from app.services.chat import create_conversation, edit_latest_user_turn, memory_storage_allowed
from app.services.continuity import (
    delete_conversation_threads,
    remove_message_source_threads,
)
from app.services.conversation_presence import (
    advance_read_cursor,
    get_conversation_summary,
    list_conversation_summaries,
)
from app.services.conversation_privacy import (
    build_privacy_mode_event,
    conversation_is_private,
    conversation_privacy_mode,
    message_is_private,
    set_conversation_privacy_mode,
)
from app.services.conversation_scenario import (
    ConversationScenarioError,
    build_scenario_event,
    set_conversation_scenario,
)
from app.services.diagnostics import record_generation_error
from app.services.journal import maybe_create_journal_from_conversation
from app.services.memory import (
    MemoryCaptureError,
    memory_preferences_from_boundaries,
    remember_message_as_memory,
    remove_message_source_memories,
)
from app.services.proactive import ensure_proactive_jobs
from app.services.proactive_presence import (
    cancel_pending_for_character,
    mark_candidates_opened_through,
)
from app.services.relationship import reverse_relationship_message_effect
from app.services.scheduler import run_post_chat_job

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ConversationOut]:
    return await list_conversation_summaries(session, user_id=user.id)


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation_endpoint(
    payload: ConversationCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationOut:
    conversation = await create_conversation(
        session,
        user,
        character_id=payload.character_id,
        title=payload.title,
        privacy_mode=payload.privacy_mode,
    )
    await session.commit()
    await session.refresh(conversation)
    return await get_conversation_summary(session, conversation)


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationOut:
    conversation = await require_conversation(
        conversation_id,
        user,
        session,
        for_update=True,
    )
    if "title" in payload.model_fields_set:
        conversation.title = payload.title
    if payload.privacy_mode is not None:
        previous_privacy_mode = conversation_privacy_mode(conversation)
        if payload.privacy_mode != previous_privacy_mode:
            set_conversation_privacy_mode(conversation, payload.privacy_mode)
            session.add(build_privacy_mode_event(conversation, payload.privacy_mode))
        if payload.privacy_mode == "private":
            await cancel_pending_for_character(
                session,
                character_id=conversation.character_id,
                conversation_id=conversation.id,
                reason_code="conversation_became_private",
            )
            await _delete_conversation_jobs(session, conversation.id)
    if payload.scenario is not None:
        try:
            scenario_changed = set_conversation_scenario(
                conversation,
                mode=payload.scenario.mode,
                text=payload.scenario.text,
            )
        except ConversationScenarioError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if scenario_changed:
            session.add(build_scenario_event(conversation, payload.scenario.mode))
    await session.commit()
    await session.refresh(conversation)
    return await get_conversation_summary(session, conversation)


@router.post("/{conversation_id}/read", response_model=ConversationOut)
async def mark_conversation_read(
    conversation_id: uuid.UUID,
    payload: ConversationReadRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationOut:
    conversation = await require_conversation(conversation_id, user, session)
    advanced = await advance_read_cursor(
        session,
        conversation,
        through_message_id=payload.through_message_id,
    )
    if not advanced:
        await session.rollback()
        raise HTTPException(
            status_code=404,
            detail="Readable companion message was not found in this thread.",
        )
    await mark_candidates_opened_through(session, conversation=conversation)
    await session.commit()
    await session.refresh(conversation)
    return await get_conversation_summary(session, conversation)


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
    normalized_query = q.strip()
    if not normalized_query:
        raise HTTPException(
            status_code=422,
            detail="Search query must contain visible text.",
        )
    escaped_query = normalized_query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    result = await session.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.content.ilike(f"%{escaped_query}%", escape="\\"),
        )
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


@router.post(
    "/{conversation_id}/messages/{message_id}/remember",
    response_model=MemoryOut,
)
async def remember_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    conversation = await require_conversation(conversation_id, user, session)
    result = await session.execute(
        select(Message).where(
            Message.id == message_id,
            Message.conversation_id == conversation.id,
        )
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=404, detail="Message was not found.")
    if message.role not in {"user", "assistant"}:
        raise HTTPException(
            status_code=422,
            detail="Only user or companion messages can be remembered.",
        )

    metadata = message.metadata_json or {}
    if conversation_is_private(conversation) or message_is_private(message):
        raise HTTPException(
            status_code=409,
            detail="Memory stays off for lines written in a private thread.",
        )

    character = await require_character(conversation.character_id, user, session)
    content_mode = "adult" if metadata.get("content_mode") == "adult" else "sfw"
    if not memory_storage_allowed(character, content_mode):
        preferences = memory_preferences_from_boundaries(character.boundaries_json)
        detail = (
            "Memory is paused in this character's profile."
            if preferences.get("private_mode_default") is True
            else "Adult memory storage is off for this character."
        )
        raise HTTPException(status_code=409, detail=detail)

    try:
        memory = await remember_message_as_memory(
            session,
            user_id=user.id,
            character_id=character.id,
            message_id=message.id,
            content=message.content,
            source_role=message.role,
            scope=(
                "adult"
                if (message.metadata_json or {}).get("content_mode") == "adult"
                else "general"
            ),
        )
    except MemoryCaptureError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await session.commit()
    await session.refresh(memory)
    return memory


@router.patch("/{conversation_id}/messages/{message_id}", response_model=ChatResponse)
async def edit_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    payload: MessageUpdate,
    background_tasks: BackgroundTasks,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChatResponse:
    conversation = await require_conversation(
        conversation_id,
        user,
        session,
        for_update=True,
    )
    provider = get_llm_provider()
    user_id = user.id
    character_id = conversation.character_id
    current_conversation_id = conversation.id
    try:
        user_message, assistant_message = await edit_latest_user_turn(
            session,
            user=user,
            conversation=conversation,
            message_id=message_id,
            content=payload.content,
            provider=provider,
        )
    except LLMProviderUnavailable as exc:
        await session.rollback()
        await record_generation_error(
            user_id=user_id,
            character_id=character_id,
            conversation_id=current_conversation_id,
            operation="edit",
            code="provider_unavailable",
            provider=provider.name,
        )
        raise HTTPException(status_code=503, detail=SAFE_PROVIDER_UNAVAILABLE_DETAIL) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - keep provider defects out of logs/responses
        await session.rollback()
        await record_generation_error(
            user_id=user_id,
            character_id=character_id,
            conversation_id=current_conversation_id,
            operation="edit",
            code="generation_failed",
            provider=provider.name,
        )
        raise HTTPException(
            status_code=503,
            detail="The backend could not refresh that reply. The original turn is unchanged.",
        ) from exc
    job_id = (assistant_message.metadata_json or {}).get("post_chat_job_id")
    if isinstance(job_id, str):
        try:
            background_tasks.add_task(run_post_chat_job, uuid.UUID(job_id))
        except ValueError:
            pass
    return ChatResponse(
        user_message=MessageOut.model_validate(user_message),
        assistant_message=MessageOut.model_validate(assistant_message),
    )


@router.delete("/{conversation_id}/messages/{message_id}", response_model=DeleteResponse)
async def delete_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeleteResponse:
    conversation = await require_conversation(
        conversation_id,
        user,
        session,
        for_update=True,
    )
    result = await session.execute(
        select(Message)
        .where(
            Message.id == message_id,
            Message.conversation_id == conversation.id,
        )
        .with_for_update()
    )
    message = result.scalar_one_or_none()
    if message is None:
        await session.rollback()
        raise HTTPException(status_code=404, detail="Message was not found.")

    if message.role == "user":
        deleted = await _delete_latest_user_turn(
            session,
            user=user,
            conversation=conversation,
            user_message=message,
        )
    elif message.role == "assistant":
        deleted = await _delete_assistant_message(
            session,
            user=user,
            conversation=conversation,
            assistant_message=message,
        )
    else:
        result = await session.execute(delete(Message).where(Message.id == message.id))
        deleted = int(result.rowcount or 0)
        conversation.updated_at = utc_now()

    await session.commit()
    return DeleteResponse(deleted=deleted)


@router.delete("/{conversation_id}/messages", response_model=DeleteResponse)
async def clear_conversation_messages(
    conversation_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeleteResponse:
    conversation = await require_conversation(
        conversation_id,
        user,
        session,
        for_update=True,
    )
    await delete_conversation_threads(session, conversation.id)
    await cancel_pending_for_character(
        session,
        character_id=conversation.character_id,
        conversation_id=conversation.id,
        reason_code="conversation_cleared",
    )
    result = await session.execute(
        delete(Message).where(Message.conversation_id == conversation.id)
    )
    await _delete_conversation_journals(session, conversation.id)
    await _delete_conversation_jobs(session, conversation.id)
    conversation.updated_at = utc_now()
    await session.commit()
    return DeleteResponse(deleted=int(result.rowcount or 0))


@router.delete("/{conversation_id}", response_model=DeleteResponse)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeleteResponse:
    conversation = await require_conversation(conversation_id, user, session)
    await session.execute(delete(Message).where(Message.conversation_id == conversation.id))
    await _delete_conversation_jobs(session, conversation.id)
    result = await session.execute(delete(Conversation).where(Conversation.id == conversation.id))
    await session.commit()
    return DeleteResponse(deleted=int(result.rowcount or 0))


async def _delete_assistant_message(
    session: AsyncSession,
    *,
    user: User,
    conversation: Conversation,
    assistant_message: Message,
) -> int:
    await remove_message_source_memories(
        session,
        user_id=user.id,
        character_id=conversation.character_id,
        message_id=assistant_message.id,
    )
    await cancel_pending_for_character(
        session,
        character_id=conversation.character_id,
        conversation_id=conversation.id,
        reason_code="conversation_context_rebuilt",
    )
    await _delete_conversation_jobs(session, conversation.id)
    await _delete_conversation_journals(session, conversation.id)
    result = await session.execute(delete(Message).where(Message.id == assistant_message.id))
    await _rebuild_remaining_conversation_state(
        session,
        user=user,
        conversation=conversation,
    )
    conversation.updated_at = utc_now()
    return int(result.rowcount or 0)


async def _delete_latest_user_turn(
    session: AsyncSession,
    *,
    user: User,
    conversation: Conversation,
    user_message: Message,
) -> int:
    later_result = await session.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.created_at > user_message.created_at,
        )
        .order_by(Message.created_at.asc())
        .with_for_update()
    )
    later_messages = list(later_result.scalars().all())
    if any(message.role != "assistant" for message in later_messages):
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Only the latest user turn can be deleted safely.",
        )

    metadata = user_message.metadata_json if isinstance(user_message.metadata_json, dict) else {}
    if not conversation_is_private(conversation) and not message_is_private(user_message):
        await reverse_relationship_message_effect(
            session,
            user.id,
            conversation.character_id,
            metadata.get("relationship_effect"),
        )
    await remove_message_source_memories(
        session,
        user_id=user.id,
        character_id=conversation.character_id,
        message_id=user_message.id,
    )
    await remove_message_source_threads(
        session,
        user_id=user.id,
        character_id=conversation.character_id,
        message_id=user_message.id,
    )
    for dependent_message in later_messages:
        await remove_message_source_memories(
            session,
            user_id=user.id,
            character_id=conversation.character_id,
            message_id=dependent_message.id,
        )
    await cancel_pending_for_character(
        session,
        character_id=conversation.character_id,
        conversation_id=conversation.id,
        reason_code="conversation_context_rebuilt",
    )
    await _delete_conversation_jobs(session, conversation.id)
    await _delete_conversation_journals(session, conversation.id)

    ids_to_delete = [user_message.id, *[message.id for message in later_messages]]
    result = await session.execute(delete(Message).where(Message.id.in_(ids_to_delete)))
    await _rebuild_remaining_conversation_state(
        session,
        user=user,
        conversation=conversation,
    )
    conversation.updated_at = utc_now()
    return int(result.rowcount or 0)


async def _rebuild_remaining_conversation_state(
    session: AsyncSession,
    *,
    user: User,
    conversation: Conversation,
) -> None:
    character = await session.get(Character, conversation.character_id)
    if character is None or character.owner_user_id != user.id:
        return
    await maybe_create_journal_from_conversation(
        session,
        user=user,
        character=character,
        conversation=conversation,
    )
    await _ensure_remaining_thread_proactive_jobs(
        session,
        user=user,
        conversation=conversation,
        character=character,
    )


async def _ensure_remaining_thread_proactive_jobs(
    session: AsyncSession,
    *,
    user: User,
    conversation: Conversation,
    character: Character,
) -> None:
    if conversation_is_private(conversation):
        return

    latest = await _latest_stateful_message(session, conversation.id)
    if latest is None or latest.role != "assistant":
        return

    metadata = latest.metadata_json if isinstance(latest.metadata_json, dict) else {}
    if (
        message_is_private(latest)
        or metadata.get("content_mode") == "adult"
        or metadata.get("proactive") is True
    ):
        return

    await ensure_proactive_jobs(
        session,
        conversation=conversation,
        user_id=user.id,
        character_id=character.id,
    )


async def _latest_stateful_message(
    session: AsyncSession,
    conversation_id: uuid.UUID,
) -> Message | None:
    result = await session.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.role.in_(("user", "assistant")),
        )
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _delete_conversation_journals(
    session: AsyncSession,
    conversation_id: uuid.UUID,
) -> None:
    await session.execute(
        delete(EpisodicJournal).where(EpisodicJournal.conversation_id == conversation_id)
    )


async def _delete_conversation_jobs(session: AsyncSession, conversation_id: uuid.UUID) -> None:
    await session.execute(
        delete(ScheduledJob).where(
            ScheduledJob.payload_json["conversation_id"].as_string() == str(conversation_id)
        )
    )
