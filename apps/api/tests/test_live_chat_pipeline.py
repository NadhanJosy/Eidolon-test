from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest
from helpers import auth_headers
from httpx import AsyncClient
from pytest import MonkeyPatch
from sqlalchemy import select

from app.api import chat as chat_api
from app.db.session import AsyncSessionLocal
from app.llm.base import (
    LLMGeneration,
    LLMProviderUnavailable,
    LLMStreamEvent,
    TokenUsage,
)
from app.models import Message, ScheduledJob, User
from app.schemas import ChatRequest
from app.services import scheduler


class FailOnceProvider:
    name = "groq"
    model = "llama-3.3-70b-versatile"

    def __init__(self) -> None:
        self.stream_calls = 0

    async def generate(self, _: str) -> LLMGeneration:
        return LLMGeneration("Recovered.", self.name, self.model, "stop")

    async def stream(self, _: str) -> AsyncIterator[LLMStreamEvent]:
        self.stream_calls += 1
        if self.stream_calls == 1:
            raise LLMProviderUnavailable(
                "The text provider timed out. Your message was saved; retry the reply.",
                failure_type="timeout",
            )
        yield LLMStreamEvent("Recovered", self.name, self.model)
        yield LLMStreamEvent(
            ".",
            self.name,
            self.model,
            "stop",
            TokenUsage(input_tokens=33, output_tokens=2, total_tokens=35),
        )

    async def health(self) -> dict[str, str]:
        return {"status": "ok", "provider": self.name}


class BlockingProvider:
    name = "groq"
    model = "llama-3.3-70b-versatile"

    async def generate(self, _: str) -> LLMGeneration:
        raise AssertionError("The cancellation test must use streaming.")

    async def stream(self, _: str) -> AsyncIterator[LLMStreamEvent]:
        yield LLMStreamEvent("partial text", self.name, self.model)
        await asyncio.Event().wait()

    async def health(self) -> dict[str, str]:
        return {"status": "ok", "provider": self.name}


class PromiseProvider:
    name = "groq"
    model = "llama-3.3-70b-versatile"

    async def generate(self, _: str) -> LLMGeneration:
        return LLMGeneration(
            "I promise I will remember the name you shared.",
            self.name,
            self.model,
            "stop",
            TokenUsage(input_tokens=24, output_tokens=9, total_tokens=33),
        )

    async def stream(self, _: str) -> AsyncIterator[LLMStreamEvent]:
        yield LLMStreamEvent(
            "I promise I will remember the name you shared.",
            self.name,
            self.model,
            "stop",
        )

    async def health(self) -> dict[str, str]:
        return {"status": "ok", "provider": self.name}


class UnexpectedFailureProvider(PromiseProvider):
    async def generate(self, _: str) -> LLMGeneration:
        raise RuntimeError("private unexpected provider detail")


async def test_failed_stream_preserves_one_user_message_and_retry_completes_once(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    provider = FailOnceProvider()
    monkeypatch.setattr(chat_api, "get_llm_provider", lambda: provider)
    content = "Please stay with this retry test."

    first = await _stream_request(
        client,
        headers=headers,
        payload={"conversation_id": conversation_id, "content": content},
    )
    assert "event: message_start" in first
    assert '"failure_type": "timeout"' in first
    assert "event: message_done" not in first

    failed_history = (
        await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    ).json()
    assert len(failed_history) == 1
    user_message = failed_history[0]
    assert user_message["role"] == "user"
    assert user_message["metadata_json"]["generation_state"] == "retryable"

    retried = await _stream_request(
        client,
        headers=headers,
        payload={
            "conversation_id": conversation_id,
            "content": content,
            "retry_user_message_id": user_message["id"],
        },
    )
    assert '"retry": true' in retried
    assert "event: token" in retried
    assert "event: message_done" in retried

    completed_history = (
        await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    ).json()
    assert [message["role"] for message in completed_history] == ["user", "assistant"]
    assert completed_history[0]["id"] == user_message["id"]
    assistant = completed_history[1]
    assert assistant["content"] == "Recovered."
    assert assistant["metadata_json"]["reply_to_user_message_id"] == user_message["id"]
    assert assistant["metadata_json"]["generation"] == {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "latency_ms": assistant["metadata_json"]["generation"]["latency_ms"],
        "first_token_ms": assistant["metadata_json"]["generation"]["first_token_ms"],
        "input_tokens": 33,
        "output_tokens": 2,
        "total_tokens": 35,
        "finish_reason": "stop",
    }

    duplicate_retry = await _stream_request(
        client,
        headers=headers,
        payload={
            "conversation_id": conversation_id,
            "content": content,
            "retry_user_message_id": user_message["id"],
        },
    )
    assert "already has a completed reply" in duplicate_retry
    final_history = (
        await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    ).json()
    assert [message["id"] for message in final_history] == [
        user_message["id"],
        assistant["id"],
    ]


async def test_stream_cancellation_saves_no_partial_assistant(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = uuid.UUID(conversation.json()["id"])
    monkeypatch.setattr(chat_api, "get_llm_provider", lambda: BlockingProvider())

    async with AsyncSessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == "user@example.com"))
        ).scalar_one()
        response = await chat_api.chat_stream(
            ChatRequest(
                conversation_id=conversation_id,
                content="Stop after the first partial fragment.",
            ),
            user,
            session,
        )
        iterator = response.body_iterator.__aiter__()
        start_event = await iterator.__anext__()
        token_event = await iterator.__anext__()
        assert "event: message_start" in _event_text(start_event)
        assert "partial text" in _event_text(token_event)

        blocked_read = asyncio.create_task(iterator.__anext__())
        await asyncio.sleep(0)
        blocked_read.cancel()
        with pytest.raises(asyncio.CancelledError):
            await blocked_read

    async with AsyncSessionLocal() as session:
        messages = list(
            (
                await session.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at)
                )
            ).scalars()
        )
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].metadata_json["generation_state"] == "cancelled"
    assert messages[0].metadata_json["generation_failure_type"] == "cancelled"


async def test_post_chat_memory_failure_never_erases_completed_chat(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]

    async def fail_memory(*_: object, **__: object) -> None:
        raise RuntimeError("deterministic memory failure")

    monkeypatch.setattr(scheduler, "_run_memory_extract_job", fail_memory)
    response = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "Please remember that I prefer quiet mornings.",
        },
        headers=headers,
    )
    assert response.status_code == 200

    history = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    assert [message["role"] for message in history.json()] == ["user", "assistant"]
    job_id = response.json()["assistant_message"]["metadata_json"]["post_chat_job_id"]
    async with AsyncSessionLocal() as session:
        job = await session.get(ScheduledJob, uuid.UUID(job_id))
        assert job is not None
        assert job.status == "pending"
        assert job.retry_count == 1
        assert job.last_error == "Transient job failure; retry scheduled."


async def test_post_chat_extracts_user_fact_and_assistant_promise(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    character_id = conversation.json()["character_id"]
    monkeypatch.setattr(chat_api, "get_llm_provider", lambda: PromiseProvider())

    response = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "My name is Rowan and my pronouns are they/them.",
        },
        headers=headers,
    )
    assert response.status_code == 200

    memories = await client.get(f"/characters/{character_id}/memories", headers=headers)
    journals = await client.get(f"/characters/{character_id}/journals", headers=headers)

    assert any(memory["memory_type"] == "user_fact" for memory in memories.json())
    assert any(
        "i promise" in callback.lower()
        for journal in journals.json()
        for callback in journal["callbacks_json"]
    )


async def test_unexpected_nonstream_provider_failure_preserves_retryable_user_turn(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    monkeypatch.setattr(chat_api, "get_llm_provider", lambda: UnexpectedFailureProvider())

    response = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "Keep this accepted turn."},
        headers=headers,
    )

    assert response.status_code == 503
    assert "private unexpected provider detail" not in response.text
    history = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    assert [message["role"] for message in history.json()] == ["user"]
    assert history.json()[0]["metadata_json"]["generation_state"] == "retryable"


async def _stream_request(
    client: AsyncClient,
    *,
    headers: dict[str, str],
    payload: dict[str, object],
) -> str:
    async with client.stream("POST", "/chat/stream", json=payload, headers=headers) as response:
        assert response.status_code == 200
        return (await response.aread()).decode()


def _event_text(value: str | bytes) -> str:
    return value.decode() if isinstance(value, bytes) else value
