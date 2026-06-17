from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import LLMProvider
from app.models import Character, Conversation, Message, User, utc_now
from app.services.journal import maybe_create_journal_from_conversation
from app.services.memory import maybe_extract_memory
from app.services.proactive import ensure_proactive_jobs
from app.services.prompt import PromptBundle, assemble_prompt
from app.services.reasoning import build_reasoning_context
from app.services.relationship import get_or_create_relationship, update_relationship_from_message
from app.services.safety import resolve_content_mode, validate_user_content


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
        description="A private text-only companion for a calm, continuous conversation.",
        personality_core="Patient, observant, grounded, and gently curious.",
        speech_style="Plainspoken, warm, and concise.",
        boundaries_json={"default": "SFW unless structural adult gates pass"},
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
    session.add(conversation)
    await session.flush()
    return conversation


async def prepare_user_message(
    session: AsyncSession,
    user: User,
    conversation: Conversation,
    content: str,
    requested_mode: str,
) -> tuple[Message, Character, PromptBundle]:
    validate_user_content(content)
    character = await session.get(Character, conversation.character_id)
    if character is None or character.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Character was not found.")

    content_mode = resolve_content_mode(user, character, requested_mode)
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=content,
        metadata_json={"content_mode": content_mode},
    )
    conversation.updated_at = utc_now()
    session.add(user_message)
    await session.flush()

    relationship = await get_or_create_relationship(session, user.id, character.id)
    context = await build_reasoning_context(
        session,
        user=user,
        character=character,
        conversation=conversation,
        current_message=content,
        requested_mode=requested_mode,
    )
    prompt = assemble_prompt(
        user=user,
        character=character,
        relationship=context.relationship or relationship,
        memories=context.memories,
        journals=context.journals,
        recent_messages=context.recent_messages,
        current_message=content,
        content_mode=context.safety_status["effective_mode"],
        safety_status=context.safety_status,
        time_context=context.time_context,
    )
    return user_message, character, prompt


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
) -> Message:
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=assistant_content.strip() or "I am here, but the model returned an empty response.",
        metadata_json={
            "provider": provider.name,
            "prompt_version": prompt.prompt_version,
            "content_mode": prompt.content_mode,
            "streaming_complete": True,
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
    await maybe_extract_memory(
        session,
        user_id=user.id,
        character_id=character.id,
        message_id=user_message.id,
        content=user_message.content,
    )
    await update_relationship_from_message(session, user.id, character.id, user_message.content)
    await maybe_create_journal_from_conversation(
        session,
        user=user,
        character=character,
        conversation=conversation,
    )
    await ensure_proactive_jobs(
        session,
        conversation=conversation,
        user_id=user.id,
        character_id=character.id,
    )
    await session.flush()
    return assistant_message


async def run_chat(
    session: AsyncSession,
    *,
    user: User,
    conversation: Conversation,
    content: str,
    requested_mode: str,
    provider: LLMProvider,
) -> tuple[Message, Message]:
    user_message, character, prompt = await prepare_user_message(
        session,
        user,
        conversation,
        content,
        requested_mode,
    )
    assistant_content = await provider.generate(prompt.prompt)
    assistant_message = await complete_assistant_message(
        session,
        user=user,
        conversation=conversation,
        character=character,
        user_message=user_message,
        assistant_content=assistant_content,
        provider=provider,
        prompt=prompt,
    )
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
    context = await build_reasoning_context(
        session,
        user=user,
        character=character,
        conversation=conversation,
        current_message=user_message.content,
        requested_mode=requested_mode,
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
    )
    reroll_prompt = (
        f"{prompt.prompt}\n\n"
        "Reroll instruction: write an alternate reply without mentioning rerolling."
    )
    assistant_content = await provider.generate(reroll_prompt)
    rerolled = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=assistant_content.strip() or "I am here, but the model returned an empty response.",
        metadata_json={
            "provider": provider.name,
            "prompt_version": prompt.prompt_version,
            "content_mode": prompt.content_mode,
            "streaming_complete": True,
            "reroll_of": str(assistant_message.id),
            "rerollable": True,
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
