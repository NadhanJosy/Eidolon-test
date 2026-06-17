from __future__ import annotations

import httpx

from app.config import Settings
from app.llm.base import LLMProviderUnavailable
from app.llm.factory import get_llm_provider
from app.llm.mock import MockLLMProvider
from app.llm.ollama import OllamaProvider

PROMPT = """
You are a fictional text-only companion inside Eidolon. Stay in character.

Content mode: SFW.

Character name: Mira
Speech style: quiet, observant, and concise

Relationship state: familiarity 4.0/100, trust 1.0/100, warmth 2.0/100.

Relevant memories:
- [preference, confidence 0.9] User likes quiet late-night conversations.

Recent messages:
user: Hello
assistant: I am here.
user: Can we talk for a minute?

Current user display name: Nadhan
Current user message: I had a long day and want something calm.
"""


async def test_mock_provider_uses_prompt_context_without_plain_echo() -> None:
    provider = MockLLMProvider()

    response = await provider.generate(PROMPT)

    assert response.startswith("[mock:Mira]")
    assert "quiet, observant, and concise" in response
    assert "User likes quiet late-night conversations." in response
    assert "Relationship state:" in response
    assert "I had a long day and want something calm" not in response
    assert "I heard:" not in response


async def test_mock_provider_streaming_returns_natural_chunks() -> None:
    provider = MockLLMProvider()

    chunks = [chunk async for chunk in provider.stream(PROMPT)]

    assert len(chunks) > 2
    assert "".join(chunks) == await provider.generate(PROMPT)
    assert any(chunk.endswith(" ") for chunk in chunks[:-1])


def test_provider_selection_defaults_to_mock() -> None:
    provider = get_llm_provider(Settings())

    assert provider.name == "mock"
    assert isinstance(provider, MockLLMProvider)


def test_provider_selection_can_choose_ollama() -> None:
    provider = get_llm_provider(
        Settings(
            llm_provider="ollama",
            ollama_base_url="http://ollama.test",
            ollama_model="llama3.1:8b",
        )
    )

    assert provider.name == "ollama"
    assert isinstance(provider, OllamaProvider)


async def test_ollama_generate_unavailable_raises_controlled_error() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(
        base_url="http://ollama.test",
        model="llama3.1:8b",
        timeout_seconds=5,
        client=client,
    )

    try:
        try:
            await provider.generate("hello")
        except LLMProviderUnavailable as exc:
            assert "Ollama provider is unavailable" in str(exc)
        else:
            raise AssertionError("Expected controlled Ollama provider error.")
    finally:
        await client.aclose()


async def test_ollama_stream_unavailable_raises_controlled_error() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="not ready")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(
        base_url="http://ollama.test",
        model="llama3.1:8b",
        timeout_seconds=5,
        client=client,
    )

    try:
        try:
            _ = [chunk async for chunk in provider.stream("hello")]
        except LLMProviderUnavailable as exc:
            assert "Ollama provider is unavailable" in str(exc)
        else:
            raise AssertionError("Expected controlled Ollama provider error.")
    finally:
        await client.aclose()
