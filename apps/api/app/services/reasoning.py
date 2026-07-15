from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.companion.domain import CharacterSoul, EmotionalState, ResponsePlan, TurnPerception
from app.companion.emotion import project_emotional_state
from app.companion.perception import infer_turn_perception
from app.companion.soul import character_soul
from app.models import (
    Character,
    Conversation,
    EpisodicJournal,
    MemoryItem,
    Message,
    RelationshipState,
    User,
    utc_now,
)
from app.services.conversation_privacy import ConversationPrivacyMode
from app.services.conversation_scenario import (
    ConversationScenarioMode,
    effective_conversation_scenario,
)
from app.services.journal import list_journals
from app.services.memory import retrieve_memories
from app.services.relationship import get_current_relationship, get_or_create_relationship
from app.services.response_planner import (
    build_response_plan,
    build_structured_response_plan,
    list_pending_proactive_events,
)
from app.services.safety import adult_gate_status


@dataclass(frozen=True)
class ReasoningContext:
    relationship: RelationshipState
    memories: list[MemoryItem]
    journals: list[EpisodicJournal]
    recent_messages: list[Message]
    safety_status: dict
    time_context: str
    pending_proactive_events: list[str]
    response_plan: str
    structured_plan: ResponsePlan
    perception: TurnPerception
    emotional_state: EmotionalState
    soul: CharacterSoul
    scenario_mode: ConversationScenarioMode
    scenario_text: str | None


async def build_reasoning_context(
    session: AsyncSession,
    *,
    user: User,
    character: Character,
    conversation: Conversation,
    current_message: str,
    requested_mode: str,
    privacy_mode: ConversationPrivacyMode,
    current_message_id: uuid.UUID | None = None,
) -> ReasoningContext:
    is_private_turn = privacy_mode == "private"
    # Stage 1: perceive the turn from the live thread before durable retrieval.
    recent_messages = await _list_recent_messages(
        session,
        conversation.id,
        limit=14,
        include_private=is_private_turn,
        exclude_message_id=current_message_id,
    )
    perception = infer_turn_perception(
        current_message,
        recent_messages=recent_messages,
        journals=[],
    )

    # Stage 2: retrieve relationship, durable memories, and episodic context.
    if is_private_turn:
        relationship = await get_or_create_relationship(session, user.id, character.id)
    else:
        relationship = await get_current_relationship(session, user.id, character.id)
    memories = await retrieve_memories(
        session,
        user_id=user.id,
        character_id=character.id,
        query=current_message,
        limit=7,
        mark_recalled=not is_private_turn,
    )
    journal_candidates = await list_journals(session, user.id, character.id, limit=50)
    journals = rank_relevant_journals(journal_candidates, query=current_message, limit=4)
    pending_proactive_events = await list_pending_proactive_events(
        session,
        user_id=user.id,
        character_id=character.id,
        conversation_id=conversation.id,
    )
    now = utc_now()
    # Stage 3: resolve structural boundaries and the companion's decayed mood.
    safety_status = adult_gate_status(
        user,
        character,
        requested_mode,
        relationship=relationship,
    )
    time_context = now.strftime("%A, %Y-%m-%d %H:%M UTC")
    scenario = effective_conversation_scenario(conversation, character)
    emotional_state = project_emotional_state(relationship, now=now)
    soul = character_soul(character)
    # Stage 4: choose a bounded private response strategy before generation.
    structured_plan = build_structured_response_plan(
        character=character,
        relationship=relationship,
        memories=memories,
        journals=journals,
        recent_messages=recent_messages,
        current_message=current_message,
        content_mode=safety_status["effective_mode"],
        safety_status=safety_status,
        soul=soul,
        perception=perception,
        emotion=emotional_state,
    )
    response_plan = build_response_plan(
        character=character,
        relationship=relationship,
        memories=memories,
        journals=journals,
        recent_messages=recent_messages,
        current_message=current_message,
        content_mode=safety_status["effective_mode"],
        safety_status=safety_status,
        time_context=time_context,
        pending_proactive_events=pending_proactive_events,
        scenario_mode=scenario.mode,
        scenario_text=scenario.text,
    )
    return ReasoningContext(
        relationship=relationship,
        memories=memories,
        journals=journals,
        recent_messages=recent_messages,
        safety_status=safety_status,
        time_context=time_context,
        pending_proactive_events=pending_proactive_events,
        response_plan=response_plan,
        structured_plan=structured_plan,
        perception=perception,
        emotional_state=emotional_state,
        soul=soul,
        scenario_mode=scenario.mode,
        scenario_text=scenario.text,
    )


def rank_relevant_journals(
    journals: list[EpisodicJournal],
    *,
    query: str,
    limit: int,
) -> list[EpisodicJournal]:
    query_terms = _ranking_terms(query)

    def ranking_key(journal: EpisodicJournal) -> tuple[float, float, float, str]:
        journal_text = " ".join(
            (
                journal.title,
                journal.summary,
                *journal.callbacks_json,
                *journal.unresolved_threads_json,
            )
        )
        journal_terms = _ranking_terms(journal_text)
        relevance = (
            len(query_terms & journal_terms) / max(len(query_terms), 1) if query_terms else 0.0
        )
        emotional_importance = min(len(journal.emotional_tags_json), 3) * 0.08
        timestamp = (journal.updated_at or journal.created_at).timestamp()
        return relevance, journal.importance + emotional_importance, timestamp, str(journal.id)

    return sorted(journals, key=ranking_key, reverse=True)[: max(0, limit)]


def _ranking_terms(value: str) -> set[str]:
    return {term for term in re.findall(r"[a-z0-9']+", value.casefold()) if len(term) > 2}


async def _list_recent_messages(
    session: AsyncSession,
    conversation_id,
    *,
    limit: int,
    include_private: bool,
    exclude_message_id: uuid.UUID | None = None,
) -> list[Message]:
    statement = select(Message).where(Message.conversation_id == conversation_id)
    if exclude_message_id is not None:
        statement = statement.where(Message.id != exclude_message_id)
    if not include_private:
        message_privacy = Message.metadata_json["privacy_mode"].as_string()
        statement = statement.where(
            or_(
                Message.role == "system",
                message_privacy.is_(None),
                message_privacy != "private",
            )
        )
    result = await session.execute(statement.order_by(desc(Message.created_at)).limit(limit))
    return list(reversed(result.scalars().all()))
