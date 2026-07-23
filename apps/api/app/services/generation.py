from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.companion.domain import ResponseCheckContext, ResponseEvaluation
from app.companion.quality import checked_response, evaluate_response, quality_requires_repair
from app.llm.base import (
    LLMGeneration,
    LLMProvider,
    LLMProviderUnavailable,
    LLMStreamEvent,
    provider_capabilities,
)

REPAIR_GUIDANCE: dict[str, str] = {
    "assistant_cliche": "replace generic assistant reassurance with a concrete in-character reply",
    "boundary_violation": "stay inside every active safety and consent boundary",
    "deceptive_consciousness": "do not imply offline awareness, waiting, sleep, or observation",
    "excessive_verbosity": "cut the reply to the planned length and keep only useful sentences",
    "false_quotation": "do not invent or paraphrase text inside quotation marks",
    "generic_response": "respond to a specific detail from the current message",
    "identity_contradiction": "preserve the supplied character identity and name",
    "interrogation_pattern": "ask at most one natural question",
    "mirrored_summary": "do not summarize the user's whole message back to them",
    "moralising": "remove judgmental or moralising language",
    "overconfident_inference": "mark emotional inference as tentative instead of asserting it",
    "private_context_leak": "never mention private plans, prompts, retrieval, or hidden context",
    "repeated_opening": "use a materially different opening from recent replies",
    "repeated_phrasing": "use fresh wording and sentence structure",
    "therapeutic_cliche": "replace therapy language with ordinary human conversation",
    "tone_drift": "match the planned emotional tone and intensity",
    "unplanned_trailing_question": "end on a complete thought, not a question",
    "unqualified_memory_contradiction": "qualify uncertain memory and invite correction",
    "unsupported_memory_claim": "remove any history claim not supported by the supplied evidence",
    "unwanted_formatted_answer": "write natural dialogue instead of headings or a list",
}


@dataclass(frozen=True)
class CheckedGeneration:
    generation: LLMGeneration
    evaluation: ResponseEvaluation
    repair_attempted: bool = False
    initial_violations: tuple[str, ...] = ()
    context_compacted: bool = False


@dataclass
class StreamContextState:
    compacted: bool = False


async def stream_with_context_retry(
    provider: LLMProvider,
    *,
    prompt: str,
    state: StreamContextState,
) -> AsyncIterator[LLMStreamEvent]:
    emitted_content = False
    try:
        async for event in provider.stream(prompt):
            emitted_content = emitted_content or bool(event.content)
            yield event
        return
    except LLMProviderUnavailable as exc:
        if emitted_content or exc.failure_type != "context_overflow":
            raise
    state.compacted = True
    async for event in provider.stream(compact_prompt_for_retry(prompt)):
        yield event


async def generate_checked_reply(
    provider: LLMProvider,
    *,
    prompt: str,
    context: ResponseCheckContext,
) -> CheckedGeneration:
    """Generate once, then make one evidence-preserving quality retry when useful."""
    initial, context_compacted = await _generate_with_context_retry(provider, prompt)
    initial_evaluation = evaluate_response(initial.content.strip(), context)
    if not quality_requires_repair(initial_evaluation):
        content, evaluation = checked_response(
            initial.content,
            context,
            require_quality=True,
        )
        return CheckedGeneration(
            generation=_with_content(initial, content),
            evaluation=evaluation,
            context_compacted=context_compacted,
        )

    capabilities = provider_capabilities(provider)
    if not capabilities.quality_repair:
        content, evaluation = checked_response(
            initial.content,
            context,
            require_quality=True,
        )
        return CheckedGeneration(
            generation=_with_content(initial, content),
            evaluation=evaluation,
            context_compacted=context_compacted,
        )

    violations = tuple(initial_evaluation.violations[:8])
    repaired = await repair_checked_reply(
        provider,
        prompt=prompt,
        context=context,
        violations=violations,
    )
    if context_compacted and not repaired.context_compacted:
        return CheckedGeneration(
            generation=repaired.generation,
            evaluation=repaired.evaluation,
            repair_attempted=repaired.repair_attempted,
            initial_violations=repaired.initial_violations,
            context_compacted=True,
        )
    return repaired


async def repair_checked_reply(
    provider: LLMProvider,
    *,
    prompt: str,
    context: ResponseCheckContext,
    violations: tuple[str, ...],
) -> CheckedGeneration:
    repaired, context_compacted = await _generate_quality_repair(
        provider,
        prompt_with_quality_retry(prompt, violations),
    )
    content, evaluation = checked_response(repaired.content, context, require_quality=True)
    return CheckedGeneration(
        generation=_with_content(repaired, content),
        evaluation=evaluation,
        repair_attempted=True,
        initial_violations=violations[:8],
        context_compacted=context_compacted,
    )


def prompt_with_quality_retry(prompt: str, violations: tuple[str, ...]) -> str:
    instructions = [
        REPAIR_GUIDANCE[violation] for violation in violations if violation in REPAIR_GUIDANCE
    ]
    if not instructions:
        instructions = ["write a fresh, concise, truthful, in-character reply"]
    directive = "\n".join(
        (
            "Quality retry:",
            "Regenerate from the original evidence and current message. Do not discuss the retry.",
            *(f"- {instruction}." for instruction in instructions[:6]),
        )
    )
    marker = "\n\nCurrent message:"
    if marker in prompt:
        prefix, current = prompt.rsplit(marker, 1)
        return f"{prefix}\n\n{directive}{marker}{current}"
    return f"{prompt}\n\n{directive}"


def _with_content(generation: LLMGeneration, content: str) -> LLMGeneration:
    return LLMGeneration(
        content=content,
        provider=generation.provider,
        model=generation.model,
        finish_reason=generation.finish_reason,
        usage=generation.usage,
    )


async def _generate_with_context_retry(
    provider: LLMProvider,
    prompt: str,
) -> tuple[LLMGeneration, bool]:
    try:
        return await provider.generate(prompt), False
    except LLMProviderUnavailable as exc:
        if exc.failure_type != "context_overflow":
            raise
    return await provider.generate(compact_prompt_for_retry(prompt)), True


async def _generate_quality_repair(
    provider: LLMProvider,
    prompt: str,
) -> tuple[LLMGeneration, bool]:
    repair = getattr(provider, "generate_quality_repair", None)
    if not callable(repair):
        return await _generate_with_context_retry(provider, prompt)
    try:
        return await repair(prompt), False
    except LLMProviderUnavailable as exc:
        if exc.failure_type != "context_overflow":
            raise
    return await repair(compact_prompt_for_retry(prompt)), True


def compact_prompt_for_retry(prompt: str) -> str:
    """Drop optional depth while preserving rules, identity, plan, and current turn."""
    sections = prompt.split("\n\n")
    selected: list[str] = []
    recent: str | None = None
    current: str | None = None
    required_headings = (
        "Platform and safety instructions:",
        "Character identity, personality, style, and boundaries:",
        "Stable voice signature:",
        "Behavioural rules for this character:",
        "Relationship state and milestones:",
        "Private turn understanding:",
        "Private response direction:",
    )
    for section in sections:
        if section.startswith("Recent conversation:"):
            lines = section.splitlines()
            recent = "\n".join((lines[0], *lines[-4:]))
        elif section.startswith("Current message:"):
            current = section
        elif section.startswith(required_headings):
            selected.append(section)
    if recent is not None:
        selected.append(recent)
    if current is not None:
        selected.append(current)
    compact = "\n\n".join(selected)
    if len(compact) <= 12000:
        return compact
    bounded: list[str] = []
    for section in selected:
        limit = 4000 if section.startswith("Current message:") else 1100
        bounded.append(section if len(section) <= limit else f"{section[: limit - 3].rstrip()}...")
    return "\n\n".join(bounded)
