from __future__ import annotations

from helpers import auth_headers
from httpx import AsyncClient

from app.services.prompt import HARD_BOUNDARIES


async def test_manual_memory_retrieval_and_debug_prompt(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    characters = await client.get("/characters", headers=headers)
    character_id = characters.json()[0]["id"]

    created = await client.post(
        f"/characters/{character_id}/memories",
        json={
            "memory_type": "preference",
            "content": "User likes quiet late-night conversations.",
            "confidence": 0.9,
        },
        headers=headers,
    )
    assert created.status_code == 201

    search = await client.get(
        f"/characters/{character_id}/memories/search?q=quiet",
        headers=headers,
    )
    assert search.status_code == 200
    assert search.json()[0]["content"] == "User likes quiet late-night conversations."

    debug = await client.get(f"/debug/character/{character_id}", headers=headers)
    assert debug.status_code == 200
    prompt = debug.json()["prompt_context"]["prompt"]
    assert "User likes quiet late-night conversations." in prompt
    assert HARD_BOUNDARIES in prompt
    assert "password_hash" not in prompt


async def test_relationship_updates_after_chat(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    character_id = conversation.json()["character_id"]

    await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "Thank you, I appreciate this."},
        headers=headers,
    )

    relationship = await client.get(f"/characters/{character_id}/relationship", headers=headers)
    payload = relationship.json()
    assert payload["familiarity"] > 0
    assert payload["warmth"] > 0
    assert payload["trust"] > 0


async def test_adult_mode_structural_gates(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    characters = await client.get("/characters", headers=headers)
    character_id = characters.json()[0]["id"]

    blocked_debug = await client.get(f"/debug/character/{character_id}", headers=headers)
    assert "Content mode: SFW." in blocked_debug.json()["prompt_context"]["prompt"]

    await client.patch("/auth/me", json={"age_gate_confirmed": True}, headers=headers)
    await client.patch(
        f"/characters/{character_id}",
        json={"explicit_age": 28, "adult_mode_allowed": True},
        headers=headers,
    )
    conversation = await client.post(
        "/conversations",
        json={"character_id": character_id},
        headers=headers,
    )
    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation.json()["id"],
            "content": "Keep the tone warm and private.",
            "content_mode": "adult",
        },
        headers=headers,
    )
    assert chat.status_code == 200
    assert chat.json()["assistant_message"]["metadata_json"]["content_mode"] == "adult"
