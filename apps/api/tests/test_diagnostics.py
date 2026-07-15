from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from helpers import auth_headers, register_user
from httpx import AsyncClient
from pytest import MonkeyPatch
from sqlalchemy import func, select

from app.api import chat as chat_api
from app.api import conversations as conversations_api
from app.db.session import AsyncSessionLocal
from app.llm.base import SAFE_PROVIDER_UNAVAILABLE_DETAIL, LLMProviderUnavailable
from app.models import Character, DiagnosticEvent, User
from app.services import diagnostics

SECRET_FAILURE_DETAIL = "transport-secret at http://private-host.invalid/token"


class SecretFailingProvider:
    name = "ollama http://private-host.invalid/transport-secret"
    model = "private-model-label"

    async def generate(self, prompt: str) -> str:
        raise LLMProviderUnavailable(SECRET_FAILURE_DETAIL)

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        raise LLMProviderUnavailable(SECRET_FAILURE_DETAIL)
        yield ""  # pragma: no cover - keeps this an async generator

    async def health(self) -> dict[str, str]:
        return {"status": "degraded", "provider": self.name}


class UnexpectedSecretFailingProvider(SecretFailingProvider):
    async def generate(self, prompt: str) -> str:
        raise RuntimeError(SECRET_FAILURE_DETAIL)


async def test_provider_failures_are_private_safe_and_durable(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await auth_headers(client)
    characters = await client.get("/characters", headers=headers)
    character_id = characters.json()[0]["id"]
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    monkeypatch.setattr(chat_api, "get_llm_provider", lambda: SecretFailingProvider())

    failed_message = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "A normal test message."},
        headers=headers,
    )
    assert failed_message.status_code == 503
    assert failed_message.json() == {"detail": SAFE_PROVIDER_UNAVAILABLE_DETAIL}
    assert SECRET_FAILURE_DETAIL not in failed_message.text

    history = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    assert history.status_code == 200
    assert [message["role"] for message in history.json()] == ["user"]
    assert history.json()[0]["metadata_json"]["generation_state"] == "retryable"

    async with client.stream(
        "POST",
        "/chat/stream",
        json={"conversation_id": conversation_id, "content": "A streamed test message."},
        headers=headers,
    ) as response:
        stream_body = (await response.aread()).decode()
    assert response.status_code == 200
    assert f'"detail": "{SAFE_PROVIDER_UNAVAILABLE_DETAIL}"' in stream_body
    assert SECRET_FAILURE_DETAIL not in stream_body

    debug = await client.get(f"/debug/character/{character_id}", headers=headers)
    assert debug.status_code == 200
    errors = debug.json()["errors"]
    assert [event["operation"] for event in errors] == ["stream", "message"]
    assert {event["code"] for event in errors} == {"provider_unavailable"}
    assert {event["provider"] for event in errors} == {"unknown"}
    serialized_errors = debug.text
    assert SECRET_FAILURE_DETAIL not in serialized_errors
    assert "private-host" not in serialized_errors

    other_token, _ = await register_user(
        client,
        email="diagnostic-other@example.com",
        password="other-good-password",
    )
    other_headers = {"Authorization": f"Bearer {other_token}"}
    other_characters = await client.get("/characters", headers=other_headers)
    other_character_id = other_characters.json()[0]["id"]
    other_debug = await client.get(
        f"/debug/character/{other_character_id}",
        headers=other_headers,
    )
    assert other_debug.status_code == 200
    assert other_debug.json()["errors"] == []
    forbidden = await client.get(
        f"/debug/character/{character_id}",
        headers=other_headers,
    )
    assert forbidden.status_code == 404


async def test_diagnostic_retention_is_bounded(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_payload = conversation.json()

    async with AsyncSessionLocal() as session:
        user_id = await session.scalar(select(User.id).where(User.email == "user@example.com"))
        character_id = await session.scalar(
            select(Character.id).where(Character.owner_user_id == user_id)
        )
    assert user_id is not None
    assert character_id is not None

    monkeypatch.setattr(diagnostics, "MAX_DIAGNOSTIC_EVENTS_PER_USER", 3)
    for _ in range(5):
        await diagnostics.record_generation_error(
            user_id=user_id,
            character_id=character_id,
            conversation_id=uuid.UUID(conversation_payload["id"]),
            operation="message",
            code="provider_unavailable",
            provider="ollama",
        )

    async with AsyncSessionLocal() as session:
        event_count = await session.scalar(
            select(func.count(DiagnosticEvent.id)).where(DiagnosticEvent.user_id == user_id)
        )
    assert event_count == 3


async def test_reroll_and_edit_failures_preserve_existing_history(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await auth_headers(client)
    characters = await client.get("/characters", headers=headers)
    character_id = characters.json()[0]["id"]
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    original = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "Keep this line unchanged."},
        headers=headers,
    )
    assert original.status_code == 200
    original_payload = original.json()

    missing_message_id = str(uuid.uuid4())
    missing_reroll = await client.post(
        "/chat/reroll",
        json={
            "conversation_id": conversation_id,
            "assistant_message_id": missing_message_id,
        },
        headers=headers,
    )
    assert missing_reroll.status_code == 404
    missing_edit = await client.patch(
        f"/conversations/{conversation_id}/messages/{missing_message_id}",
        json={"content": "This message does not exist."},
        headers=headers,
    )
    assert missing_edit.status_code == 404

    monkeypatch.setattr(chat_api, "get_llm_provider", lambda: SecretFailingProvider())
    monkeypatch.setattr(
        conversations_api,
        "get_llm_provider",
        lambda: SecretFailingProvider(),
    )

    reroll = await client.post(
        "/chat/reroll",
        json={
            "conversation_id": conversation_id,
            "assistant_message_id": original_payload["assistant_message"]["id"],
        },
        headers=headers,
    )
    assert reroll.status_code == 503
    assert reroll.json() == {"detail": SAFE_PROVIDER_UNAVAILABLE_DETAIL}

    edit = await client.patch(
        f"/conversations/{conversation_id}/messages/{original_payload['user_message']['id']}",
        json={"content": "This edit must roll back."},
        headers=headers,
    )
    assert edit.status_code == 503
    assert edit.json() == {"detail": SAFE_PROVIDER_UNAVAILABLE_DETAIL}

    monkeypatch.setattr(
        chat_api,
        "get_llm_provider",
        lambda: UnexpectedSecretFailingProvider(),
    )
    monkeypatch.setattr(
        conversations_api,
        "get_llm_provider",
        lambda: UnexpectedSecretFailingProvider(),
    )
    unexpected_reroll = await client.post(
        "/chat/reroll",
        json={
            "conversation_id": conversation_id,
            "assistant_message_id": original_payload["assistant_message"]["id"],
        },
        headers=headers,
    )
    assert unexpected_reroll.status_code == 503
    assert unexpected_reroll.json() == {
        "detail": "The backend could not create an alternate reply. The existing reply is safe."
    }
    assert SECRET_FAILURE_DETAIL not in unexpected_reroll.text

    unexpected_edit = await client.patch(
        f"/conversations/{conversation_id}/messages/{original_payload['user_message']['id']}",
        json={"content": "This unexpected edit must roll back."},
        headers=headers,
    )
    assert unexpected_edit.status_code == 503
    assert unexpected_edit.json() == {
        "detail": "The backend could not refresh that reply. The original turn is unchanged."
    }
    assert SECRET_FAILURE_DETAIL not in unexpected_edit.text

    history = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    assert history.status_code == 200
    assert [message["content"] for message in history.json()] == [
        original_payload["user_message"]["content"],
        original_payload["assistant_message"]["content"],
    ]

    debug = await client.get(f"/debug/character/{character_id}", headers=headers)
    assert debug.status_code == 200
    assert {event["operation"] for event in debug.json()["errors"]} == {"edit", "reroll"}
    assert {event["code"] for event in debug.json()["errors"]} == {
        "generation_failed",
        "provider_unavailable",
    }
