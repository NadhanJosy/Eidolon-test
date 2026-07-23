from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.companion.domain import ResponseCheckContext, ResponsePlan
from app.llm.base import (
    LLMGeneration,
    LLMProviderUnavailable,
    LLMStreamEvent,
    ProviderCapabilities,
)
from app.llm.fallback import FallbackLLMProvider
from app.services.generation import (
    StreamContextState,
    generate_checked_reply,
    stream_with_context_retry,
)


def _context() -> ResponseCheckContext:
    return ResponseCheckContext(
        plan=ResponsePlan(
            strategy="share_the_moment",
            secondary_strategy=None,
            should_ask_question=False,
            desired_length="short",
            rhythm="steady",
            opening="answer the concrete detail",
        ),
        recent_assistant_messages=(),
        recent_transcript=(),
        selected_memory_contents=(),
        uncertain_memory_contents=(),
        current_user_message="The deadline moved to Friday.",
        known_character_name="Mara",
    )


class RepairProvider:
    name = "test"
    model = "repair-model"
    capabilities = ProviderCapabilities(
        context_window_tokens=8192,
        prompt_variant="compact",
        structured_output=False,
        streaming=True,
        quality_repair=True,
    )

    def __init__(self, *, persistent_defect: bool = False) -> None:
        self.prompts: list[str] = []
        self.persistent_defect = persistent_defect

    async def generate(self, prompt: str) -> LLMGeneration:
        self.prompts.append(prompt)
        if len(self.prompts) == 1 or self.persistent_defect:
            content = "It sounds like you are saying that deadlines are difficult."
        else:
            content = "Friday is the pressure point; the smaller scope now matters most."
        return LLMGeneration(content, self.name, self.model, "stop")

    async def stream(self, _: str) -> AsyncIterator[LLMStreamEvent]:
        yield LLMStreamEvent()

    async def health(self) -> dict[str, str]:
        return {"status": "ok"}


class ContextOverflowProvider(RepairProvider):
    def __init__(self) -> None:
        super().__init__()
        self.stream_calls = 0

    async def stream(self, prompt: str) -> AsyncIterator[LLMStreamEvent]:
        self.stream_calls += 1
        self.prompts.append(prompt)
        if self.stream_calls == 1:
            raise LLMProviderUnavailable(
                failure_type="context_overflow",
                retryable=True,
            )
        yield LLMStreamEvent(
            "Friday is the pressure point.",
            self.name,
            self.model,
            "stop",
        )


class GoodFallbackProvider(RepairProvider):
    name = "fallback"
    model = "steady-model"

    async def generate(self, prompt: str) -> LLMGeneration:
        self.prompts.append(prompt)
        return LLMGeneration(
            "Friday is the pressure point; cutting the scope is the clean next move.",
            self.name,
            self.model,
            "stop",
        )


async def test_generation_repairs_once_without_feeding_back_bad_prose() -> None:
    provider = RepairProvider()

    result = await generate_checked_reply(
        provider,
        prompt="Private response direction:\nBe concise.\n\nCurrent message:\nThe deadline moved.",
        context=_context(),
    )

    assert result.repair_attempted is True
    assert "mirrored_summary" in result.initial_violations
    assert result.generation.content.startswith("Friday is the pressure point")
    assert "deadlines are difficult" not in provider.prompts[1]
    assert "Quality retry:" in provider.prompts[1]


async def test_generation_rejects_a_persistent_quality_defect_after_one_retry() -> None:
    provider = RepairProvider(persistent_defect=True)

    with pytest.raises(LLMProviderUnavailable) as failure:
        await generate_checked_reply(
            provider,
            prompt="Current message:\nThe deadline moved.",
            context=_context(),
        )

    assert failure.value.failure_type == "malformed_response"
    assert len(provider.prompts) == 2


async def test_quality_retry_routes_to_fallback_after_weak_primary_prose() -> None:
    primary = RepairProvider(persistent_defect=True)
    fallback = GoodFallbackProvider()
    provider = FallbackLLMProvider(primary, fallback)

    result = await generate_checked_reply(
        provider,
        prompt="Current message:\nThe deadline moved.",
        context=_context(),
    )

    assert result.repair_attempted is True
    assert result.generation.provider == "fallback"
    assert len(primary.prompts) == 1
    assert len(fallback.prompts) == 1
    assert "Quality retry:" in fallback.prompts[0]


async def test_stream_context_overflow_retries_once_with_compact_context() -> None:
    provider = ContextOverflowProvider()
    state = StreamContextState()
    prompt = (
        "Platform and safety instructions:\nStay safe.\n\n"
        "Character identity, personality, style, and boundaries:\nMara.\n\n"
        "Private response direction:\nBe direct.\n\n"
        "Recent conversation:\nuser: old\nassistant: old\nuser: recent\nassistant: recent\n\n"
        "Current message:\nThe deadline moved to Friday."
    )

    events = [
        event
        async for event in stream_with_context_retry(
            provider,
            prompt=prompt,
            state=state,
        )
    ]

    assert state.compacted is True
    assert provider.stream_calls == 2
    assert events[0].content == "Friday is the pressure point."
    assert "Current message:" in provider.prompts[1]
