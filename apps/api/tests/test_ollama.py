from __future__ import annotations

import httpx

from app.llm.ollama import OllamaProvider


async def test_ollama_generate_uses_mocked_http() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate"
        return httpx.Response(200, json={"response": "mocked ollama"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(
        base_url="http://ollama.test",
        model="llama3.1:8b",
        timeout_seconds=5,
        client=client,
    )

    try:
        assert await provider.generate("hello") == "mocked ollama"
    finally:
        await client.aclose()


async def test_ollama_stream_uses_mocked_http() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        lines = b'{"response":"hel","done":false}\n{"response":"lo","done":true}\n'
        return httpx.Response(200, content=lines)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(
        base_url="http://ollama.test",
        model="llama3.1:8b",
        timeout_seconds=5,
        client=client,
    )

    try:
        chunks = [chunk async for chunk in provider.stream("hello")]
        assert chunks == ["hel", "lo"]
    finally:
        await client.aclose()
