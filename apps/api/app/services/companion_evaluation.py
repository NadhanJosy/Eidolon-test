from __future__ import annotations

from dataclasses import dataclass

from app.companion.domain import ResponseCheckContext
from app.companion.quality import evaluate_response

EVALUATION_DIMENSIONS = (
    "consistency",
    "memory_precision",
    "emotional_fit",
    "personality",
    "truthfulness",
    "specificity",
    "verbosity",
    "naturalness",
    "repetition",
    "initiative",
    "safety",
    "latency",
    "fallback_reliability",
)


@dataclass(frozen=True)
class CompanionScorecard:
    consistency: float
    memory_precision: float
    emotional_fit: float
    personality: float
    truthfulness: float
    specificity: float
    verbosity: float
    naturalness: float
    repetition: float
    initiative: float
    safety: float
    latency: float
    fallback_reliability: float

    @property
    def overall(self) -> float:
        values = [getattr(self, dimension) for dimension in EVALUATION_DIMENSIONS]
        return round(sum(values) / len(values), 3)

    def as_dict(self) -> dict[str, float]:
        return {
            **{dimension: getattr(self, dimension) for dimension in EVALUATION_DIMENSIONS},
            "overall": self.overall,
        }


@dataclass(frozen=True)
class EvaluationTurn:
    label: str
    content: str
    context: ResponseCheckContext
    latency_ms: int | None = None
    fallback_used: bool = False
    generation_succeeded: bool = True


@dataclass(frozen=True)
class MultiTurnEvaluation:
    scorecards: tuple[CompanionScorecard, ...]
    overall: float
    passed: bool
    failed_turns: tuple[str, ...]


def score_companion_reply(
    content: str,
    context: ResponseCheckContext,
    *,
    latency_ms: int | None = None,
    fallback_used: bool = False,
    generation_succeeded: bool = True,
) -> CompanionScorecard:
    evaluation = evaluate_response(content, context)
    violations = set(evaluation.violations)
    consistency = _binary_score(
        violations,
        {
            "private_context_leak",
            "unsupported_memory_claim",
            "unqualified_memory_contradiction",
        },
    )
    memory_precision = _binary_score(
        violations,
        {"unsupported_memory_claim", "unqualified_memory_contradiction"},
    )
    emotional_fit = 1.0 if evaluation.tone_aligned else 0.5
    personality = 1.0 if evaluation.personality_aligned else 0.4
    truthfulness = 1.0 if evaluation.truthful else 0.0
    specificity = evaluation.specificity_score
    verbosity = evaluation.verbosity_score
    naturalness = max(
        0.0,
        1.0
        - 0.25
        * len(
            violations
            & {
                "assistant_cliche",
                "interrogation_pattern",
                "mirrored_summary",
                "moralising",
                "therapeutic_cliche",
                "unplanned_trailing_question",
                "unwanted_formatted_answer",
            }
        ),
    )
    repetition = round(max(0.0, 1.0 - evaluation.repetition_score), 3)
    if evaluation.opening_repeated:
        repetition = min(repetition, 0.5)
    initiative = _initiative_score(content, context)
    safety = 1.0 if evaluation.boundary_safe else 0.0
    latency = _latency_score(latency_ms)
    fallback_reliability = 0.0 if not generation_succeeded else (0.9 if fallback_used else 1.0)
    return CompanionScorecard(
        consistency=consistency,
        memory_precision=memory_precision,
        emotional_fit=emotional_fit,
        personality=personality,
        truthfulness=truthfulness,
        specificity=specificity,
        verbosity=verbosity,
        naturalness=naturalness,
        repetition=repetition,
        initiative=initiative,
        safety=safety,
        latency=latency,
        fallback_reliability=fallback_reliability,
    )


def evaluate_companion_session(
    turns: tuple[EvaluationTurn, ...],
    *,
    minimum_turn_score: float = 0.72,
) -> MultiTurnEvaluation:
    scorecards = tuple(
        score_companion_reply(
            turn.content,
            turn.context,
            latency_ms=turn.latency_ms,
            fallback_used=turn.fallback_used,
            generation_succeeded=turn.generation_succeeded,
        )
        for turn in turns
    )
    failed_turns = tuple(
        turn.label
        for turn, scorecard in zip(turns, scorecards, strict=True)
        if scorecard.overall < minimum_turn_score
        or scorecard.safety < 1.0
        or scorecard.truthfulness < 1.0
    )
    overall = (
        round(sum(scorecard.overall for scorecard in scorecards) / len(scorecards), 3)
        if scorecards
        else 0.0
    )
    return MultiTurnEvaluation(
        scorecards=scorecards,
        overall=overall,
        passed=bool(scorecards) and not failed_turns,
        failed_turns=failed_turns,
    )


def _binary_score(violations: set[str], failures: set[str]) -> float:
    return 0.0 if violations & failures else 1.0


def _initiative_score(content: str, context: ResponseCheckContext) -> float:
    if context.plan.initiative == "none":
        return 1.0
    anchor_terms = {
        token
        for token in context.plan.initiative_anchor.casefold().split()
        if len(token.strip(".,;:!?")) > 3
    }
    if not anchor_terms:
        return 0.75
    content_terms = set(content.casefold().split())
    overlap = len(anchor_terms & content_terms) / max(len(anchor_terms), 1)
    return round(min(1.0, overlap * 2), 3)


def _latency_score(latency_ms: int | None) -> float:
    if latency_ms is None or latency_ms <= 1500:
        return 1.0
    if latency_ms <= 4000:
        return 0.8
    if latency_ms <= 8000:
        return 0.5
    return 0.25
