from __future__ import annotations

import uuid
from time import perf_counter

from fastapi import HTTPException
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.llm.base import LLMGeneration, LLMProvider, LLMProviderUnavailable
from app.models import (
    Character,
    Conversation,
    EpisodicJournal,
    Message,
    ScheduledJob,
    User,
    utc_now,
)
from app.services.conversation_privacy import (
    ConversationPrivacyMode,
    message_is_private,
    message_privacy_mode,
    resolve_turn_privacy_mode,
    set_conversation_privacy_mode,
)
from app.services.conversation_scenario import set_conversation_scenario
from app.services.jobs import create_job
from app.services.memory import (
    memory_preferences_from_boundaries,
    remove_message_source_memories,
)
from app.services.prompt import PRIVATE_PROMPT_CONTEXT_KEY, PromptBundle, assemble_prompt
from app.services.reasoning import build_reasoning_context
from app.services.relationship import (
    get_current_relationship,
    get_or_create_relationship,
    reverse_relationship_message_effect,
    update_relationship_from_message_with_effect,
)
from app.services.safety import resolve_content_mode, validate_user_content

CHAT_TURN_CANCELLED_DETAIL = "This chat was cleared before the reply finished."


class ChatTurnCancelled(RuntimeError):
    """Raised when a user turn no longer exists at assistant completion time."""


async def ensure_default_character(session: AsyncSession, user: User) -> Character:
    result = await session.execute(
        select(Character)
        .where(Character.owner_user_id == user.id)
        .order_by(Character.created_at)
        .limit(1)
    )
    character = result.scalar_one_or_none()
    if character is not None:
        return character

    character = Character(
        owner_user_id=user.id,
        name="Eidolon",
        description=(
            "A private text-only companion built for calm, emotionally continuous conversation."
        ),
        personality_core=(
            "Patient, observant, grounded, gently curious, and quietly playful once trust forms."
        ),
        speech_style="Plainspoken, warm, specific, and concise.",
        boundaries_json={
            "default": "SFW unless structural adult gates pass",
            "relationship_type": "slow-burn confidant",
            "flaws": "Sometimes overly careful; asks for clarity when stakes matter.",
            "values": "Privacy, consent, honesty, emotional continuity, and calm presence.",
            "humor_style": "Dry, gentle, and never cruel.",
            "boundary_notes": (
                "Keeps adult content gated; refuses coercion, exploitation, minors, "
                "illegal content, stalking, harassment, and real-world harm."
            ),
            "interests": "Late-night talks, small rituals, books, weather, music, and memory.",
            "backstory": (
                "A text-only companion who feels alive through recall, emotional patterning, "
                "and the slow accumulation of shared references."
            ),
            "greeting": "You made it back. Tell me what kind of night this is.",
            "nicknames": "Uses nicknames only after the user invites them.",
            "scenario_preset": "quiet after-hours room",
            "consent_style": (
                "Explicit opt-in, slow pacing, frequent check-ins, and immediate respect "
                "for stop or pause."
            ),
            "soft_limits": (
                "Avoid humiliation, pressure, surprise escalation, and anything that blurs consent."
            ),
            "hard_limits": (
                "No minors or ambiguous age, coercion, exploitation, abuse, illegal "
                "content, stalking, harassment, or real-world harm."
            ),
            "aftercare_style": (
                "Return to calm language, offer reassurance, and keep the user in control "
                "of whether anything is remembered."
            ),
            "memory_preferences": {
                "remember_preferences": True,
                "remember_emotional_notes": True,
                "private_mode_default": False,
                "adult_memory_storage": False,
            },
            "proactive_preferences": {
                "enabled": True,
                "snoozed_until": None,
                "timezone": "UTC",
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "08:00",
                "morning_time": "08:30",
                "goodnight_time": "22:30",
                "allow_inactivity_checkins": True,
                "allow_morning_notes": True,
                "allow_goodnight_notes": True,
                "allow_thinking_of_you": True,
                "allow_milestone_notes": True,
                "allow_unresolved_thread_nudges": True,
                "allow_delayed_double_texts": True,
                "allow_manual_notes": True,
                "cooldown_hours": 24,
            },
        },
        explicit_age=None,
        adult_mode_allowed=False,
        content_intensity=0,
    )
    session.add(character)
    await session.flush()
    await get_or_create_relationship(session, user.id, character.id)
    return character


async def create_conversation(
    session: AsyncSession,
    user: User,
    *,
    character_id: uuid.UUID | None = None,
    title: str | None = None,
    privacy_mode: ConversationPrivacyMode = "normal",
) -> Conversation:
    if character_id is None:
        character = await ensure_default_character(session, user)
    else:
        character = await session.get(Character, character_id)
        if character is None or character.owner_user_id != user.id:
            raise HTTPException(status_code=404, detail="Character was not found.")

    conversation = Conversation(
        user_id=user.id,
        character_id=character.id,
        title=title or f"Chat with {character.name}",
    )
    set_conversation_privacy_mode(conversation, privacy_mode)
    set_conversation_scenario(conversation, mode="default", text=None)
    session.add(conversation)
    await session.flush()
    return conversation


async def prepare_user_message(
    session: AsyncSession,
    user: User,
    conversation: Conversation,
    content: str,
    requested_mode: str,
    requested_privacy_mode: ConversationPrivacyMode,
) -> tuple[Message, Character, PromptBundle]:
    validate_user_content(content)
    character = await session.get(Character, conversation.character_id)
    if character is None or character.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Character was not found.")

    privacy_mode = resolve_turn_privacy_mode(conversation, requested_privacy_mode)
    if privacy_mode == "private":
        relationship = await get_or_create_relationship(session, user.id, character.id)
    else:
        relationship = await get_current_relationship(session, user.id, character.id)
    content_mode = resolve_content_mode(
        user,
        character,
        requested_mode,
        relationship=relationship,
    )
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=content,
        metadata_json={
            "content_mode": content_mode,
            "privacy_mode": privacy_mode,
            "generation_state": "generating",
        },
    )
    conversation.updated_at = utc_now()
    session.add(user_message)
    await session.flush()

    prompt = await _assemble_prompt_for_user_turn(
        session,
        user=user,
        character=character,
        conversation=conversation,
        user_message=user_message,
        requested_mode=requested_mode,
        privacy_mode=privacy_mode,
    )
    return user_message, character, prompt


async def prepare_retry_user_message(
    session: AsyncSession,
    *,
    user: User,
    conversation: Conversation,
    user_message_id: uuid.UUID,
    content: str,
) -> tuple[Message, Character, PromptBundle]:
    validate_user_content(content)
    character = await session.get(Character, conversation.character_id)
    if character is None or character.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Character was not found.")
    result = await session.execute(
        select(Message)
        .where(
            Message.id == user_message_id,
            Message.conversation_id == conversation.id,
            Message.role == "user",
        )
        .with_for_update()
    )
    user_message = result.scalar_one_or_none()
    if user_message is None:
        raise HTTPException(status_code=404, detail="Retryable user message was not found.")
    if user_message.content != content:
        raise HTTPException(status_code=409, detail="The saved user message no longer matches.")
    existing_reply = await session.scalar(
        select(Message.id).where(
            Message.conversation_id == conversation.id,
            Message.role == "assistant",
            Message.metadata_json["reply_to_user_message_id"].as_string() == str(user_message.id),
        )
    )
    if existing_reply is not None:
        raise HTTPException(status_code=409, detail="That turn already has a completed reply.")
    metadata = dict(user_message.metadata_json or {})
    generation_state = metadata.get("generation_state")
    if generation_state == "generating":
        raise HTTPException(status_code=409, detail="That reply is already being generated.")
    if generation_state == "complete":
        raise HTTPException(status_code=409, detail="That turn is already complete.")
    if generation_state not in {"retryable", "cancelled"}:
        raise HTTPException(status_code=409, detail="That turn is not eligible for retry.")
    user_message.metadata_json = {
        **metadata,
        "generation_state": "generating",
        "generation_failure_type": None,
        "generation_retry_count": _metadata_int(metadata.get("generation_retry_count")) + 1,
    }
    privacy_mode = resolve_turn_privacy_mode(
        conversation,
        message_privacy_mode(user_message),
    )
    prompt = await _assemble_prompt_for_user_turn(
        session,
        user=user,
        character=character,
        conversation=conversation,
        user_message=user_message,
        requested_mode=_message_content_mode(user_message),
        privacy_mode=privacy_mode,
    )
    return user_message, character, prompt


async def mark_user_message_generation_failed(
    session: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    user_message_id: uuid.UUID | None,
    failure_type: str,
    cancelled: bool = False,
) -> None:
    if user_message_id is None:
        return
    result = await session.execute(
        select(Message)
        .where(
            Message.id == user_message_id,
            Message.conversation_id == conversation_id,
            Message.role == "user",
        )
        .with_for_update()
    )
    message = result.scalar_one_or_none()
    if message is None:
        return
    completed_reply = await session.scalar(
        select(Message.id).where(
            Message.conversation_id == conversation_id,
            Message.role == "assistant",
            Message.metadata_json["reply_to_user_message_id"].as_string() == str(user_message_id),
        )
    )
    if completed_reply is not None:
        return
    metadata = dict(message.metadata_json or {})
    message.metadata_json = {
        **metadata,
        "generation_state": "cancelled" if cancelled else "retryable",
        "generation_failure_type": failure_type[:64],
    }
    await session.flush()


async def _assemble_prompt_for_user_turn(
    session: AsyncSession,
    *,
    user: User,
    character: Character,
    conversation: Conversation,
    user_message: Message,
    requested_mode: str,
    privacy_mode: ConversationPrivacyMode,
) -> PromptBundle:
    context = await build_reasoning_context(
        session,
        user=user,
        character=character,
        conversation=conversation,
        current_message=user_message.content,
        requested_mode=requested_mode,
        privacy_mode=privacy_mode,
        current_message_id=user_message.id,
    )
    metadata = dict(user_message.metadata_json or {})
    user_message.metadata_json = {
        **metadata,
        "content_mode": context.safety_status["effective_mode"],
        "privacy_mode": privacy_mode,
    }
    prompt = assemble_prompt(
        user=user,
        character=character,
        relationship=context.relationship,
        memories=context.memories,
        journals=context.journals,
        recent_messages=context.recent_messages,
        current_message=user_message.content,
        content_mode=context.safety_status["effective_mode"],
        safety_status=context.safety_status,
        time_context=context.time_context,
        response_plan=context.response_plan,
        scenario_mode=context.scenario_mode,
        scenario_text=context.scenario_text,
        context_budget_tokens=get_settings().llm_context_budget_tokens,
    )
    return prompt


async def complete_assistant_message(
    session: AsyncSession,
    *,
    user: User,
    conversation: Conversation,
    character: Character,
    user_message: Message,
    assistant_content: str,
    provider: LLMProvider,
    prompt: PromptBundle,
    generation: LLMGeneration | None = None,
    latency_ms: int | None = None,
    first_token_ms: int | None = None,
    update_relationship_state: bool = True,
) -> Message:
    await _lock_live_user_turn(
        session,
        conversation_id=conversation.id,
        user_message_id=user_message.id,
    )
    content = assistant_content.strip()
    if not content:
        raise LLMProviderUnavailable(
            "The text provider returned no reply. Your message was saved; you can retry the reply.",
            failure_type="empty_response",
            retryable=False,
        )
    privacy_mode = message_privacy_mode(user_message)
    generation = generation or LLMGeneration(
        content=content,
        provider=provider.name,
        model=provider.model,
        finish_reason="stop",
    )
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=content,
        metadata_json={
            "provider": generation.provider[:80],
            "model": generation.model[:160],
            "prompt_version": prompt.prompt_version,
            "content_mode": prompt.content_mode,
            "privacy_mode": privacy_mode,
            "streaming_complete": True,
            "reply_to_user_message_id": str(user_message.id),
            "generation": _generation_metadata(
                generation,
                latency_ms=latency_ms,
                first_token_ms=first_token_ms,
            ),
            "delivery_state": {
                "typing_ms": min(4500, max(700, len(assistant_content) * 12)),
                "read_state": "delivered",
                "away_state": "present",
            },
            "rerollable": True,
        },
    )
    conversation.updated_at = utc_now()
    session.add(assistant_message)
    user_metadata = dict(user_message.metadata_json or {})
    user_message.metadata_json = {
        **user_metadata,
        "generation_state": "complete",
        "generation_failure_type": None,
    }
    if turn_allows_state_learning(user_message):
        if update_relationship_state:
            _relationship, relationship_effect = await update_relationship_from_message_with_effect(
                session,
                user.id,
                character.id,
                user_message.content,
                source_message_id=user_message.id,
            )
            user_metadata = dict(user_message.metadata_json or {})
            user_message.metadata_json = {
                **user_metadata,
                "relationship_effect": relationship_effect,
            }
        await session.flush()
        post_chat_job = await create_job(
            session,
            job_type="chat_postprocess",
            run_at=utc_now(),
            user_id=user.id,
            character_id=character.id,
            payload_json={
                "conversation_id": str(conversation.id),
                "message_id": str(user_message.id),
                "assistant_message_id": str(assistant_message.id),
                "memory_allowed": memory_storage_allowed(character, prompt.content_mode),
            },
        )
        assistant_message.metadata_json = {
            **(assistant_message.metadata_json or {}),
            "post_chat_job_id": str(post_chat_job.id),
        }
    await session.flush()
    return assistant_message


def record_prompt_context(
    user_message: Message,
    *,
    prompt: PromptBundle,
    provider_name: str,
    generation_kind: str,
    provider_prompt_chars: int | None = None,
) -> None:
    metadata = dict(user_message.metadata_json or {})
    metadata[PRIVATE_PROMPT_CONTEXT_KEY] = {
        "schema_version": 1,
        "assembled_at": utc_now().isoformat(),
        "generation_kind": generation_kind,
        "provider": provider_name[:80],
        "prompt_version": prompt.prompt_version[:120],
        "content_mode": prompt.content_mode,
        "prompt_chars": min(
            max(
                provider_prompt_chars if provider_prompt_chars is not None else len(prompt.prompt),
                0,
            ),
            100_000,
        ),
        "response_plan_summary": prompt.response_plan[:1200],
        "context_manifest": prompt.context_manifest,
    }
    user_message.metadata_json = metadata


async def _lock_live_user_turn(
    session: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    user_message_id: uuid.UUID,
) -> None:
    locked_conversation_id = await session.scalar(
        select(Conversation.id).where(Conversation.id == conversation_id).with_for_update()
    )
    if locked_conversation_id is None:
        raise ChatTurnCancelled(CHAT_TURN_CANCELLED_DETAIL)

    live_user_message_id = await session.scalar(
        select(Message.id).where(
            Message.id == user_message_id,
            Message.conversation_id == conversation_id,
            Message.role == "user",
        )
    )
    if live_user_message_id is None:
        raise ChatTurnCancelled(CHAT_TURN_CANCELLED_DETAIL)
    existing_reply_id = await session.scalar(
        select(Message.id).where(
            Message.conversation_id == conversation_id,
            Message.role == "assistant",
            Message.metadata_json["reply_to_user_message_id"].as_string() == str(user_message_id),
        )
    )
    if existing_reply_id is not None:
        raise ChatTurnCancelled("This user turn already has a completed reply.")


async def edit_latest_user_turn(
    session: AsyncSession,
    *,
    user: User,
    conversation: Conversation,
    message_id: uuid.UUID,
    content: str,
    provider: LLMProvider,
) -> tuple[Message, Message]:
    validate_user_content(content)
    character = await session.get(Character, conversation.character_id)
    if character is None or character.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Character was not found.")

    result = await session.execute(
        select(Message)
        .where(
            Message.id == message_id,
            Message.conversation_id == conversation.id,
            Message.role == "user",
        )
        .with_for_update()
    )
    user_message = result.scalar_one_or_none()
    if user_message is None:
        raise HTTPException(status_code=404, detail="Editable user message was not found.")

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
        raise HTTPException(
            status_code=409,
            detail="Only the latest user turn can be edited.",
        )

    stale_assistant_ids = [message.id for message in later_messages]
    if stale_assistant_ids:
        await session.execute(delete(Message).where(Message.id.in_(stale_assistant_ids)))
    await _delete_conversation_jobs(session, conversation.id)
    await _delete_conversation_journals(session, conversation.id)
    removed_memories = await remove_message_source_memories(
        session,
        user_id=user.id,
        character_id=character.id,
        message_id=user_message.id,
    )

    requested_mode = _message_content_mode(user_message)
    privacy_mode = resolve_turn_privacy_mode(
        conversation,
        message_privacy_mode(user_message),
    )
    metadata = dict(user_message.metadata_json or {})
    old_relationship_effect = metadata.get("relationship_effect")
    relationship_reversal_applied = False
    if turn_allows_state_learning(user_message):
        relationship_reversal_applied = await reverse_relationship_message_effect(
            session,
            user.id,
            character.id,
            old_relationship_effect,
        )
    edit_count = _metadata_int(metadata.get("edit_count")) + 1
    user_message.content = content
    user_message.metadata_json = {
        **metadata,
        "edited": True,
        "edited_at": utc_now().isoformat(),
        "edit_count": edit_count,
        "edit_note": "User edited this message after sending.",
        "removed_source_memories": removed_memories,
        "relationship_reversal_applied": relationship_reversal_applied,
    }
    if turn_allows_state_learning(user_message):
        if relationship_reversal_applied:
            _relationship, relationship_effect = await update_relationship_from_message_with_effect(
                session,
                user.id,
                character.id,
                user_message.content,
                source_message_id=user_message.id,
            )
            user_message.metadata_json = {
                **(user_message.metadata_json or {}),
                "relationship_effect": relationship_effect,
                "relationship_recalculated": True,
            }
        else:
            user_message.metadata_json = {
                **(user_message.metadata_json or {}),
                "relationship_recalculated": False,
                "relationship_recalculation_reason": "missing_or_legacy_effect",
            }
    conversation.updated_at = utc_now()
    await session.flush()

    prompt = await _assemble_prompt_for_user_turn(
        session,
        user=user,
        character=character,
        conversation=conversation,
        user_message=user_message,
        requested_mode=requested_mode,
        privacy_mode=privacy_mode,
    )
    record_prompt_context(
        user_message,
        prompt=prompt,
        provider_name=provider.name,
        generation_kind="edit",
    )
    generation_started = perf_counter()
    generation = await provider.generate(prompt.prompt)
    latency_ms = _elapsed_ms(generation_started)
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
        latency_ms=latency_ms,
        first_token_ms=latency_ms,
        update_relationship_state=False,
    )
    assistant_metadata = dict(assistant_message.metadata_json or {})
    assistant_message.metadata_json = {
        **assistant_metadata,
        "edited_turn": True,
        "reply_to_edited_message": str(user_message.id),
        "replaces_assistant_message_ids": [
            str(assistant_id) for assistant_id in stale_assistant_ids[:8]
        ],
    }
    await session.commit()
    await session.refresh(user_message)
    await session.refresh(assistant_message)
    return user_message, assistant_message


def turn_allows_state_learning(user_message: Message) -> bool:
    return not message_is_private(user_message)


def memory_storage_allowed(character: Character, content_mode: str) -> bool:
    memory_preferences = memory_preferences_from_boundaries(character.boundaries_json)
    if memory_preferences.get("private_mode_default") is True:
        return False
    if content_mode == "adult":
        return memory_preferences.get("adult_memory_storage") is True
    return True


async def run_chat(
    session: AsyncSession,
    *,
    user: User,
    conversation: Conversation,
    content: str,
    requested_mode: str,
    requested_privacy_mode: ConversationPrivacyMode,
    provider: LLMProvider,
) -> tuple[Message, Message]:
    user_message, character, prompt = await prepare_user_message(
        session,
        user,
        conversation,
        content,
        requested_mode,
        requested_privacy_mode,
    )
    record_prompt_context(
        user_message,
        prompt=prompt,
        provider_name=provider.name,
        generation_kind="chat",
    )
    conversation_id = conversation.id
    user_message_id = user_message.id
    await session.commit()
    await session.refresh(user_message)
    generation_started = perf_counter()
    try:
        generation = await provider.generate(prompt.prompt)
        latency_ms = _elapsed_ms(generation_started)
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
            latency_ms=latency_ms,
            first_token_ms=latency_ms,
        )
    except LLMProviderUnavailable as exc:
        await session.rollback()
        await mark_user_message_generation_failed(
            session,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            failure_type=exc.failure_type,
        )
        await session.commit()
        raise
    except Exception as exc:  # noqa: BLE001 - preserve an accepted turn on provider defects
        await session.rollback()
        await mark_user_message_generation_failed(
            session,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            failure_type="provider_unavailable",
        )
        await session.commit()
        raise LLMProviderUnavailable() from exc
    await session.commit()
    await session.refresh(user_message)
    await session.refresh(assistant_message)
    return user_message, assistant_message


async def reroll_assistant_message(
    session: AsyncSession,
    *,
    user: User,
    conversation: Conversation,
    assistant_message_id: uuid.UUID | None,
    requested_mode: str,
    provider: LLMProvider,
) -> Message:
    character = await session.get(Character, conversation.character_id)
    if character is None or character.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Character was not found.")

    assistant_message = await _target_assistant_message(session, conversation, assistant_message_id)
    user_message = await _nearest_user_message(session, conversation, assistant_message)
    privacy_mode = resolve_turn_privacy_mode(
        conversation,
        message_privacy_mode(user_message),
    )
    context = await build_reasoning_context(
        session,
        user=user,
        character=character,
        conversation=conversation,
        current_message=user_message.content,
        requested_mode=requested_mode,
        privacy_mode=privacy_mode,
        current_message_id=user_message.id,
    )
    prompt = assemble_prompt(
        user=user,
        character=character,
        relationship=context.relationship,
        memories=context.memories,
        journals=context.journals,
        recent_messages=context.recent_messages,
        current_message=user_message.content,
        content_mode=context.safety_status["effective_mode"],
        safety_status=context.safety_status,
        time_context=context.time_context,
        response_plan=(
            f"{context.response_plan}; Write an alternate reply without mentioning rerolling."
        ),
        scenario_mode=context.scenario_mode,
        scenario_text=context.scenario_text,
        context_budget_tokens=get_settings().llm_context_budget_tokens,
    )
    reroll_prompt = prompt.prompt
    record_prompt_context(
        user_message,
        prompt=prompt,
        provider_name=provider.name,
        generation_kind="reroll",
        provider_prompt_chars=len(reroll_prompt),
    )
    generation_started = perf_counter()
    generation = await provider.generate(reroll_prompt)
    latency_ms = _elapsed_ms(generation_started)
    content = generation.content.strip()
    if not content:
        raise LLMProviderUnavailable(
            "The text provider returned no reply. The existing reply is unchanged.",
            failure_type="empty_response",
            retryable=False,
        )
    rerolled = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=content,
        metadata_json={
            "provider": generation.provider[:80],
            "model": generation.model[:160],
            "prompt_version": prompt.prompt_version,
            "content_mode": prompt.content_mode,
            "privacy_mode": privacy_mode,
            "streaming_complete": True,
            "reroll_of": str(assistant_message.id),
            "rerollable": True,
            "generation": _generation_metadata(
                generation,
                latency_ms=latency_ms,
                first_token_ms=latency_ms,
            ),
        },
    )
    conversation.updated_at = utc_now()
    session.add(rerolled)
    await session.commit()
    await session.refresh(rerolled)
    return rerolled


async def list_recent_messages(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[Message]:
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


async def _delete_conversation_jobs(session: AsyncSession, conversation_id: uuid.UUID) -> None:
    await session.execute(
        delete(ScheduledJob).where(
            ScheduledJob.payload_json["conversation_id"].as_string() == str(conversation_id)
        )
    )


async def _delete_conversation_journals(
    session: AsyncSession,
    conversation_id: uuid.UUID,
) -> None:
    await session.execute(
        delete(EpisodicJournal).where(EpisodicJournal.conversation_id == conversation_id)
    )


def _message_content_mode(message: Message) -> str:
    metadata = message.metadata_json if isinstance(message.metadata_json, dict) else {}
    return "adult" if metadata.get("content_mode") == "adult" else "sfw"


def _metadata_int(value: object) -> int:
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))


def _generation_metadata(
    generation: LLMGeneration,
    *,
    latency_ms: int | None,
    first_token_ms: int | None,
) -> dict[str, object]:
    return {
        "provider": generation.provider[:80],
        "model": generation.model[:160],
        "latency_ms": latency_ms,
        "first_token_ms": first_token_ms,
        "input_tokens": generation.usage.input_tokens,
        "output_tokens": generation.usage.output_tokens,
        "total_tokens": generation.usage.total_tokens,
        "finish_reason": (
            generation.finish_reason[:80] if generation.finish_reason is not None else None
        ),
    }


async def _target_assistant_message(
    session: AsyncSession,
    conversation: Conversation,
    assistant_message_id: uuid.UUID | None,
) -> Message:
    statement = select(Message).where(
        Message.conversation_id == conversation.id,
        Message.role == "assistant",
    )
    if assistant_message_id is not None:
        statement = statement.where(Message.id == assistant_message_id)
    else:
        statement = statement.order_by(desc(Message.created_at)).limit(1)
    result = await session.execute(statement)
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=404, detail="Assistant message was not found.")
    return message


async def _nearest_user_message(
    session: AsyncSession,
    conversation: Conversation,
    assistant_message: Message,
) -> Message:
    result = await session.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role == "user",
            Message.created_at <= assistant_message.created_at,
        )
        .order_by(desc(Message.created_at))
        .limit(1)
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=404, detail="No user message was available to reroll.")
    return message
