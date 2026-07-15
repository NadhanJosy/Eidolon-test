from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from helpers import auth_headers, register_user
from httpx import AsyncClient
from pytest import MonkeyPatch

from app.api import chat as chat_api
from app.llm.base import LLMGeneration, LLMStreamEvent


class CapturingProvider:
    name = "mock"
    model = "capturing-test"

    def __init__(self) -> None:
        self.prompt = ""

    async def generate(self, prompt: str) -> LLMGeneration:
        self.prompt = prompt
        return LLMGeneration("I can hold that setting with you.", self.name, self.model, "stop")

    async def stream(self, prompt: str) -> AsyncIterator[LLMStreamEvent]:
        self.prompt = prompt
        yield LLMStreamEvent("I can hold that setting with you.", self.name, self.model, "stop")

    async def health(self) -> dict[str, str]:
        return {"status": "ok", "provider": self.name}


async def test_shared_scene_is_thread_scoped_idempotent_and_private_in_debug(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await auth_headers(client)
    characters = await client.get("/characters", headers=headers)
    character_id = characters.json()[0]["id"]
    first = await client.post(
        "/conversations",
        json={"character_id": character_id},
        headers=headers,
    )
    sibling = await client.post(
        "/conversations",
        json={"character_id": character_id},
        headers=headers,
    )
    first_id = first.json()["id"]
    sibling_id = sibling.json()["id"]
    scene = "A focused co-working project with one calm next step."

    first_update, repeated_update = await asyncio.gather(
        client.patch(
            f"/conversations/{first_id}",
            json={"scenario": {"mode": "custom", "text": scene}},
            headers=headers,
        ),
        client.patch(
            f"/conversations/{first_id}",
            json={"scenario": {"mode": "custom", "text": f"  {scene}  "}},
            headers=headers,
        ),
    )
    assert first_update.status_code == 200
    assert repeated_update.status_code == 200
    for response in (first_update, repeated_update):
        assert response.json()["metadata_json"]["scenario_mode"] == "custom"
        assert response.json()["metadata_json"]["scenario_text"] == scene

    history = await client.get(f"/conversations/{first_id}/messages", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 1
    event = history.json()[0]
    assert event["role"] == "system"
    assert event["metadata_json"]["event_type"] == "scenario_changed"
    assert event["metadata_json"]["scenario_mode"] == "custom"
    assert scene not in event["content"]

    provider = CapturingProvider()
    monkeypatch.setattr(chat_api, "get_llm_provider", lambda: provider)
    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": first_id, "content": "Let us begin."},
        headers=headers,
    )
    assert chat.status_code == 200
    assert "Active shared scene mode: custom" in provider.prompt
    assert f"Active shared scene: {scene}" in provider.prompt
    assert "Shared scene changed." not in provider.prompt

    debug = await client.get(f"/debug/conversation/{first_id}", headers=headers)
    assert debug.status_code == 200
    manifest = debug.json()["last_assembled_context"]["context_manifest"]
    assert manifest["scenario"] == {"mode": "custom", "text_chars": len(scene)}
    assert scene not in debug.text

    sibling_messages = await client.get(
        f"/conversations/{sibling_id}/messages",
        headers=headers,
    )
    assert sibling_messages.status_code == 200
    assert sibling_messages.json() == []
    conversations = await client.get("/conversations", headers=headers)
    sibling_payload = next(item for item in conversations.json() if item["id"] == sibling_id)
    assert sibling_payload["metadata_json"].get("scenario_mode") != "custom"
    assert "scenario_text" not in sibling_payload["metadata_json"]

    other_token, _ = await register_user(
        client,
        email="scene-other@example.com",
        password="other-good-password",
    )
    blocked = await client.patch(
        f"/conversations/{first_id}",
        json={"scenario": {"mode": "default"}},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert blocked.status_code == 404

    reset = await client.patch(
        f"/conversations/{first_id}",
        json={"scenario": {"mode": "default"}},
        headers=headers,
    )
    assert reset.status_code == 200
    assert reset.json()["metadata_json"]["scenario_mode"] == "default"
    assert "scenario_text" not in reset.json()["metadata_json"]
    repeated_reset = await client.patch(
        f"/conversations/{first_id}",
        json={"scenario": {"mode": "default"}},
        headers=headers,
    )
    assert repeated_reset.status_code == 200
    reset_history = await client.get(f"/conversations/{first_id}/messages", headers=headers)
    scenario_events = [
        message
        for message in reset_history.json()
        if message["metadata_json"].get("event_type") == "scenario_changed"
    ]
    assert [message["metadata_json"]["scenario_mode"] for message in scenario_events] == [
        "custom",
        "default",
    ]


async def test_shared_scene_validation_fails_closed(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]

    invalid_payloads = [
        ({"scenario": None}, 422),
        ({"scenario": {"mode": "custom"}}, 422),
        ({"scenario": {"mode": "custom", "text": "   "}}, 422),
        ({"scenario": {"mode": "custom", "text": "\u200d"}}, 422),
        ({"scenario": {"mode": "default", "text": "Not allowed here."}}, 422),
        ({"scenario": {"mode": "custom", "text": "x" * 1201}}, 422),
        (
            {
                "scenario": {
                    "mode": "custom",
                    "text": "A setting that asks us to bypass safety rules.",
                }
            },
            400,
        ),
    ]
    for payload, expected_status in invalid_payloads:
        response = await client.patch(
            f"/conversations/{conversation_id}",
            json=payload,
            headers=headers,
        )
        assert response.status_code == expected_status, (payload, response.text)

    unchanged = await client.get("/conversations", headers=headers)
    stored = next(item for item in unchanged.json() if item["id"] == conversation_id)
    assert stored["metadata_json"] == {
        "privacy_mode": "normal",
        "scenario_mode": "default",
    }
    history = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    assert history.json() == []


async def test_mock_reply_uses_custom_shared_scene(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    updated = await client.patch(
        f"/conversations/{conversation_id}",
        json={
            "scenario": {
                "mode": "custom",
                "text": "A focused co-working project with practical companionship.",
            }
        },
        headers=headers,
    )
    assert updated.status_code == 200

    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "I am ready to start."},
        headers=headers,
    )
    assert chat.status_code == 200
    reply = chat.json()["assistant_message"]["content"].lower()
    assert "work one clear next step" in reply
    assert "active shared scene" not in reply
    assert "scenario" not in reply
