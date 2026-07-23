from __future__ import annotations

from collections.abc import Sequence

from app.companion.domain import (
    CharacterSoul,
    EmotionalState,
    ResponsePlan,
    TurnPerception,
)
from app.companion.emotion import emotional_posture
from app.models import ContinuityThread, EpisodicJournal, MemoryItem, Message, RelationshipState
from app.services.relationship import (
    RelationshipPlanContext,
    build_relationship_plan_context,
    relationship_behavioral_stage_text,
)


def plan_response(
    *,
    soul: CharacterSoul,
    perception: TurnPerception,
    emotion: EmotionalState,
    relationship: RelationshipState,
    memories: Sequence[MemoryItem],
    journals: Sequence[EpisodicJournal],
    recent_messages: Sequence[Message],
    content_mode: str,
    safety_status: dict,
    threads: Sequence[ContinuityThread] = (),
    relationship_context: RelationshipPlanContext | None = None,
) -> ResponsePlan:
    selected_relationship_context = relationship_context or build_relationship_plan_context(
        relationship
    )
    strategy, secondary = _strategies(
        soul=soul,
        perception=perception,
        relationship=relationship,
        content_mode=content_mode,
    )
    question = _question_is_useful(
        perception,
        recent_messages,
        strategy=strategy,
        repair_needed=relationship.repair_needed,
    )
    desired_length = _desired_length(perception, strategy)
    rhythm = _rhythm(perception, emotion, strategy)
    initiative, anchor, memory_id = _initiative(
        soul=soul,
        perception=perception,
        relationship=relationship,
        memories=memories,
        journals=journals,
        threads=threads,
        recent_messages=recent_messages,
        strategy=strategy,
    )
    reasons = safety_status.get("reasons") or []
    boundary_posture = (
        "adult mode is active, but consent and every hard boundary remain active"
        if content_mode == "adult"
        else "stay SFW and respect the character's personal boundaries"
    )
    if reasons and content_mode != "adult":
        boundary_posture += "; do not discuss internal gate mechanics"
    return ResponsePlan(
        strategy=strategy,
        secondary_strategy=secondary,
        should_ask_question=question,
        desired_length=desired_length,
        rhythm=rhythm,
        opening=_opening(perception, strategy),
        initiative=initiative,
        initiative_anchor=anchor,
        memory_callback_id=memory_id,
        tone=emotional_posture(emotion, repair_needed=relationship.repair_needed),
        continuity=_continuity(perception, relationship, journals, threads),
        boundary_posture=boundary_posture,
        relationship_state=selected_relationship_context.current_state,
        recent_relationship_change=selected_relationship_context.recent_change,
        unresolved_tension=selected_relationship_context.unresolved_tension,
        active_boundary=selected_relationship_context.active_boundary,
        familiarity_posture=selected_relationship_context.familiarity,
        initiative_posture=selected_relationship_context.initiative,
        avoid=_avoid_list(perception, question),
    )


def relationship_behavioral_stage(state: RelationshipState) -> str:
    return relationship_behavioral_stage_text(state)


def _strategies(
    *,
    soul: CharacterSoul,
    perception: TurnPerception,
    relationship: RelationshipState,
    content_mode: str,
) -> tuple[str, str | None]:
    if relationship.repair_needed:
        return ("repair", "listen")
    if perception.repair_signal:
        return ("repair", "share_the_moment")
    if perception.intent == "conflict":
        return ("apologise", "listen")
    if perception.challenge_signal:
        return ("challenge", "share_the_moment")
    if perception.disclosure_signal:
        return ("disclose", "share_the_moment")
    if perception.intent == "advise":
        return ("advise", None)
    if perception.intent == "support":
        if "does not want advice" in perception.subtext:
            return ("listen", "comfort")
        return ("comfort", "listen")
    if perception.intent == "celebrate":
        return ("celebrate", "share_the_moment")
    if perception.intent == "play":
        return ("tease", "share_the_moment")
    if perception.callback_signal:
        return ("reminisce", "share_the_moment")
    romantic_ready = (
        soul.relationship_path == "romantic"
        and relationship.familiarity >= 2
        and relationship.trust >= 1
        and relationship.emotional_safety >= 50
        and relationship.boundary_alignment >= 98
    )
    if perception.flirt_signal and romantic_ready:
        return ("flirt", None)
    if perception.flirt_signal and content_mode == "adult":
        return ("redirect", "share_the_moment")
    if perception.intent == "information":
        return ("advise", None)
    return ("share_the_moment", None)


def _question_is_useful(
    perception: TurnPerception,
    recent_messages: Sequence[Message],
    *,
    strategy: str,
    repair_needed: bool,
) -> bool:
    recent_assistant = [
        message.content.strip()
        for message in recent_messages
        if message.role == "assistant" and message.content.strip()
    ][-4:]
    recent_questions = sum(content.endswith("?") for content in recent_assistant)
    if recent_questions >= 2:
        return False
    if perception.intent in {"advise", "celebrate", "information", "play"}:
        return False
    if perception.direct_question:
        return False
    if repair_needed or strategy in {"apologise", "repair"}:
        return recent_questions == 0
    if perception.emotional_disclosure:
        return recent_questions == 0 and len(perception.subtext) == 0
    return len(recent_assistant) >= 2 and recent_questions == 0


def _desired_length(perception: TurnPerception, strategy: str) -> str:
    if perception.intent in {"play", "celebrate"}:
        return "brief"
    if perception.tone in {"guarded", "tender"}:
        return "short"
    if strategy == "advise" and perception.advice_requested:
        return "medium"
    if perception.intent in {"conflict", "repair", "support"}:
        return "short"
    return "short"


def _rhythm(perception: TurnPerception, emotion: EmotionalState, strategy: str) -> str:
    if strategy in {"tease", "celebrate"} or emotion.amusement >= 0.35:
        return "playful"
    if perception.tone == "guarded" or emotion.guardedness >= 0.4:
        return "hesitant"
    if perception.tone in {"anxious", "heavy", "tender"}:
        return "quiet"
    if strategy == "advise":
        return "crisp"
    return "steady"


def _initiative(
    *,
    soul: CharacterSoul,
    perception: TurnPerception,
    relationship: RelationshipState,
    memories: Sequence[MemoryItem],
    journals: Sequence[EpisodicJournal],
    threads: Sequence[ContinuityThread],
    recent_messages: Sequence[Message],
    strategy: str,
) -> tuple[str, str, str | None]:
    if strategy in {
        "advise",
        "apologise",
        "challenge",
        "comfort",
        "disclose",
        "listen",
        "redirect",
        "repair",
    }:
        return "none", "", None
    if perception.direct_question or perception.tone in {"anxious", "heavy", "sharp"}:
        return "none", "", None
    if (
        relationship.repair_needed
        or relationship.emotional_safety < 48
        or relationship.boundary_alignment < 98
    ):
        return "none", "", None

    if perception.callback_signal and memories:
        memory = memories[0]
        return "memory_callback", _compact(memory.content, 180), str(memory.id)

    for thread in threads:
        if thread.status == "open" and perception.intent == "connect":
            return "unresolved_thread", _compact(thread.content, 180), None

    for journal in journals:
        if journal.unresolved_threads_json and perception.intent == "connect":
            anchor = _compact(journal.unresolved_threads_json[0], 180)
            return "unresolved_thread", anchor, None

    assistant_turns = sum(message.role == "assistant" for message in recent_messages)
    if perception.intent in {"celebrate", "play"} and assistant_turns >= 2:
        return "activity", "suggest one small shared text-based activity", None
    if assistant_turns >= 4 and relationship.reciprocity >= 2:
        anchor = _compact(soul.initiative_style, 180)
        return "own_thought", anchor, None
    if (
        relationship.familiarity >= 3
        and relationship.shared_history_depth >= 2
        and assistant_turns >= 3
        and memories
    ):
        memory = memories[0]
        return "memory_callback", _compact(memory.content, 180), str(memory.id)
    return "none", "", None


def _opening(perception: TurnPerception, strategy: str) -> str:
    if perception.time_gap == "long_absence":
        return "acknowledge the time gap lightly, with no guilt or claim of waiting"
    if perception.time_gap in {"days", "hours"}:
        return "re-enter naturally without pretending continuous awareness"
    if strategy == "advise":
        return "answer directly before adding context"
    if strategy == "comfort":
        return "notice one specific emotional cue without paraphrasing the whole message"
    if strategy == "celebrate":
        return "meet the energy immediately"
    if strategy in {"repair", "listen"} and perception.conflict_signal:
        return "do not defend; acknowledge the impact first"
    if strategy == "apologise":
        return "own the specific impact without excuses or performative self-blame"
    if strategy == "challenge":
        return "state the honest disagreement plainly, with warmth but no automatic agreement"
    if strategy == "disclose":
        return "offer a character-specific view without pretending to have an offline life"
    if strategy == "tease":
        return "begin with a light character-specific beat"
    return "enter on the concrete detail or feeling that matters most"


def _continuity(
    perception: TurnPerception,
    relationship: RelationshipState,
    journals: Sequence[EpisodicJournal],
    threads: Sequence[ContinuityThread],
) -> str:
    if relationship.repair_needed:
        return "keep the repair arc visible and let trust recover through repeated evidence"
    if perception.unresolved_context and journals:
        return "keep the unresolved thread available without dragging it into every turn"
    if perception.unresolved_context and threads:
        return "keep the grounded living thread available without forcing a callback"
    if perception.callback_signal:
        return "use only selected memory evidence; acknowledge uncertainty rather than inventing"
    return "stay with the current moment and preserve the established relationship pace"


def _avoid_list(perception: TurnPerception, should_ask_question: bool) -> tuple[str, ...]:
    avoid = [
        "assistant clichés",
        "mirroring the user's wording",
        "repeated reassurance",
        "unsolicited advice",
        "headings or lists unless practical advice requires structure",
    ]
    if not should_ask_question:
        avoid.append("ending with a question")
    if perception.time_gap == "long_absence":
        avoid.extend(("guilt about absence", "claims of waiting or offline awareness"))
    return tuple(avoid)


def _compact(value: str, limit: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."
