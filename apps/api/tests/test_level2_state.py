from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from helpers import auth_headers, register_user
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.llm.mock import MockLLMProvider
from app.models import (
    Character,
    Conversation,
    EpisodicJournal,
    Message,
    RelationshipState,
    ScheduledJob,
    User,
)
from app.services.chat import (
    ChatTurnCancelled,
    complete_assistant_message,
    prepare_user_message,
)
from app.services.jobs import create_job
from app.services.reasoning import build_reasoning_context
from app.services.scheduler import process_due_jobs


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
    contradiction_id = contradiction.json()["id"]
    assert contradiction.json()["contradiction_group"] == "preference:jasmine-tea"
    assert contradiction.json()["metadata_json"]["contradicts_memory_id"] == memory_id
    assert memory_id in contradiction.json()["metadata_json"]["contradicts_memory_ids"]
    assert contradiction.json()["metadata_json"]["supersedes_memory_id"] == memory_id

    memories_after_conflict = await client.get(
        f"/characters/{character_id}/memories",
        headers=headers,
    )
    original = next(
        memory for memory in memories_after_conflict.json() if memory["id"] == memory_id
    )
    assert original["metadata_json"]["contradiction_status"] == "conflicts"
    assert original["metadata_json"]["contradicted_by_memory_id"] == contradiction_id
    assert contradiction_id in original["metadata_json"]["contradicted_by_memory_ids"]

    resolved = await client.patch(
        f"/characters/{character_id}/memories/{contradiction_id}",
        json={"content": "I like jasmine tea in winter."},
        headers=headers,
    )
    assert resolved.status_code == 200
    assert "contradiction_status" not in resolved.json()["metadata_json"]

    memories_after_resolve = await client.get(
        f"/characters/{character_id}/memories",
        headers=headers,
    )
    original_after_resolve = next(
        memory for memory in memories_after_resolve.json() if memory["id"] == memory_id
    )
    assert "contradicted_by_memory_id" not in original_after_resolve["metadata_json"]
    assert original_after_resolve["metadata_json"]["polarity"] == "positive"

    removed = await client.delete(
        f"/characters/{character_id}/memories/{memory_id}",
        headers=headers,
    )
    assert removed.status_code == 200
    assert removed.json()["deleted"] == 1

    cleared = await client.delete(f"/characters/{character_id}/memories", headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["deleted"] == 1


async def test_memory_conflict_resolution_keeps_selected_version(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    character_id = (await client.get("/characters", headers=headers)).json()[0]["id"]

    first = await client.post(
        f"/characters/{character_id}/memories",
        json={"memory_type": "preference", "content": "I like jasmine tea."},
        headers=headers,
    )
    assert first.status_code == 201
    stale_memory_id = first.json()["id"]
    correction = await client.post(
        f"/characters/{character_id}/memories",
        json={"memory_type": "preference", "content": "I don't like jasmine tea."},
        headers=headers,
    )
    assert correction.status_code == 201
    correction_id = correction.json()["id"]
    assert correction.json()["metadata_json"]["contradiction_status"] == "conflicts"

    resolved = await client.post(
        f"/characters/{character_id}/memories/{correction_id}/resolve",
        headers=headers,
    )

    assert resolved.status_code == 200
    payload = resolved.json()
    assert payload["removed"] == 1
    assert payload["removed_memory_ids"] == [stale_memory_id]
    assert payload["memory"]["id"] == correction_id
    assert payload["memory"]["pinned"] is True
    assert payload["memory"]["confidence"] >= 0.88
    assert payload["memory"]["metadata_json"]["resolution"] == "kept_by_user"
    assert "resolved_conflict_at" in payload["memory"]["metadata_json"]
    assert "contradiction_status" not in payload["memory"]["metadata_json"]
    assert "contradicts_memory_id" not in payload["memory"]["metadata_json"]

    memories = await client.get(f"/characters/{character_id}/memories", headers=headers)
    assert memories.status_code == 200
    memory_ids = {memory["id"] for memory in memories.json()}
    assert correction_id in memory_ids
    assert stale_memory_id not in memory_ids

    no_conflict = await client.post(
        f"/characters/{character_id}/memories/{correction_id}/resolve",
        headers=headers,
    )
    assert no_conflict.status_code == 409
    assert no_conflict.json()["detail"] == "This memory does not have an active conflict."


async def test_memory_forget_restore_is_reversible_private_and_conflict_aware(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    character_id = (await client.get("/characters", headers=headers)).json()[0]["id"]

    liked = await client.post(
        f"/characters/{character_id}/memories",
        json={
            "memory_type": "preference",
            "content": "I like cedar tea.",
            "pinned": True,
        },
        headers=headers,
    )
    disliked = await client.post(
        f"/characters/{character_id}/memories",
        json={"memory_type": "preference", "content": "I don't like cedar tea."},
        headers=headers,
    )
    assert liked.status_code == 201
    assert disliked.status_code == 201
    liked_id = liked.json()["id"]
    disliked_id = disliked.json()["id"]
    assert disliked.json()["metadata_json"]["contradiction_status"] == "conflicts"

    forgotten = await client.post(
        f"/characters/{character_id}/memories/{disliked_id}/forget",
        headers=headers,
    )
    assert forgotten.status_code == 200
    forgotten_at = forgotten.json()["forgotten_at"]
    assert forgotten_at is not None
    assert forgotten.json()["metadata_json"]["last_forget_reason"] == "forgotten_by_user"
    assert "contradiction_status" not in forgotten.json()["metadata_json"]

    repeated = await client.post(
        f"/characters/{character_id}/memories/{disliked_id}/forget",
        headers=headers,
    )
    assert repeated.status_code == 200
    assert repeated.json()["forgotten_at"] == forgotten_at
    assert len(repeated.json()["metadata_json"]["forget_history"]) == 1

    active = await client.get(f"/characters/{character_id}/memories", headers=headers)
    assert active.status_code == 200
    assert [memory["id"] for memory in active.json()] == [liked_id]
    assert "contradiction_status" not in active.json()[0]["metadata_json"]

    search = await client.get(
        f"/characters/{character_id}/memories/search",
        params={"q": "cedar tea"},
        headers=headers,
    )
    assert search.status_code == 200
    assert [memory["id"] for memory in search.json()] == [liked_id]

    faded = await client.get(
        f"/characters/{character_id}/memories",
        params={"state": "forgotten"},
        headers=headers,
    )
    assert faded.status_code == 200
    assert [memory["id"] for memory in faded.json()] == [disliked_id]

    other_token, _ = await register_user(
        client,
        email="memory-owner-check@example.com",
        password="good-password",
    )
    forbidden_restore = await client.post(
        f"/characters/{character_id}/memories/{disliked_id}/restore",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert forbidden_restore.status_code == 404

    restored = await client.post(
        f"/characters/{character_id}/memories/{disliked_id}/restore",
        headers=headers,
    )
    assert restored.status_code == 200
    assert restored.json()["forgotten_at"] is None
    assert restored.json()["metadata_json"]["last_restore_reason"] == "restored_by_user"
    assert restored.json()["metadata_json"]["contradiction_status"] == "conflicts"

    active_after_restore = await client.get(
        f"/characters/{character_id}/memories",
        headers=headers,
    )
    by_id = {memory["id"]: memory for memory in active_after_restore.json()}
    assert set(by_id) == {liked_id, disliked_id}
    assert by_id[liked_id]["metadata_json"]["contradiction_status"] == "conflicts"


async def test_memory_decay_forgetting_is_non_destructive_and_relearning_revives(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    character_id = (await client.get("/characters", headers=headers)).json()[0]["id"]

    fading = await client.post(
        f"/characters/{character_id}/memories",
        json={
            "memory_type": "preference",
            "content": "I like rainy station platforms.",
            "confidence": 0.0,
        },
        headers=headers,
    )
    anchored = await client.post(
        f"/characters/{character_id}/memories",
        json={
            "memory_type": "event",
            "content": "A pinned shared ritual remains here.",
            "confidence": 0.0,
            "pinned": True,
        },
        headers=headers,
    )
    assert fading.status_code == 201
    assert anchored.status_code == 201
    fading_id = fading.json()["id"]

    bulk_forget = await client.post(
        f"/characters/{character_id}/memories/forget",
        headers=headers,
    )
    assert bulk_forget.status_code == 200
    assert bulk_forget.json() == {"forgotten": 1}
    repeated = await client.post(
        f"/characters/{character_id}/memories/forget",
        headers=headers,
    )
    assert repeated.status_code == 200
    assert repeated.json() == {"forgotten": 0}

    active = await client.get(f"/characters/{character_id}/memories", headers=headers)
    assert [memory["id"] for memory in active.json()] == [anchored.json()["id"]]
    forgotten = await client.get(
        f"/characters/{character_id}/memories",
        params={"state": "forgotten"},
        headers=headers,
    )
    assert forgotten.json()[0]["id"] == fading_id
    assert forgotten.json()[0]["metadata_json"]["last_forget_reason"] == "faded_by_decay"

    relearned = await client.post(
        f"/characters/{character_id}/memories",
        json={
            "memory_type": "preference",
            "content": "I like rainy station platforms.",
            "confidence": 0.9,
        },
        headers=headers,
    )
    assert relearned.status_code == 201
    assert relearned.json()["id"] == fading_id
    assert relearned.json()["forgotten_at"] is None
    assert relearned.json()["metadata_json"]["last_restore_reason"] == "relearned"

    export = await client.get("/account/export", headers=headers)
    assert export.status_code == 200
    exported_by_id = {memory["id"]: memory for memory in export.json()["memories"]}
    assert exported_by_id[fading_id]["forgotten_at"] is None
    assert "forget_history" in exported_by_id[fading_id]["metadata_json"]


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
    journal = journals.json()[0]
    assert journal["callbacks_json"]
    assert journal["journal_type"] == "inside_joke"
    continuity_signals = set(journal["metadata_json"]["continuity_signals"])
    assert {"inside_joke", "callback_request"} <= continuity_signals
    assert "open_thread" not in continuity_signals
    continuity_notes = journal["metadata_json"]["continuity_notes"]
    assert any(note.startswith("Inside joke:") for note in continuity_notes)

    debug = await client.get(f"/debug/character/{character_id}", headers=headers)
    assert debug.status_code == 200
    journal_summaries = debug.json()["prompt_context"]["current_summary"]["journals"]
    selected_signals = {
        signal for summary in journal_summaries for signal in summary["continuity_signals"]
    }
    assert {"inside_joke", "callback_request"} <= selected_signals

    relationship = await client.get(f"/characters/{character_id}/relationship", headers=headers)
    assert relationship.json()["metadata_json"]["timeline"]

    jobs = await client.get("/debug/jobs", headers=headers)
    assert jobs.status_code == 200
    job_types = {job["job_type"] for job in jobs.json()}
    assert "relationship_decay" in job_types
    assert "proactive_inactivity_check" in job_types
    assert "proactive_unresolved_thread_nudge" not in job_types


async def test_manual_journal_survives_later_conversation_summary_refresh(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    assert conversation.status_code == 201
    conversation_id = conversation.json()["id"]
    character_id = conversation.json()["character_id"]

    first_chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "Remember that the old station clock made me smile.",
        },
        headers=headers,
    )
    assert first_chat.status_code == 200

    manual = await client.post(
        f"/characters/{character_id}/journals",
        json={
            "conversation_id": conversation_id,
            "journal_type": "manual_note",
            "title": "  My station note  ",
            "summary": "  Keep the warm feeling from the station clock.  ",
            "importance": 0.8,
        },
        headers=headers,
    )
    assert manual.status_code == 201
    manual_id = manual.json()["id"]
    assert manual.json()["title"] == "My station note"
    assert manual.json()["summary"] == "Keep the warm feeling from the station clock."
    assert manual.json()["metadata_json"] == {"source": "manual"}

    second_chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "Today I found a bright blue ticket beside it.",
        },
        headers=headers,
    )
    assert second_chat.status_code == 200

    journals = await client.get(f"/characters/{character_id}/journals", headers=headers)
    assert journals.status_code == 200
    assert len(journals.json()) == 2
    journals_by_id = {journal["id"]: journal for journal in journals.json()}
    persisted_manual = journals_by_id[manual_id]
    assert persisted_manual["title"] == "My station note"
    assert persisted_manual["summary"] == "Keep the warm feeling from the station clock."
    generated = next(journal for journal in journals.json() if journal["id"] != manual_id)
    assert generated["metadata_json"]["source"] == "deterministic_summarizer"
    assert generated["metadata_json"]["message_count"] == 4
    assert "bright blue ticket" in generated["summary"].lower()


async def test_manual_journal_mutation_is_validated_and_owner_scoped(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    assert conversation.status_code == 201
    conversation_id = conversation.json()["id"]
    character_id = conversation.json()["character_id"]
    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "Thank you for staying."},
        headers=headers,
    )
    assert chat.status_code == 200
    generated = (await client.get(f"/characters/{character_id}/journals", headers=headers)).json()[
        0
    ]

    whitespace = await client.post(
        f"/characters/{character_id}/journals",
        json={"title": "   ", "summary": "A visible summary."},
        headers=headers,
    )
    assert whitespace.status_code == 422

    manual = await client.post(
        f"/characters/{character_id}/journals",
        json={
            "conversation_id": conversation_id,
            "journal_type": "manual_note",
            "title": "A personal note",
            "summary": "The first version.",
            "importance": 0.6,
        },
        headers=headers,
    )
    assert manual.status_code == 201
    manual_id = manual.json()["id"]

    for payload in ({}, {"title": None}, {"summary": " \n \t "}):
        invalid = await client.patch(
            f"/characters/{character_id}/journals/{manual_id}",
            json=payload,
            headers=headers,
        )
        assert invalid.status_code == 422

    updated = await client.patch(
        f"/characters/{character_id}/journals/{manual_id}",
        json={
            "title": "  A clearer note  ",
            "summary": "  The corrected version stays mine.  ",
            "importance": 0.9,
        },
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "A clearer note"
    assert updated.json()["summary"] == "The corrected version stays mine."
    assert updated.json()["importance"] == 0.9
    assert "edited_by_user_at" in updated.json()["metadata_json"]

    generated_patch = await client.patch(
        f"/characters/{character_id}/journals/{generated['id']}",
        json={"title": "Do not overwrite transcript state"},
        headers=headers,
    )
    assert generated_patch.status_code == 409
    assert "Edit the transcript" in generated_patch.json()["detail"]
    generated_delete = await client.delete(
        f"/characters/{character_id}/journals/{generated['id']}",
        headers=headers,
    )
    assert generated_delete.status_code == 409
    assert "conversation" in generated_delete.json()["detail"].lower()

    other_token, _ = await register_user(
        client,
        email="journal-owner-check@example.com",
        password="good-password",
    )
    other_headers = {"Authorization": f"Bearer {other_token}"}
    forbidden_patch = await client.patch(
        f"/characters/{character_id}/journals/{manual_id}",
        json={"title": "Cross-account edit"},
        headers=other_headers,
    )
    assert forbidden_patch.status_code == 404
    forbidden_delete = await client.delete(
        f"/characters/{character_id}/journals/{manual_id}",
        headers=other_headers,
    )
    assert forbidden_delete.status_code == 404

    deleted = await client.delete(
        f"/characters/{character_id}/journals/{manual_id}",
        headers=headers,
    )
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": 1}
    repeated = await client.delete(
        f"/characters/{character_id}/journals/{manual_id}",
        headers=headers,
    )
    assert repeated.status_code == 404


async def test_journal_only_tracks_intentional_open_threads(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    character_id = conversation.json()["character_id"]

    answered_question = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "What should we cook tonight?",
        },
        headers=headers,
    )
    assert answered_question.status_code == 200

    journals = await client.get(f"/characters/{character_id}/journals", headers=headers)
    assert journals.status_code == 200
    assert journals.json()[0]["unresolved_threads_json"] == []
    assert "open_thread" not in journals.json()[0]["metadata_json"]["continuity_signals"]

    jobs_after_answered_question = await client.get("/debug/jobs", headers=headers)
    job_types = {job["job_type"] for job in jobs_after_answered_question.json()}
    assert "proactive_unresolved_thread_nudge" not in job_types

    future_loop = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "Can we come back to the lantern plan later?",
        },
        headers=headers,
    )
    assert future_loop.status_code == 200

    updated_journals = await client.get(f"/characters/{character_id}/journals", headers=headers)
    assert updated_journals.status_code == 200
    updated_journal = updated_journals.json()[0]
    assert updated_journal["unresolved_threads_json"]
    assert "lantern plan" in updated_journal["unresolved_threads_json"][-1]
    assert "open_thread" in updated_journal["metadata_json"]["continuity_signals"]

    jobs_after_future_loop = await client.get("/debug/jobs", headers=headers)
    future_job_types = {job["job_type"] for job in jobs_after_future_loop.json()}
    assert "proactive_unresolved_thread_nudge" in future_job_types


async def test_journal_distinguishes_anniversary_and_shared_moment(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    first_conversation = await client.post("/conversations", json={}, headers=headers)
    character_id = first_conversation.json()["character_id"]
    anniversary_chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": first_conversation.json()["id"],
            "content": "Today marks the anniversary of our first lantern walk.",
        },
        headers=headers,
    )
    assert anniversary_chat.status_code == 200

    second_conversation = await client.post(
        "/conversations",
        json={"character_id": character_id},
        headers=headers,
    )
    shared_moment_chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": second_conversation.json()["id"],
            "content": "I want to keep this shared moment we made together.",
        },
        headers=headers,
    )
    assert shared_moment_chat.status_code == 200

    journals = await client.get(f"/characters/{character_id}/journals", headers=headers)
    assert journals.status_code == 200
    assert len(journals.json()) == 2
    journals_by_conversation = {journal["conversation_id"]: journal for journal in journals.json()}

    anniversary = journals_by_conversation[first_conversation.json()["id"]]
    assert anniversary["journal_type"] == "anniversary"
    assert anniversary["metadata_json"]["episode_focus"] == "anniversary"
    assert anniversary["metadata_json"]["continuity_signals"] == ["anniversary"]
    assert anniversary["metadata_json"]["continuity_notes"][0].startswith("Anniversary:")

    shared_moment = journals_by_conversation[second_conversation.json()["id"]]
    assert shared_moment["journal_type"] == "shared_moment"
    assert shared_moment["metadata_json"]["episode_focus"] == "shared_moment"
    assert shared_moment["metadata_json"]["continuity_signals"] == ["shared_moment"]
    assert shared_moment["metadata_json"]["continuity_notes"][0].startswith("Shared moment:")

    debug = await client.get(f"/debug/character/{character_id}", headers=headers)
    assert debug.status_code == 200
    journal_summaries = debug.json()["prompt_context"]["current_summary"]["journals"]
    selected_signals = {
        signal for summary in journal_summaries for signal in summary["continuity_signals"]
    }
    assert {"anniversary", "shared_moment"} <= selected_signals


async def test_relationship_milestones_create_timeline_and_memory_once(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    character_id = conversation.json()["character_id"]
    character_uuid = uuid.UUID(character_id)

    async with AsyncSessionLocal() as session:
        relationship = (
            await session.execute(
                select(RelationshipState).where(
                    RelationshipState.character_id == character_uuid,
                )
            )
        ).scalar_one()
        relationship.warmth = 0.9
        relationship.trust = 0.45
        relationship.familiarity = 0.9
        relationship.metadata_json = {}
        await session.commit()

    first_chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "Thank you, I appreciate this good moment.",
        },
        headers=headers,
    )
    assert first_chat.status_code == 200

    relationship_response = await client.get(
        f"/characters/{character_id}/relationship",
        headers=headers,
    )
    timeline = relationship_response.json()["metadata_json"]["timeline"]
    milestone_ids = {
        event.get("milestone_id") for event in timeline if event.get("kind") == "milestone"
    }
    assert {"first_warmth", "trust_seed", "steady_rhythm"}.issubset(milestone_ids)

    memories = await client.get(f"/characters/{character_id}/memories", headers=headers)
    milestone_memories = [
        memory for memory in memories.json() if memory["memory_type"] == "relationship_milestone"
    ]
    memory_ids = {memory["metadata_json"]["milestone_id"] for memory in milestone_memories}
    assert {"first_warmth", "trust_seed", "steady_rhythm"} == memory_ids

    second_chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "Thank you, I appreciate this good moment again.",
        },
        headers=headers,
    )
    assert second_chat.status_code == 200

    memories_after_second_chat = await client.get(
        f"/characters/{character_id}/memories",
        headers=headers,
    )
    milestone_memories_after_second_chat = [
        memory
        for memory in memories_after_second_chat.json()
        if memory["memory_type"] == "relationship_milestone"
    ]
    assert len(milestone_memories_after_second_chat) == 3


async def test_private_conversation_skips_durable_companion_state(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post(
        "/conversations",
        json={"privacy_mode": "private"},
        headers=headers,
    )
    assert conversation.status_code == 201
    conversation_payload = conversation.json()
    conversation_id = conversation_payload["id"]
    character_id = conversation_payload["character_id"]
    assert conversation_payload["metadata_json"]["privacy_mode"] == "private"

    memory = await client.post(
        f"/characters/{character_id}/memories",
        json={
            "memory_type": "preference",
            "content": "User likes moonlit walks.",
            "importance": 0.8,
        },
        headers=headers,
    )
    assert memory.status_code == 201

    async with AsyncSessionLocal() as session:
        relationship = (
            await session.execute(
                select(RelationshipState).where(
                    RelationshipState.character_id == uuid.UUID(character_id),
                )
            )
        ).scalar_one()
        relationship.warmth = 10.0
        relationship.last_interaction_at = datetime.now(UTC) - timedelta(days=5)
        relationship.metadata_json = {
            "timeline": [{"kind": "baseline", "summary": "state before private chat"}]
        }
        await session.commit()

    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "Thanks. Please remember that I like moonlit walks and silver rain.",
        },
        headers=headers,
    )
    assert chat.status_code == 200
    chat_payload = chat.json()
    assert chat_payload["user_message"]["metadata_json"]["privacy_mode"] == "private"
    assert chat_payload["assistant_message"]["metadata_json"]["privacy_mode"] == "private"

    memories = await client.get(f"/characters/{character_id}/memories", headers=headers)
    assert memories.status_code == 200
    memory_payload = memories.json()
    assert len(memory_payload) == 1
    assert memory_payload[0]["content"] == "User likes moonlit walks."
    assert memory_payload[0]["last_recalled_at"] is None

    journals = await client.get(f"/characters/{character_id}/journals", headers=headers)
    assert journals.status_code == 200
    assert journals.json() == []

    async with AsyncSessionLocal() as session:
        relationship = (
            await session.execute(
                select(RelationshipState).where(
                    RelationshipState.character_id == uuid.UUID(character_id),
                )
            )
        ).scalar_one()
        assert relationship.familiarity == 0
        assert relationship.warmth == 10.0
        assert relationship.metadata_json == {
            "timeline": [{"kind": "baseline", "summary": "state before private chat"}]
        }

    jobs = await client.get("/debug/jobs", headers=headers)
    assert jobs.status_code == 200
    assert jobs.json() == []


async def test_private_turn_stays_out_of_later_continuity(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation = conversation_response.json()
    conversation_id = conversation["id"]
    character_id = conversation["character_id"]
    private_detail = "Please remember that my private signal is winter glass?"

    baseline = await client.get(
        f"/characters/{character_id}/relationship",
        headers=headers,
    )
    assert baseline.status_code == 200

    private_chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": private_detail,
            "privacy_mode": "private",
        },
        headers=headers,
    )
    assert private_chat.status_code == 200
    private_payload = private_chat.json()
    assert private_payload["user_message"]["metadata_json"]["privacy_mode"] == "private"
    assert private_payload["assistant_message"]["metadata_json"]["privacy_mode"] == "private"

    relationship_after_private = await client.get(
        f"/characters/{character_id}/relationship",
        headers=headers,
    )
    assert relationship_after_private.status_code == 200
    for field in (
        "trust",
        "intimacy",
        "warmth",
        "tension",
        "familiarity",
        "attachment",
        "mood",
        "conflict_state",
        "repair_needed",
        "last_interaction_at",
        "metadata_json",
    ):
        assert relationship_after_private.json()[field] == baseline.json()[field]

    memories = await client.get(f"/characters/{character_id}/memories", headers=headers)
    journals = await client.get(f"/characters/{character_id}/journals", headers=headers)
    jobs = await client.get("/debug/jobs", headers=headers)
    assert memories.json() == []
    assert journals.json() == []
    assert jobs.json() == []

    rerolled = await client.post(
        "/chat/reroll",
        json={
            "conversation_id": conversation_id,
            "assistant_message_id": private_payload["assistant_message"]["id"],
        },
        headers=headers,
    )
    assert rerolled.status_code == 200
    assert rerolled.json()["metadata_json"]["privacy_mode"] == "private"

    remember = await client.post(
        (
            f"/conversations/{conversation_id}/messages/"
            f"{private_payload['user_message']['id']}/remember"
        ),
        headers=headers,
    )
    assert remember.status_code == 409

    normal_chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "The ordinary afternoon feels calm.",
        },
        headers=headers,
    )
    assert normal_chat.status_code == 200
    assert normal_chat.json()["user_message"]["metadata_json"]["privacy_mode"] == "normal"

    journals = await client.get(f"/characters/{character_id}/journals", headers=headers)
    assert journals.status_code == 200
    assert len(journals.json()) == 1
    journal = journals.json()[0]
    durable_journal_text = " ".join(
        [
            journal["title"],
            journal["summary"],
            *journal["callbacks_json"],
            *journal["unresolved_threads_json"],
            *journal["metadata_json"].get("continuity_notes", []),
        ]
    )
    assert "winter glass" not in durable_journal_text.lower()
    assert journal["metadata_json"]["message_count"] == 2

    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User))).scalars().one()
        character = await session.get(Character, uuid.UUID(character_id))
        stored_conversation = await session.get(Conversation, uuid.UUID(conversation_id))
        assert character is not None
        assert stored_conversation is not None
        context = await build_reasoning_context(
            session,
            user=user,
            character=character,
            conversation=stored_conversation,
            current_message="Keep this ordinary moment grounded.",
            requested_mode="sfw",
            privacy_mode="normal",
        )
        assert all(
            "winter glass" not in message.content.lower() for message in context.recent_messages
        )
        await session.rollback()

    history = await client.get(
        f"/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert history.status_code == 200
    assert any("winter glass" in message["content"].lower() for message in history.json())

    search = await client.get(
        f"/conversations/{conversation_id}/search",
        params={"q": "winter glass"},
        headers=headers,
    )
    assert search.status_code == 200
    assert any("winter glass" in message["content"].lower() for message in search.json())


async def test_conversation_search_is_trimmed_bounded_and_literal(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    assert conversation.status_code == 201
    conversation_id = conversation.json()["id"]

    literal_content = "Progress is 50% on code_name under C:\\notes."
    literal_turn = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": literal_content},
        headers=headers,
    )
    assert literal_turn.status_code == 200
    ordinary_turn = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "A plain second message."},
        headers=headers,
    )
    assert ordinary_turn.status_code == 200

    for query, marker in (("%", "%"), ("_", "_"), ("\\", "\\")):
        response = await client.get(
            f"/conversations/{conversation_id}/search",
            params={"q": query},
            headers=headers,
        )
        assert response.status_code == 200
        results = response.json()
        assert results
        assert all(marker in message["content"] for message in results)

    trimmed = await client.get(
        f"/conversations/{conversation_id}/search",
        params={"q": "  50%  "},
        headers=headers,
    )
    assert trimmed.status_code == 200
    trimmed_contents = [message["content"] for message in trimmed.json()]
    assert literal_content in trimmed_contents
    assert all("50%" in content for content in trimmed_contents)

    blank = await client.get(
        f"/conversations/{conversation_id}/search",
        params={"q": "   "},
        headers=headers,
    )
    assert blank.status_code == 422
    assert blank.json()["detail"] == "Search query must contain visible text."

    oversized = await client.get(
        f"/conversations/{conversation_id}/search",
        params={"q": "x" * 121},
        headers=headers,
    )
    assert oversized.status_code == 422


async def test_relationship_read_applies_absence_decay(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    character_id = conversation.json()["character_id"]
    character_uuid = uuid.UUID(character_id)

    await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation.json()["id"],
            "content": "Thank you, I am glad we can talk.",
        },
        headers=headers,
    )

    async with AsyncSessionLocal() as session:
        relationship = (
            await session.execute(
                select(RelationshipState).where(
                    RelationshipState.character_id == character_uuid,
                )
            )
        ).scalar_one()
        relationship.warmth = 12.0
        relationship.tension = 6.0
        relationship.attachment = 3.0
        relationship.last_interaction_at = datetime.now(UTC) - timedelta(days=5)
        await session.commit()

    response = await client.get(f"/characters/{character_id}/relationship", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["warmth"] == 12.0
    assert payload["tension"] < 6.0
    assert "absence" in payload["tags_json"]
    assert payload["metadata_json"]["timeline"][-1]["kind"] == "absence"


async def test_scheduler_processes_relationship_decay_job(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    character_id = conversation.json()["character_id"]
    user_id = conversation.json()["user_id"]
    character_uuid = uuid.UUID(character_id)
    user_uuid = uuid.UUID(user_id)

    await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation.json()["id"],
            "content": "Thank you, I appreciate this.",
        },
        headers=headers,
    )

    async with AsyncSessionLocal() as session:
        relationship = (
            await session.execute(
                select(RelationshipState).where(
                    RelationshipState.character_id == character_uuid,
                )
            )
        ).scalar_one()
        relationship.warmth = 10.0
        relationship.tension = 4.0
        relationship.last_interaction_at = datetime.now(UTC) - timedelta(days=4)
        await session.execute(
            delete(ScheduledJob).where(
                ScheduledJob.user_id == user_uuid,
                ScheduledJob.character_id == character_uuid,
                ScheduledJob.job_type == "relationship_decay",
            )
        )
        job = await create_job(
            session,
            job_type="relationship_decay",
            run_at=datetime.now(UTC) - timedelta(minutes=1),
            user_id=user_uuid,
            character_id=character_uuid,
            payload_json={"source": "test"},
        )
        job_id = job.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.payload_json["result"] == "relationship_decay_applied"
        queued_next = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.user_id == user_uuid,
                    ScheduledJob.character_id == character_uuid,
                    ScheduledJob.job_type == "relationship_decay",
                    ScheduledJob.status == "pending",
                )
            )
        ).scalar_one_or_none()
        assert queued_next is not None

        relationship = (
            await session.execute(
                select(RelationshipState).where(
                    RelationshipState.character_id == character_uuid,
                )
            )
        ).scalar_one()
        assert relationship.warmth == 10.0
        assert relationship.tension < 4.0
        assert "absence" in relationship.tags_json


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
    character_id = conversation.json()["character_id"]

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
    reroll_debug = await client.get(f"/debug/conversation/{conversation_id}", headers=headers)
    assert reroll_debug.status_code == 200
    assert reroll_debug.json()["last_assembled_context"]["generation_kind"] == "reroll"

    memory = await client.post(
        f"/characters/{character_id}/memories",
        json={
            "memory_type": "preference",
            "content": "User enjoys quiet window seats.",
            "importance": 0.8,
        },
        headers=headers,
    )
    assert memory.status_code == 201

    sibling_conversation = await client.post(
        "/conversations",
        json={"character_id": character_id, "title": "Sibling thread"},
        headers=headers,
    )
    assert sibling_conversation.status_code == 201
    sibling_conversation_id = sibling_conversation.json()["id"]
    sibling_chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": sibling_conversation_id,
            "content": "Keep this sibling conversation intact.",
        },
        headers=headers,
    )
    assert sibling_chat.status_code == 200

    journals_before_clear = await client.get(
        f"/characters/{character_id}/journals",
        headers=headers,
    )
    journal_conversation_ids = {
        journal["conversation_id"] for journal in journals_before_clear.json()
    }
    assert {conversation_id, sibling_conversation_id}.issubset(journal_conversation_ids)

    jobs_before_clear = await client.get("/debug/jobs", headers=headers)
    assert _conversation_job_count(jobs_before_clear.json(), conversation_id) > 0
    assert _conversation_job_count(jobs_before_clear.json(), sibling_conversation_id) > 0

    clear = await client.delete(f"/conversations/{conversation_id}/messages", headers=headers)
    assert clear.status_code == 200
    assert clear.json()["deleted"] == 3

    messages = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    assert messages.json() == []

    sibling_messages = await client.get(
        f"/conversations/{sibling_conversation_id}/messages",
        headers=headers,
    )
    assert len(sibling_messages.json()) == 2

    journals_after_clear = await client.get(
        f"/characters/{character_id}/journals",
        headers=headers,
    )
    remaining_journal_conversation_ids = {
        journal["conversation_id"] for journal in journals_after_clear.json()
    }
    assert conversation_id not in remaining_journal_conversation_ids
    assert sibling_conversation_id in remaining_journal_conversation_ids

    memories_after_clear = await client.get(
        f"/characters/{character_id}/memories",
        headers=headers,
    )
    assert any(item["id"] == memory.json()["id"] for item in memories_after_clear.json())

    jobs_after_clear = await client.get("/debug/jobs", headers=headers)
    assert _conversation_job_count(jobs_after_clear.json(), conversation_id) == 0
    assert _conversation_job_count(jobs_after_clear.json(), sibling_conversation_id) > 0


async def test_conversation_clear_cancels_delayed_assistant_completion(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation_response.json()["id"]

    async with AsyncSessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == "user@example.com"))
        ).scalar_one()
        conversation = await session.get(Conversation, uuid.UUID(conversation_id))
        assert conversation is not None
        user_message, character, prompt = await prepare_user_message(
            session,
            user,
            conversation,
            "A reply that should not outlive this room.",
            "sfw",
            "normal",
        )
        await session.commit()

        clear = await client.delete(
            f"/conversations/{conversation_id}/messages",
            headers=headers,
        )
        assert clear.status_code == 200
        assert clear.json()["deleted"] == 1

        with pytest.raises(ChatTurnCancelled, match="cleared before the reply finished"):
            await complete_assistant_message(
                session,
                user=user,
                conversation=conversation,
                character=character,
                user_message=user_message,
                assistant_content="This delayed reply must not be stored.",
                provider=MockLLMProvider(),
                prompt=prompt,
            )
        await session.rollback()

    messages = await client.get(
        f"/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert messages.status_code == 200
    assert messages.json() == []


async def test_edit_latest_user_turn_regenerates_reply_and_cleans_state(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    character_id = conversation.json()["character_id"]

    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "Remember that I like quiet tea.",
        },
        headers=headers,
    )
    assert chat.status_code == 200
    user_message = chat.json()["user_message"]
    old_assistant = chat.json()["assistant_message"]

    memories_before = await client.get(f"/characters/{character_id}/memories", headers=headers)
    assert memories_before.status_code == 200
    assert any("quiet tea" in memory["content"].lower() for memory in memories_before.json())

    journals_before = await client.get(f"/characters/{character_id}/journals", headers=headers)
    assert journals_before.status_code == 200
    assert any("quiet tea" in journal["summary"].lower() for journal in journals_before.json())

    jobs_before = await client.get("/debug/jobs", headers=headers)
    old_conversation_job_ids = {
        job["id"]
        for job in jobs_before.json()
        if (job.get("payload_json") or {}).get("conversation_id") == conversation_id
    }
    assert old_conversation_job_ids

    edited = await client.patch(
        f"/conversations/{conversation_id}/messages/{user_message['id']}",
        json={"content": "Remember that I prefer bright mornings."},
        headers=headers,
    )
    assert edited.status_code == 200
    assert edited.json()["user_message"]["id"] == user_message["id"]
    assert edited.json()["user_message"]["content"] == ("Remember that I prefer bright mornings.")
    assert edited.json()["user_message"]["metadata_json"]["edited"] is True
    assert edited.json()["assistant_message"]["id"] != old_assistant["id"]
    assert edited.json()["assistant_message"]["metadata_json"]["edited_turn"] is True
    assert (
        edited.json()["assistant_message"]["metadata_json"]["reply_to_edited_message"]
        == (user_message["id"])
    )
    edit_debug = await client.get(f"/debug/conversation/{conversation_id}", headers=headers)
    assert edit_debug.status_code == 200
    edit_context = edit_debug.json()["last_assembled_context"]
    assert edit_context["generation_kind"] == "edit"
    assert edit_context["context_manifest"]["current_message_chars"] == len(
        "Remember that I prefer bright mornings."
    )

    messages = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    assert messages.status_code == 200
    assert [message["id"] for message in messages.json()] == [
        user_message["id"],
        edited.json()["assistant_message"]["id"],
    ]
    assert old_assistant["id"] not in {message["id"] for message in messages.json()}

    memories_after = await client.get(f"/characters/{character_id}/memories", headers=headers)
    assert memories_after.status_code == 200
    memory_contents = [memory["content"].lower() for memory in memories_after.json()]
    assert any("bright mornings" in content for content in memory_contents)
    assert all("quiet tea" not in content for content in memory_contents)

    journals_after = await client.get(f"/characters/{character_id}/journals", headers=headers)
    assert journals_after.status_code == 200
    journal_summaries = [journal["summary"].lower() for journal in journals_after.json()]
    assert any("bright mornings" in summary for summary in journal_summaries)
    assert all("quiet tea" not in summary for summary in journal_summaries)

    jobs_after = await client.get("/debug/jobs", headers=headers)
    new_conversation_job_ids = {
        job["id"]
        for job in jobs_after.json()
        if (job.get("payload_json") or {}).get("conversation_id") == conversation_id
    }
    assert new_conversation_job_ids
    assert old_conversation_job_ids.isdisjoint(new_conversation_job_ids)

    follow_up = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "A second line lands here."},
        headers=headers,
    )
    assert follow_up.status_code == 200
    blocked_older_edit = await client.patch(
        f"/conversations/{conversation_id}/messages/{user_message['id']}",
        json={"content": "Remember that I prefer rainy walks."},
        headers=headers,
    )
    assert blocked_older_edit.status_code == 409

    token_two, _ = await register_user(
        client,
        email="turn-edit-other@example.com",
        password="good-password",
    )
    cross_account = await client.patch(
        f"/conversations/{conversation_id}/messages/{follow_up.json()['user_message']['id']}",
        json={"content": "This should not cross accounts."},
        headers={"Authorization": f"Bearer {token_two}"},
    )
    assert cross_account.status_code == 404


async def test_edit_latest_user_turn_recalculates_relationship_effect(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    character_id = conversation.json()["character_id"]

    first = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "I am angry and frustrated, and I hate how this feels.",
        },
        headers=headers,
    )
    assert first.status_code == 200
    user_message = first.json()["user_message"]
    old_effect = user_message["metadata_json"]["relationship_effect"]
    assert old_effect["version"] == "relationship_effect_v2"
    assert old_effect["event_ids"]
    assert old_effect["deltas"]["tension"] > 0
    assert old_effect["deltas"]["warmth"] < 0

    relationship_after_first = await client.get(
        f"/characters/{character_id}/relationship",
        headers=headers,
    )
    assert relationship_after_first.status_code == 200
    assert relationship_after_first.json()["tension"] > 0
    assert relationship_after_first.json()["warmth"] < 0
    assert relationship_after_first.json()["repair_needed"] is True

    edited = await client.patch(
        f"/conversations/{conversation_id}/messages/{user_message['id']}",
        json={"content": "Thank you, I appreciate this good and kind moment."},
        headers=headers,
    )
    assert edited.status_code == 200
    edited_metadata = edited.json()["user_message"]["metadata_json"]
    assert edited_metadata["relationship_reversal_applied"] is True
    assert edited_metadata["relationship_recalculated"] is True
    new_effect = edited_metadata["relationship_effect"]
    assert new_effect["deltas"]["tension"] == 0.0
    assert new_effect["deltas"]["warmth"] > 0
    assert new_effect["deltas"]["trust"] > 0

    relationship_after_edit = await client.get(
        f"/characters/{character_id}/relationship",
        headers=headers,
    )
    assert relationship_after_edit.status_code == 200
    assert relationship_after_edit.json()["tension"] == 0.0
    assert relationship_after_edit.json()["warmth"] > 0
    assert relationship_after_edit.json()["trust"] > 0
    assert relationship_after_edit.json()["repair_needed"] is False
    assert "tension" not in relationship_after_edit.json()["tags_json"]
    assert "warm" in relationship_after_edit.json()["tags_json"]

    timeline = relationship_after_edit.json()["metadata_json"]["timeline"]
    assert all(
        event.get("source_message_id") != user_message["id"]
        or "angry" not in event.get("summary", "").lower()
        for event in timeline
    )


async def test_delete_older_assistant_message_rebuilds_dependent_state(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    character_id = conversation.json()["character_id"]

    first = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "A quiet first exchange."},
        headers=headers,
    )
    assert first.status_code == 200
    first_user = first.json()["user_message"]
    first_assistant = first.json()["assistant_message"]

    remembered = await client.post(
        (f"/conversations/{conversation_id}/messages/{first_assistant['id']}/remember"),
        headers=headers,
    )
    assert remembered.status_code == 200
    assert remembered.json()["source_message_id"] == first_assistant["id"]

    second = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "A calm second exchange."},
        headers=headers,
    )
    assert second.status_code == 200
    second_user = second.json()["user_message"]
    second_assistant = second.json()["assistant_message"]

    remembered_second_reply = await client.post(
        f"/conversations/{conversation_id}/messages/{second_assistant['id']}/remember",
        headers=headers,
    )
    assert remembered_second_reply.status_code == 200
    assert remembered_second_reply.json()["source_message_id"] == second_assistant["id"]

    journals_before = await client.get(
        f"/characters/{character_id}/journals",
        headers=headers,
    )
    conversation_journal_before = next(
        journal
        for journal in journals_before.json()
        if journal["conversation_id"] == conversation_id
    )
    assert conversation_journal_before["metadata_json"]["message_count"] == 4

    jobs_before = await client.get("/debug/jobs", headers=headers)
    old_conversation_job_ids = {
        job["id"]
        for job in jobs_before.json()
        if (job.get("payload_json") or {}).get("conversation_id") == conversation_id
    }
    assert old_conversation_job_ids

    deleted = await client.delete(
        f"/conversations/{conversation_id}/messages/{first_assistant['id']}",
        headers=headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 1

    messages_after = await client.get(
        f"/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert [message["id"] for message in messages_after.json()] == [
        first_user["id"],
        second_user["id"],
        second_assistant["id"],
    ]

    memories_after = await client.get(
        f"/characters/{character_id}/memories",
        headers=headers,
    )
    assert all(
        memory["source_message_id"] != first_assistant["id"]
        and first_assistant["id"] not in memory["metadata_json"].get("source_message_ids", [])
        for memory in memories_after.json()
    )

    journals_after = await client.get(
        f"/characters/{character_id}/journals",
        headers=headers,
    )
    conversation_journal_after = next(
        journal
        for journal in journals_after.json()
        if journal["conversation_id"] == conversation_id
    )
    assert conversation_journal_after["metadata_json"]["message_count"] == 3

    jobs_after = await client.get("/debug/jobs", headers=headers)
    new_conversation_job_ids = {
        job["id"]
        for job in jobs_after.json()
        if (job.get("payload_json") or {}).get("conversation_id") == conversation_id
    }
    assert new_conversation_job_ids
    assert old_conversation_job_ids.isdisjoint(new_conversation_job_ids)


async def test_delete_latest_assistant_message_leaves_user_ending_thread_quiet(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    character_id = conversation.json()["character_id"]

    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "A quiet line for now."},
        headers=headers,
    )
    assert chat.status_code == 200
    user_message = chat.json()["user_message"]
    assistant_message = chat.json()["assistant_message"]

    remembered = await client.post(
        (f"/conversations/{conversation_id}/messages/{assistant_message['id']}/remember"),
        headers=headers,
    )
    assert remembered.status_code == 200

    jobs_before = await client.get("/debug/jobs", headers=headers)
    assert _conversation_job_count(jobs_before.json(), conversation_id) > 0

    deleted = await client.delete(
        f"/conversations/{conversation_id}/messages/{assistant_message['id']}",
        headers=headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 1

    messages_after = await client.get(
        f"/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert [message["id"] for message in messages_after.json()] == [user_message["id"]]

    memories_after = await client.get(
        f"/characters/{character_id}/memories",
        headers=headers,
    )
    assert all(
        memory["source_message_id"] != assistant_message["id"]
        and assistant_message["id"] not in memory["metadata_json"].get("source_message_ids", [])
        for memory in memories_after.json()
    )

    journals_after = await client.get(
        f"/characters/{character_id}/journals",
        headers=headers,
    )
    assert all(journal["conversation_id"] != conversation_id for journal in journals_after.json())

    jobs_after = await client.get("/debug/jobs", headers=headers)
    assert _conversation_job_count(jobs_after.json(), conversation_id) == 0


async def test_delete_latest_user_turn_removes_dependent_state(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    character_id = conversation.json()["character_id"]

    first = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "A quiet hello."},
        headers=headers,
    )
    assert first.status_code == 200
    first_user = first.json()["user_message"]
    first_assistant = first.json()["assistant_message"]

    second = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "Remember that I like quiet tea, and I am angry and frustrated.",
        },
        headers=headers,
    )
    assert second.status_code == 200
    second_user = second.json()["user_message"]
    second_assistant = second.json()["assistant_message"]

    blocked_older_delete = await client.delete(
        f"/conversations/{conversation_id}/messages/{first_user['id']}",
        headers=headers,
    )
    assert blocked_older_delete.status_code == 409

    relationship_before_delete = await client.get(
        f"/characters/{character_id}/relationship",
        headers=headers,
    )
    assert relationship_before_delete.status_code == 200
    assert relationship_before_delete.json()["tension"] > 0
    assert relationship_before_delete.json()["warmth"] < 0

    memories_before_delete = await client.get(
        f"/characters/{character_id}/memories",
        headers=headers,
    )
    assert any("quiet tea" in memory["content"].lower() for memory in memories_before_delete.json())
    jobs_before_delete = await client.get("/debug/jobs", headers=headers)
    old_conversation_job_ids = {
        job["id"]
        for job in jobs_before_delete.json()
        if (job.get("payload_json") or {}).get("conversation_id") == conversation_id
    }
    assert _conversation_job_count(jobs_before_delete.json(), conversation_id) > 0

    deleted = await client.delete(
        f"/conversations/{conversation_id}/messages/{second_user['id']}",
        headers=headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 2

    messages_after_delete = await client.get(
        f"/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert [message["id"] for message in messages_after_delete.json()] == [
        first_user["id"],
        first_assistant["id"],
    ]
    assert second_assistant["id"] not in {message["id"] for message in messages_after_delete.json()}

    relationship_after_delete = await client.get(
        f"/characters/{character_id}/relationship",
        headers=headers,
    )
    assert relationship_after_delete.status_code == 200
    assert relationship_after_delete.json()["familiarity"] == 0.0
    assert relationship_after_delete.json()["attachment"] == 0.0
    assert relationship_after_delete.json()["tension"] == 0.0
    assert relationship_after_delete.json()["warmth"] == 0.0
    assert relationship_after_delete.json()["repair_needed"] is False
    assert "tension" not in relationship_after_delete.json()["tags_json"]

    memories_after_delete = await client.get(
        f"/characters/{character_id}/memories",
        headers=headers,
    )
    assert all(
        "quiet tea" not in memory["content"].lower() for memory in memories_after_delete.json()
    )
    assert all(
        memory["source_message_id"] != second_assistant["id"]
        and second_assistant["id"] not in memory["metadata_json"].get("source_message_ids", [])
        for memory in memories_after_delete.json()
    )

    journals_after_delete = await client.get(
        f"/characters/{character_id}/journals",
        headers=headers,
    )
    remaining_conversation_journals = [
        journal
        for journal in journals_after_delete.json()
        if journal["conversation_id"] == conversation_id
    ]
    assert len(remaining_conversation_journals) == 1
    remaining_summary = remaining_conversation_journals[0]["summary"].lower()
    assert "quiet hello" in remaining_summary
    assert "quiet tea" not in remaining_summary
    assert "angry" not in remaining_summary
    assert "frustrated" not in remaining_summary

    jobs_after_delete = await client.get("/debug/jobs", headers=headers)
    new_conversation_job_ids = {
        job["id"]
        for job in jobs_after_delete.json()
        if (job.get("payload_json") or {}).get("conversation_id") == conversation_id
    }
    assert new_conversation_job_ids
    assert old_conversation_job_ids.isdisjoint(new_conversation_job_ids)


async def test_delete_only_user_turn_does_not_requeue_proactive_jobs(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]

    first = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "A first quiet line."},
        headers=headers,
    )
    assert first.status_code == 200
    first_user = first.json()["user_message"]

    jobs_before_delete = await client.get("/debug/jobs", headers=headers)
    assert _conversation_job_count(jobs_before_delete.json(), conversation_id) > 0

    deleted = await client.delete(
        f"/conversations/{conversation_id}/messages/{first_user['id']}",
        headers=headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 2

    messages_after_delete = await client.get(
        f"/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert messages_after_delete.status_code == 200
    assert messages_after_delete.json() == []

    jobs_after_delete = await client.get("/debug/jobs", headers=headers)
    assert _conversation_job_count(jobs_after_delete.json(), conversation_id) == 0


async def test_conversation_title_can_be_updated(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={"title": "Old title"}, headers=headers)
    conversation_id = conversation.json()["id"]

    updated = await client.patch(
        f"/conversations/{conversation_id}",
        json={"title": "Quiet evening"},
        headers=headers,
    )

    assert updated.status_code == 200
    assert updated.json()["title"] == "Quiet evening"


async def test_conversation_privacy_mode_can_be_updated(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    assert conversation.json()["metadata_json"]["privacy_mode"] == "normal"

    updated, concurrent_update = await asyncio.gather(
        client.patch(
            f"/conversations/{conversation_id}",
            json={"privacy_mode": "private"},
            headers=headers,
        ),
        client.patch(
            f"/conversations/{conversation_id}",
            json={"privacy_mode": "private"},
            headers=headers,
        ),
    )

    assert updated.status_code == 200
    assert updated.json()["metadata_json"]["privacy_mode"] == "private"
    assert updated.json()["unread_count"] == 0
    assert concurrent_update.status_code == 200
    assert concurrent_update.json()["metadata_json"]["privacy_mode"] == "private"

    private_history = await client.get(
        f"/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert private_history.status_code == 200
    assert len(private_history.json()) == 1
    private_event = private_history.json()[0]
    assert private_event["role"] == "system"
    assert private_event["metadata_json"] == {
        "system_event": True,
        "event_type": "privacy_mode_changed",
        "event_label": "Private room opened",
        "privacy_mode": "private",
        "content_mode": "sfw",
    }
    assert private_event["content"].startswith("Private room opened.")

    repeated = await client.patch(
        f"/conversations/{conversation_id}",
        json={"privacy_mode": "private"},
        headers=headers,
    )
    assert repeated.status_code == 200
    repeated_history = await client.get(
        f"/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert len(repeated_history.json()) == 1

    resumed = await client.patch(
        f"/conversations/{conversation_id}",
        json={"privacy_mode": "normal"},
        headers=headers,
    )
    assert resumed.status_code == 200
    assert resumed.json()["metadata_json"]["privacy_mode"] == "normal"
    assert resumed.json()["unread_count"] == 0

    resumed_history = await client.get(
        f"/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert [message["metadata_json"]["privacy_mode"] for message in resumed_history.json()] == [
        "private",
        "normal",
    ]

    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "It is good to be back in this conversation.",
        },
        headers=headers,
    )
    assert chat.status_code == 200

    journals = await client.get(
        f"/characters/{conversation.json()['character_id']}/journals",
        headers=headers,
    )
    assert journals.status_code == 200
    assert len(journals.json()) == 1
    assert "Private room opened" not in journals.json()[0]["summary"]
    assert "continuity resumed" not in journals.json()[0]["summary"].lower()


async def test_conversation_delete_removes_queued_jobs(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]

    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "Hello there"},
        headers=headers,
    )
    assert chat.status_code == 200

    journals_before_delete = await client.get(
        f"/characters/{conversation.json()['character_id']}/journals",
        headers=headers,
    )
    assert journals_before_delete.status_code == 200
    assert any(
        journal["conversation_id"] == conversation_id for journal in journals_before_delete.json()
    )

    jobs_before_delete = await client.get("/debug/jobs", headers=headers)
    assert jobs_before_delete.json()

    token_two, _ = await register_user(
        client,
        email="thread-delete-other@example.com",
        password="good-password",
    )
    other_headers = {"Authorization": f"Bearer {token_two}"}
    blocked = await client.delete(f"/conversations/{conversation_id}", headers=other_headers)
    assert blocked.status_code == 404

    deleted = await client.delete(f"/conversations/{conversation_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 1

    jobs_after_delete = await client.get("/debug/jobs", headers=headers)
    assert _conversation_job_count(jobs_after_delete.json(), conversation_id) == 0

    async with AsyncSessionLocal() as session:
        conversation_uuid = uuid.UUID(conversation_id)
        assert await session.get(Conversation, conversation_uuid) is None
        stored_messages = await session.execute(
            select(Message).where(Message.conversation_id == conversation_uuid)
        )
        assert list(stored_messages.scalars().all()) == []
        stored_journals = await session.execute(
            select(EpisodicJournal).where(EpisodicJournal.conversation_id == conversation_uuid)
        )
        assert list(stored_journals.scalars().all()) == []


def _conversation_job_count(jobs: list[dict], conversation_id: str) -> int:
    return sum(
        1
        for job in jobs
        if (job.get("payload_json") or {}).get("conversation_id") == conversation_id
    )
