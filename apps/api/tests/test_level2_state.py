from __future__ import annotations

from helpers import auth_headers, register_user
from httpx import AsyncClient


async def test_memory_v2_edit_delete_dedupe_and_contradiction(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    character_id = (await client.get("/characters", headers=headers)).json()[0]["id"]

    first = await client.post(
        f"/characters/{character_id}/memories",
        json={
            "memory_type": "preference",
            "content": "I like tea.",
            "importance": 0.8,
            "confidence": 0.9,
            "pinned": True,
        },
        headers=headers,
    )
    assert first.status_code == 201
    duplicate = await client.post(
        f"/characters/{character_id}/memories",
        json={"memory_type": "preference", "content": "I like tea.", "confidence": 0.7},
        headers=headers,
    )
    assert duplicate.status_code == 201

    memories = await client.get(f"/characters/{character_id}/memories", headers=headers)
    assert len(memories.json()) == 1
    memory_id = memories.json()[0]["id"]
    assert memories.json()[0]["pinned"] is True

    edited = await client.patch(
        f"/characters/{character_id}/memories/{memory_id}",
        json={"content": "I like jasmine tea.", "importance": 0.9, "pinned": False},
        headers=headers,
    )
    assert edited.status_code == 200
    assert edited.json()["importance"] == 0.9
    assert edited.json()["pinned"] is False

    contradiction = await client.post(
        f"/characters/{character_id}/memories",
        json={"memory_type": "preference", "content": "I don't like jasmine tea."},
        headers=headers,
    )
    assert contradiction.status_code == 201
    assert contradiction.json()["contradiction_group"] == "preference:jasmine-tea"
    assert contradiction.json()["metadata_json"]["contradicts_memory_id"] == memory_id

    removed = await client.delete(
        f"/characters/{character_id}/memories/{memory_id}",
        headers=headers,
    )
    assert removed.status_code == 200
    assert removed.json()["deleted"] == 1

    cleared = await client.delete(f"/characters/{character_id}/memories", headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["deleted"] == 1


async def test_journal_relationship_and_proactive_hooks_after_chat(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    character_id = conversation.json()["character_id"]

    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "Thanks. Remember that our inside joke is the midnight kettle?",
        },
        headers=headers,
    )
    assert chat.status_code == 200
    assert chat.json()["assistant_message"]["metadata_json"]["delivery_state"]["read_state"] == (
        "delivered"
    )

    journals = await client.get(f"/characters/{character_id}/journals", headers=headers)
    assert journals.status_code == 200
    assert len(journals.json()) == 1
    assert journals.json()[0]["callbacks_json"]

    relationship = await client.get(f"/characters/{character_id}/relationship", headers=headers)
    assert relationship.json()["metadata_json"]["timeline"]

    jobs = await client.get("/debug/jobs", headers=headers)
    assert jobs.status_code == 200
    job_types = {job["job_type"] for job in jobs.json()}
    assert "proactive_inactivity_check" in job_types
    assert "proactive_unresolved_thread_nudge" in job_types


async def test_adult_status_and_access_control_are_structural(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    character_id = (await client.get("/characters", headers=headers)).json()[0]["id"]

    status = await client.get(f"/characters/{character_id}/adult-status", headers=headers)
    assert status.status_code == 200
    assert status.json()["effective_mode"] == "sfw"
    assert "User age gate is not confirmed." in status.json()["reasons"]

    token_two, _ = await register_user(
        client,
        email="second@example.com",
        password="good-password",
    )
    other_headers = {"Authorization": f"Bearer {token_two}"}
    blocked = await client.get(f"/characters/{character_id}", headers=other_headers)
    assert blocked.status_code == 404


async def test_conversation_clear_and_reroll(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]

    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "Hello there"},
        headers=headers,
    )
    assistant_id = chat.json()["assistant_message"]["id"]

    reroll = await client.post(
        "/chat/reroll",
        json={"conversation_id": conversation_id, "assistant_message_id": assistant_id},
        headers=headers,
    )
    assert reroll.status_code == 200
    assert reroll.json()["metadata_json"]["reroll_of"] == assistant_id

    clear = await client.delete(f"/conversations/{conversation_id}/messages", headers=headers)
    assert clear.status_code == 200
    assert clear.json()["deleted"] == 3

    messages = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    assert messages.json() == []
