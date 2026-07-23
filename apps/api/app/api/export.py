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
    EpisodicJournalSource,
    MemoryEntity,
    MemoryEntityLink,
    MemoryEvidence,
    MemoryItem,
    Message,
    ProactiveCandidate,
    ProactiveCandidateEvent,
    RelationshipEvent,
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
    memory_list = list(
        (await session.execute(select(MemoryItem).where(MemoryItem.user_id == user.id)))
        .scalars()
        .all()
    )
    memory_ids = [memory.id for memory in memory_list]
    memory_evidence: list[MemoryEvidence] = []
    memory_entity_links: list[MemoryEntityLink] = []
    if memory_ids:
        memory_evidence = list(
            (
                await session.execute(
                    select(MemoryEvidence).where(MemoryEvidence.memory_id.in_(memory_ids))
                )
            )
            .scalars()
            .all()
        )
        memory_entity_links = list(
            (
                await session.execute(
                    select(MemoryEntityLink).where(MemoryEntityLink.memory_id.in_(memory_ids))
                )
            )
            .scalars()
            .all()
        )
    memory_entities = list(
        (await session.execute(select(MemoryEntity).where(MemoryEntity.user_id == user.id)))
        .scalars()
        .all()
    )
    journal_list = list(
        (await session.execute(select(EpisodicJournal).where(EpisodicJournal.user_id == user.id)))
        .scalars()
        .all()
    )
    journal_sources: dict[str, list[str]] = {}
    if journal_list:
        source_rows = await session.execute(
            select(EpisodicJournalSource).where(
                EpisodicJournalSource.journal_id.in_([journal.id for journal in journal_list])
            )
        )
        for source in source_rows.scalars().all():
            journal_sources.setdefault(str(source.journal_id), []).append(str(source.message_id))
    continuity_threads = (
        await session.execute(select(ContinuityThread).where(ContinuityThread.user_id == user.id))
    ).scalars()
    relationships = (
        await session.execute(select(RelationshipState).where(RelationshipState.user_id == user.id))
    ).scalars()
    relationship_events = (
        await session.execute(select(RelationshipEvent).where(RelationshipEvent.user_id == user.id))
    ).scalars()
    proactive_candidates = list(
        (
            await session.execute(
                select(ProactiveCandidate).where(ProactiveCandidate.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    proactive_candidate_events: list[ProactiveCandidateEvent] = []
    if proactive_candidates:
        proactive_candidate_events = list(
            (
                await session.execute(
                    select(ProactiveCandidateEvent).where(
                        ProactiveCandidateEvent.candidate_id.in_(
                            [candidate.id for candidate in proactive_candidates]
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
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
        memories=[memory_to_dict(memory) for memory in memory_list],
        memory_evidence=[memory_evidence_to_dict(item) for item in memory_evidence],
        memory_entities=[memory_entity_to_dict(entity) for entity in memory_entities],
        memory_entity_links=[
            {
                "memory_id": str(link.memory_id),
                "entity_id": str(link.entity_id),
                "relation": link.relation,
                "created_at": link.created_at.isoformat(),
            }
            for link in memory_entity_links
        ],
        episodic_journals=[
            journal_to_dict(journal, journal_sources.get(str(journal.id), []))
            for journal in journal_list
        ],
        continuity_threads=[continuity_thread_to_dict(thread) for thread in continuity_threads],
        relationship_states=[relationship_to_dict(relationship) for relationship in relationships],
        relationship_events=[relationship_event_to_dict(event) for event in relationship_events],
        proactive_candidates=[
            proactive_candidate_to_dict(candidate) for candidate in proactive_candidates
        ],
        proactive_candidate_events=[
            proactive_candidate_event_to_dict(event) for event in proactive_candidate_events
        ],
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
        "scope": memory.scope,
        "claim_key": memory.claim_key,
        "retention_tier": memory.retention_tier,
        "lifecycle_state": memory.lifecycle_state,
        "sensitivity": memory.sensitivity,
        "memory_type": memory.memory_type,
        "content": memory.content,
        "importance": memory.importance,
        "confidence": memory.confidence,
        "emotional_weight": memory.emotional_weight,
        "emotional_context_json": memory.emotional_context_json,
        "novelty": memory.novelty,
        "future_relevance": memory.future_relevance,
        "reinforcement_count": memory.reinforcement_count,
        "pinned": memory.pinned,
        "decay_score": memory.decay_score,
        "contradiction_group": memory.contradiction_group,
        "last_recalled_at": isoformat_or_none(memory.last_recalled_at),
        "last_reinforced_at": isoformat_or_none(memory.last_reinforced_at),
        "last_evidence_at": isoformat_or_none(memory.last_evidence_at),
        "superseded_by_id": str(memory.superseded_by_id) if memory.superseded_by_id else None,
        "forgotten_at": isoformat_or_none(memory.forgotten_at),
        "metadata_json": memory.metadata_json,
        "created_at": memory.created_at.isoformat(),
        "updated_at": memory.updated_at.isoformat(),
    }


def memory_evidence_to_dict(evidence: MemoryEvidence) -> dict:
    return {
        "id": str(evidence.id),
        "memory_id": str(evidence.memory_id),
        "source_message_id": (
            str(evidence.source_message_id) if evidence.source_message_id else None
        ),
        "action": evidence.action,
        "actor": evidence.actor,
        "reason": evidence.reason,
        "snapshot_json": evidence.snapshot_json,
        "created_at": evidence.created_at.isoformat(),
    }


def memory_entity_to_dict(entity: MemoryEntity) -> dict:
    return {
        "id": str(entity.id),
        "user_id": str(entity.user_id),
        "character_id": str(entity.character_id),
        "entity_type": entity.entity_type,
        "name": entity.name,
        "first_seen_at": entity.first_seen_at.isoformat(),
        "last_seen_at": entity.last_seen_at.isoformat(),
        "mention_count": entity.mention_count,
        "created_at": entity.created_at.isoformat(),
        "updated_at": entity.updated_at.isoformat(),
    }


def journal_to_dict(journal: EpisodicJournal, source_message_ids: list[str]) -> dict:
    return {
        "id": str(journal.id),
        "user_id": str(journal.user_id),
        "character_id": str(journal.character_id),
        "conversation_id": str(journal.conversation_id) if journal.conversation_id else None,
        "scope": journal.scope,
        "source_message_ids": source_message_ids,
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
        "emotional_safety": relationship.emotional_safety,
        "reliability": relationship.reliability,
        "reciprocity": relationship.reciprocity,
        "repair_progress": relationship.repair_progress,
        "boundary_alignment": relationship.boundary_alignment,
        "shared_history_depth": relationship.shared_history_depth,
        "mood": relationship.mood,
        "conflict_state": relationship.conflict_state,
        "repair_needed": relationship.repair_needed,
        "tags_json": relationship.tags_json,
        "last_interaction_at": isoformat_or_none(relationship.last_interaction_at),
        "metadata_json": relationship.metadata_json,
        "created_at": relationship.created_at.isoformat(),
        "updated_at": relationship.updated_at.isoformat(),
    }


def relationship_event_to_dict(event: RelationshipEvent) -> dict:
    return {
        "id": str(event.id),
        "user_id": str(event.user_id),
        "character_id": str(event.character_id),
        "source_message_id": str(event.source_message_id) if event.source_message_id else None,
        "memory_id": str(event.memory_id) if event.memory_id else None,
        "journal_id": str(event.journal_id) if event.journal_id else None,
        "scope": event.scope,
        "event_key": event.event_key,
        "event_type": event.event_type,
        "summary": event.summary,
        "evidence_quote": event.evidence_quote,
        "confidence": event.confidence,
        "significance": event.significance,
        "dimension_deltas_json": event.dimension_deltas_json,
        "affects_current_state": event.affects_current_state,
        "occurred_at": event.occurred_at.isoformat(),
        "metadata_json": event.metadata_json,
        "created_at": event.created_at.isoformat(),
        "updated_at": event.updated_at.isoformat(),
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
        "dedupe_key": job.dedupe_key,
        "expires_at": isoformat_or_none(job.expires_at),
        "cancelled_at": isoformat_or_none(job.cancelled_at),
        "payload_json": job.payload_json,
        "retry_count": job.retry_count,
        "last_error": job.last_error,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


def proactive_candidate_to_dict(candidate: ProactiveCandidate) -> dict:
    return {
        "id": str(candidate.id),
        "user_id": str(candidate.user_id),
        "character_id": str(candidate.character_id),
        "conversation_id": (str(candidate.conversation_id) if candidate.conversation_id else None),
        "source_message_id": (
            str(candidate.source_message_id) if candidate.source_message_id else None
        ),
        "memory_id": str(candidate.memory_id) if candidate.memory_id else None,
        "journal_id": str(candidate.journal_id) if candidate.journal_id else None,
        "continuity_thread_id": (
            str(candidate.continuity_thread_id) if candidate.continuity_thread_id else None
        ),
        "relationship_event_id": (
            str(candidate.relationship_event_id) if candidate.relationship_event_id else None
        ),
        "message_id": str(candidate.message_id) if candidate.message_id else None,
        "candidate_type": candidate.candidate_type,
        "initiative_kind": candidate.initiative_kind,
        "source": candidate.source,
        "rationale": candidate.rationale,
        "confidence": candidate.confidence,
        "urgency": candidate.urgency,
        "relevance_score": candidate.relevance_score,
        "sensitivity": candidate.sensitivity,
        "state": candidate.state,
        "scheduled_for": isoformat_or_none(candidate.scheduled_for),
        "expires_at": candidate.expires_at.isoformat(),
        "generated_at": isoformat_or_none(candidate.generated_at),
        "delivered_at": isoformat_or_none(candidate.delivered_at),
        "opened_at": isoformat_or_none(candidate.opened_at),
        "dismissed_at": isoformat_or_none(candidate.dismissed_at),
        "replied_at": isoformat_or_none(candidate.replied_at),
        "cancelled_at": isoformat_or_none(candidate.cancelled_at),
        "failed_at": isoformat_or_none(candidate.failed_at),
        "notification_preview": candidate.notification_preview,
        "failure_code": candidate.failure_code,
        "dismissal_feedback": candidate.dismissal_feedback,
        "delivery_constraints_json": candidate.delivery_constraints_json,
        "score_factors_json": candidate.score_factors_json,
        "created_at": candidate.created_at.isoformat(),
        "updated_at": candidate.updated_at.isoformat(),
    }


def proactive_candidate_event_to_dict(event: ProactiveCandidateEvent) -> dict:
    return {
        "id": str(event.id),
        "candidate_id": str(event.candidate_id),
        "from_state": event.from_state,
        "to_state": event.to_state,
        "reason_code": event.reason_code,
        "metadata_json": event.metadata_json,
        "created_at": event.created_at.isoformat(),
    }


def isoformat_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
