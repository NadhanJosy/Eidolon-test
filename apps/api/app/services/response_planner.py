from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import replace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.companion.domain import CharacterSoul, EmotionalState, ResponsePlan, TurnPerception
from app.companion.emotion import project_emotional_state
from app.companion.perception import infer_turn_perception
from app.companion.planning import plan_response
from app.companion.soul import character_soul
from app.models import (
    Character,
    ContinuityThread,
    EpisodicJournal,
    MemoryItem,
    Message,
    RelationshipState,
    ScheduledJob,
)
from app.services.journal import journal_continuity_notes, journal_continuity_signals
from app.services.relationship import RelationshipPlanContext

PROACTIVE_LABELS = {
    "proactive_inactivity_check": "quiet check-in",
    "proactive_morning_check": "morning note",
    "proactive_goodnight_check": "goodnight note",
    "proactive_thinking_of_you": "thinking-of-you note",
    "proactive_milestone_check": "milestone note",
    "proactive_unresolved_thread_nudge": "open-thread follow-up",
    "proactive_delayed_double_text": "delayed follow-up",
    "proactive_message_create": "manual check-in",
}


async def list_pending_proactive_events(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    conversation_id: uuid.UUID | None = None,
    limit: int = 8,
) -> list[str]:
    statement = (
        select(ScheduledJob)
        .where(
            ScheduledJob.user_id == user_id,
            ScheduledJob.character_id == character_id,
            ScheduledJob.status == "pending",
            ScheduledJob.job_type.like("proactive_%"),
        )
        .order_by(ScheduledJob.run_at)
        .limit(max(1, min(limit * 3, 24)))
    )
    if conversation_id is not None:
        statement = statement.where(
            ScheduledJob.payload_json["conversation_id"].as_string() == str(conversation_id)
        )
    result = await session.execute(statement)
    labels: list[str] = []
    seen: set[str] = set()
    for job in result.scalars().all():
        label = PROACTIVE_LABELS.get(job.job_type, job.job_type.replace("_", " "))
        if label in seen:
            continue
        labels.append(label)
        seen.add(label)
        if len(labels) >= limit:
            break
    return labels


def build_response_plan(
    *,
    character: Character,
    relationship: RelationshipState,
    memories: Sequence[MemoryItem],
    journals: Sequence[EpisodicJournal],
    threads: Sequence[ContinuityThread],
    recent_messages: Sequence[Message],
    current_message: str,
    content_mode: str,
    safety_status: dict,
    time_context: str,
    pending_proactive_events: Sequence[str],
    scenario_mode: str = "default",
    scenario_text: str | None = None,
    relationship_context: RelationshipPlanContext | None = None,
) -> str:
    structured = build_structured_response_plan(
        character=character,
        relationship=relationship,
        memories=memories,
        journals=journals,
        threads=threads,
        recent_messages=recent_messages,
        current_message=current_message,
        content_mode=content_mode,
        safety_status=safety_status,
        relationship_context=relationship_context,
    )
    continuity = _continuity(recent_messages, pending_proactive_events)
    memory_focus = _memory_focus(memories)
    episode_focus = _episode_focus(journals)
    thread_focus = _thread_focus(threads)
    scene = _scene_focus(scenario_mode, scenario_text)
    summary = structured.private_summary()
    return _compact(
        f"Continuity: {continuity}; Relationship-aware plan: {summary}; "
        f"Memory focus: {memory_focus}; "
        f"Episode focus: {episode_focus}; Living thread: {thread_focus}; "
        f"Scene: {scene}; Timing: {time_context}",
        1800,
    )


def build_structured_response_plan(
    *,
    character: Character,
    relationship: RelationshipState,
    memories: Sequence[MemoryItem],
    journals: Sequence[EpisodicJournal],
    threads: Sequence[ContinuityThread],
    recent_messages: Sequence[Message],
    current_message: str,
    content_mode: str,
    safety_status: dict,
    soul: CharacterSoul | None = None,
    perception: TurnPerception | None = None,
    emotion: EmotionalState | None = None,
    relationship_context: RelationshipPlanContext | None = None,
) -> ResponsePlan:
    selected_soul = soul or character_soul(character)
    selected_perception = perception or infer_turn_perception(
        current_message,
        recent_messages=list(recent_messages),
        journals=list(journals),
        threads=list(threads),
    )
    selected_emotion = emotion or project_emotional_state(relationship)
    plan = plan_response(
        soul=selected_soul,
        perception=selected_perception,
        emotion=selected_emotion,
        relationship=relationship,
        memories=memories,
        journals=journals,
        threads=threads,
        recent_messages=recent_messages,
        content_mode=content_mode,
        safety_status=safety_status,
        relationship_context=relationship_context,
    )
    return replace(plan, continuity=_compact(plan.continuity, 260))


def _scene_focus(mode: str, text: str | None) -> str:
    if not text:
        return "no authored scene; follow the character's general setting"
    normalized = text.lower()
    if any(marker in normalized for marker in ("repair", "tension", "accountability")):
        focus = "repair setting"
    elif any(marker in normalized for marker in ("project", "co-working", "focus")):
        focus = "shared project setting"
    elif any(marker in normalized for marker in ("late", "night", "evening")):
        focus = "quiet check-in setting"
    elif any(marker in normalized for marker in ("ritual", "daily", "familiar")):
        focus = "familiar ritual setting"
    else:
        focus = "authored shared setting"
    scope = "thread-specific" if mode == "custom" else "character default"
    return f"{scope} {focus} is active"


def _tone(character: Character, relationship: RelationshipState) -> str:
    speech_style = character.speech_style or ""
    if relationship.repair_needed or relationship.conflict_state == "strained":
        return "careful, accountable, and repair-first"
    if relationship.tension >= 8:
        return "gentle and non-escalating"
    if relationship.warmth >= 10 or relationship.mood in {"warm", "close"}:
        return "warm, familiar, and specific"
    if speech_style:
        return speech_style
    return "steady, attentive, and concise"


def _continuity(
    recent_messages: Sequence[Message],
    pending_proactive_events: Sequence[str],
) -> str:
    user_turns = sum(1 for message in recent_messages if message.role == "user")
    assistant_turns = sum(1 for message in recent_messages if message.role == "assistant")
    if pending_proactive_events:
        pending = ", ".join(pending_proactive_events[:3])
        return f"thread has {user_turns} recent user turns and pending presence: {pending}"
    if user_turns + assistant_turns >= 6:
        return "thread has enough recent context to keep rhythm and callbacks"
    if user_turns > 0:
        return "thread is still forming; keep entry gentle"
    return "new thread; invite the user in without assuming history"


def _memory_focus(memories: Sequence[MemoryItem]) -> str:
    if not memories:
        return "no selected durable memories; avoid claiming recall"
    pinned = [memory for memory in memories if memory.pinned]
    contradiction = [
        memory
        for memory in memories
        if (memory.metadata_json or {}).get("contradiction_status") == "conflicts"
    ]
    if contradiction:
        return "selected memories include a contradiction; acknowledge uncertainty if relevant"
    target = pinned[0] if pinned else max(memories, key=lambda memory: memory.importance)
    return f"use this known detail only when relevant: {_compact(target.content, 140)}"


def _episode_focus(journals: Sequence[EpisodicJournal]) -> str:
    if not journals:
        return "no selected episodes; let this exchange become context"
    for signal in (
        "repair_arc",
        "anniversary",
        "open_thread",
        "callback_request",
        "inside_joke",
        "shared_moment",
        "shared_reference",
        "milestone",
        "adult_redacted",
    ):
        for journal in journals:
            if signal in journal_continuity_signals(journal):
                note = _journal_continuity_note(journal, signal)
                if note:
                    return f"{signal.replace('_', ' ')}: {note}"
                return signal.replace("_", " ")
    for journal in journals:
        if journal.unresolved_threads_json:
            return f"open thread: {_compact(journal.unresolved_threads_json[-1], 140)}"
    for journal in journals:
        if journal.callbacks_json:
            return f"callback available: {_compact(journal.callbacks_json[-1], 140)}"
    strongest = max(journals, key=lambda journal: journal.importance)
    return f"episode anchor: {_compact(strongest.title, 120)}"


def _thread_focus(threads: Sequence[ContinuityThread]) -> str:
    if not threads:
        return "none selected; do not invent an unfinished promise or plan"
    strongest = max(threads, key=lambda thread: (thread.salience, thread.confidence))
    return (
        f"{strongest.thread_kind.replace('_', ' ')} grounded in the user's words: "
        f"{_compact(strongest.content, 160)}; mention only if relevant"
    )


def _boundary_focus(content_mode: str, safety_status: dict, profile: dict) -> str:
    if content_mode == "adult":
        return "adult structural mode is active; consent and all hard boundaries remain active"
    reasons = safety_status.get("reasons") or []
    if reasons:
        return f"SFW mode; adult gates inactive because {reasons[0]}"
    boundary_notes = _profile_text(profile, "boundary_notes")
    if boundary_notes:
        return f"SFW mode; respect character boundaries: {_compact(boundary_notes, 140)}"
    return "SFW mode; hard boundaries remain active"


def _next_move(
    current_message: str,
    relationship: RelationshipState,
    journals: Sequence[EpisodicJournal],
) -> str:
    normalized = current_message.lower()
    if "?" in current_message:
        return "answer the question directly, then leave room for continuation"
    if relationship.repair_needed:
        return "prioritize repair and emotional clarity"
    if any(
        marker in normalized
        for marker in ("anniversary", "one year since", "a year since", "years since")
    ):
        return "acknowledge the anniversary warmly without inventing dates or shared details"
    if any(marker in normalized for marker in ("inside joke", "our joke", "running joke")):
        return "meet the playful callback using only the shared reference that is present"
    if any(
        marker in normalized
        for marker in ("shared moment", "moment we shared", "made this together")
    ):
        return "honor the shared moment with one specific, grounded reflection"
    if any(marker in normalized for marker in ("remember", "next time", "later")):
        return "notice the callback request and keep it concise"
    if any("repair_arc" in journal_continuity_signals(journal) for journal in journals):
        return "keep the repair arc visible without forcing a resolution"
    if any(journal.unresolved_threads_json for journal in journals):
        return "respond to the current message while gently preserving the open loop"
    return "respond in character with one concrete hook for the next turn"


def _journal_continuity_note(journal: EpisodicJournal, signal: str) -> str:
    notes = journal_continuity_notes(journal)
    prefix = {
        "repair_arc": "repair arc:",
        "anniversary": "anniversary:",
        "open_thread": "open thread:",
        "callback_request": "callback requested:",
        "inside_joke": "inside joke:",
        "shared_moment": "shared moment:",
        "shared_reference": "shared reference:",
        "milestone": "milestone:",
        "adult_redacted": "adult-mode episode redacted",
    }.get(signal)
    if prefix:
        for note in notes:
            if note.lower().startswith(prefix):
                return note
    return notes[0] if notes else ""


def _profile_text(profile: dict, key: str) -> str:
    value = profile.get(key)
    if isinstance(value, str) and value.strip():
        return " ".join(value.split())
    return ""


def _compact(value: str, limit: int) -> str:
    compact = " ".join(value.strip().split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."
