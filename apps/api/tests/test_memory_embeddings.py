from __future__ import annotations

import math
import uuid
from datetime import timedelta

from helpers import auth_headers
from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import MemoryItem, utc_now
from app.services.embedding import (
    EMBEDDING_DIMENSIONS,
    coerce_embedding,
    cosine_similarity,
    text_embedding,
)


def test_text_embedding_is_deterministic_normalized_and_semantically_adjacent() -> None:
    first = text_embedding("Calm chats after a difficult day")
    repeated = text_embedding("Calm chats after a difficult day")
    adjacent = text_embedding("Peaceful conversations when the day feels heavy")
    unrelated = text_embedding("Bright citrus fruit on the kitchen table")

    assert len(first) == EMBEDDING_DIMENSIONS
    assert first == repeated
    assert all(math.isfinite(value) for value in first)
    assert math.isclose(math.sqrt(sum(value * value for value in first)), 1.0, rel_tol=1e-6)
    assert cosine_similarity(first, adjacent) > cosine_similarity(first, unrelated) + 0.1


def test_embedding_coercion_rejects_malformed_or_non_finite_values() -> None:
    valid = text_embedding("A stable memory")

    assert coerce_embedding(valid) == valid
    assert coerce_embedding("[" + ",".join(str(value) for value in valid) + "]") == valid
    assert coerce_embedding(valid[:-1]) is None
    assert coerce_embedding([*valid[:-1], float("nan")]) is None
    assert coerce_embedding("not-a-vector") is None


async def test_memory_embeddings_cover_create_edit_retrieval_and_legacy_backfill(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    character_id = (await client.get("/characters", headers=headers)).json()[0]["id"]

    relevant = await client.post(
        f"/characters/{character_id}/memories",
        json={
            "memory_type": "preference",
            "content": "User values peaceful conversations when the day feels heavy.",
            "importance": 0.55,
            "confidence": 0.8,
        },
        headers=headers,
    )
    assert relevant.status_code == 201
    assert "embedding" not in relevant.json()

    unrelated = await client.post(
        f"/characters/{character_id}/memories",
        json={
            "memory_type": "preference",
            "content": "User keeps bright citrus fruit on the kitchen table.",
            "importance": 0.65,
            "confidence": 0.8,
        },
        headers=headers,
    )
    assert unrelated.status_code == 201

    relevant_id = uuid.UUID(relevant.json()["id"])
    async with AsyncSessionLocal() as session:
        stored = await session.get(MemoryItem, relevant_id)
        assert stored is not None
        created_embedding = coerce_embedding(stored.embedding)
        assert created_embedding is not None
        assert len(created_embedding) == EMBEDDING_DIMENSIONS

    search = await client.get(
        f"/characters/{character_id}/memories/search?q=calm%20chats",
        headers=headers,
    )
    assert search.status_code == 200
    assert search.json()[0]["id"] == str(relevant_id)
    assert all("embedding" not in memory for memory in search.json())

    punctuation_search = await client.get(
        f"/characters/{character_id}/memories/search?q=%21%21%21",
        headers=headers,
    )
    assert punctuation_search.status_code == 200
    assert len(punctuation_search.json()) == 2

    edited = await client.patch(
        f"/characters/{character_id}/memories/{relevant_id}",
        json={"content": "User feels energized by lively morning conversation."},
        headers=headers,
    )
    assert edited.status_code == 200
    async with AsyncSessionLocal() as session:
        stored = await session.get(MemoryItem, relevant_id)
        assert stored is not None
        edited_embedding = coerce_embedding(stored.embedding)
        assert edited_embedding is not None
        assert edited_embedding != created_embedding
        stored.embedding = None
        await session.commit()

    legacy_search = await client.get(
        f"/characters/{character_id}/memories/search?q=morning%20energy",
        headers=headers,
    )
    assert legacy_search.status_code == 200
    assert legacy_search.json()[0]["id"] == str(relevant_id)

    async with AsyncSessionLocal() as session:
        backfilled = await session.execute(select(MemoryItem).where(MemoryItem.id == relevant_id))
        stored = backfilled.scalar_one()
        assert coerce_embedding(stored.embedding) is not None


async def test_pgvector_candidates_recover_relevant_memory_outside_recent_cohort(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    character = (await client.get("/characters", headers=headers)).json()[0]
    user_id = uuid.UUID(character["owner_user_id"])
    character_id = uuid.UUID(character["id"])
    now = utc_now()
    relevant_content = "User values peaceful conversations when the day feels heavy."
    relevant = MemoryItem(
        user_id=user_id,
        character_id=character_id,
        memory_type="preference",
        content=relevant_content,
        importance=0.55,
        confidence=0.8,
        emotional_weight=0.1,
        pinned=False,
        embedding=text_embedding(relevant_content),
        decay_score=0.0,
        contradiction_group=None,
        metadata_json={"source": "retrieval-test"},
        created_at=now - timedelta(days=30),
        updated_at=now - timedelta(days=30),
    )
    decoys = []
    for index in range(110):
        content = f"Archive marker {index} records copper inventory for storage shelf {index}."
        decoys.append(
            MemoryItem(
                user_id=user_id,
                character_id=character_id,
                memory_type="event",
                content=content,
                importance=0.55,
                confidence=0.8,
                emotional_weight=0.0,
                pinned=False,
                embedding=text_embedding(content),
                decay_score=0.0,
                contradiction_group=None,
                metadata_json={"source": "retrieval-test"},
                created_at=now,
                updated_at=now,
            )
        )
    async with AsyncSessionLocal() as session:
        session.add_all([relevant, *decoys])
        await session.commit()
        relevant_id = relevant.id

    search = await client.get(
        f"/characters/{character_id}/memories/search?q=calm%20chats",
        headers=headers,
    )
    assert search.status_code == 200
    assert search.json()[0]["id"] == str(relevant_id)
