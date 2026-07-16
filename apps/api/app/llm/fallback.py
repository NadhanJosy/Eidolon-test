from __future__ import annotations

from collections.abc import AsyncIterator

from app.llm.base import LLMGeneration, LLMProvider, LLMProviderUnavailable, LLMStreamEvent

FALLBACK_FAILURE_TYPES = {
    "model_unavailable",
    "provider_unavailable",
    "quota_exhausted",
    "rate_limited",
    "timeout",
}


class FallbackLLMProvider:
    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self.primary = primary
        self.fallback = fallback
        self.name = primary.name
        self.model = primary.model

    async def generate(self, prompt: str) -> LLMGeneration:
        try:
            return await self.primary.generate(prompt)
        except LLMProviderUnavailable as exc:
            if exc.failure_type not in FALLBACK_FAILURE_TYPES:
                raise
            return await self.fallback.generate(prompt)

    async def generate_structured(
        self,
        prompt: str,
        *,
        schema_name: str,
        schema: dict[str, object],
        max_output_tokens: int,
    ) -> LLMGeneration:
        try:
            return await self.primary.generate_structured(
                prompt,
                schema_name=schema_name,
                schema=schema,
                max_output_tokens=max_output_tokens,
            )
        except LLMProviderUnavailable as exc:
            if exc.failure_type not in FALLBACK_FAILURE_TYPES:
                raise
            return await self.fallback.generate_structured(
                prompt,
                schema_name=schema_name,
                schema=schema,
                max_output_tokens=max_output_tokens,
            )

    async def stream(self, prompt: str) -> AsyncIterator[LLMStreamEvent]:
        emitted_content = False
        try:
            async for event in self.primary.stream(prompt):
                if event.content:
                    emitted_content = True
                yield event
            return
        except LLMProviderUnavailable as exc:
            if emitted_content or exc.failure_type not in FALLBACK_FAILURE_TYPES:
                raise
        async for event in self.fallback.stream(prompt):
            yield event

    async def health(self) -> dict[str, str]:
        primary_health = await self.primary.health()
        return {
            **primary_health,
            "fallback_provider": self.fallback.name,
            "fallback_model": self.fallback.model,
        }
