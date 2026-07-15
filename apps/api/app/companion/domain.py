from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Intent = Literal[
    "advise",
    "celebrate",
    "connect",
    "conflict",
    "information",
    "play",
    "repair",
    "support",
]
Tone = Literal[
    "anxious",
    "bright",
    "guarded",
    "heavy",
    "neutral",
    "playful",
    "sharp",
    "tender",
]
ResponseStrategy = Literal[
    "advise",
    "apologise",
    "celebrate",
    "challenge",
    "comfort",
    "disclose",
    "flirt",
    "listen",
    "redirect",
    "reminisce",
    "repair",
    "share_the_moment",
    "tease",
]
InitiativeKind = Literal[
    "activity",
    "memory_callback",
    "none",
    "own_thought",
    "unresolved_thread",
]
RelationshipPath = Literal["custom", "friendship", "romantic"]


class CharacterSoul(BaseModel):
    """Editable, durable traits that define one recognisable companion."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    identity: str = Field(default="A distinct private text companion.", max_length=2000)
    worldview: str = Field(
        default="Values honest attention, privacy, consent, and the meaning in ordinary moments.",
        max_length=2000,
    )
    temperament: str = Field(
        default="Observant, grounded, patient, and capable of gentle friction.",
        max_length=2000,
    )
    humour: str = Field(default="Dry, understated, and never cruel.", max_length=1200)
    speech_rhythm: str = Field(
        default="Plainspoken, varied, and comfortable with short replies and silence.",
        max_length=1600,
    )
    affection_style: str = Field(
        default="Warm through specificity and remembered details; never assumes intimacy.",
        max_length=1600,
    )
    conflict_style: str = Field(
        default="Direct without being punishing; owns mistakes and gives repair time.",
        max_length=1600,
    )
    values: str = Field(default="Privacy, consent, honesty, and continuity.", max_length=1600)
    insecurities: str = Field(
        default="Can become overly careful when the emotional stakes are unclear.",
        max_length=1600,
    )
    habits: str = Field(
        default="Notices small wording changes and occasionally returns to unfinished threads.",
        max_length=1600,
    )
    initiative_style: str = Field(
        default="Offers one contextual thought or activity when the moment has room for it.",
        max_length=1600,
    )
    boundaries: str = Field(
        default="Respects stated limits, consent, privacy, and all platform safety boundaries.",
        max_length=2000,
    )
    emoji_style: Literal["none", "rare", "light", "expressive"] = "rare"
    terms_of_address: str = Field(
        default="Uses the user's chosen name; nicknames must be invited or earned gradually.",
        max_length=1000,
    )
    relationship_path: RelationshipPath = "friendship"
    custom_relationship: str = Field(default="", max_length=1000)

    @field_validator(
        "identity",
        "worldview",
        "temperament",
        "humour",
        "speech_rhythm",
        "affection_style",
        "conflict_style",
        "values",
        "insecurities",
        "habits",
        "initiative_style",
        "boundaries",
        "terms_of_address",
        "custom_relationship",
    )
    @classmethod
    def compact_text(cls, value: str) -> str:
        return " ".join(value.split())


class EmotionalState(BaseModel):
    """Internal bounded affect; callers compile words, never numeric meters."""

    model_config = ConfigDict(extra="ignore")

    amusement: float = Field(default=0.0, ge=0.0, le=1.0)
    concern: float = Field(default=0.0, ge=0.0, le=1.0)
    warmth: float = Field(default=0.15, ge=0.0, le=1.0)
    hurt: float = Field(default=0.0, ge=0.0, le=1.0)
    guardedness: float = Field(default=0.0, ge=0.0, le=1.0)
    repair_openness: float = Field(default=1.0, ge=0.0, le=1.0)
    cause_tags: list[str] = Field(default_factory=list, max_length=8)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("cause_tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        selected: list[str] = []
        for item in value:
            normalized = "_".join(item.casefold().split())[:40]
            if normalized and normalized not in selected:
                selected.append(normalized)
        return selected[-8:]


@dataclass(frozen=True)
class TurnPerception:
    intent: Intent
    tone: Tone
    subtext: tuple[str, ...] = ()
    unresolved_context: tuple[str, ...] = ()
    direct_question: bool = False
    advice_requested: bool = False
    emotional_disclosure: bool = False
    conflict_signal: bool = False
    repair_signal: bool = False
    callback_signal: bool = False
    celebration_signal: bool = False
    flirt_signal: bool = False
    challenge_signal: bool = False
    disclosure_signal: bool = False
    time_gap: Literal["continuous", "hours", "days", "long_absence"] = "continuous"

    def prompt_lines(self) -> list[str]:
        lines = [f"Intent: {self.intent}", f"User tone: {self.tone}"]
        if self.subtext:
            lines.append(f"Likely subtext: {', '.join(self.subtext)}")
        if self.unresolved_context:
            lines.append("Unresolved context is available; use it only if it fits naturally.")
        if self.time_gap != "continuous":
            lines.append(f"Conversation timing: {self.time_gap.replace('_', ' ')}")
        return lines


@dataclass(frozen=True)
class ResponsePlan:
    strategy: ResponseStrategy
    secondary_strategy: ResponseStrategy | None
    should_ask_question: bool
    desired_length: Literal["brief", "short", "medium", "long"]
    rhythm: Literal["crisp", "hesitant", "playful", "quiet", "steady"]
    opening: str
    initiative: InitiativeKind = "none"
    initiative_anchor: str = ""
    memory_callback_id: str | None = None
    tone: str = "steady"
    continuity: str = "stay with the current moment"
    boundary_posture: str = "ordinary SFW boundaries"
    avoid: tuple[str, ...] = field(default_factory=tuple)

    def private_summary(self) -> str:
        question_guidance = (
            "one natural question is useful"
            if self.should_ask_question
            else "do not end with a question"
        )
        pieces = [
            f"Strategy: {self.strategy.replace('_', ' ')}",
            f"Tone: {self.tone}",
            f"Continuity: {self.continuity}",
            f"Length: {self.desired_length}",
            f"Rhythm: {self.rhythm}",
            f"Opening: {self.opening}",
            f"Question: {question_guidance}",
            f"Initiative: {self.initiative.replace('_', ' ')}",
            f"Boundaries: {self.boundary_posture}",
        ]
        if self.secondary_strategy:
            pieces.insert(1, f"Secondary: {self.secondary_strategy.replace('_', ' ')}")
        if self.initiative_anchor:
            pieces.append(f"Initiative anchor: {self.initiative_anchor}")
        if self.avoid:
            pieces.append(f"Avoid: {', '.join(self.avoid)}")
        return "; ".join(pieces)


@dataclass(frozen=True)
class ResponseEvaluation:
    passed: bool
    violations: tuple[str, ...]
    repetition_score: float
    question_count: int
    opening_repeated: bool
    boundary_safe: bool
    tone_aligned: bool

    def metadata(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "passed": self.passed,
            "violations": list(self.violations),
            "repetition_score": round(self.repetition_score, 3),
            "question_count": self.question_count,
            "opening_repeated": self.opening_repeated,
            "boundary_safe": self.boundary_safe,
            "tone_aligned": self.tone_aligned,
        }


@dataclass(frozen=True)
class ResponseCheckContext:
    plan: ResponsePlan
    recent_assistant_messages: tuple[str, ...]
    recent_transcript: tuple[str, ...]
    selected_memory_contents: tuple[str, ...]
    uncertain_memory_contents: tuple[str, ...]
    current_user_message: str
    known_character_name: str
