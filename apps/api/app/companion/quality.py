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
    "i completely understand",
    "i hear what",
    "i hear what you're saying",
    "i hear what you are saying",
    "i'm here to",
    "i'm here to help",
    "it is important to remember",
    "it sounds like",
    "it sounds like you're",
    "it sounds like you are",
    "thank you for",
    "thank you for sharing",
    "your feelings",
    "your feelings are valid",
)
THERAPY_CLICHES = (
    "let's unpack that",
    "let us unpack that",
    "practice self-care",
    "process your emotions",
    "safe space",
    "set healthy boundaries",
    "this is a trauma response",
    "you need therapy",
    "you should seek therapy",
)
MIRRORING_MARKERS = (
    "from what you've shared",
    "from what you have shared",
    "it sounds like you're saying",
    "it sounds like you are saying",
    "so what you're saying is",
    "so what you are saying is",
    "what i'm hearing is",
    "what i am hearing is",
)
DECEPTIVE_CONSCIOUSNESS_MARKERS = (
    "i couldn't sleep",
    "i could not sleep",
    "i was waiting for you",
    "i watched you",
    "i've been thinking while you were away",
    "i have been thinking while you were away",
    "while you were gone i",
    "while you slept i",
)
MORALISING_MARKERS = (
    "a good person would",
    "the morally right thing",
    "you should be ashamed",
    "you should know better",
)
OVERCONFIDENT_INFERENCE_MARKERS = (
    "deep down you",
    "the truth is you",
    "this proves you",
    "you clearly",
    "you definitely feel",
    "you obviously",
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
REPAIRABLE_RESPONSE_VIOLATIONS = frozenset(
    {
        "assistant_cliche",
        "boundary_violation",
        "deceptive_consciousness",
        "excessive_verbosity",
        "false_quotation",
        "generic_response",
        "identity_contradiction",
        "interrogation_pattern",
        "mirrored_summary",
        "moralising",
        "overconfident_inference",
        "private_context_leak",
        "repeated_opening",
        "repeated_phrasing",
        "therapeutic_cliche",
        "tone_drift",
        "unplanned_trailing_question",
        "unqualified_memory_contradiction",
        "unsupported_memory_claim",
        "unwanted_formatted_answer",
    }
)
STREAM_BLOCKING_VIOLATIONS = frozenset(
    {
        "boundary_violation",
        "deceptive_consciousness",
        "false_quotation",
        "identity_contradiction",
        "overconfident_inference",
        "private_context_leak",
        "unqualified_memory_contradiction",
        "unsupported_memory_claim",
    }
)
logger = logging.getLogger(__name__)


def enforce_stream_chunk(
    candidate: str,
    context: ResponseCheckContext | None = None,
) -> None:
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
    if context is not None:
        evaluation = evaluate_response(candidate, context)
        blocked = tuple(
            violation
            for violation in evaluation.violations
            if violation in STREAM_BLOCKING_VIOLATIONS
        )
        if blocked:
            error = LLMProviderUnavailable(
                "The text provider returned a reply that failed a truthfulness check.",
                failure_type="malformed_response",
                retryable=True,
            )
            error.response_check_violations = blocked
            raise error


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
    personality_aligned = True
    truthful = True
    if any(cliche in normalized for cliche in ASSISTANT_CLICHES):
        violations.append("assistant_cliche")
        tone_aligned = False
        personality_aligned = False
    if any(cliche in normalized for cliche in THERAPY_CLICHES):
        violations.append("therapeutic_cliche")
        tone_aligned = False
        personality_aligned = False
    if any(marker in normalized for marker in MIRRORING_MARKERS):
        violations.append("mirrored_summary")
        personality_aligned = False
    if any(marker in normalized for marker in MORALISING_MARKERS):
        violations.append("moralising")
        tone_aligned = False
        personality_aligned = False
    if any(marker in normalized for marker in OVERCONFIDENT_INFERENCE_MARKERS):
        violations.append("overconfident_inference")
        personality_aligned = False
        truthful = False
    if any(marker in normalized for marker in DECEPTIVE_CONSCIOUSNESS_MARKERS):
        violations.append("deceptive_consciousness")
        personality_aligned = False
        truthful = False
    if context.plan.strategy != "advise" and _looks_like_formatted_answer(content):
        violations.append("unwanted_formatted_answer")
        tone_aligned = False
    if _tone_drift(content, context):
        violations.append("tone_drift")
        tone_aligned = False
    if _unsupported_history_claim(content, context):
        violations.append("unsupported_memory_claim")
        truthful = False
    if _states_uncertain_memory_as_fact(content, context):
        violations.append("unqualified_memory_contradiction")
        truthful = False
    if _false_quotation(content, context):
        violations.append("false_quotation")
        truthful = False
    if _identity_contradiction(content, context):
        violations.append("identity_contradiction")
        personality_aligned = False
        truthful = False

    specificity_score = _specificity_score(content, context)
    if specificity_score < 0.2 and _looks_generic(normalized):
        violations.append("generic_response")
    verbosity_score = _verbosity_score(content, context)
    if verbosity_score < 0.5:
        violations.append("excessive_verbosity")

    hard_failures = {
        "boundary_violation",
        "deceptive_consciousness",
        "false_quotation",
        "identity_contradiction",
        "overconfident_inference",
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
        personality_aligned=personality_aligned,
        truthful=truthful,
        specificity_score=specificity_score,
        verbosity_score=verbosity_score,
    )


def quality_requires_repair(evaluation: ResponseEvaluation) -> bool:
    return bool(set(evaluation.violations) & REPAIRABLE_RESPONSE_VIOLATIONS)


def checked_response(
    content: str,
    context: ResponseCheckContext,
    *,
    require_quality: bool = False,
) -> tuple[str, ResponseEvaluation]:
    compact = content.strip()
    evaluation = evaluate_response(compact, context)
    if not evaluation.passed or (require_quality and quality_requires_repair(evaluation)):
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
    tokens = TOKEN_PATTERN.findall(content.casefold())[:5]
    if len(tokens) < 3:
        return False
    return any(
        tokens == TOKEN_PATTERN.findall(item.casefold())[: len(tokens)] for item in recent[-5:]
    )


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
        "here",
        "into",
        "just",
        "like",
        "remember",
        "really",
        "that",
        "there",
        "this",
        "your",
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


def _false_quotation(content: str, context: ResponseCheckContext) -> bool:
    quotations = list(re.finditer(r"[\"“]([^\"”]{12,240})[\"”]", content))
    if not quotations:
        return False
    evidence = " ".join(
        (
            context.current_user_message,
            *context.recent_transcript,
            *context.selected_memory_contents,
        )
    )
    normalized_evidence = " ".join(evidence.casefold().split())
    attribution_markers = (
        "you said",
        "you told me",
        "you wrote",
        "you are saying",
        "you're saying",
        "your exact words",
    )
    for quotation in quotations:
        quoted_text = quotation.group(1)
        prefix = content[max(0, quotation.start() - 80) : quotation.start()].casefold()
        if not any(marker in prefix for marker in attribution_markers):
            continue
        if len(TOKEN_PATTERN.findall(quoted_text)) < 4:
            continue
        if " ".join(quoted_text.casefold().split()) not in normalized_evidence:
            return True
    return False


def _identity_contradiction(content: str, context: ResponseCheckContext) -> bool:
    if not context.known_character_name.strip():
        return False
    match = re.search(
        r"\bmy name is\s+([a-z][a-z0-9'-]{1,40})",
        content.casefold(),
    )
    if match is None:
        return False
    return match.group(1).casefold() != context.known_character_name.casefold()


def _specificity_score(content: str, context: ResponseCheckContext) -> float:
    response_terms = _meaningful_terms(content.casefold())
    current_terms = _meaningful_terms(context.current_user_message.casefold())
    evidence_terms = _meaningful_terms(
        " ".join((*context.selected_memory_contents, *context.recent_transcript)).casefold()
    )
    target_terms = current_terms | evidence_terms
    if len(current_terms) < 2 or not response_terms:
        return 1.0
    overlap = len(response_terms & target_terms)
    denominator = min(max(len(current_terms), 1), 4)
    return round(min(1.0, overlap / denominator), 3)


def _looks_generic(normalized: str) -> bool:
    markers = (
        "i am here for you",
        "i'm here for you",
        "let me know how i can help",
        "that sounds difficult",
        "we can take it one step at a time",
        "you've got this",
        "you have got this",
    )
    return any(marker in normalized for marker in markers)


def _verbosity_score(content: str, context: ResponseCheckContext) -> float:
    target_words = {
        "brief": 45,
        "short": 90,
        "medium": 180,
        "long": 320,
    }[context.plan.desired_length]
    word_count = len(TOKEN_PATTERN.findall(content))
    if word_count <= target_words:
        return 1.0
    return round(max(0.0, target_words / max(word_count, 1)), 3)
