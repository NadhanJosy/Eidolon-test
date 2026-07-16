from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import LLMProvider, LLMProviderUnavailable, TokenUsage
from app.models import EpisodicJournal, MemoryItem, Message, utc_now
from app.services.journal import create_journal
from app.services.memory import (
    create_memory,
    forget_memory,
    memory_type_allowed_by_preferences,
)
from app.services.relationship import clamp
from app.services.safety import is_blocked_content

COGNITION_VERSION = "grounded_cognition_v1"
COGNITION_SCHEMA_NAME = "eidolon_grounded_cognition_v1"
MAX_COGNITION_CONTEXT_CHARS = 6000
MEMORY_TYPES = {
    "boundary",
    "date",
    "event",
    "inside_joke",
    "interest",
    "person",
    "place",
    "preference",
    "promise",
    "routine",
    "shared_lore",
    "shared_moment",
    "theme",
    "user_fact",
}
RELATIONSHIP_SIGNALS = {
    "boundary_assertion",
    "conflict",
    "gratitude",
    "play",
    "reliability",
    "repair_attempt",
    "shared_ritual",
    "support",
    "vulnerability",
}
CORRECTION_MARKERS = (
    "actually",
    "anymore",
    "correction",
    "i changed",
    "i don't now",
    "i do not now",
    "not anymore",
    "rather than",
)
SELECTIVE_MARKERS = (
    "always",
    "anniversary",
    "boundary",
    "call me",
    "every day",
    "every morning",
    "every night",
    "favorite",
    "friend",
    "i am",
    "i feel",
    "i felt",
    "i hate",
    "i keep",
    "i like",
    "i live",
    "i love",
    "i need",
    "i prefer",
    "i promise",
    "inside joke",
    "my name",
    "my partner",
    "my pronouns",
    "next time",
    "please don't",
    "please remember",
    "remind me",
    "remember that",
    "ritual",
    "we call",
)
UNSAFE_DURABLE_MARKERS = (
    "api key",
    "credential",
    "password",
    "private key",
    "secret token",
)
GROUNDING_STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "as",
    "at",
    "be",
    "been",
    "being",
    "by",
    "carry",
    "carried",
    "for",
    "forward",
    "from",
    "has",
    "have",
    "i",
    "is",
    "it",
    "its",
    "me",
    "my",
    "named",
    "of",
    "our",
    "said",
    "says",
    "that",
    "the",
    "their",
    "them",
    "they",
    "this",
    "to",
    "user",
    "us",
    "was",
    "we",
    "were",
    "with",
    "worth",
}
PREFERENCE_POSITIVE_TERMS = {
    "adore",
    "enjoy",
    "favorite",
    "favourite",
    "like",
    "love",
    "prefer",
}
PREFERENCE_NEGATIVE_TERMS = {
    "avoid",
    "dislike",
    "hate",
}
NEGATION_TERMS = {"cannot", "cant", "don't", "dont", "never", "no", "not", "without"}
GROUNDING_PARAPHRASE_GROUPS = (
    PREFERENCE_POSITIVE_TERMS,
    PREFERENCE_NEGATIVE_TERMS,
    {"home", "live", "reside"},
    {"partner", "spouse"},
    {"routine", "ritual"},
)


class CognitionMemoryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_type: str = Field(min_length=1, max_length=40)
    canonical_text: str = Field(min_length=1, max_length=500)
    evidence_quote: str = Field(min_length=1, max_length=600)
    claim_key: str | None = Field(max_length=160)
    retrieval_facets: list[str] = Field(max_length=8)
    salience: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    emotional_weight: float = Field(ge=-1.0, le=1.0)
    stability: str
    is_correction: bool


class CognitionEpisode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    worthy: bool
    title: str | None = Field(max_length=200)
    summary: str | None = Field(max_length=1200)
    emotional_tags: list[str] = Field(max_length=6)
    evidence_quotes: list[str] = Field(max_length=3)
    source_message_ids: list[str] = Field(max_length=8)
    salience: float = Field(ge=0.0, le=1.0)


class CognitionRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signals: list[str] = Field(max_length=6)
    confidence: float = Field(ge=0.0, le=1.0)


class CognitionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_candidates: list[CognitionMemoryCandidate] = Field(max_length=3)
    episode: CognitionEpisode
    relationship: CognitionRelationship
    referenced_memory_ids: list[str] = Field(max_length=8)


@dataclass(frozen=True)
class CognitionAnalysis:
    report: CognitionReport | None
    source: str
    failure_code: str | None = None
    usage: TokenUsage = TokenUsage()


@dataclass(frozen=True)
class CognitionApplication:
    memory_ids: tuple[uuid.UUID, ...] = ()
    moment_id: uuid.UUID | None = None
    change_labels: tuple[str, ...] = ()
    relationship_signals: tuple[str, ...] = ()
    relationship_confidence: float = 0.0


def cognition_schema() -> dict[str, object]:
    return CognitionReport.model_json_schema()


def turn_is_eligible(content: str, *, mode: str) -> bool:
    normalized = _normalized_text(content)
    if mode == "off" or len(normalized) < 12:
        return False
    if any(marker in normalized for marker in UNSAFE_DURABLE_MARKERS):
        return False
    if is_blocked_content(content):
        return False
    if mode == "all":
        return True
    if any(marker in normalized for marker in SELECTIVE_MARKERS):
        return True
    return len(normalized) >= 140 and len(_meaningful_tokens(normalized)) >= 12


async def analyze_completed_turn(
    *,
    provider: LLMProvider,
    user_message: Message,
    assistant_message: Message,
    recent_messages: list[Message],
    selected_memories: list[MemoryItem],
    mode: str,
    max_output_tokens: int,
) -> CognitionAnalysis:
    if not turn_is_eligible(user_message.content, mode=mode):
        return CognitionAnalysis(report=None, source="skipped")
    prompt = _cognition_prompt(
        user_message=user_message,
        assistant_message=assistant_message,
        recent_messages=recent_messages,
        selected_memories=selected_memories,
    )
    try:
        generation = await provider.generate_structured(
            prompt,
            schema_name=COGNITION_SCHEMA_NAME,
            schema=cognition_schema(),
            max_output_tokens=max_output_tokens,
        )
        report = CognitionReport.model_validate(json.loads(generation.content))
    except LLMProviderUnavailable as exc:
        return CognitionAnalysis(
            report=None,
            source="degraded",
            failure_code=_safe_failure_code(exc.failure_type),
        )
    except (AttributeError, json.JSONDecodeError, ValidationError, TypeError, ValueError):
        return CognitionAnalysis(
            report=None,
            source="degraded",
            failure_code="invalid_structured_output",
        )
    grounded = _ground_report(
        report,
        user_message=user_message,
        assistant_message=assistant_message,
        selected_memories=selected_memories,
    )
    return CognitionAnalysis(
        report=grounded,
        source="structured",
        usage=generation.usage,
    )


async def apply_cognition_report(
    session: AsyncSession,
    *,
    report: CognitionReport,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user_message: Message,
    assistant_message: Message,
    scope: str,
    memory_preferences: dict[str, object],
) -> CognitionApplication:
    memory_ids: list[uuid.UUID] = []
    labels: list[str] = []
    for candidate in report.memory_candidates:
        if candidate.memory_type not in MEMORY_TYPES:
            continue
        if not memory_type_allowed_by_preferences(candidate.memory_type, memory_preferences):
            continue
        if candidate.stability == "transient" or candidate.confidence < 0.62:
            continue
        memory, change = await _apply_memory_candidate(
            session,
            candidate=candidate,
            user_id=user_id,
            character_id=character_id,
            source_message_id=user_message.id,
            scope=scope,
        )
        memory_ids.append(memory.id)
        if change not in labels:
            labels.append(change)

    known_memory_ids = {
        memory_id
        for value in report.referenced_memory_ids
        if (memory_id := _optional_uuid(value)) is not None
    }
    if known_memory_ids:
        readable_scopes = ("general", "adult") if scope == "adult" else ("general",)
        recalled = await session.execute(
            select(MemoryItem).where(
                MemoryItem.id.in_(known_memory_ids),
                MemoryItem.user_id == user_id,
                MemoryItem.character_id == character_id,
                MemoryItem.scope.in_(readable_scopes),
                MemoryItem.forgotten_at.is_(None),
            )
        )
        for memory in recalled.scalars().all():
            memory.last_recalled_at = utc_now()
            memory.decay_score = clamp(memory.decay_score - 0.05, 0.0, 1.0)

    moment_id = await _apply_episode(
        session,
        report=report,
        user_id=user_id,
        character_id=character_id,
        conversation_id=conversation_id,
        user_message=user_message,
        assistant_message=assistant_message,
        scope=scope,
    )
    if moment_id is not None:
        labels.append("moment")

    relationship_signals = tuple(
        signal for signal in report.relationship.signals if signal in RELATIONSHIP_SIGNALS
    )
    return CognitionApplication(
        memory_ids=tuple(dict.fromkeys(memory_ids)),
        moment_id=moment_id,
        change_labels=tuple(dict.fromkeys(labels)),
        relationship_signals=relationship_signals,
        relationship_confidence=report.relationship.confidence,
    )


async def _apply_memory_candidate(
    session: AsyncSession,
    *,
    candidate: CognitionMemoryCandidate,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    source_message_id: uuid.UUID,
    scope: str,
) -> tuple[MemoryItem, str]:
    claim_key = _claim_key(candidate.claim_key, candidate.memory_type, candidate.canonical_text)
    result = await session.execute(
        select(MemoryItem)
        .where(
            MemoryItem.user_id == user_id,
            MemoryItem.character_id == character_id,
            MemoryItem.scope == scope,
            MemoryItem.claim_key == claim_key,
            MemoryItem.forgotten_at.is_(None),
        )
        .order_by(desc(MemoryItem.updated_at), MemoryItem.id.asc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    same_claim = existing is not None and _normalized_text(existing.content) == _normalized_text(
        candidate.canonical_text
    )
    if same_claim:
        memory = await create_memory(
            session,
            user_id=user_id,
            character_id=character_id,
            content=candidate.canonical_text,
            memory_type=candidate.memory_type,
            importance=candidate.salience,
            confidence=candidate.confidence,
            emotional_weight=candidate.emotional_weight,
            source_message_id=source_message_id,
            extraction_metadata={"version": COGNITION_VERSION, "grounded": True},
            memory_source="grounded_cognition",
            scope=scope,
            claim_key=claim_key,
            retrieval_facets=candidate.retrieval_facets,
        )
        return memory, "reinforced"

    explicit_correction = candidate.is_correction and any(
        marker in _normalized_text(candidate.evidence_quote) for marker in CORRECTION_MARKERS
    )
    if existing is not None and explicit_correction:
        await forget_memory(session, existing, reason="superseded_by_explicit_correction")
        memory = await create_memory(
            session,
            user_id=user_id,
            character_id=character_id,
            content=candidate.canonical_text,
            memory_type=candidate.memory_type,
            importance=max(candidate.salience, 0.7),
            confidence=max(candidate.confidence, 0.82),
            emotional_weight=candidate.emotional_weight,
            source_message_id=source_message_id,
            extraction_metadata={"version": COGNITION_VERSION, "grounded": True},
            memory_source="grounded_cognition",
            capture_metadata={"supersedes_memory_id": str(existing.id)},
            merge_similar=False,
            scope=scope,
            claim_key=claim_key,
            retrieval_facets=candidate.retrieval_facets,
        )
        existing.metadata_json = {
            **(existing.metadata_json or {}),
            "superseded_by_memory_id": str(memory.id),
        }
        return memory, "corrected"

    memory = await create_memory(
        session,
        user_id=user_id,
        character_id=character_id,
        content=candidate.canonical_text,
        memory_type=candidate.memory_type,
        importance=candidate.salience,
        confidence=candidate.confidence,
        emotional_weight=candidate.emotional_weight,
        source_message_id=source_message_id,
        extraction_metadata={"version": COGNITION_VERSION, "grounded": True},
        memory_source="grounded_cognition",
        merge_similar=existing is None,
        scope=scope,
        claim_key=claim_key,
        retrieval_facets=candidate.retrieval_facets,
    )
    if existing is not None and existing.id != memory.id:
        group = f"claim:{hashlib.sha256(claim_key.encode()).hexdigest()[:32]}"
        existing.contradiction_group = group
        memory.contradiction_group = group
        existing.metadata_json = {
            **(existing.metadata_json or {}),
            "contradiction_status": "conflicts",
            "contradicts_memory_ids": [str(memory.id)],
        }
        memory.metadata_json = {
            **(memory.metadata_json or {}),
            "contradiction_status": "conflicts",
            "contradicts_memory_ids": [str(existing.id)],
        }
    return memory, "remembered"


async def _apply_episode(
    session: AsyncSession,
    *,
    report: CognitionReport,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user_message: Message,
    assistant_message: Message,
    scope: str,
) -> uuid.UUID | None:
    episode = report.episode
    if not episode.worthy or episode.salience < 0.62 or not episode.title or not episode.summary:
        return None
    result = await session.execute(
        select(EpisodicJournal).where(
            EpisodicJournal.user_id == user_id,
            EpisodicJournal.character_id == character_id,
            EpisodicJournal.metadata_json["primary_source_message_id"].as_string()
            == str(user_message.id),
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.title = episode.title
        existing.summary = episode.summary
        existing.emotional_tags_json = _bounded_tags(episode.emotional_tags)
        existing.importance = max(existing.importance, episode.salience)
        existing.scope = scope
        existing.updated_at = utc_now()
        return existing.id
    source_ids = [
        value
        for value in (_optional_uuid(item) for item in episode.source_message_ids)
        if value in {user_message.id, assistant_message.id}
    ]
    if user_message.id not in source_ids:
        source_ids.insert(0, user_message.id)
    journal = await create_journal(
        session,
        user_id,
        character_id,
        conversation_id=conversation_id,
        scope=scope,
        title=episode.title,
        summary=episode.summary,
        journal_type="grounded_episode",
        emotional_tags_json=_bounded_tags(episode.emotional_tags),
        importance=episode.salience,
        metadata_json={
            "source": COGNITION_VERSION,
            "primary_source_message_id": str(user_message.id),
            "grounded": True,
        },
        source_message_ids=source_ids,
    )
    return journal.id


def _ground_report(
    report: CognitionReport,
    *,
    user_message: Message,
    assistant_message: Message,
    selected_memories: list[MemoryItem],
) -> CognitionReport:
    candidates = [
        candidate
        for candidate in report.memory_candidates
        if _candidate_is_grounded(candidate, user_message.content)
    ][:3]
    known_message_ids = {str(user_message.id), str(assistant_message.id)}
    episode = report.episode
    episode_sources = (user_message.content, assistant_message.content)
    evidence_quotes = [
        quote
        for quote in episode.evidence_quotes
        if any(_normalized_text(quote) in _normalized_text(source) for source in episode_sources)
    ][:3]
    episode_claim = f"{episode.title or ''} {episode.summary or ''}"
    episode_grounded = _claim_is_grounded(
        episode_claim,
        " ".join(evidence_quotes),
    )
    grounded_episode = CognitionEpisode(
        worthy=episode.worthy and bool(evidence_quotes) and episode_grounded,
        title=episode.title,
        summary=episode.summary,
        emotional_tags=_bounded_tags(episode.emotional_tags),
        evidence_quotes=evidence_quotes,
        source_message_ids=[
            value for value in episode.source_message_ids if value in known_message_ids
        ],
        salience=episode.salience,
    )
    known_memory_ids = {str(memory.id) for memory in selected_memories}
    return CognitionReport(
        memory_candidates=candidates,
        episode=grounded_episode,
        relationship=CognitionRelationship(
            signals=[
                signal for signal in report.relationship.signals if signal in RELATIONSHIP_SIGNALS
            ],
            confidence=report.relationship.confidence,
        ),
        referenced_memory_ids=[
            value for value in report.referenced_memory_ids if value in known_memory_ids
        ],
    )


def _candidate_is_grounded(candidate: CognitionMemoryCandidate, source: str) -> bool:
    if candidate.memory_type not in MEMORY_TYPES or candidate.stability not in {
        "durable",
        "evolving",
        "transient",
    }:
        return False
    evidence = _normalized_text(candidate.evidence_quote)
    normalized_source = _normalized_text(source)
    if not evidence or evidence not in normalized_source:
        return False
    if any(marker in evidence for marker in UNSAFE_DURABLE_MARKERS):
        return False
    return _claim_is_grounded(
        candidate.canonical_text,
        candidate.evidence_quote,
    )


def _claim_is_grounded(claim: str, evidence: str) -> bool:
    if not _named_numeric_anchors_are_grounded(claim, evidence):
        return False
    claim_tokens = _grounding_tokens(claim)
    if not claim_tokens:
        return False

    return any(
        _claim_tokens_are_supported(claim_tokens, _grounding_tokens(clause))
        for clause in _grounding_clauses(evidence)
    )


def _claim_tokens_are_supported(
    claim_tokens: set[str],
    evidence_tokens: set[str],
) -> bool:
    if not evidence_tokens:
        return False

    claim_positive = bool(claim_tokens & PREFERENCE_POSITIVE_TERMS)
    claim_negative = bool(claim_tokens & PREFERENCE_NEGATIVE_TERMS)
    evidence_has_negative_posture = bool(
        evidence_tokens & (PREFERENCE_NEGATIVE_TERMS | NEGATION_TERMS)
    )
    if claim_positive and evidence_has_negative_posture:
        return False
    if claim_negative and not evidence_has_negative_posture:
        return False
    if claim_tokens & NEGATION_TERMS and not evidence_tokens & NEGATION_TERMS:
        return False

    supported = {
        token
        for token in claim_tokens
        if token in evidence_tokens or _has_grounded_paraphrase(token, evidence_tokens)
    }
    required = 1 if len(claim_tokens) == 1 else max(2, round(len(claim_tokens) * 0.66))
    return len(supported) >= required


def _grounding_clauses(value: str) -> list[str]:
    clauses = re.split(
        r"(?:[|;.!?]+|\bbut\b|\bhowever\b)",
        _normalized_text(value),
    )
    return [clause.strip() for clause in clauses if clause.strip()]


def _named_numeric_anchors_are_grounded(claim: str, evidence: str) -> bool:
    anchors = [
        anchor
        for anchor in re.findall(
            r"\b(?:[A-Z][\w'-]{2,}|\d[\d:/.-]*)\b",
            unicodedata.normalize("NFKC", claim),
        )
        if anchor.casefold() not in GROUNDING_STOP_WORDS
    ]
    evidence_folded = unicodedata.normalize("NFKC", evidence).casefold()
    return all(anchor.casefold() in evidence_folded for anchor in anchors)


def _grounding_tokens(value: str) -> set[str]:
    return {
        token
        for raw_token in re.findall(r"[a-z0-9']+", _normalized_text(value))
        if (token := _grounding_stem(raw_token)) and token not in GROUNDING_STOP_WORDS
    }


def _grounding_stem(value: str) -> str:
    token = value.strip("'")
    if token.endswith("'s"):
        token = token[:-2]
    if len(token) > 5 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def _has_grounded_paraphrase(token: str, evidence_tokens: set[str]) -> bool:
    return any(
        token in group and bool(group & evidence_tokens) for group in GROUNDING_PARAPHRASE_GROUPS
    )


def _cognition_prompt(
    *,
    user_message: Message,
    assistant_message: Message,
    recent_messages: list[Message],
    selected_memories: list[MemoryItem],
) -> str:
    recent_lines = [
        f"{message.id} {message.role}: {_compact(message.content, 600)}"
        for message in recent_messages[-6:]
        if message.role in {"user", "assistant"}
    ]
    memory_lines = [
        f"{memory.id} {memory.memory_type}: {_compact(memory.content, 320)}"
        for memory in selected_memories[:7]
    ]
    prompt = "\n".join(
        (
            "Analyze one completed fictional-companion turn for durable continuity.",
            "Return only the required schema. Do not include reasoning.",
            "Memory candidates may come only from the CURRENT USER message.",
            "Every evidence_quote must be an exact contiguous quote from that message.",
            "Do not infer unstated names, dates, preferences, relationships, or events.",
            "Prefer no memory over a speculative memory. Transient feelings are not durable facts.",
            (
                "An episode is worthy only when the exchange has specific lasting emotional "
                "or shared-history value."
            ),
            (
                "Every episode evidence quote must be exact text from CURRENT USER "
                "or CURRENT ASSISTANT."
            ),
            "Referenced memory IDs must be selected memories visibly used in the assistant reply.",
            "Relationship signals describe evidence only; they never set scores.",
            "RECENT ELIGIBLE CONTEXT:",
            *(recent_lines or ["none"]),
            "SELECTED MEMORIES:",
            *(memory_lines or ["none"]),
            "CURRENT USER:",
            f"{user_message.id}: {_compact(user_message.content, 2600)}",
            "CURRENT ASSISTANT:",
            f"{assistant_message.id}: {_compact(assistant_message.content, 2200)}",
        )
    )
    return prompt[:MAX_COGNITION_CONTEXT_CHARS]


def _claim_key(value: str | None, memory_type: str, content: str) -> str:
    candidate = _normalized_text(value or "")
    if not candidate:
        tokens = sorted(_meaningful_tokens(content))[:8]
        candidate = ":".join((memory_type, *tokens))
    cleaned = re.sub(r"[^a-z0-9:_-]+", "-", candidate).strip("-:")
    return cleaned[:160] or f"{memory_type}:{hashlib.sha256(content.encode()).hexdigest()[:24]}"


def _bounded_tags(values: list[str]) -> list[str]:
    tags: list[str] = []
    for value in values:
        tag = re.sub(r"[^a-z0-9_-]+", "_", value.casefold()).strip("_")[:40]
        if tag and tag not in tags:
            tags.append(tag)
        if len(tags) >= 6:
            break
    return tags


def _meaningful_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9']+", value.casefold())
        if len(token) > 2 and token not in {"and", "but", "for", "that", "the", "this", "with"}
    }


def _normalized_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())


def _compact(value: str, limit: int) -> str:
    compact = " ".join(str(value or "").strip().split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _optional_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _safe_failure_code(value: str) -> str:
    return (
        value
        if value
        in {
            "authentication",
            "model_unavailable",
            "provider_unavailable",
            "quota_exhausted",
            "rate_limited",
            "timeout",
        }
        else "provider_unavailable"
    )
