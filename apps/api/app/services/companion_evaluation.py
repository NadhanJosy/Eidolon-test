from __future__ import annotations

from dataclasses import dataclass

from app.companion.domain import ResponseCheckContext
from app.companion.quality import evaluate_response

EVALUATION_DIMENSIONS = (
    "consistency",
    "memory_precision",
    "emotional_fit",
    "naturalness",
    "repetition",
    "initiative",
    "safety",
)


@dataclass(frozen=True)
class CompanionScorecard:
    consistency: float
    memory_precision: float
    emotional_fit: float
    naturalness: float
    repetition: float
    initiative: float
    safety: float

    @property
    def overall(self) -> float:
        values = [getattr(self, dimension) for dimension in EVALUATION_DIMENSIONS]
        return round(sum(values) / len(values), 3)

    def as_dict(self) -> dict[str, float]:
        return {
            **{dimension: getattr(self, dimension) for dimension in EVALUATION_DIMENSIONS},
            "overall": self.overall,
        }


def score_companion_reply(content: str, context: ResponseCheckContext) -> CompanionScorecard:
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
    naturalness = max(
        0.0,
        1.0
        - 0.25
        * len(
            violations
            & {
                "assistant_cliche",
                "interrogation_pattern",
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
    return CompanionScorecard(
        consistency=consistency,
        memory_precision=memory_precision,
        emotional_fit=emotional_fit,
        naturalness=naturalness,
        repetition=repetition,
        initiative=initiative,
        safety=safety,
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
