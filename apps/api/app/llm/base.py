from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol

SAFE_PROVIDER_UNAVAILABLE_DETAIL = (
    "The text provider is unavailable. Your message was saved; you can retry the reply."
)

ProviderFailureType = Literal[
    "authentication",
    "cancelled",
    "context_overflow",
    "empty_response",
    "malformed_response",
    "model_unavailable",
    "provider_unavailable",
    "quota_exhausted",
    "rate_limited",
    "refusal",
    "timeout",
]

PUBLIC_FAILURE_DETAILS: dict[ProviderFailureType, str] = {
    "authentication": "The text provider is not configured correctly. Your message was saved.",
    "cancelled": "The response was stopped. Your message was saved.",
    "context_overflow": (
        "This conversation has outgrown the provider context window. Your message was saved."
    ),
    "empty_response": (
        "The text provider returned no reply. Your message was saved; you can retry the reply."
    ),
    "malformed_response": (
        "The text provider returned an unreadable reply. Your message was saved; retry the reply."
    ),
    "model_unavailable": "The configured text model is unavailable. Your message was saved.",
    "provider_unavailable": SAFE_PROVIDER_UNAVAILABLE_DETAIL,
    "quota_exhausted": (
        "The text provider quota is exhausted. Your message was saved; retry after it resets."
    ),
    "rate_limited": ("The text provider is busy. Your message was saved; retry the reply shortly."),
    "refusal": (
        "The text provider could not answer that message. Your message was saved so you can "
        "revise it."
    ),
    "timeout": "The text provider timed out. Your message was saved; retry the reply.",
}


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class LLMGeneration:
    content: str
    provider: str
    model: str
    finish_reason: str | None = None
    usage: TokenUsage = TokenUsage()


@dataclass(frozen=True)
class LLMStreamEvent:
    content: str = ""
    provider: str = ""
    model: str = ""
    finish_reason: str | None = None
    usage: TokenUsage = TokenUsage()


class LLMProvider(Protocol):
    name: str
    model: str

    async def generate(self, prompt: str) -> LLMGeneration: ...

    async def generate_structured(
        self,
        prompt: str,
        *,
        schema_name: str,
        schema: dict[str, object],
        max_output_tokens: int,
    ) -> LLMGeneration: ...

    async def stream(self, prompt: str) -> AsyncIterator[LLMStreamEvent]: ...

    async def health(self) -> dict[str, str]: ...


class LLMProviderUnavailable(RuntimeError):
    """A privacy-safe provider failure suitable for chat recovery decisions."""

    def __init__(
        self,
        detail: str = SAFE_PROVIDER_UNAVAILABLE_DETAIL,
        *,
        failure_type: ProviderFailureType = "provider_unavailable",
        retryable: bool = True,
        status_code: int | None = None,
    ) -> None:
        super().__init__(detail)
        self.safe_detail = detail
        self.failure_type = failure_type
        self.retryable = retryable
        self.status_code = status_code


def public_provider_failure_detail(exc: LLMProviderUnavailable) -> str:
    return PUBLIC_FAILURE_DETAILS.get(exc.failure_type, SAFE_PROVIDER_UNAVAILABLE_DETAIL)
