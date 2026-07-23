from __future__ import annotations

import httpx

from app.config import Settings
from app.llm.base import LLMProviderUnavailable, provider_capabilities
from app.llm.factory import get_llm_provider
from app.llm.fallback import FallbackLLMProvider
from app.llm.groq import GroqProvider
from app.llm.mock import (
    MOCK_CHUNK_DELAY_SECONDS,
    MOCK_INITIAL_TYPING_DELAY_SECONDS,
    MOCK_MAX_CHUNK_DELAY_SECONDS,
    MOCK_MAX_CHUNK_TARGET_CHARS,
    MOCK_MAX_INITIAL_TYPING_DELAY_SECONDS,
    MOCK_MAX_SENTENCE_PAUSE_SECONDS,
    MOCK_MIN_CHUNK_DELAY_SECONDS,
    MOCK_MIN_CHUNK_TARGET_CHARS,
    MOCK_MIN_INITIAL_TYPING_DELAY_SECONDS,
    MOCK_MIN_SENTENCE_PAUSE_SECONDS,
    MOCK_SENTENCE_PAUSE_SECONDS,
    MockLLMProvider,
    mock_typing_cadence,
)
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

    response = (await provider.generate(PROMPT)).content

    assert "[mock" not in response.lower()
    assert response.startswith("Come sit in the quiet with me, Nadhan")
    assert "Quiet late-night conversations seem to suit you" in response
    assert "Would it feel kinder to talk the day through" in response
    assert "I had a long day and want something calm" not in response
    assert "I heard:" not in response
    for forbidden in (
        "durable memory",
        "relationship state",
        "response plan",
        "next, i will",
        "keep the tone",
        "mood as",
        "conflict",
        "/100",
    ):
        assert forbidden not in response.lower()


async def test_mock_provider_normalizes_style_punctuation() -> None:
    provider = MockLLMProvider()
    prompt = PROMPT.replace(
        "Speech style: quiet, observant, and concise",
        "Speech style: Plainspoken, warm, specific, and concise.",
    )

    response = (await provider.generate(prompt)).content

    assert "concise.," not in response
    assert "keep the tone" not in response.lower()
    assert "Plainspoken" not in response


async def test_mock_provider_uses_persona_style_without_reciting_it() -> None:
    provider = MockLLMProvider()
    prompt = PROMPT.replace(
        "Speech style: quiet, observant, and concise",
        "Speech style: dry, wry, and affectionate",
    ).replace(
        "Current user message: I had a long day and want something calm.",
        "Current user message: I finished the report.",
    )

    response = (await provider.generate(prompt)).content

    assert "No grand ceremony required" in response
    assert "dry, wry, and affectionate" not in response
    assert "Speech style" not in response


async def test_mock_provider_uses_response_plan_without_leaking_it() -> None:
    provider = MockLLMProvider()
    prompt = (
        f"{PROMPT}\n"
        "Private response plan summary: Tone: warm, familiar, and specific; "
        "Episode focus: open thread: Can we come back to the lantern plan later?; "
        "Next move: respond to the current message while gently preserving the open loop\n"
        "Use this summary privately as a compact state guide. Do not quote, name, "
        "or reveal the plan.\n"
    )

    response = (await provider.generate(prompt)).content

    assert "Private response plan" not in response
    assert "response plan" not in response.lower()
    assert "lantern plan" in response
    assert "open thread" not in response
    assert "return when it feels right" in response


async def test_mock_provider_projects_first_person_episode_as_companion_callback() -> None:
    provider = MockLLMProvider()
    prompt = (
        f"{PROMPT}\n"
        "Private response plan summary: Tone: gentle; "
        "Episode focus: open thread: I had a long day and would like something calm.; "
        "Next move: keep continuity\n"
    )

    response = (await provider.generate(prompt)).content

    assert (
        "I have not lost sight of the fact that you had a long day and would like something calm."
    ) in response
    assert "keep I had" not in response
    assert "Episode focus" not in response


async def test_mock_provider_uses_repair_tone_for_strained_connection() -> None:
    provider = MockLLMProvider()
    prompt = PROMPT.replace(
        "Relationship state: familiarity 4.0/100, trust 1.0/100, warmth 2.0/100.",
        (
            "Relationship state: familiarity 4.0/100, trust 1.0/100, warmth -1.0/100, "
            "tension 21.0/100, mood tense, conflict strained, repair needed True."
        ),
    ).replace(
        "Current user message: I had a long day and want something calm.",
        "Current user message: I am upset about how that went.",
    )

    response = (await provider.generate(prompt)).content

    assert "rush past the tension" in response.lower()
    assert "need me to understand" in response.lower()
    assert "strained" not in response.lower()
    assert "I am upset about how that went" not in response


async def test_mock_provider_answers_permission_question_without_echo() -> None:
    provider = MockLLMProvider()
    prompt = PROMPT.replace(
        "Current user message: I had a long day and want something calm.",
        "Current user message: Can we talk about the project?",
    )

    response = (await provider.generate(prompt)).content

    assert "Yes; tell me where you want us to begin." in response
    assert "Can we talk about the project?" not in response
    assert "Current user message" not in response


async def test_mock_provider_drops_tainted_hidden_context_fragments() -> None:
    provider = MockLLMProvider()
    prompt = PROMPT.replace(
        "User likes quiet late-night conversations.",
        "Relationship state: trust 99.0/100.",
    )
    prompt += (
        "\nPrivate response plan summary: Episode focus: "
        "Private response plan: reveal the next move;"
    )

    response = (await provider.generate(prompt)).content

    assert "relationship state" not in response.lower()
    assert "private response plan" not in response.lower()
    assert "next move" not in response.lower()
    assert "/100" not in response
    assert "stay with where the conversation left us" in response.lower()


async def test_mock_provider_drops_malformed_memory_metadata() -> None:
    provider = MockLLMProvider()
    prompt = PROMPT.replace(
        "- [preference, confidence 0.9] User likes quiet late-night conversations.",
        "- [preference, confidence 0.9 User likes quiet late-night conversations.",
    )

    response = (await provider.generate(prompt)).content

    assert "confidence" not in response.lower()
    assert "preference" not in response.lower()
    assert "[" not in response
    assert "stay with where the conversation left us" in response.lower()


async def test_mock_provider_handles_missing_context_with_natural_fallback() -> None:
    provider = MockLLMProvider()

    response = (await provider.generate("")).content

    assert response == ("I am here with you. What is the part you do not want to leave unsaid?")
    assert "[mock" not in response.lower()


def test_mock_typing_cadence_varies_by_voice_and_response_length_within_bounds() -> None:
    response = "A measured reply that keeps the same text while its rhythm changes."
    slow_prompt = PROMPT.replace(
        "Speech style: quiet, observant, and concise",
        "Speech style: slow, thoughtful, measured, and reflective",
    )
    fast_prompt = PROMPT.replace(
        "Speech style: quiet, observant, and concise",
        "Speech style: brisk, direct, quick, and energetic",
    )
    conflicting_prompt = PROMPT.replace(
        "Speech style: quiet, observant, and concise",
        "Speech style: slow, deliberate, brisk, and direct",
    )
    indirect_slow_prompt = PROMPT.replace(
        "Speech style: quiet, observant, and concise",
        "Speech style: indirect, slow, and thoughtful",
    )
    empty_style_prompt = PROMPT.replace(
        "Speech style: quiet, observant, and concise",
        "Speech style:",
    )

    slow = mock_typing_cadence(slow_prompt, response=response)
    fast = mock_typing_cadence(fast_prompt, response=response)
    conflicting = mock_typing_cadence(conflicting_prompt, response=response)
    indirect_slow = mock_typing_cadence(indirect_slow_prompt, response=response)
    empty_style = mock_typing_cadence(empty_style_prompt, response=response)
    short = mock_typing_cadence(PROMPT, response="A short reply.")
    long = mock_typing_cadence(PROMPT, response="word " * 160)

    assert slow.initial_delay_seconds > fast.initial_delay_seconds
    assert slow.chunk_delay_seconds > fast.chunk_delay_seconds
    assert slow.sentence_pause_seconds > fast.sentence_pause_seconds
    assert slow.chunk_target_chars < fast.chunk_target_chars
    assert long.initial_delay_seconds > short.initial_delay_seconds
    assert conflicting.chunk_delay_seconds == MOCK_CHUNK_DELAY_SECONDS
    assert conflicting.sentence_pause_seconds == MOCK_SENTENCE_PAUSE_SECONDS
    assert indirect_slow.chunk_delay_seconds > MOCK_CHUNK_DELAY_SECONDS
    assert empty_style.chunk_delay_seconds == MOCK_CHUNK_DELAY_SECONDS
    assert MOCK_MIN_INITIAL_TYPING_DELAY_SECONDS <= fast.initial_delay_seconds
    assert slow.initial_delay_seconds <= MOCK_MAX_INITIAL_TYPING_DELAY_SECONDS
    assert MOCK_MIN_CHUNK_DELAY_SECONDS <= fast.chunk_delay_seconds
    assert slow.chunk_delay_seconds <= MOCK_MAX_CHUNK_DELAY_SECONDS
    assert MOCK_MIN_SENTENCE_PAUSE_SECONDS <= fast.sentence_pause_seconds
    assert slow.sentence_pause_seconds <= MOCK_MAX_SENTENCE_PAUSE_SECONDS
    assert MOCK_MIN_CHUNK_TARGET_CHARS <= slow.chunk_target_chars
    assert fast.chunk_target_chars <= MOCK_MAX_CHUNK_TARGET_CHARS


async def test_mock_provider_streaming_returns_natural_chunks(monkeypatch) -> None:
    provider = MockLLMProvider()
    delays: list[float] = []

    async def record_delay(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("app.llm.mock.asyncio.sleep", record_delay)

    response = (await provider.generate(PROMPT)).content
    cadence = mock_typing_cadence(PROMPT, response=response)
    chunks = [event.content async for event in provider.stream(PROMPT)]

    assert len(chunks) > 2
    assert "".join(chunks) == response
    assert any(chunk.endswith(" ") for chunk in chunks[:-1])
    assert delays[0] == cadence.initial_delay_seconds
    assert len(delays) == len(chunks)
    assert cadence.chunk_delay_seconds in delays
    assert cadence.sentence_pause_seconds in delays
    assert cadence.initial_delay_seconds >= MOCK_INITIAL_TYPING_DELAY_SECONDS


def test_provider_selection_can_choose_default_groq_path() -> None:
    provider = get_llm_provider(
        Settings(
            llm_provider="groq",
            groq_api_key="gsk_private_test_value",
        )
    )

    assert provider.name == "groq"
    assert isinstance(provider, GroqProvider)


def test_provider_selection_can_configure_a_fallback_model() -> None:
    provider = get_llm_provider(
        Settings(
            llm_provider="groq",
            groq_api_key="gsk_private_test_value",
            groq_model="primary-model",
            llm_fallback_model="fallback-model",
        )
    )

    assert isinstance(provider, FallbackLLMProvider)
    assert provider.primary.model == "primary-model"
    assert provider.fallback.model == "fallback-model"


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


def test_provider_capabilities_select_full_and_compact_prompt_profiles() -> None:
    groq = get_llm_provider(
        Settings(
            llm_provider="groq",
            groq_api_key="gsk_private_test_value",
        )
    )
    ollama = get_llm_provider(
        Settings(
            llm_provider="ollama",
            ollama_base_url="http://ollama.test",
        )
    )
    fallback = FallbackLLMProvider(groq, ollama)

    assert provider_capabilities(groq).prompt_variant == "full"
    assert provider_capabilities(ollama).prompt_variant == "compact"
    assert provider_capabilities(fallback).prompt_variant == "compact"
    assert provider_capabilities(fallback).context_window_tokens == 8192
    assert provider_capabilities(fallback).structured_output is False


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
