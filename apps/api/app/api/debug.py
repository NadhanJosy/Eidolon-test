from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_session
from app.dependencies import get_current_user, require_character, require_conversation
from app.llm.factory import get_llm_provider
from app.models import (
    Character,
    DiagnosticEvent,
    MemoryItem,
    Message,
    ScheduledJob,
    User,
    utc_now,
)
from app.schemas import MessageOut, ScheduledJobOut
from app.services.conversation_privacy import (
    conversation_is_private,
    message_is_private,
    message_privacy_mode,
)
from app.services.journal import list_journals
from app.services.memory import (
    analyze_memory_candidate,
    memory_preferences_from_boundaries,
    retrieve_memories,
)
from app.services.proactive import create_inactivity_proactive_message
from app.services.prompt import PRIVATE_PROMPT_CONTEXT_KEY, PROMPT_VERSION
from app.services.relationship import get_current_relationship
from app.services.response_planner import list_pending_proactive_events
from app.services.safety import adult_gate_status


def require_debug_routes_enabled() -> None:
    if not get_settings().debug_routes_available:
        raise HTTPException(status_code=404, detail="Debug routes are not available.")


router = APIRouter(
    prefix="/debug",
    tags=["debug"],
    dependencies=[Depends(require_debug_routes_enabled)],
)


@router.get("/character/{character_id}")
async def debug_character(
    character_id: uuid.UUID,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    settings = get_settings()
    character = await require_character(character_id, user, session)
    relationship = await get_current_relationship(session, user.id, character.id)
    memories = await retrieve_memories(
        session,
        user_id=user.id,
        character_id=character.id,
        query="",
        limit=10,
        mark_recalled=False,
    )
    journals = await list_journals(session, user.id, character.id, limit=4)
    pending_proactive_events = await list_pending_proactive_events(
        session,
        user_id=user.id,
        character_id=character.id,
    )
    diagnostic_result = await session.execute(
        select(DiagnosticEvent)
        .where(
            DiagnosticEvent.user_id == user.id,
            DiagnosticEvent.character_id == character.id,
        )
        .order_by(desc(DiagnosticEvent.created_at), desc(DiagnosticEvent.id))
        .limit(20)
    )
    diagnostic_events = list(diagnostic_result.scalars().all())
    safety_status = adult_gate_status(user, character, "sfw", relationship=relationship)
    time_context = utc_now().strftime("%A, %Y-%m-%d %H:%M UTC")
    await session.commit()
    return {
        "runtime": {
            "scheduler_enabled": bool(
                getattr(request.app.state, "scheduler_enabled", settings.enable_scheduler)
            ),
            "scheduler_running": _scheduler_running(request),
            "scheduler_interval_seconds": settings.scheduler_interval_seconds,
            "scheduler_job_limit": settings.scheduler_job_limit,
            "scheduler_max_retries": settings.scheduler_max_retries,
        },
        "character": {
            "id": str(character.id),
            "name": character.name,
            "description": character.description,
            "explicit_age": character.explicit_age,
            "adult_mode_allowed": character.adult_mode_allowed,
        },
        "relationship": {
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
            "timeline": (relationship.metadata_json or {}).get("timeline", []),
        },
        "memories": [
            {
                "id": str(memory.id),
                "memory_type": memory.memory_type,
                "content": memory.content,
                "importance": memory.importance,
                "confidence": memory.confidence,
                "pinned": memory.pinned,
            }
            for memory in memories
        ],
        "journals": [
            {
                "id": str(journal.id),
                "journal_type": journal.journal_type,
                "title": journal.title,
                "summary": journal.summary,
                "importance": journal.importance,
                "emotional_tags_json": journal.emotional_tags_json,
            }
            for journal in journals
        ],
        "errors": [
            {
                "id": str(event.id),
                "conversation_id": str(event.conversation_id)
                if event.conversation_id is not None
                else None,
                "source": event.source,
                "operation": event.operation,
                "code": event.code,
                "provider": event.provider,
                "safe_message": event.safe_message,
                "created_at": event.created_at.isoformat(),
            }
            for event in diagnostic_events
        ],
        "prompt_context": {
            "prompt_version": PROMPT_VERSION,
            "content_mode": safety_status["effective_mode"],
            "llm_provider": get_llm_provider().name,
            "current_summary": _current_context_summary(
                character=character,
                relationship=relationship,
                memories=memories,
                journals=journals,
                pending_proactive_events=pending_proactive_events,
                safety_status=safety_status,
                time_context=time_context,
            ),
        },
    }


@router.get("/conversation/{conversation_id}")
async def debug_conversation(
    conversation_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    conversation = await require_conversation(conversation_id, user, session)
    character = await session.get(Character, conversation.character_id)
    if character is None or character.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Character was not found.")
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(desc(Message.created_at))
        .limit(20)
    )
    messages = list(reversed(result.scalars().all()))
    last_assembled_context = await _last_assembled_context(session, conversation.id)
    pipeline = await _memory_pipeline_debug(
        session,
        user=user,
        character=character,
        messages=messages,
        private_conversation=conversation_is_private(conversation),
    )
    return {
        "conversation": {
            "id": str(conversation.id),
            "character_id": str(conversation.character_id),
            "title": conversation.title,
        },
        "recent_messages": [
            MessageOut.model_validate(message).model_dump(mode="json") for message in messages
        ],
        "memory_pipeline": pipeline,
        "last_assembled_context": last_assembled_context,
    }


@router.get("/jobs", response_model=list[ScheduledJobOut])
async def debug_jobs(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ScheduledJob]:
    result = await session.execute(
        select(ScheduledJob)
        .where(ScheduledJob.user_id == user.id)
        .order_by(desc(ScheduledJob.created_at))
        .limit(50)
    )
    return list(result.scalars().all())


@router.post("/conversation/{conversation_id}/proactive", response_model=MessageOut | None)
async def debug_create_proactive(
    conversation_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Message | None:
    conversation = await require_conversation(conversation_id, user, session)
    settings = get_settings()
    message = await create_inactivity_proactive_message(
        session,
        conversation,
        inactivity_hours=settings.proactive_inactivity_hours,
        force=True,
        proactive_type="proactive_message_create",
        provider=get_llm_provider(),
    )
    await session.commit()
    if message is not None:
        await session.refresh(message)
    return message


def _current_context_summary(
    *,
    character: Character,
    relationship: object,
    memories: list[MemoryItem],
    journals: list[object],
    pending_proactive_events: list[str],
    safety_status: dict,
    time_context: str,
) -> dict[str, object]:
    return {
        "snapshot_at": time_context[:80],
        "character": {"id": str(character.id), "name": character.name[:120]},
        "relationship": {
            "mood": _bounded_string(getattr(relationship, "mood", None), 80, "unknown"),
            "conflict_state": _bounded_string(
                getattr(relationship, "conflict_state", None),
                80,
                "unknown",
            ),
            "repair_needed": bool(getattr(relationship, "repair_needed", False)),
        },
        "retrieved_memories": [
            {
                "id": str(memory.id),
                "memory_type": memory.memory_type[:80],
                "pinned": memory.pinned,
            }
            for memory in memories[:12]
        ],
        "journals": [
            {
                "id": str(journal.id),
                "journal_type": _bounded_string(
                    getattr(journal, "journal_type", None),
                    80,
                    "summary",
                ),
                "continuity_signals": _bounded_string_list(
                    (getattr(journal, "metadata_json", None) or {}).get("continuity_signals"),
                    limit=8,
                    item_limit=80,
                ),
            }
            for journal in journals[:8]
        ],
        "pending_proactive_events": [event[:80] for event in pending_proactive_events[:8]],
        "safety": {
            "effective_mode": (
                "adult" if safety_status.get("effective_mode") == "adult" else "sfw"
            ),
            "allowed": bool(safety_status.get("allowed", False)),
            "reasons": _bounded_string_list(
                safety_status.get("reasons"),
                limit=8,
                item_limit=160,
            ),
            "intensity": _bounded_int(safety_status.get("intensity"), maximum=3),
        },
    }


async def _last_assembled_context(
    session: AsyncSession,
    conversation_id: uuid.UUID,
) -> dict[str, object] | None:
    assembled_at = Message.metadata_json[PRIVATE_PROMPT_CONTEXT_KEY]["assembled_at"].as_string()
    result = await session.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.role == "user",
            Message.metadata_json.has_key(PRIVATE_PROMPT_CONTEXT_KEY),  # type: ignore[attr-defined]
        )
        .order_by(assembled_at.desc().nullslast(), Message.created_at.desc())
        .limit(20)
    )
    for message in result.scalars().all():
        metadata = message.metadata_json if isinstance(message.metadata_json, dict) else {}
        context = _sanitize_prompt_context(metadata.get(PRIVATE_PROMPT_CONTEXT_KEY))
        if context is not None:
            return context
    return None


def _sanitize_prompt_context(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        return None
    assembled_at = _valid_timestamp(value.get("assembled_at"))
    generation_kind = value.get("generation_kind")
    provider = _safe_label(value.get("provider"), 80)
    prompt_version = _safe_label(value.get("prompt_version"), 120)
    content_mode = value.get("content_mode")
    manifest = _sanitize_context_manifest(value.get("context_manifest"))
    if (
        assembled_at is None
        or generation_kind not in {"chat", "stream", "reroll", "edit"}
        or provider is None
        or prompt_version is None
        or content_mode not in {"sfw", "adult"}
        or manifest is None
    ):
        return None
    return {
        "schema_version": 1,
        "assembled_at": assembled_at,
        "generation_kind": generation_kind,
        "provider": provider,
        "prompt_version": prompt_version,
        "content_mode": content_mode,
        "prompt_chars": _bounded_int(value.get("prompt_chars"), maximum=100_000),
        "response_plan_summary": _bounded_string(
            value.get("response_plan_summary"),
            1200,
            "No private response plan was assembled.",
        ),
        "context_manifest": manifest,
    }


def _sanitize_context_manifest(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    character = value.get("character")
    relationship = value.get("relationship")
    safety = value.get("safety")
    if not isinstance(character, dict) or not isinstance(relationship, dict):
        return None
    if not isinstance(safety, dict):
        return None
    character_id = _uuid_string(character.get("id"))
    if character_id is None:
        return None
    return {
        "character": {
            "id": character_id,
            "name": _bounded_string(character.get("name"), 120, "Unknown character"),
        },
        "relationship": {
            "mood": _bounded_string(relationship.get("mood"), 80, "unknown"),
            "conflict_state": _bounded_string(
                relationship.get("conflict_state"),
                80,
                "unknown",
            ),
            "repair_needed": relationship.get("repair_needed") is True,
        },
        "scenario": _sanitize_context_scenario(value.get("scenario")),
        "memory_items": _sanitize_context_items(
            value.get("memory_items"),
            type_key="memory_type",
            limit=12,
            include_pinned=True,
        ),
        "journal_items": _sanitize_context_items(
            value.get("journal_items"),
            type_key="journal_type",
            limit=8,
            include_signals=True,
        ),
        "recent_messages": _sanitize_recent_messages(value.get("recent_messages")),
        "safety": {
            "effective_mode": "adult" if safety.get("effective_mode") == "adult" else "sfw",
            "allowed": safety.get("allowed") is True,
            "reasons": _bounded_string_list(
                safety.get("reasons"),
                limit=8,
                item_limit=160,
            ),
            "intensity": _bounded_int(safety.get("intensity"), maximum=3),
        },
        "time_context": _bounded_string(value.get("time_context"), 80, "not provided"),
        "current_message_chars": _bounded_int(
            value.get("current_message_chars"),
            maximum=6000,
        ),
    }


def _sanitize_context_scenario(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {"mode": "default", "text_chars": 0}
    return {
        "mode": "custom" if value.get("mode") == "custom" else "default",
        "text_chars": _bounded_int(value.get("text_chars"), maximum=1200),
    }


def _sanitize_context_items(
    value: object,
    *,
    type_key: str,
    limit: int,
    include_pinned: bool = False,
    include_signals: bool = False,
) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, object]] = []
    for raw_item in value[:limit]:
        if not isinstance(raw_item, dict):
            continue
        item_id = _uuid_string(raw_item.get("id"))
        item_type = _safe_label(raw_item.get(type_key), 80)
        if item_id is None or item_type is None:
            continue
        item: dict[str, object] = {"id": item_id, type_key: item_type}
        if include_pinned:
            item["pinned"] = raw_item.get("pinned") is True
        if include_signals:
            item["continuity_signals"] = _bounded_string_list(
                raw_item.get("continuity_signals"),
                limit=8,
                item_limit=80,
            )
        items.append(item)
    return items


def _sanitize_recent_messages(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    messages: list[dict[str, str]] = []
    for raw_message in value[:12]:
        if not isinstance(raw_message, dict):
            continue
        message_id = _uuid_string(raw_message.get("id"))
        role = raw_message.get("role")
        privacy_mode = raw_message.get("privacy_mode")
        if message_id is None or role not in {"user", "assistant", "system"}:
            continue
        messages.append(
            {
                "id": message_id,
                "role": role,
                "privacy_mode": "private" if privacy_mode == "private" else "normal",
            }
        )
    return messages


def _valid_timestamp(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return value


def _uuid_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


def _safe_label(value: object, limit: int) -> str | None:
    if not isinstance(value, str) or not value or len(value) > limit:
        return None
    if not all(character.isalnum() or character in {"-", "_", ".", ":"} for character in value):
        return None
    return value


def _bounded_string(value: object, limit: int, fallback: str) -> str:
    if not isinstance(value, str) or not value:
        return fallback
    return value[:limit]


def _bounded_string_list(value: object, *, limit: int, item_limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item[:item_limit] for item in value[:limit] if isinstance(item, str)]


def _bounded_int(value: object, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, min(value, maximum))


def _scheduler_running(request: Request) -> bool:
    scheduler = getattr(request.app.state, "scheduler", None)
    return bool(scheduler is not None and getattr(scheduler, "running", False))


async def _memory_pipeline_debug(
    session: AsyncSession,
    *,
    user: User,
    character: Character,
    messages: list[Message],
    private_conversation: bool,
) -> list[dict[str, object]]:
    user_messages = [message for message in messages if message.role == "user"]
    if not user_messages:
        return []
    memory_by_source = await _memory_by_source_message(
        session,
        user_id=user.id,
        character_id=character.id,
        message_ids=[message.id for message in user_messages],
    )
    preferences = memory_preferences_from_boundaries(character.boundaries_json)
    rows: list[dict[str, object]] = []
    for message in user_messages:
        content_mode = _message_content_mode(message)
        if private_conversation or message_is_private(message):
            decision = {
                "accepted": False,
                "reason": "conversation_private",
            }
        elif not _memory_storage_allowed_for_debug(character, content_mode):
            decision = {
                "accepted": False,
                "reason": _memory_storage_block_reason(character, content_mode),
            }
        else:
            decision = analyze_memory_candidate(
                message.content,
                memory_preferences=preferences,
            ).to_metadata()
        stored_memory = memory_by_source.get(message.id)
        rows.append(
            {
                "message_id": str(message.id),
                "created_at": message.created_at.isoformat(),
                "content_mode": content_mode,
                "privacy_mode": message_privacy_mode(message),
                "decision": decision,
                "stored_memory": _memory_debug_payload(stored_memory),
            }
        )
    return rows


async def _memory_by_source_message(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    message_ids: list[uuid.UUID],
) -> dict[uuid.UUID, MemoryItem]:
    result = await session.execute(
        select(MemoryItem)
        .where(
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
            MemoryItem.source_message_id.in_(message_ids),
            MemoryItem.forgotten_at.is_(None),
        )
        .order_by(desc(MemoryItem.created_at))
    )
    memories: dict[uuid.UUID, MemoryItem] = {}
    for memory in result.scalars().all():
        if memory.source_message_id is not None and memory.source_message_id not in memories:
            memories[memory.source_message_id] = memory
    return memories


def _memory_debug_payload(memory: MemoryItem | None) -> dict[str, object] | None:
    if memory is None:
        return None
    return {
        "id": str(memory.id),
        "memory_type": memory.memory_type,
        "importance": memory.importance,
        "confidence": memory.confidence,
    }


def _message_content_mode(message: Message) -> str:
    metadata = message.metadata_json if isinstance(message.metadata_json, dict) else {}
    value = metadata.get("content_mode")
    return str(value) if value in {"sfw", "adult"} else "sfw"


def _memory_storage_allowed_for_debug(character: Character, content_mode: str) -> bool:
    preferences = memory_preferences_from_boundaries(character.boundaries_json)
    if preferences.get("private_mode_default") is True:
        return False
    if content_mode == "adult":
        return preferences.get("adult_memory_storage") is True
    return True


def _memory_storage_block_reason(character: Character, content_mode: str) -> str:
    preferences = memory_preferences_from_boundaries(character.boundaries_json)
    if preferences.get("private_mode_default") is True:
        return "character_private_memory_default"
    if content_mode == "adult":
        return "adult_memory_storage_disabled"
    return "storage_blocked"
