from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol


class LLMProvider(Protocol):
    name: str

    async def generate(self, prompt: str) -> str: ...

    async def stream(self, prompt: str) -> AsyncIterator[str]: ...

    async def health(self) -> dict[str, str]: ...


class LLMProviderUnavailable(RuntimeError):
    """Raised when a configured provider cannot produce a response."""
