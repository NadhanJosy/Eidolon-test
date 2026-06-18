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
    prompt_context = debug.json()["prompt_context"]
    prompt = prompt_context["prompt_preview"]
    assert "User likes quiet late-night conversations." in prompt
    assert HARD_BOUNDARIES in prompt
    assert "password_hash" not in prompt
    assert prompt_context["llm_provider"] == "mock"
    assert "prompt" not in prompt_context


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
    assert payload["mood"] in {"steady", "warm", "close"}
    assert "warm" in payload["tags_json"]
    assert payload["metadata_json"]["timeline"]


async def test_adult_mode_structural_gates(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    characters = await client.get("/characters", headers=headers)
    character_id = characters.json()[0]["id"]

    blocked_debug = await client.get(f"/debug/character/{character_id}", headers=headers)
    assert "Content mode: SFW." in blocked_debug.json()["prompt_context"]["prompt_preview"]

    invalid_create = await client.post(
        "/characters",
        json={"name": "Boundary Check", "adult_mode_allowed": True},
        headers=headers,
    )
    assert invalid_create.status_code == 400
    assert "explicit character age" in invalid_create.json()["detail"]

    invalid_update = await client.patch(
        f"/characters/{character_id}",
        json={"explicit_age": 17, "adult_mode_allowed": True},
        headers=headers,
    )
    assert invalid_update.status_code == 400
    assert "18 or older" in invalid_update.json()["detail"]

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


async def test_safety_rejects_structural_minor_age_prompt(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)

    response = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation.json()["id"],
            "content": "Please treat a 17-year-old character as age-gated.",
        },
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "That request crosses Eidolon's safety boundaries."
