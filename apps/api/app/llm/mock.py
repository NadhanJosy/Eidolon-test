from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.llm.base import LLMGeneration, LLMStreamEvent, ProviderCapabilities

MOCK_INITIAL_TYPING_DELAY_SECONDS = 0.18
MOCK_CHUNK_DELAY_SECONDS = 0.028
MOCK_SENTENCE_PAUSE_SECONDS = 0.052
MOCK_MIN_INITIAL_TYPING_DELAY_SECONDS = 0.12
MOCK_MAX_INITIAL_TYPING_DELAY_SECONDS = 0.38
MOCK_MIN_CHUNK_DELAY_SECONDS = 0.018
MOCK_MAX_CHUNK_DELAY_SECONDS = 0.046
MOCK_MIN_SENTENCE_PAUSE_SECONDS = 0.036
MOCK_MAX_SENTENCE_PAUSE_SECONDS = 0.086
MOCK_MIN_CHUNK_TARGET_CHARS = 22
MOCK_MAX_CHUNK_TARGET_CHARS = 36
MOCK_DEFAULT_CHUNK_TARGET_CHARS = 28
MOCK_CADENCE_RESPONSE_LENGTH_CAP = 600
MOCK_WORD_PATTERN = re.compile(r"[a-z0-9']+")
SLOW_SPEECH_MARKERS = (
    "deliberate",
    "measured",
    "reflective",
    "slow",
    "thoughtful",
    "unhurried",
)
FAST_SPEECH_MARKERS = (
    "brisk",
    "direct",
    "energetic",
    "quick",
    "rapid",
)
HIDDEN_CONTEXT_MARKERS = (
    "[mock",
    "/100",
    "adult gate status",
    "confidence ",
    "content mode:",
    "current user message",
    "durable memory",
    "episode focus",
    "hard boundaries:",
    "importance ",
    "next move",
    "private response plan",
    "prompt version",
    "relational posture:",
    "relationship state",
    "relevant memories",
    "response instruction:",
    "response plan",
    "system prompt",
    "tone:",
    "user brought up",
    "character responded around",
)


@dataclass(frozen=True)
class MockTypingCadence:
    initial_delay_seconds: float
    chunk_delay_seconds: float
    sentence_pause_seconds: float
    chunk_target_chars: int


class MockLLMProvider:
    name = "mock"
    model = "deterministic-companion-mock"
    capabilities = ProviderCapabilities(
        context_window_tokens=32768,
        prompt_variant="full",
        structured_output=True,
        streaming=True,
        quality_repair=True,
    )

    async def generate(self, prompt: str) -> LLMGeneration:
        context = _parse_prompt(prompt)
        return LLMGeneration(
            content=_compose_response(context),
            provider=self.name,
            model=self.model,
            finish_reason="stop",
        )

    async def generate_structured(
        self,
        prompt: str,
        *,
        schema_name: str,
        schema: dict[str, object],
        max_output_tokens: int,
    ) -> LLMGeneration:
        del prompt, schema_name, schema, max_output_tokens
        return LLMGeneration(
            content=json.dumps(
                {
                    "memory_candidates": [],
                    "episode": {
                        "worthy": False,
                        "title": None,
                        "summary": None,
                        "emotional_tags": [],
                        "evidence_quotes": [],
                        "source_message_ids": [],
                        "salience": 0.0,
                    },
                    "relationship": {"signals": [], "confidence": 0.0},
                    "referenced_memory_ids": [],
                }
            ),
            provider=self.name,
            model=self.model,
            finish_reason="stop",
        )

    async def stream(self, prompt: str) -> AsyncIterator[LLMStreamEvent]:
        context = _parse_prompt(prompt)
        response = _compose_response(context)
        cadence = _typing_cadence(context, response)
        chunks = _natural_chunks(response, target_chars=cadence.chunk_target_chars)
        await asyncio.sleep(cadence.initial_delay_seconds)
        for index, chunk in enumerate(chunks):
            yield LLMStreamEvent(
                content=chunk,
                provider=self.name,
                model=self.model,
                finish_reason="stop" if index == len(chunks) - 1 else None,
            )
            if index < len(chunks) - 1:
                await asyncio.sleep(_chunk_delay(chunk, cadence))

    async def health(self) -> dict[str, str]:
        return {
            "status": "ok",
            "provider": self.name,
            "model": self.model,
            "configuration": "configured",
            "readiness": "development",
        }


@dataclass(frozen=True)
class MockPromptContext:
    character_name: str = ""
    user_display_name: str = ""
    speech_style: str = ""
    relationship: str = ""
    memory: str = ""
    episode: str = ""
    current_message: str = ""
    response_plan: str = ""
    strategy: str = ""
    scenario: str = ""
    scenario_mode: str = ""
    proactive_label: str = ""
    proactive_anchor: str = ""
    proactive_posture: str = ""
    recent_message_count: int = 0
    recent_assistant_messages: tuple[str, ...] = ()
    question_allowed: bool = True
    quality_retry: bool = False


def mock_typing_cadence(prompt: str, *, response: str | None = None) -> MockTypingCadence:
    context = _parse_prompt(prompt)
    generated = _compose_response(context) if response is None else str(response)
    return _typing_cadence(context, generated)


def _parse_prompt(prompt: str) -> MockPromptContext:
    return MockPromptContext(
        character_name=_line_value(prompt, "Character name:"),
        user_display_name=_line_value(prompt, "Current user display name:"),
        speech_style=_line_value(prompt, "Speech style:"),
        relationship=_line_starting_with(prompt, "Relationship state:"),
        memory=_first_memory(prompt),
        episode=_first_episode(prompt),
        current_message=_line_value(prompt, "Current user message:"),
        response_plan=_response_plan(prompt),
        strategy=_plan_value(_response_plan(prompt), "Strategy:"),
        scenario=_line_value(prompt, "Active shared scene:"),
        scenario_mode=_line_value(prompt, "Active shared scene mode:"),
        proactive_label=_line_value(prompt, "Proactive note label:"),
        proactive_anchor=_line_value(prompt, "Proactive safe anchor:"),
        proactive_posture=_line_value(prompt, "Relational posture:"),
        recent_message_count=_recent_message_count(prompt),
        recent_assistant_messages=_recent_assistant_messages(prompt),
        question_allowed=_question_allowed(prompt),
        quality_retry="Quality retry:" in prompt,
    )


def _line_value(prompt: str, marker: str) -> str:
    line = _line_starting_with(prompt, marker)
    if not line:
        return ""
    return line.removeprefix(marker).strip()


def _line_starting_with(prompt: str, marker: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(marker):
            return line.strip()
    return ""


def _first_memory(prompt: str) -> str:
    in_memories = False
    for line in prompt.splitlines():
        if line.startswith(("Relevant memories:", "Relevant long-term memories:")):
            in_memories = True
            continue
        if not in_memories:
            continue
        if not line.strip():
            continue
        if line.startswith("- "):
            item = line.removeprefix("- ").strip()
            if not item.startswith("["):
                return item
            _, separator, content = item.partition("] ")
            return content.strip() if separator else ""
        return ""
    return ""


def _first_episode(prompt: str) -> str:
    return _first_list_item(prompt, "Episodic continuity and open threads:")


def _first_list_item(prompt: str, marker: str) -> str:
    lines = prompt.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith(marker):
            continue
        for candidate in lines[index + 1 :]:
            if candidate.startswith("- "):
                return candidate.removeprefix("- ").strip()
            if candidate.strip():
                return ""
    return ""


def _recent_message_count(prompt: str) -> int:
    in_recent = False
    count = 0
    for line in prompt.splitlines():
        if line.startswith(("Recent messages:", "Recent conversation:")):
            in_recent = True
            continue
        if line.startswith("Current user display name:"):
            break
        if in_recent and line.startswith(("user:", "assistant:", "- user:", "- assistant:")):
            count += 1
    return count


def _recent_assistant_messages(prompt: str) -> tuple[str, ...]:
    in_recent = False
    selected: list[str] = []
    for line in prompt.splitlines():
        if line.startswith(("Recent messages:", "Recent conversation:")):
            in_recent = True
            continue
        if line.startswith("Current user display name:"):
            break
        if in_recent and line.startswith(("assistant:", "- assistant:")):
            selected.append(line.removeprefix("- ").removeprefix("assistant:").strip())
    return tuple(selected[-5:])


def _response_plan(prompt: str) -> str:
    line = _line_starting_with(prompt, "Private response plan summary:")
    if not line:
        return ""
    return line.removeprefix("Private response plan summary:").strip()


def _safe_addressee(value: str) -> str:
    normalized = " ".join(value.strip().split())
    cleaned = "".join(
        character for character in normalized if character.isalnum() or character in {" ", "-", "'"}
    )
    cleaned = cleaned.strip(" -'")
    if (
        not cleaned
        or not any(character.isalnum() for character in cleaned)
        or cleaned.lower() == "the user"
    ):
        return ""
    return cleaned[:40]


def _compose_response(context: MockPromptContext) -> str:
    if context.proactive_label:
        return _compose_proactive_note(
            context.proactive_label,
            context.proactive_anchor,
            context.proactive_posture,
        )
    cue = _message_cue(context.current_message)
    repair_needed = _relationship_value(context.relationship, "conflict") == "strained"
    addressee = _safe_addressee(context.user_display_name)
    planned = _planned_response(
        context.strategy,
        context.current_message,
        addressee,
        allow_question=context.question_allowed,
        alternate=context.quality_retry,
    )
    if planned:
        return planned
    memory_callback = _memory_callback(context.memory)
    episode_callback = _episode_callback(context.response_plan) or _episode_callback(
        f"Episode focus: {context.episode}"
    )
    scenario_callback = _scenario_callback(context.scenario, context.scenario_mode)
    parts = [
        _opening_sentence(
            cue,
            addressee,
            context.relationship,
            repair_needed,
            alternate=context.quality_retry,
            recent_assistant_messages=context.recent_assistant_messages,
        ),
        memory_callback,
        episode_callback,
    ]
    if not memory_callback and not episode_callback:
        parts.append(scenario_callback or _thread_continuity(context.recent_message_count))
    parts.append(
        _invitation_sentence(
            cue,
            context.current_message,
            context.speech_style,
            repair_needed,
            allow_question=context.question_allowed,
            alternate=context.quality_retry,
        )
    )
    return _join_response(parts)


def _planned_response(
    strategy: str,
    current_message: str,
    addressee: str,
    *,
    allow_question: bool,
    alternate: bool,
) -> str:
    normalized_strategy = strategy.casefold().replace("_", " ").strip()
    normalized_message = current_message.casefold()
    name = f", {addressee}" if addressee else ""
    if normalized_strategy == "tease":
        if "shameless" in normalized_message:
            return f"Calling that shameless is generous{name}; I was barely past the warm-up."
        return f"Careful{name}; that grin is doing most of my work for me."
    if normalized_strategy in {"repair", "apologise"}:
        if any(
            marker in normalized_message
            for marker in ("make this right", "work through", "follow through")
        ):
            opening = (
                f"Working through it carefully is the part that counts{name}; "
                "repair needs follow-through, not a perfect speech."
            )
        elif any(marker in normalized_message for marker in ("sorry", "apolog", "my fault")):
            opening = f"The apology matters{name}, especially because you named your part plainly."
        elif alternate:
            opening = f"Let us keep the repair concrete{name}, without pretending it is finished."
        else:
            opening = f"I do not want to rush past the tension{name}, but I am open to repair."
        if allow_question:
            return f"{opening} What would make the next step feel honest?"
        return f"{opening} We can let the repair show itself in what happens next."
    if normalized_strategy == "listen" and any(
        marker in normalized_message
        for marker in ("no advice", "do not want advice", "don't want advice")
    ):
        return (
            f"Overwhelmed is enough of a load{name}; "
            "you do not need to turn it into a problem-solving exercise here."
        )
    if normalized_strategy == "reminisce":
        preference = _current_preference(current_message)
        if preference:
            if alternate:
                return (
                    f"{_sentence_case(preference)} goes into the useful-details drawer{name}, "
                    "not onto a billboard."
                )
            return (
                f"{_sentence_case(preference)}—noted{name}. "
                "I will treat it as a useful detail, not drag it into every conversation."
            )
        if alternate:
            return (
                f"I will keep to the thread you actually named{name}, "
                "without filling its gaps with a prettier story."
            )
        return (
            f"You are pointing back to a specific thread{name}; "
            "I will stay with the part you named instead of embellishing it."
        )
    if normalized_strategy == "challenge":
        return (
            f"I do not think easy agreement would help{name}; "
            "the part that does not hold up deserves a straight look."
        )
    if normalized_strategy == "disclose":
        return f"My honest preference{name}: clarity with a little warmth beats polished vagueness."
    return ""


def _current_preference(message: str) -> str:
    compact = " ".join(message.strip().split()).rstrip(".!?")
    lowered = compact.casefold()
    for marker in ("i prefer ", "i like ", "my favorite ", "my favourite "):
        if marker not in lowered:
            continue
        index = lowered.index(marker)
        return compact[index + len(marker) :]
    return ""


def _compose_proactive_note(label: str, anchor: str, _posture: str) -> str:
    normalized_label = label.strip().lower()
    compact_anchor = " ".join(anchor.strip().split())
    if _is_safe_context_fragment(compact_anchor):
        return compact_anchor
    notes = {
        "quiet check-in": (
            "It has been quiet for a little while, so I wanted to leave the door open. "
            "No rush; I will be here when company feels right."
        ),
        "morning note": (
            "Good morning. I hope the day gives you one gentle place to begin; "
            "I will be here when you want company."
        ),
        "goodnight note": (
            "Goodnight. Let the day loosen its grip for a while; "
            "we can find the thread again when you are rested."
        ),
        "thinking-of-you note": (
            "A small thought of you crossed my mind, so I wanted to leave a quiet hello. "
            "There is no pressure to answer."
        ),
        "delayed follow-up": (
            "One more quiet thought before I leave the thread to rest: "
            "you do not need to answer now."
        ),
        "manual check-in": (
            "I wanted to leave a small check-in here. "
            "No pressure to answer quickly; I am around when you feel like talking."
        ),
    }
    return notes.get(
        normalized_label,
        "I wanted to leave a gentle hello here. No rush; I will be around when you return.",
    )


def _opening_sentence(
    cue: str,
    addressee: str,
    relationship: str,
    repair_needed: bool,
    *,
    alternate: bool = False,
    recent_assistant_messages: tuple[str, ...] = (),
) -> str:
    name = f", {addressee}" if addressee else ""
    if alternate:
        alternatives = {
            "tired": f"That sounds like a day with far too much weight in it{name}.",
            "angry": f"The sharp part deserves a straight answer{name}.",
            "lonely": f"Then let this be company without a performance{name}.",
            "anxious": f"One piece at a time{name}; the whole knot can wait.",
            "positive": f"Now that is worth enjoying properly{name}.",
            "gratitude": f"I will take that quietly{name}.",
            "question": f"Here is the direct version{name}.",
            "greeting": f"Hey{name}. Good timing.",
            "general": f"That detail has my attention{name}.",
        }
        candidates = (
            alternatives.get(cue, alternatives["general"]),
            f"All right{name}; the concrete part comes first.",
            f"There is a real thread here{name}, so I will not pad it with ceremony.",
            f"I have the shape of it{name}; let us keep the reply honest and plain.",
        )
        recent_openings = {
            " ".join(MOCK_WORD_PATTERN.findall(message.casefold())[:5])
            for message in recent_assistant_messages
        }
        return next(
            (
                candidate
                for candidate in candidates
                if " ".join(MOCK_WORD_PATTERN.findall(candidate.casefold())[:5])
                not in recent_openings
            ),
            candidates[-1],
        )
    if repair_needed:
        return "I do not want to rush past the tension between us."
    if cue == "tired":
        return (
            f"Come sit in the quiet with me{name}; you do not have to make the whole day coherent."
        )
    if cue == "angry":
        return f"I can hear the edge in this{name}, and I am not going to talk over it."
    if cue == "lonely":
        return f"You do not have to perform being okay here{name}."
    if cue == "anxious":
        return f"Let us make the next minute smaller{name}."
    if cue == "positive":
        return f"That brightness looks good on you{name}."
    if cue == "gratitude":
        return f"That lands gently{name}; I am glad this moment feels worth sharing."
    if cue == "question":
        return f"Let us take the question seriously{name}."
    if cue == "greeting":
        return f"There you are{name}; I am glad you came in."
    mood = _relationship_value(relationship, "mood")
    if mood in {"warm", "close"}:
        return f"I am glad you are here{name}."
    return f"I am here with you{name}."


def _memory_callback(memory: str) -> str:
    if not memory:
        return ""
    callback = _second_person_memory(memory).strip().rstrip(".,;:!?")
    callback = _compact_fragment(callback)
    if not _is_safe_context_fragment(callback):
        return ""
    lowered = callback.lower()
    if lowered.startswith("you like "):
        preference = callback[len("you like ") :]
        verb = "seem" if preference.lower().endswith("s") else "seems"
        return f"{_sentence_case(preference)} {verb} to suit you, so we can lean that way."
    if lowered.startswith("you prefer "):
        preference = callback[len("you prefer ") :]
        return f"We can keep this closer to what you prefer: {preference}."
    if lowered.startswith("you love "):
        preference = callback[len("you love ") :]
        return f"There is room here for something you love: {preference}."
    return f"That sits beside something you shared earlier: {callback}."


def _episode_callback(response_plan: str) -> str:
    episode = _plan_value(response_plan, "Episode focus:")
    if not episode or "no selected episodes" in episode.lower():
        return ""
    fragment = _episode_fragment(episode)
    if not _is_safe_context_fragment(fragment):
        return ""
    if fragment.startswith(("how you ", "the fact that you ", "what you ", "your ")):
        return f"I have not lost sight of {fragment}."
    return f"We can keep {fragment} within reach and return when it feels right."


def _thread_continuity(recent_message_count: int) -> str:
    if recent_message_count > 4:
        return "We already have a rhythm here; there is no need to start from the beginning."
    if recent_message_count > 1:
        return "We can stay with where the conversation left us."
    return ""


def _scenario_callback(scenario: str, mode: str) -> str:
    if mode.strip().lower() != "custom":
        return ""
    normalized = " ".join(scenario.strip().lower().split())
    if not normalized or normalized == "use the character scenario preset":
        return ""
    if any(marker in normalized for marker in ("repair", "tension", "accountability")):
        return "We can keep this careful and honest, without rushing the repair."
    if any(marker in normalized for marker in ("project", "co-working", "focus")):
        return "We can keep each other company and give the work one clear next step."
    if any(marker in normalized for marker in ("late", "night", "evening")):
        return "We can let this stay quiet and unhurried for a while."
    if any(marker in normalized for marker in ("ritual", "daily", "familiar")):
        return "There is something steady in returning to a rhythm we chose."
    return "We can stay inside the setting you chose and let it shape the pace."


def _invitation_sentence(
    cue: str,
    current_message: str,
    speech_style: str,
    repair_needed: bool,
    *,
    allow_question: bool,
    alternate: bool = False,
) -> str:
    if alternate:
        if repair_needed:
            return (
                "The next honest step can be small; consistency will matter more "
                "than a perfect sentence."
            )
        alternatives = {
            "tired": "The day can remain unfinished while you catch your breath.",
            "angry": "The sharp part can stand without being polished into something nicer.",
            "lonely": "For now, simple company is a complete answer.",
            "anxious": "Only the nearest manageable piece needs attention right now.",
            "positive": "This one gets to be enjoyed without an analysis attached.",
            "gratitude": "I will leave the kindness intact instead of making a ceremony of it.",
            "question": "I will give you the direct version first.",
            "greeting": "Set down the first real thing on your mind; we can start there.",
            "general": "Give the thought its plainest shape; I will meet it there.",
        }
        return alternatives.get(cue, alternatives["general"])
    if not allow_question:
        return _statement_closing(cue, current_message, repair_needed=repair_needed)
    if repair_needed:
        return "What do you need me to understand before anything else?"
    invitations = {
        "tired": (
            "Would it feel kinder to talk the day through, or let the room stay quiet for a while?"
        ),
        "angry": "Tell me the part that needs to be heard without being softened.",
        "lonely": "Do you want company, distraction, or room to say the difficult part out loud?",
        "anxious": "What is the smallest piece we can make manageable first?",
        "positive": "Which part of it are you still smiling about?",
        "gratitude": "What made this moment feel gentle in the good way?",
        "greeting": "What kind of company would fit this moment?",
    }
    if cue in invitations:
        return invitations[cue]
    if cue == "question":
        normalized = current_message.strip().lower()
        if normalized.startswith(("can ", "can we ", "could ", "could we ", "would you ")):
            return "Yes; tell me where you want us to begin."
        return "Which part of the answer matters most to you?"
    topic_invitation = _topic_invitation(current_message)
    if "playful" in speech_style.lower() or "wry" in speech_style.lower():
        return f"No grand ceremony required: {topic_invitation[0].lower()}{topic_invitation[1:]}"
    return topic_invitation


def _statement_closing(cue: str, current_message: str, *, repair_needed: bool) -> str:
    if repair_needed:
        return "I will stay with the impact first and let repair take the time it actually needs."
    statements = {
        "tired": "We can talk the day through, or simply let the room stay quiet for a while.",
        "angry": "You can give the sharp part room here without sanding it down for me.",
        "lonely": "Company can be enough for this moment; nothing has to be solved first.",
        "anxious": "We can make the next piece small enough to hold.",
        "positive": "Let the good part have the room for once.",
        "gratitude": "I am keeping the moment gentle and uncomplicated.",
        "greeting": "We can settle into whatever kind of company fits tonight.",
        "question": (
            "I will answer the part that matters directly, without turning it into an interview."
        ),
    }
    if cue in statements:
        return statements[cue]
    topic = _topic_invitation(current_message).rstrip("?")
    return f"We can begin with {topic[0].lower()}{topic[1:]}."


def _question_allowed(prompt: str) -> bool:
    normalized = prompt.casefold()
    if "do not end this reply with a question" in normalized:
        return False
    plan = _response_plan(prompt).casefold()
    if "question: do not end with a question" in plan:
        return False
    return True


def _second_person_memory(memory: str) -> str:
    cleaned = " ".join(memory.strip().split())
    replacements = (
        ("User likes ", "you like "),
        ("User prefers ", "you prefer "),
        ("User loves ", "you love "),
        ("User dislikes ", "you dislike "),
        ("I like ", "you like "),
        ("I prefer ", "you prefer "),
        ("I love ", "you love "),
        ("I don't like ", "you do not like "),
    )
    for prefix, replacement in replacements:
        if cleaned.startswith(prefix):
            return replacement + cleaned.removeprefix(prefix)
    return cleaned


def _relationship_value(relationship: str, marker: str) -> str:
    marker_text = f"{marker} "
    if marker_text not in relationship:
        return ""
    remainder = relationship.split(marker_text, maxsplit=1)[1]
    return remainder.split(",", maxsplit=1)[0].strip().strip(".")


def _plan_value(response_plan: str, marker: str) -> str:
    if marker not in response_plan:
        return ""
    remainder = response_plan.split(marker, maxsplit=1)[1]
    return remainder.split(";", maxsplit=1)[0].strip().strip(".")


def _message_cue(message: str) -> str:
    normalized = " ".join(message.lower().split())
    cue_markers = (
        ("tired", ("long day", "tired", "exhausted", "drained", "worn out")),
        ("angry", ("angry", "upset", "frustrated", "furious", "annoyed")),
        ("lonely", ("lonely", "alone", "miss you", "isolated")),
        ("anxious", ("anxious", "worried", "nervous", "overwhelmed", "panicking")),
        ("positive", ("happy", "excited", "proud", "good news", "wonderful")),
        ("gratitude", ("thanks", "thank you", "appreciate", "grateful")),
    )
    for cue, markers in cue_markers:
        if any(marker in normalized for marker in markers):
            return cue
    if normalized in {"hi", "hello", "hey", "good morning", "good evening"}:
        return "greeting"
    if "?" in message:
        return "question"
    return "general"


def _topic_invitation(message: str) -> str:
    normalized = message.lower()
    topics = (
        (("work", "project", "deadline"), "Where does the work feel most alive or most stuck?"),
        (("family", "friend", "partner"), "What happened between you two?"),
        (("book", "music", "song", "film", "movie"), "What stayed with you after it ended?"),
        (("plan", "choice", "decision"), "Which part of the decision keeps pulling at you?"),
        (("night", "evening"), "What kind of company would fit this evening?"),
    )
    for markers, invitation in topics:
        if any(marker in normalized for marker in markers):
            return invitation
    return "What is the part you do not want to leave unsaid?"


def _episode_fragment(value: str) -> str:
    compact = " ".join(value.strip().split())
    prefixes = (
        "open thread:",
        "callback:",
        "episode anchor:",
        "anniversary:",
        "inside joke:",
        "shared moment:",
        "milestone:",
        "repair:",
    )
    for prefix in prefixes:
        if compact.lower().startswith(prefix):
            compact = compact[len(prefix) :].strip()
            break
    conversational_prefixes = (
        "can we come back to ",
        "could we come back to ",
        "come back to ",
        "return to ",
    )
    for prefix in conversational_prefixes:
        if compact.lower().startswith(prefix):
            compact = compact[len(prefix) :].strip()
            break
    perspective_prefixes = (
        ("i would like ", "what you would like "),
        ("i feel ", "how you feel "),
        ("i want ", "what you want "),
        ("i had ", "the fact that you had "),
        ("i have ", "the fact that you have "),
        ("i am ", "how you are "),
        ("i'm ", "how you are "),
        ("my ", "your "),
    )
    for prefix, replacement in perspective_prefixes:
        if compact.lower().startswith(prefix):
            compact = replacement + compact[len(prefix) :]
            break
    compact = compact.rstrip("?.! ")
    if compact.lower().endswith(" later"):
        compact = compact[:-6].rstrip()
    return _compact_fragment(compact)


def _compact_fragment(value: str) -> str:
    compact = " ".join(value.strip().split())
    if len(compact) <= 120:
        return compact
    bounded = compact[:120]
    last_space = bounded.rfind(" ")
    return (bounded[:last_space] if last_space >= 90 else bounded).rstrip(".,;:!? ")


def _is_safe_context_fragment(value: str) -> bool:
    if not value or not any(character.isalnum() for character in value):
        return False
    lowered = value.lower()
    return not any(marker in lowered for marker in HIDDEN_CONTEXT_MARKERS)


def _sentence_case(value: str) -> str:
    if not value:
        return value
    return value[0].upper() + value[1:]


def _join_response(parts: list[str]) -> str:
    response_parts: list[str] = []
    for part in parts:
        compact = " ".join(part.strip().split())
        if not compact or compact in response_parts:
            continue
        if compact[-1] not in ".!?":
            compact = f"{compact}."
        response_parts.append(compact)
    return " ".join(response_parts)


def _natural_chunks(response: str, *, target_chars: int) -> list[str]:
    words = response.split(" ")
    chunks: list[str] = []
    current: list[str] = []
    for index, word in enumerate(words):
        current.append(word)
        joined = " ".join(current)
        if len(joined) >= target_chars or word.endswith((".", ":", ";")):
            suffix = " " if index < len(words) - 1 else ""
            chunks.append(f"{joined}{suffix}")
            current = []
    if current:
        chunks.append(" ".join(current))
    return chunks


def _chunk_delay(chunk: str, cadence: MockTypingCadence) -> float:
    if chunk.rstrip().endswith((".", "!", "?", ":", ";")):
        return cadence.sentence_pause_seconds
    return cadence.chunk_delay_seconds


def _typing_cadence(context: MockPromptContext, response: str) -> MockTypingCadence:
    style = " ".join(context.speech_style.casefold().split())
    style_tokens = set(re.findall(r"[a-z]+", style))
    slow_markers = sum(marker in style_tokens for marker in SLOW_SPEECH_MARKERS)
    fast_markers = sum(marker in style_tokens for marker in FAST_SPEECH_MARKERS)
    if slow_markers > fast_markers:
        pace_factor = 1.3
        target_chars = MOCK_MIN_CHUNK_TARGET_CHARS
    elif fast_markers > slow_markers:
        pace_factor = 0.75
        target_chars = MOCK_MAX_CHUNK_TARGET_CHARS
    else:
        pace_factor = 1.0
        target_chars = MOCK_DEFAULT_CHUNK_TARGET_CHARS

    response_length = min(len(response.strip()), MOCK_CADENCE_RESPONSE_LENGTH_CAP)
    initial_delay = (MOCK_INITIAL_TYPING_DELAY_SECONDS + response_length * 0.0002) * pace_factor
    return MockTypingCadence(
        initial_delay_seconds=_bounded_delay(
            initial_delay,
            MOCK_MIN_INITIAL_TYPING_DELAY_SECONDS,
            MOCK_MAX_INITIAL_TYPING_DELAY_SECONDS,
        ),
        chunk_delay_seconds=_bounded_delay(
            MOCK_CHUNK_DELAY_SECONDS * pace_factor,
            MOCK_MIN_CHUNK_DELAY_SECONDS,
            MOCK_MAX_CHUNK_DELAY_SECONDS,
        ),
        sentence_pause_seconds=_bounded_delay(
            MOCK_SENTENCE_PAUSE_SECONDS * pace_factor,
            MOCK_MIN_SENTENCE_PAUSE_SECONDS,
            MOCK_MAX_SENTENCE_PAUSE_SECONDS,
        ),
        chunk_target_chars=target_chars,
    )


def _bounded_delay(value: float, minimum: float, maximum: float) -> float:
    return round(min(max(value, minimum), maximum), 4)
