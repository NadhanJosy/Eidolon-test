from __future__ import annotations

from helpers import auth_headers
from httpx import AsyncClient


async def test_register_login_me_and_default_character(client: AsyncClient) -> None:
    headers = await auth_headers(client)

    me = await client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"

    characters = await client.get("/characters", headers=headers)
    assert characters.status_code == 200
    assert len(characters.json()) == 1

    login = await client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "good-password"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]
    assert login.json()["refresh_token"]


async def test_refresh_token_rotates_and_logout_revokes(client: AsyncClient) -> None:
    register = await client.post(
        "/auth/register",
        json={
            "email": "refresh@example.com",
            "password": "good-password",
            "display_name": "Refresh",
        },
    )
    assert register.status_code == 201
    first_refresh_token = register.json()["refresh_token"]

    refreshed = await client.post(
        "/auth/refresh",
        json={"refresh_token": first_refresh_token},
    )
    assert refreshed.status_code == 200
    second_refresh_token = refreshed.json()["refresh_token"]
    assert second_refresh_token != first_refresh_token

    reused = await client.post(
        "/auth/refresh",
        json={"refresh_token": first_refresh_token},
    )
    assert reused.status_code == 401

    me = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    assert me.status_code == 200

    logout = await client.post(
        "/auth/logout",
        json={"refresh_token": second_refresh_token},
    )
    assert logout.status_code == 200

    revoked = await client.post(
        "/auth/refresh",
        json={"refresh_token": second_refresh_token},
    )
    assert revoked.status_code == 401


async def test_protected_endpoint_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/characters")

    assert response.status_code == 401


async def test_chat_persists_user_and_assistant_messages(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    assert conversation.status_code == 201
    conversation_id = conversation.json()["id"]

    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "Hello there"},
        headers=headers,
    )
    assert chat.status_code == 200, chat.text
    payload = chat.json()
    assert payload["user_message"]["content"] == "Hello there"
    assert payload["assistant_message"]["role"] == "assistant"
    assert payload["assistant_message"]["metadata_json"]["provider"] == "mock"
    assert payload["assistant_message"]["content"].startswith("[mock:Eidolon]")
    assert "I heard:" not in payload["assistant_message"]["content"]

    messages = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    assert messages.status_code == 200
    assert [message["role"] for message in messages.json()] == ["user", "assistant"]


async def test_stream_persists_final_assistant_without_duplicate(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]

    async with client.stream(
        "POST",
        "/chat/stream",
        json={"conversation_id": conversation_id, "content": "Please remember that I like tea."},
        headers=headers,
    ) as response:
        body = await response.aread()

    assert response.status_code == 200
    text = body.decode()
    assert "event: message_start" in text
    assert "event: token" in text
    assert "event: message_done" in text

    messages = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    assert [message["role"] for message in messages.json()] == ["user", "assistant"]

    characters = await client.get("/characters", headers=headers)
    character_id = characters.json()[0]["id"]
    memories = await client.get(f"/characters/{character_id}/memories", headers=headers)
    assert memories.status_code == 200
    assert len(memories.json()) == 1
