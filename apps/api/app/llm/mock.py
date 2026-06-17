from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator


class MockLLMProvider:
    name = "mock"

    async def generate(self, prompt: str) -> str:
        message = _current_message(prompt)
        if message:
            return f"I'm here with you. I heard: {message[:220]}"
        return "I'm here with you. Tell me what is on your mind."

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        response = await self.generate(prompt)
        for word in response.split(" "):
            await asyncio.sleep(0)
            yield f"{word} "

    async def health(self) -> dict[str, str]:
        return {"status": "ok", "provider": self.name}


def _current_message(prompt: str) -> str:
    marker = "Current user message:"
    if marker not in prompt:
        return ""
    return prompt.split(marker, maxsplit=1)[1].strip().splitlines()[0].strip()
