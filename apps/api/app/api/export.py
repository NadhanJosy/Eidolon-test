from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models import (
    Character,
    ContinuityThread,
    Conversation,
    EpisodicJournal,
    MemoryItem,
    Message,
    RelationshipState,
    ScheduledJob,
    User,
    utc_now,
)
from app.schemas import AccountDeleteRequest, DeleteResponse, ExportOut
from app.security import verify_password
from app.services.auth_session import clear_refresh_cookie

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/export", response_model=ExportOut)
async def export_account(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExportOut:
    characters = (
        await session.execute(select(Character).where(Character.owner_user_id == user.id))
    ).scalars()
    conversations = (
        await session.execute(select(Conversation).where(Conversation.user_id == user.id))
    ).scalars()
    conversation_list = list(conversations)
    conversation_ids = [conversation.id for conversation in conversation_list]
    messages = []
    if conversation_ids:
        messages = list(
            (
                await session.execute(
                    select(Message).where(Message.conversation_id.in_(conversation_ids))
                )
            )
            .scalars()
            .all()
        )
    memories = (
        await session.execute(select(MemoryItem).where(MemoryItem.user_id == user.id))
    ).scalars()
    journals = (
        await session.execute(select(EpisodicJournal).where(EpisodicJournal.user_id == user.id))
    ).scalars()
    continuity_threads = (
        await session.execute(select(ContinuityThread).where(ContinuityThread.user_id == user.id))
    ).scalars()
    relationships = (
        await session.execute(select(RelationshipState).where(RelationshipState.user_id == user.id))
    ).scalars()
    jobs = (
        await session.execute(select(ScheduledJob).where(ScheduledJob.user_id == user.id))
    ).scalars()

    return ExportOut(
        exported_at=utc_now().astimezone(UTC),
        user={
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "age_gate_confirmed": user.age_gate_confirmed,
            "created_at": user.created_at.isoformat(),
        },
        characters=[character_to_dict(character) for character in characters],
        conversations=[conversation_to_dict(conversation) for conversation in conversation_list],
        messages=[message_to_dict(message) for message in messages],
        memories=[memory_to_dict(memory) for memory in memories],
        episodic_journals=[journal_to_dict(journal) for journal in journals],
        continuity_threads=[continuity_thread_to_dict(thread) for thread in continuity_threads],
        relationship_states=[relationship_to_dict(relationship) for relationship in relationships],
        scheduled_jobs=[job_to_dict(job) for job in jobs],
    )


@router.delete("", response_model=DeleteResponse)
async def delete_account(
    payload: AccountDeleteRequest,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeleteResponse:
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=403, detail="Password did not match.")

    result = await session.execute(delete(User).where(User.id == user.id))
    await session.commit()
    clear_refresh_cookie(response)
    return DeleteResponse(deleted=int(result.rowcount or 0))


def character_to_dict(character: Character) -> dict:
    return {
        "id": str(character.id),
        "name": character.name,
        "description": character.description,
        "personality_core": character.personality_core,
        "speech_style": character.speech_style,
        "soul_json": character.soul_json,
        "boundaries_json": character.boundaries_json,
        "explicit_age": character.explicit_age,
        "adult_mode_allowed": character.adult_mode_allowed,
        "content_intensity": character.content_intensity,
        "created_at": character.created_at.isoformat(),
        "updated_at": character.updated_at.isoformat(),
    }


def conversation_to_dict(conversation: Conversation) -> dict:
    return {
        "id": str(conversation.id),
        "character_id": str(conversation.character_id),
        "title": conversation.title,
        "metadata_json": conversation.metadata_json,
        "last_read_at": conversation.last_read_at.isoformat(),
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }


def message_to_dict(message: Message) -> dict:
    return {
        "id": str(message.id),
        "conversation_id": str(message.conversation_id),
        "role": message.role,
        "content": message.content,
        "metadata_json": message.metadata_json,
        "created_at": message.created_at.isoformat(),
    }


def memory_to_dict(memory: MemoryItem) -> dict:
    return {
        "id": str(memory.id),
        "user_id": str(memory.user_id),
        "character_id": str(memory.character_id),
        "source_message_id": str(memory.source_message_id) if memory.source_message_id else None,
        "memory_type": memory.memory_type,
        "content": memory.content,
        "importance": memory.importance,
        "confidence": memory.confidence,
        "emotional_weight": memory.emotional_weight,
        "pinned": memory.pinned,
        "decay_score": memory.decay_score,
        "contradiction_group": memory.contradiction_group,
        "last_recalled_at": isoformat_or_none(memory.last_recalled_at),
        "forgotten_at": isoformat_or_none(memory.forgotten_at),
        "metadata_json": memory.metadata_json,
        "created_at": memory.created_at.isoformat(),
        "updated_at": memory.updated_at.isoformat(),
    }


def journal_to_dict(journal: EpisodicJournal) -> dict:
    return {
        "id": str(journal.id),
        "user_id": str(journal.user_id),
        "character_id": str(journal.character_id),
        "conversation_id": str(journal.conversation_id) if journal.conversation_id else None,
        "journal_type": journal.journal_type,
        "title": journal.title,
        "summary": journal.summary,
        "emotional_tags_json": journal.emotional_tags_json,
        "unresolved_threads_json": journal.unresolved_threads_json,
        "callbacks_json": journal.callbacks_json,
        "importance": journal.importance,
        "metadata_json": journal.metadata_json,
        "created_at": journal.created_at.isoformat(),
        "updated_at": journal.updated_at.isoformat(),
    }


def continuity_thread_to_dict(thread: ContinuityThread) -> dict:
    return {
        "id": str(thread.id),
        "user_id": str(thread.user_id),
        "character_id": str(thread.character_id),
        "conversation_id": str(thread.conversation_id) if thread.conversation_id else None,
        "source_message_id": (str(thread.source_message_id) if thread.source_message_id else None),
        "thread_kind": thread.thread_kind,
        "content": thread.content,
        "status": thread.status,
        "salience": thread.salience,
        "confidence": thread.confidence,
        "last_referenced_at": isoformat_or_none(thread.last_referenced_at),
        "last_proactive_at": isoformat_or_none(thread.last_proactive_at),
        "resolved_at": isoformat_or_none(thread.resolved_at),
        "metadata_json": thread.metadata_json,
        "created_at": thread.created_at.isoformat(),
        "updated_at": thread.updated_at.isoformat(),
    }


def relationship_to_dict(relationship: RelationshipState) -> dict:
    return {
        "id": str(relationship.id),
        "user_id": str(relationship.user_id),
        "character_id": str(relationship.character_id),
        "trust": relationship.trust,
        "intimacy": relationship.intimacy,
        "warmth": relationship.warmth,
        "tension": relationship.tension,
        "familiarity": relationship.familiarity,
        "attachment": relationship.attachment,
        "mood": relationship.mood,
        "conflict_state": relationship.conflict_state,
        "repair_needed": relationship.repair_needed,
        "tags_json": relationship.tags_json,
        "last_interaction_at": isoformat_or_none(relationship.last_interaction_at),
        "metadata_json": relationship.metadata_json,
        "created_at": relationship.created_at.isoformat(),
        "updated_at": relationship.updated_at.isoformat(),
    }


def job_to_dict(job: ScheduledJob) -> dict:
    return {
        "id": str(job.id),
        "user_id": str(job.user_id) if job.user_id else None,
        "character_id": str(job.character_id) if job.character_id else None,
        "job_type": job.job_type,
        "run_at": job.run_at.isoformat(),
        "status": job.status,
        "locked_at": isoformat_or_none(job.locked_at),
        "locked_by": job.locked_by,
        "payload_json": job.payload_json,
        "retry_count": job.retry_count,
        "last_error": job.last_error,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


def isoformat_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
