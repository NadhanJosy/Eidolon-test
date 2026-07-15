from __future__ import annotations

import os

import pytest
from helpers import auth_headers
from httpx import AsyncClient
from pytest import MonkeyPatch

from app.api import chat as chat_api
from app.llm.groq import GroqProvider


@pytest.mark.live
async def test_live_groq_stream_smoke(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    if os.environ.get("RUN_GROQ_LIVE_TEST") != "1":
        pytest.skip("Set RUN_GROQ_LIVE_TEST=1 to opt in to the live Groq smoke test.")
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        pytest.skip("GROQ_API_KEY is not configured.")

    provider = GroqProvider(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        model=os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0.2,
        max_output_tokens=32,
        timeout_seconds=30,
        max_retries=1,
        retry_base_seconds=0.5,
    )
    monkeypatch.setattr(chat_api, "get_llm_provider", lambda: provider)

    headers = await auth_headers(client)
    character = (await client.get("/characters", headers=headers)).json()[0]
    memory = await client.post(
        f"/characters/{character['id']}/memories",
        json={
            "memory_type": "preference",
            "content": "The user prefers blue comet tea.",
            "importance": 0.9,
            "confidence": 0.95,
            "pinned": True,
        },
        headers=headers,
    )
    assert memory.status_code == 201
    conversation = await client.post(
        "/conversations",
        json={"character_id": character["id"]},
        headers=headers,
    )
    assert conversation.status_code == 201
    conversation_id = conversation.json()["id"]
    content = "Which tea do I prefer? Reply with only its name."

    async with client.stream(
        "POST",
        "/chat/stream",
        json={"conversation_id": conversation_id, "content": content},
        headers=headers,
    ) as response:
        assert response.status_code == 200
        stream_body = (await response.aread()).decode()

    assert "event: message_start" in stream_body
    assert "event: token" in stream_body
    assert "event: message_done" in stream_body
    assert "blue comet" in stream_body.lower()
    history = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    assert history.status_code == 200
    messages = history.json()
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == content
    assert messages[1]["metadata_json"]["provider"] == "groq"
    assert messages[1]["metadata_json"]["model"] == provider.model
    assert "blue comet" in messages[1]["content"].lower()
    generation = messages[1]["metadata_json"]["generation"]
    assert 0 <= generation["first_token_ms"] <= generation["latency_ms"]
    assert generation["input_tokens"] > 0
    assert generation["output_tokens"] > 0
    assert generation["total_tokens"] == (generation["input_tokens"] + generation["output_tokens"])
    assert generation["finish_reason"] == "stop"
