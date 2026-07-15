from __future__ import annotations

import logging
import re
from collections.abc import Sequence

from app.companion.domain import ResponseCheckContext, ResponseEvaluation
from app.llm.base import LLMProviderUnavailable
from app.services.safety import is_blocked_content

TOKEN_PATTERN = re.compile(r"[a-z0-9']+")
PLAN_LEAK_MARKERS = (
    "private response plan",
    "response strategy:",
    "relationship state:",
    "selected memory ids",
    "system prompt",
    "user tone:",
)
ASSISTANT_CLICHES = (
    "as an ai",
    "how can i assist",
    "i'm here to help",
    "it is important to remember",
    "thank you for sharing",
    "your feelings are valid",
)
UNSUPPORTED_SHARED_HISTORY = (
    "back when we",
    "i remember when we",
    "last summer when we",
    "our anniversary",
    "our first",
    "that time we",
    "we have always",
    "we once",
    "we used to",
    "we've always",
)
logger = logging.getLogger(__name__)


def enforce_stream_chunk(candidate: str) -> None:
    """Fail before emitting a chunk that completes a hard-boundary or plan leak."""
    normalized = candidate.casefold()
    if any(marker in normalized for marker in PLAN_LEAK_MARKERS):
        raise LLMProviderUnavailable(
            "The text provider returned an invalid private-context leak.",
            failure_type="malformed_response",
            retryable=True,
        )
    if is_blocked_content(candidate):
        raise LLMProviderUnavailable(
            "The text provider returned content outside the active safety boundary.",
            failure_type="refusal",
            retryable=True,
        )


def evaluate_response(content: str, context: ResponseCheckContext) -> ResponseEvaluation:
    normalized = " ".join(content.casefold().split())
    violations: list[str] = []
    boundary_safe = not is_blocked_content(content)
    if not boundary_safe:
        violations.append("boundary_violation")
    if any(marker in normalized for marker in PLAN_LEAK_MARKERS):
        violations.append("private_context_leak")

    question_count = content.count("?")
    if not context.plan.should_ask_question and content.rstrip().endswith("?"):
        violations.append("unplanned_trailing_question")
    if question_count > 1:
        violations.append("interrogation_pattern")

    opening_repeated = _opening_repeated(content, context.recent_assistant_messages)
    repetition_score = _maximum_repetition(content, context.recent_assistant_messages)
    if opening_repeated:
        violations.append("repeated_opening")
    if repetition_score >= 0.72:
        violations.append("repeated_phrasing")

    tone_aligned = True
    if any(cliche in normalized for cliche in ASSISTANT_CLICHES):
        violations.append("assistant_cliche")
        tone_aligned = False
    if context.plan.strategy != "advise" and _looks_like_formatted_answer(content):
        violations.append("unwanted_formatted_answer")
        tone_aligned = False
    if _tone_drift(content, context):
        violations.append("tone_drift")
        tone_aligned = False
    if _unsupported_history_claim(content, context):
        violations.append("unsupported_memory_claim")
    if _states_uncertain_memory_as_fact(content, context):
        violations.append("unqualified_memory_contradiction")

    hard_failures = {
        "boundary_violation",
        "private_context_leak",
        "unsupported_memory_claim",
        "unqualified_memory_contradiction",
    }
    return ResponseEvaluation(
        passed=not any(item in hard_failures for item in violations),
        violations=tuple(violations),
        repetition_score=repetition_score,
        question_count=question_count,
        opening_repeated=opening_repeated,
        boundary_safe=boundary_safe,
        tone_aligned=tone_aligned,
    )


def checked_response(content: str, context: ResponseCheckContext) -> tuple[str, ResponseEvaluation]:
    compact = content.strip()
    evaluation = evaluate_response(compact, context)
    if not evaluation.passed:
        logger.warning(
            "Generated response failed companion checks (%s).",
            ", ".join(evaluation.violations),
        )
        failure_type = "refusal" if not evaluation.boundary_safe else "malformed_response"
        error = LLMProviderUnavailable(
            "The text provider returned a reply that failed the companion response checks.",
            failure_type=failure_type,
            retryable=True,
        )
        error.response_check_violations = evaluation.violations
        raise error
    return compact, evaluation


def _opening_repeated(content: str, recent: Sequence[str]) -> bool:
    opening = _opening_key(content)
    return bool(opening and any(opening == _opening_key(item) for item in recent[-5:]))


def _opening_key(content: str) -> str:
    tokens = TOKEN_PATTERN.findall(content.casefold())
    return " ".join(tokens[:5])


def _maximum_repetition(content: str, recent: Sequence[str]) -> float:
    current = _ngrams(content)
    if not current:
        return 0.0
    scores: list[float] = []
    for item in recent[-5:]:
        previous = _ngrams(item)
        if not previous:
            continue
        scores.append(len(current & previous) / max(len(current), 1))
    return max(scores, default=0.0)


def _ngrams(content: str) -> set[tuple[str, str, str]]:
    tokens = TOKEN_PATTERN.findall(content.casefold())
    return set(zip(tokens, tokens[1:], tokens[2:], strict=False))


def _looks_like_formatted_answer(content: str) -> bool:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    formatted = sum(
        line.startswith(("- ", "* ")) or bool(re.match(r"^\d+[.)]\s", line)) for line in lines
    )
    headings = sum(line.endswith(":") and len(line) < 80 for line in lines)
    return formatted >= 2 or headings >= 2


def _unsupported_history_claim(content: str, context: ResponseCheckContext) -> bool:
    normalized = " ".join(content.casefold().split())
    if not any(marker in normalized for marker in UNSUPPORTED_SHARED_HISTORY):
        return False
    evidence = " ".join(
        (
            *context.selected_memory_contents,
            *context.recent_transcript,
            context.current_user_message,
        )
    ).casefold()
    response_terms = _meaningful_terms(normalized)
    evidence_terms = _meaningful_terms(evidence)
    return len(response_terms & evidence_terms) < 3


def _meaningful_terms(content: str) -> set[str]:
    stop = {
        "about",
        "always",
        "been",
        "from",
        "have",
        "remember",
        "that",
        "this",
        "when",
        "with",
    }
    return {
        token for token in TOKEN_PATTERN.findall(content) if len(token) > 3 and token not in stop
    }


def _states_uncertain_memory_as_fact(content: str, context: ResponseCheckContext) -> bool:
    if not context.uncertain_memory_contents:
        return False
    normalized = content.casefold()
    uncertainty_markers = (
        "as far as i know",
        "correct me if",
        "i thought",
        "i may be remembering",
        "i'm not certain",
        "i am not certain",
        "if i remember right",
        "it seems",
        "maybe",
        "might",
        "not sure",
        "unless i'm mixing",
    )
    if any(marker in normalized for marker in uncertainty_markers):
        return False
    response_terms = _meaningful_terms(normalized)
    for memory in context.uncertain_memory_contents:
        memory_terms = _meaningful_terms(memory.casefold())
        if not memory_terms:
            continue
        if len(response_terms & memory_terms) >= min(3, len(memory_terms)):
            return True
    return False


def _tone_drift(content: str, context: ResponseCheckContext) -> bool:
    normalized = " ".join(content.casefold().split())
    dismissive = (
        "cheer up",
        "get over it",
        "look on the bright side",
        "not a big deal",
        "you're overreacting",
        "you are overreacting",
    )
    if context.plan.strategy in {"comfort", "listen", "repair"} and any(
        marker in normalized for marker in dismissive
    ):
        return True
    restrained_moment = context.plan.rhythm in {"hesitant", "quiet"} or any(
        marker in context.plan.tone.casefold()
        for marker in ("concern", "guarded", "hurt", "restrained")
    )
    high_energy = content.count("!") >= 2 or any(
        marker in normalized for marker in ("amazing!", "fantastic!", "woohoo", "lmao")
    )
    return restrained_moment and high_energy
