from __future__ import annotations

import re
from datetime import datetime

from app.companion.domain import TurnPerception
from app.models import ContinuityThread, EpisodicJournal, Message, utc_now

WORD_PATTERN = re.compile(r"[a-z0-9']+")
ADVICE_MARKERS = (
    "any advice",
    "help me decide",
    "what should i do",
    "what would you do",
    "how do i",
    "can you help me",
)
CELEBRATION_MARKERS = (
    "good news",
    "i did it",
    "i got the",
    "i passed",
    "i finished",
    "i'm proud",
    "im proud",
    "we did it",
)
PLAY_MARKERS = ("haha", "lol", "lmao", "tease me", "inside joke", "kidding", "joking")
SARCASM_MARKERS = (
    "/s",
    "as if",
    "great, just",
    "love that for me",
    "oh great",
    "sure, because",
    "what a delight",
    "yeah right",
)
MIXED_FEELING_MARKERS = (
    "and yet",
    "at the same time",
    "bittersweet",
    "but also",
    "but relieved",
    "happy and sad",
    "relieved but",
    "scared but",
)
REPAIR_MARKERS = ("i'm sorry", "im sorry", "i apologize", "i apologise", "my fault")
CALLBACK_MARKERS = ("remember", "last time", "we said", "you promised", "our joke")
FLIRT_MARKERS = ("flirt", "kiss", "date with you", "crush on you")
CHALLENGE_MARKERS = (
    "be honest with me",
    "call me out",
    "challenge me",
    "don't just agree",
    "dont just agree",
    "push back",
)
DISCLOSURE_MARKERS = (
    "tell me about yourself",
    "tell me what you think",
    "what do you believe",
    "what's your opinion",
    "whats your opinion",
    "your honest opinion",
)
SUPPORT_WORDS = {
    "afraid",
    "anxious",
    "drained",
    "exhausted",
    "lonely",
    "overwhelmed",
    "sad",
    "scared",
    "tired",
    "worried",
}
BRIGHT_WORDS = {
    "amazing",
    "excited",
    "glad",
    "great",
    "happy",
    "proud",
    "relieved",
    "wonderful",
}
SHARP_WORDS = {"angry", "annoyed", "furious", "hate", "mad", "upset"}
TENDER_WORDS = {"care", "miss", "soft", "tender", "trust", "vulnerable"}
NEGATION_WORDS = {"hardly", "never", "no", "not"}
INTENSITY_WORDS = {
    "deeply",
    "extremely",
    "incredibly",
    "really",
    "so",
    "terrified",
    "utterly",
    "very",
}
TOPIC_STOP_WORDS = {
    "about",
    "again",
    "also",
    "been",
    "could",
    "does",
    "feel",
    "from",
    "have",
    "just",
    "like",
    "really",
    "said",
    "that",
    "their",
    "there",
    "they",
    "this",
    "want",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "your",
}


def infer_turn_perception(
    current_message: str,
    *,
    recent_messages: list[Message],
    journals: list[EpisodicJournal],
    threads: list[ContinuityThread] | None = None,
    now: datetime | None = None,
) -> TurnPerception:
    normalized = " ".join(current_message.casefold().split())
    words = _affirmed_words(normalized)
    direct_question = "?" in current_message
    advice_requested = _contains_any(normalized, ADVICE_MARKERS)
    repair_signal = _contains_any(normalized, REPAIR_MARKERS)
    celebration_signal = _contains_any(normalized, CELEBRATION_MARKERS)
    callback_signal = _contains_any(normalized, CALLBACK_MARKERS)
    flirt_signal = _contains_any(normalized, FLIRT_MARKERS)
    challenge_signal = _contains_any(normalized, CHALLENGE_MARKERS)
    disclosure_signal = _contains_any(normalized, DISCLOSURE_MARKERS)
    conflict_signal = _companion_conflict_signal(normalized)
    sarcasm_signal = _contains_any(normalized, SARCASM_MARKERS)
    mixed_feelings = _mixed_feelings(normalized, words)
    humour_signal = sarcasm_signal or _contains_any(normalized, PLAY_MARKERS)
    emotional_disclosure = bool(words & (SUPPORT_WORDS | SHARP_WORDS | TENDER_WORDS))
    tone = _tone(
        words,
        normalized,
        conflict_signal=conflict_signal,
        mixed_feelings=mixed_feelings,
        sarcasm_signal=sarcasm_signal,
    )
    intent = _intent(
        normalized,
        words,
        direct_question=direct_question,
        advice_requested=advice_requested,
        repair_signal=repair_signal,
        celebration_signal=celebration_signal,
        conflict_signal=conflict_signal,
    )
    topic_terms = _topic_terms(normalized)
    unresolved_context = _unresolved_context(
        journals,
        recent_messages,
        threads or [],
        topic_terms=set(topic_terms),
    )
    return TurnPerception(
        intent=intent,
        tone=tone,
        subtext=_subtext(
            normalized,
            intent=intent,
            direct_question=direct_question,
            emotional_disclosure=emotional_disclosure,
        ),
        unresolved_context=unresolved_context,
        topic_terms=topic_terms,
        conversation_mode=_conversation_mode(
            intent,
            tone,
            humour_signal=humour_signal,
            emotional_disclosure=emotional_disclosure,
        ),
        stakes=_stakes(
            intent,
            tone,
            emotional_disclosure=emotional_disclosure,
            conflict_signal=conflict_signal,
        ),
        emotional_intensity=_emotional_intensity(
            current_message,
            words,
            emotional_disclosure=emotional_disclosure,
        ),
        direct_question=direct_question,
        advice_requested=advice_requested,
        emotional_disclosure=emotional_disclosure,
        mixed_feelings=mixed_feelings,
        sarcasm_signal=sarcasm_signal,
        humour_signal=humour_signal,
        conflict_signal=conflict_signal,
        repair_signal=repair_signal,
        callback_signal=callback_signal,
        celebration_signal=celebration_signal,
        flirt_signal=flirt_signal,
        challenge_signal=challenge_signal,
        disclosure_signal=disclosure_signal,
        time_gap=_time_gap(recent_messages, now or utc_now()),
    )


def _intent(
    normalized: str,
    words: set[str],
    *,
    direct_question: bool,
    advice_requested: bool,
    repair_signal: bool,
    celebration_signal: bool,
    conflict_signal: bool,
) -> str:
    if repair_signal:
        return "repair"
    if conflict_signal:
        return "conflict"
    if celebration_signal:
        return "celebrate"
    if advice_requested:
        return "advise"
    if words & SUPPORT_WORDS:
        return "support"
    if _contains_any(normalized, PLAY_MARKERS):
        return "play"
    if direct_question and normalized.startswith(
        ("what ", "when ", "where ", "which ", "who ", "why ", "how ")
    ):
        return "information"
    return "connect"


def _tone(
    words: set[str],
    normalized: str,
    *,
    conflict_signal: bool,
    mixed_feelings: bool,
    sarcasm_signal: bool,
) -> str:
    if conflict_signal or words & SHARP_WORDS:
        return "sharp"
    if mixed_feelings:
        return "mixed"
    if words & {"anxious", "nervous", "overwhelmed", "panicking", "worried"}:
        return "anxious"
    if words & {"sad", "lonely", "drained", "exhausted", "tired"}:
        return "heavy"
    if words & BRIGHT_WORDS:
        return "bright"
    if _contains_any(normalized, CELEBRATION_MARKERS):
        return "bright"
    if _contains_any(normalized, PLAY_MARKERS) or sarcasm_signal:
        return "playful"
    if words & TENDER_WORDS:
        return "tender"
    if any(marker in normalized for marker in ("i don't know", "not ready", "leave it")):
        return "guarded"
    return "neutral"


def _subtext(
    normalized: str,
    *,
    intent: str,
    direct_question: bool,
    emotional_disclosure: bool,
) -> tuple[str, ...]:
    signals: list[str] = []
    if intent == "support" or emotional_disclosure:
        signals.append("wants the feeling noticed before solutions")
    if intent == "celebrate":
        signals.append("wants the moment shared rather than analysed")
    if intent in {"information", "advise"} or direct_question:
        signals.append("wants a direct answer")
    if any(
        marker in normalized
        for marker in ("just listen", "don't fix", "do not want advice", "no advice")
    ):
        signals.append("does not want advice")
    if any(marker in normalized for marker in ("stay with me", "keep me company", "i'm lonely")):
        signals.append("wants company")
    if any(marker in normalized for marker in ("not now", "drop it", "leave it")):
        signals.append("wants space")
    if _contains_any(normalized, SARCASM_MARKERS):
        signals.append("literal praise may conceal frustration or dry humour")
    if _contains_any(normalized, MIXED_FEELING_MARKERS):
        signals.append("holds more than one feeling at once")
    if any(
        marker in normalized
        for marker in (
            "that's not what i said",
            "that is not what i said",
            "you got that wrong",
            "you misunderstood",
        )
    ):
        signals.append("is correcting a prior assumption; accept the correction plainly")
    return tuple(signals[:3])


def _unresolved_context(
    journals: list[EpisodicJournal],
    recent_messages: list[Message],
    threads: list[ContinuityThread],
    *,
    topic_terms: set[str],
) -> tuple[str, ...]:
    selected: list[str] = []
    for thread in threads:
        if thread.status != "open":
            continue
        compact = " ".join(thread.content.split())[:180]
        if not _context_matches(compact, topic_terms):
            continue
        if compact and compact.casefold() not in {item.casefold() for item in selected}:
            selected.append(compact)
        if len(selected) >= 3:
            return tuple(selected)
    for journal in journals:
        for thread in journal.unresolved_threads_json:
            compact = " ".join(thread.split())[:180]
            if not _context_matches(compact, topic_terms):
                continue
            if compact and compact.casefold() not in {item.casefold() for item in selected}:
                selected.append(compact)
            if len(selected) >= 3:
                return tuple(selected)
    for message in reversed(recent_messages[-8:]):
        if message.role != "user":
            continue
        normalized = message.content.casefold()
        if not any(
            marker in normalized for marker in ("later", "next time", "promise", "come back")
        ):
            continue
        compact = " ".join(message.content.split())[:180]
        if not _context_matches(compact, topic_terms):
            continue
        if compact and compact.casefold() not in {item.casefold() for item in selected}:
            selected.append(compact)
        if len(selected) >= 3:
            break
    return tuple(selected)


def _context_matches(value: str, topic_terms: set[str]) -> bool:
    if not topic_terms:
        return False
    return bool(set(_topic_terms(value.casefold())) & topic_terms)


def _time_gap(recent_messages: list[Message], now: datetime) -> str:
    timestamps = [
        message.created_at for message in recent_messages if message.created_at is not None
    ]
    if not timestamps:
        return "continuous"
    previous = max(timestamps)
    elapsed = max((now - previous).total_seconds(), 0)
    if elapsed >= 14 * 86400:
        return "long_absence"
    if elapsed >= 86400:
        return "days"
    if elapsed >= 6 * 3600:
        return "hours"
    return "continuous"


def _companion_conflict_signal(normalized: str) -> bool:
    directed_markers = (
        "angry at you",
        "you always",
        "you ignored",
        "you hurt",
        "you lied",
        "you never",
        "your answer upset",
        "your reply upset",
        "what you said",
        "that's not what i said",
        "that is not what i said",
        "you got that wrong",
    )
    return _contains_any(normalized, directed_markers)


def _contains_any(value: str, markers: tuple[str, ...]) -> bool:
    return any(marker in value for marker in markers)


def _affirmed_words(normalized: str) -> set[str]:
    tokens = WORD_PATTERN.findall(normalized)
    selected: set[str] = set()
    for index, token in enumerate(tokens):
        prior = set(tokens[max(0, index - 2) : index])
        if prior & NEGATION_WORDS:
            continue
        selected.add(token)
    return selected


def _mixed_feelings(normalized: str, words: set[str]) -> bool:
    if _contains_any(normalized, MIXED_FEELING_MARKERS):
        return True
    positive = bool(words & BRIGHT_WORDS)
    difficult = bool(words & (SUPPORT_WORDS | SHARP_WORDS))
    return positive and difficult


def _conversation_mode(
    intent: str,
    tone: str,
    *,
    humour_signal: bool,
    emotional_disclosure: bool,
) -> str:
    if intent in {"advise", "information"}:
        return "practical"
    if intent in {"conflict", "repair"}:
        return "relational"
    if intent == "play" or humour_signal:
        return "playful"
    if emotional_disclosure or tone in {"anxious", "heavy", "mixed", "tender"}:
        return "emotional"
    return "casual"


def _stakes(
    intent: str,
    tone: str,
    *,
    emotional_disclosure: bool,
    conflict_signal: bool,
) -> str:
    if conflict_signal or intent in {"conflict", "repair"}:
        return "high"
    if emotional_disclosure and tone in {"anxious", "heavy", "mixed", "sharp", "tender"}:
        return "high"
    if intent in {"advise", "celebrate", "information", "support"}:
        return "medium"
    return "low"


def _emotional_intensity(
    message: str,
    words: set[str],
    *,
    emotional_disclosure: bool,
) -> float:
    score = 0.15 if emotional_disclosure else 0.0
    score += min(len(words & (SUPPORT_WORDS | SHARP_WORDS | TENDER_WORDS)) * 0.16, 0.48)
    score += min(len(words & INTENSITY_WORDS) * 0.1, 0.2)
    if "!" in message:
        score += min(message.count("!") * 0.05, 0.12)
    return round(min(score, 1.0), 2)


def _topic_terms(normalized: str) -> tuple[str, ...]:
    selected: list[str] = []
    for term in WORD_PATTERN.findall(normalized):
        if len(term) < 4 or term in TOPIC_STOP_WORDS or term in selected:
            continue
        selected.append(term)
    return tuple(selected[:12])
