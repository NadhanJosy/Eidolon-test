from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass


class MockLLMProvider:
    name = "mock"

    async def generate(self, prompt: str) -> str:
        context = _parse_prompt(prompt)
        memory_line = (
            f" I am keeping this in view: {context.memory}."
            if context.memory
            else " I do not have a durable memory to lean on yet."
        )
        history_line = (
            " The thread already has some shape, so I will keep continuity."
            if context.recent_message_count > 1
            else " This still feels like the start of the thread."
        )
        relationship_line = (
            f" {context.relationship}"
            if context.relationship
            else " Relationship state is still new."
        )
        style = context.speech_style or "warm and concise"
        character = context.character_name or "Eidolon"

        return (
            f"[mock:{character}] I will answer in a {style} way."
            f"{memory_line}{history_line}{relationship_line}"
        )

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        response = await self.generate(prompt)
        for chunk in _natural_chunks(response):
            await asyncio.sleep(0)
            yield chunk

    async def health(self) -> dict[str, str]:
        return {"status": "ok", "provider": self.name}


@dataclass(frozen=True)
class MockPromptContext:
    character_name: str = ""
    speech_style: str = ""
    relationship: str = ""
    memory: str = ""
    current_message: str = ""
    recent_message_count: int = 0


def _parse_prompt(prompt: str) -> MockPromptContext:
    return MockPromptContext(
        character_name=_line_value(prompt, "Character name:"),
        speech_style=_line_value(prompt, "Speech style:"),
        relationship=_line_starting_with(prompt, "Relationship state:"),
        memory=_first_memory(prompt),
        current_message=_line_value(prompt, "Current user message:"),
        recent_message_count=_recent_message_count(prompt),
    )


def _line_value(prompt: str, marker: str) -> str:
    line = _line_starting_with(prompt, marker)
    if not line:
        return ""
    return line.removeprefix(marker).strip()


def _line_starting_with(prompt: str, marker: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(marker):
            return line.strip()
    return ""


def _first_memory(prompt: str) -> str:
    in_memories = False
    for line in prompt.splitlines():
        if line.startswith("Relevant memories:"):
            in_memories = True
            continue
        if not in_memories:
            continue
        if not line.strip():
            continue
        if line.startswith("- "):
            return line.split("] ", maxsplit=1)[-1].strip()
        return ""
    return ""


def _recent_message_count(prompt: str) -> int:
    in_recent = False
    count = 0
    for line in prompt.splitlines():
        if line.startswith("Recent messages:"):
            in_recent = True
            continue
        if line.startswith("Current user display name:"):
            break
        if in_recent and (line.startswith("user:") or line.startswith("assistant:")):
            count += 1
    return count


def _natural_chunks(response: str) -> list[str]:
    words = response.split(" ")
    chunks: list[str] = []
    current: list[str] = []
    for index, word in enumerate(words):
        current.append(word)
        joined = " ".join(current)
        if len(joined) >= 28 or word.endswith((".", ":", ";")):
            suffix = " " if index < len(words) - 1 else ""
            chunks.append(f"{joined}{suffix}")
            current = []
    if current:
        chunks.append(" ".join(current))
    return chunks
