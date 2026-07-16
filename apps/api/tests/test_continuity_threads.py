from __future__ import annotations

from helpers import auth_headers, register_user
from httpx import AsyncClient

from app.services.continuity import analyze_thread_candidate


def test_thread_candidate_requires_explicit_safe_future_intent() -> None:
    follow_up = analyze_thread_candidate("Can we come back to the lantern plan after work?")
    plan = analyze_thread_candidate("I will call the clinic tomorrow morning.")
    ordinary = analyze_thread_candidate("I had a complicated day at work.")
    sensitive = analyze_thread_candidate("Remind me that my recovery code is 1234 tomorrow.")

    assert follow_up.accepted is True
    assert follow_up.thread_kind == "follow_up"
    assert follow_up.confidence >= 0.9
    assert plan.accepted is True
    assert plan.thread_kind == "plan"
    assert ordinary.accepted is False
    assert ordinary.reason == "no_explicit_thread"
    assert sensitive.accepted is False
    assert sensitive.reason == "sensitive_content"


async def test_explicit_thread_enters_prompt_and_closes_only_from_user_language(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    assert conversation_response.status_code == 201
    conversation = conversation_response.json()
    character_id = conversation["character_id"]

    first_chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation["id"],
            "content": "Can we come back to the lantern plan after work?",
        },
        headers=headers,
    )
    assert first_chat.status_code == 200

    threads = await client.get(
        f"/characters/{character_id}/threads?status=all",
        headers=headers,
    )
    assert threads.status_code == 200
    assert len(threads.json()) == 1
    thread = threads.json()[0]
    assert thread["status"] == "open"
    assert thread["source_message_id"] == first_chat.json()["user_message"]["id"]
    assert thread["metadata_json"]["source"] == "explicit_user_language"

    continuation = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation["id"],
            "content": "I am still thinking about the lantern plan.",
        },
        headers=headers,
    )
    assert continuation.status_code == 200
    debug = await client.get(
        f"/debug/conversation/{conversation['id']}",
        headers=headers,
    )
    assert debug.status_code == 200
    manifest_threads = debug.json()["last_assembled_context"]["context_manifest"][
        "continuity_threads"
    ]
    assert manifest_threads == [{"id": thread["id"], "thread_kind": "follow_up", "status": "open"}]

    closure = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation["id"],
            "content": "I did it—the lantern plan is done, so we can close that loop.",
        },
        headers=headers,
    )
    assert closure.status_code == 200
    settled = await client.get(
        f"/characters/{character_id}/threads?status=resolved",
        headers=headers,
    )
    assert settled.status_code == 200
    assert [item["id"] for item in settled.json()] == [thread["id"]]
    assert settled.json()[0]["resolved_at"] is not None


async def test_thread_controls_are_owned_and_support_full_lifecycle(
    client: AsyncClient,
) -> None:
    token, _ = await register_user(client)
    headers = {"Authorization": f"Bearer {token}"}
    conversation = (await client.post("/conversations", json={}, headers=headers)).json()
    character_id = conversation["character_id"]

    sensitive = await client.post(
        f"/characters/{character_id}/threads",
        json={"content": "Keep my recovery code in view for tomorrow."},
        headers=headers,
    )
    assert sensitive.status_code == 422

    created = await client.post(
        f"/characters/{character_id}/threads",
        json={
            "conversation_id": conversation["id"],
            "thread_kind": "ritual",
            "content": "Begin Friday chats by naming one good surprise from the week.",
            "salience": 0.9,
        },
        headers=headers,
    )
    assert created.status_code == 201
    thread = created.json()
    assert thread["metadata_json"]["source"] == "manual"

    resolved = await client.patch(
        f"/characters/{character_id}/threads/{thread['id']}",
        json={"status": "resolved"},
        headers=headers,
    )
    assert resolved.status_code == 200
    assert resolved.json()["resolved_at"] is not None

    reopened = await client.patch(
        f"/characters/{character_id}/threads/{thread['id']}",
        json={"status": "open"},
        headers=headers,
    )
    assert reopened.status_code == 200
    assert reopened.json()["resolved_at"] is None

    other_token, _ = await register_user(
        client,
        email="continuity-other@example.com",
    )
    other_headers = {"Authorization": f"Bearer {other_token}"}
    hidden = await client.get(
        f"/characters/{character_id}/threads?status=all",
        headers=other_headers,
    )
    assert hidden.status_code == 404

    deleted = await client.delete(
        f"/characters/{character_id}/threads/{thread['id']}",
        headers=headers,
    )
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": 1}
    remaining = await client.get(
        f"/characters/{character_id}/threads?status=all",
        headers=headers,
    )
    assert remaining.json() == []


async def test_private_conversation_never_creates_or_accepts_threads(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post(
        "/conversations",
        json={"privacy_mode": "private"},
        headers=headers,
    )
    assert conversation_response.status_code == 201
    conversation = conversation_response.json()
    character_id = conversation["character_id"]

    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation["id"],
            "content": "Please remind me tomorrow to return to the lantern plan.",
        },
        headers=headers,
    )
    assert chat.status_code == 200
    threads = await client.get(
        f"/characters/{character_id}/threads?status=all",
        headers=headers,
    )
    assert threads.status_code == 200
    assert threads.json() == []

    manual = await client.post(
        f"/characters/{character_id}/threads",
        json={
            "conversation_id": conversation["id"],
            "content": "Return to the lantern plan.",
        },
        headers=headers,
    )
    assert manual.status_code == 409

    normal_conversation = await client.post(
        "/conversations",
        json={"character_id": character_id},
        headers=headers,
    )
    assert normal_conversation.status_code == 201
    private_turn = await client.post(
        "/chat/messages",
        json={
            "conversation_id": normal_conversation.json()["id"],
            "content": "Please remind me tomorrow to return to the lantern plan.",
            "privacy_mode": "private",
        },
        headers=headers,
    )
    assert private_turn.status_code == 200
    assert private_turn.json()["user_message"]["metadata_json"]["privacy_mode"] == "private"
    threads_after_private_turn = await client.get(
        f"/characters/{character_id}/threads?status=all",
        headers=headers,
    )
    assert threads_after_private_turn.json() == []


async def test_adult_turn_never_creates_an_automatic_thread(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    confirmed = await client.patch(
        "/auth/me",
        json={"age_gate_confirmed": True},
        headers=headers,
    )
    assert confirmed.status_code == 200
    character = (await client.get("/characters", headers=headers)).json()[0]
    adult_ready = await client.patch(
        f"/characters/{character['id']}",
        json={"explicit_age": 28, "adult_mode_allowed": True},
        headers=headers,
    )
    assert adult_ready.status_code == 200
    conversation = (
        await client.post(
            "/conversations",
            json={"character_id": character["id"]},
            headers=headers,
        )
    ).json()

    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation["id"],
            "content": "Please remind me tomorrow to return to our lantern story.",
            "content_mode": "adult",
        },
        headers=headers,
    )
    assert chat.status_code == 200
    assert chat.json()["user_message"]["metadata_json"]["content_mode"] == "adult"
    threads = await client.get(
        f"/characters/{character['id']}/threads?status=all",
        headers=headers,
    )
    assert threads.status_code == 200
    assert threads.json() == []


async def test_editing_source_message_removes_stale_automatic_thread(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = (await client.post("/conversations", json={}, headers=headers)).json()
    character_id = conversation["character_id"]
    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation["id"],
            "content": "Can we come back to the lantern plan tomorrow?",
        },
        headers=headers,
    )
    assert chat.status_code == 200

    edit = await client.patch(
        (f"/conversations/{conversation['id']}/messages/{chat.json()['user_message']['id']}"),
        json={"content": "I changed my mind and want a quiet evening."},
        headers=headers,
    )
    assert edit.status_code == 200
    threads = await client.get(
        f"/characters/{character_id}/threads?status=all",
        headers=headers,
    )
    assert threads.status_code == 200
    assert threads.json() == []
