from __future__ import annotations

import json

import httpx
import pytest

from app.llm.base import LLMGeneration, LLMProviderUnavailable, LLMStreamEvent, TokenUsage
from app.llm.fallback import FallbackLLMProvider
from app.llm.groq import GroqProvider

MODEL = "llama-3.3-70b-versatile"
TEST_KEY = "gsk_test_value_that_is_never_logged_or_persisted"


def provider(
    client: httpx.AsyncClient,
    *,
    max_retries: int = 0,
    timeout_seconds: float = 5,
) -> GroqProvider:
    return GroqProvider(
        api_key=TEST_KEY,
        base_url="https://api.groq.test/openai/v1",
        model=MODEL,
        temperature=0.7,
        max_output_tokens=256,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        retry_base_seconds=0.05,
        client=client,
    )


async def test_groq_non_streaming_uses_server_side_chat_completions_contract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/openai/v1/chat/completions"
        assert request.headers["Authorization"] == f"Bearer {TEST_KEY}"
        payload = json.loads(request.content)
        assert payload == {
            "model": MODEL,
            "messages": [{"role": "system", "content": "private assembled prompt"}],
            "temperature": 0.7,
            "max_completion_tokens": 256,
            "stream": False,
        }
        return httpx.Response(
            200,
            json={
                "model": MODEL,
                "choices": [{"message": {"content": "A grounded reply."}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 42,
                    "completion_tokens": 4,
                    "total_tokens": 46,
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        generation = await provider(client).generate("private assembled prompt")
    finally:
        await client.aclose()

    assert generation.content == "A grounded reply."
    assert generation.provider == "groq"
    assert generation.model == MODEL
    assert generation.finish_reason == "stop"
    assert generation.usage == TokenUsage(42, 4, 46)


async def test_groq_stream_parser_emits_text_finish_reason_and_usage() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        body = "".join(
            (
                _stream_data({"model": MODEL, "choices": [{"delta": {"role": "assistant"}}]}),
                _stream_data({"model": MODEL, "choices": [{"delta": {"content": "Hello"}}]}),
                _stream_data({"model": MODEL, "choices": [{"delta": {"content": " there"}}]}),
                _stream_data({"model": MODEL, "choices": [{"delta": {}, "finish_reason": "stop"}]}),
                _stream_data(
                    {
                        "choices": [],
                        "usage": {
                            "prompt_tokens": 11,
                            "completion_tokens": 2,
                            "total_tokens": 13,
                        },
                    }
                ),
                "data: [DONE]\n\n",
            )
        )
        return httpx.Response(200, text=body)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        events = [event async for event in provider(client).stream("prompt")]
    finally:
        await client.aclose()

    assert "".join(event.content for event in events) == "Hello there"
    assert [event.finish_reason for event in events if event.finish_reason] == ["stop"]
    assert [event.usage for event in events if event.usage != TokenUsage()] == [
        TokenUsage(11, 2, 13)
    ]


async def test_groq_retries_429_before_first_token_and_honors_retry_after() -> None:
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429,
                headers={"retry-after": "0"},
                json={"error": {"message": "rate limit reached", "type": "rate_limit"}},
            )
        return httpx.Response(
            200,
            text=(
                'data: {"model":"llama-3.3-70b-versatile","choices":'
                '[{"delta":{"content":"Recovered"},"finish_reason":"stop"}]}\n\n'
                "data: [DONE]\n\n"
            ),
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        events = [event async for event in provider(client, max_retries=1).stream("prompt")]
    finally:
        await client.aclose()

    assert attempts == 2
    assert "".join(event.content for event in events) == "Recovered"


@pytest.mark.parametrize("status", [500, 502, 503])
async def test_groq_retries_transient_server_failures(status: int) -> None:
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(status, json={"error": {"message": "temporary"}})
        return httpx.Response(
            200,
            json={
                "model": MODEL,
                "choices": [{"message": {"content": "Recovered."}, "finish_reason": "stop"}],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        generation = await provider(client, max_retries=1).generate("prompt")
    finally:
        await client.aclose()
    assert attempts == 2
    assert generation.content == "Recovered."


async def test_groq_timeout_becomes_private_retryable_failure() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private transport detail", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(LLMProviderUnavailable) as caught:
            await provider(client).generate("prompt")
    finally:
        await client.aclose()

    assert caught.value.failure_type == "timeout"
    assert caught.value.retryable is True
    assert "private transport detail" not in caught.value.safe_detail


async def test_groq_malformed_stream_is_not_persistable_text() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="data: {not-json}\n\ndata: [DONE]\n\n")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(LLMProviderUnavailable) as caught:
            _ = [event async for event in provider(client).stream("prompt")]
    finally:
        await client.aclose()

    assert caught.value.failure_type == "malformed_response"
    assert caught.value.retryable is False


async def test_groq_quota_exhaustion_has_distinct_safe_failure() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": {"message": "Daily quota exhausted", "type": "quota"}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(LLMProviderUnavailable) as caught:
            await provider(client).generate("prompt")
    finally:
        await client.aclose()

    assert caught.value.failure_type == "quota_exhausted"
    assert caught.value.retryable is False


async def test_groq_context_overflow_has_distinct_safe_failure() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": {"message": "maximum context length exceeded"}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(LLMProviderUnavailable) as caught:
            await provider(client).generate("prompt")
    finally:
        await client.aclose()

    assert caught.value.failure_type == "context_overflow"
    assert caught.value.retryable is False
    assert "maximum context length" not in caught.value.safe_detail


async def test_groq_health_reports_reachable_only_when_model_is_listed() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/openai/v1/models"
        return httpx.Response(200, json={"data": [{"id": MODEL}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        health = await provider(client).health()
    finally:
        await client.aclose()

    assert health == {
        "status": "ok",
        "provider": "groq",
        "model": MODEL,
        "configuration": "configured",
        "readiness": "reachable",
    }


async def test_groq_health_reports_configured_but_degraded_when_model_is_missing() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "another-model"}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        health = await provider(client).health()
    finally:
        await client.aclose()

    assert health == {
        "status": "degraded",
        "provider": "groq",
        "model": MODEL,
        "configuration": "configured",
        "readiness": "degraded",
    }


async def test_groq_empty_stream_is_distinct_from_provider_refusal() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                _stream_data({"model": MODEL, "choices": [{"delta": {}, "finish_reason": "stop"}]})
                + "data: [DONE]\n\n"
            ),
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(LLMProviderUnavailable) as caught:
            _ = [event async for event in provider(client).stream("prompt")]
    finally:
        await client.aclose()

    assert caught.value.failure_type == "empty_response"


async def test_groq_stream_refusal_is_classified_without_fake_text() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                _stream_data(
                    {
                        "model": MODEL,
                        "choices": [
                            {"delta": {"refusal": "blocked"}, "finish_reason": "content_filter"}
                        ],
                    }
                )
                + "data: [DONE]\n\n"
            ),
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(LLMProviderUnavailable) as caught:
            _ = [event async for event in provider(client).stream("prompt")]
    finally:
        await client.aclose()

    assert caught.value.failure_type == "refusal"
    assert caught.value.retryable is False


def _stream_data(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


class _StubProvider:
    def __init__(
        self,
        name: str,
        model: str,
        *,
        events: list[LLMStreamEvent] | None = None,
        failure: LLMProviderUnavailable | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.events = events or []
        self.failure = failure
        self.calls = 0

    async def generate(self, _: str) -> LLMGeneration:
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        return LLMGeneration("fallback", self.name, self.model, "stop")

    async def stream(self, _: str):
        self.calls += 1
        for event in self.events:
            yield event
        if self.failure is not None:
            raise self.failure

    async def health(self) -> dict[str, str]:
        return {"status": "ok", "provider": self.name}


async def test_configured_fallback_runs_only_before_primary_text_is_emitted() -> None:
    primary = _StubProvider(
        "groq",
        "primary",
        failure=LLMProviderUnavailable(failure_type="provider_unavailable"),
    )
    fallback = _StubProvider(
        "ollama",
        "fallback",
        events=[LLMStreamEvent("local reply", "ollama", "fallback", "stop")],
    )
    provider_with_fallback = FallbackLLMProvider(primary, fallback)

    events = [event async for event in provider_with_fallback.stream("prompt")]

    assert "".join(event.content for event in events) == "local reply"
    assert primary.calls == 1
    assert fallback.calls == 1


async def test_configured_fallback_never_replaces_partial_live_output() -> None:
    primary = _StubProvider(
        "groq",
        "primary",
        events=[LLMStreamEvent("partial", "groq", "primary")],
        failure=LLMProviderUnavailable(failure_type="provider_unavailable"),
    )
    fallback = _StubProvider(
        "ollama",
        "fallback",
        events=[LLMStreamEvent("must not appear", "ollama", "fallback")],
    )
    provider_with_fallback = FallbackLLMProvider(primary, fallback)

    collected: list[str] = []
    with pytest.raises(LLMProviderUnavailable):
        async for event in provider_with_fallback.stream("prompt"):
            collected.append(event.content)

    assert collected == ["partial"]
    assert fallback.calls == 0
