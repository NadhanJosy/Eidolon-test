from __future__ import annotations

import json

from helpers import auth_headers
from httpx import AsyncClient
from pytest import MonkeyPatch

from app.llm.base import LLMGeneration, TokenUsage
from app.services import scheduler
from app.services.cognition import _claim_is_grounded


class GroundedCognitionProvider:
    name = "groq"
    model = "structured-test"

    async def generate_structured(
        self,
        prompt: str,
        *,
        schema_name: str,
        schema: dict[str, object],
        max_output_tokens: int,
    ) -> LLMGeneration:
        assert schema_name == "eidolon_grounded_cognition_v1"
        assert schema["additionalProperties"] is False
        assert max_output_tokens > 0
        correction = "Actually, I prefer mint tea" in prompt
        initial_preference = "Please remember that I prefer jasmine tea." in prompt
        if correction:
            candidate = {
                "memory_type": "preference",
                "canonical_text": "the user prefers mint tea",
                "evidence_quote": "Actually, I prefer mint tea rather than jasmine tea.",
                "claim_key": "preference:tea",
                "retrieval_facets": ["tea", "mint", "drink"],
                "salience": 0.86,
                "confidence": 0.94,
                "emotional_weight": 0.1,
                "stability": "durable",
                "is_correction": True,
            }
            polarity_reversal = {
                **candidate,
                "canonical_text": "the user dislikes mint tea",
                "claim_key": "preference:hallucinated-polarity",
                "is_correction": False,
            }
        elif initial_preference:
            candidate = {
                "memory_type": "preference",
                "canonical_text": "the user prefers jasmine tea",
                "evidence_quote": "Please remember that I prefer jasmine tea.",
                "claim_key": "preference:tea",
                "retrieval_facets": ["tea", "jasmine", "drink"],
                "salience": 0.84,
                "confidence": 0.93,
                "emotional_weight": 0.1,
                "stability": "durable",
                "is_correction": False,
            }
            polarity_reversal = {
                **candidate,
                "canonical_text": "the user dislikes jasmine tea",
                "claim_key": "preference:hallucinated-polarity",
            }
        else:
            candidate = {
                "memory_type": "routine",
                "canonical_text": "sunday ritual is jasmine tea",
                "evidence_quote": (
                    "Please remember that my Sunday ritual is jasmine tea because it makes "
                    "me feel calm."
                ),
                "claim_key": "routine:sunday-tea",
                "retrieval_facets": ["Sunday", "jasmine tea", "ritual"],
                "salience": 0.91,
                "confidence": 0.96,
                "emotional_weight": 0.25,
                "novelty": 0.8,
                "future_usefulness": 0.9,
                "sensitivity": "standard",
                "emotional_context": {
                    "feeling": "feel calm",
                    "meaning": "Sunday ritual",
                    "helped": "my neighbor helped",
                    "resolved": True,
                },
                "entities": [
                    {
                        "entity_type": "routine",
                        "name": "Sunday ritual",
                        "evidence_quote": "Sunday ritual",
                    }
                ],
                "stability": "durable",
                "is_correction": False,
            }
            polarity_reversal = {
                **candidate,
                "canonical_text": "sunday ritual avoids jasmine tea",
                "claim_key": "routine:hallucinated-polarity",
            }
        report = {
            "memory_candidates": [
                candidate,
                polarity_reversal,
                {
                    "memory_type": "place",
                    "canonical_text": "the user lives in Paris",
                    "evidence_quote": "Please remember",
                    "claim_key": "place:home",
                    "retrieval_facets": ["Paris"],
                    "salience": 0.9,
                    "confidence": 0.9,
                    "emotional_weight": 0.0,
                    "stability": "durable",
                    "is_correction": False,
                },
            ],
            "episode": {
                "worthy": not correction and not initial_preference,
                "title": (
                    "sunday tea ritual" if not correction and not initial_preference else None
                ),
                "summary": (
                    "the user named Sunday jasmine tea as a ritual worth carrying forward."
                    if not correction and not initial_preference
                    else None
                ),
                "emotional_tags": ["warmth"],
                "evidence_quotes": (
                    [
                        "Please remember that my Sunday ritual is jasmine tea because it makes "
                        "me feel calm."
                    ]
                    if not correction and not initial_preference
                    else []
                ),
                "source_message_ids": [],
                "salience": 0.82 if not correction and not initial_preference else 0.0,
            },
            "relationship": {
                "signals": (["shared_ritual"] if not correction and not initial_preference else []),
                "confidence": 0.88 if not correction and not initial_preference else 0.0,
                "evidence": (
                    [
                        {
                            "event_type": "ritual",
                            "summary": "The user described a recurring personal ritual.",
                            "evidence_quote": (
                                "Please remember that my Sunday ritual is jasmine tea because "
                                "it makes me feel calm."
                            ),
                            "confidence": 0.88,
                            "significance": 0.75,
                        }
                    ]
                    if not correction and not initial_preference
                    else []
                ),
            },
            "referenced_memory_ids": [],
        }
        return LLMGeneration(
            content=json.dumps(report),
            provider=self.name,
            model=self.model,
            finish_reason="stop",
            usage=TokenUsage(input_tokens=120, output_tokens=90, total_tokens=210),
        )


def test_grounding_rejects_polarity_reversal_with_shared_vocabulary() -> None:
    assert _claim_is_grounded(
        "the user dislikes jasmine tea",
        "I don't like jasmine tea.",
    )
    assert not _claim_is_grounded(
        "the user likes jasmine tea",
        "I don't like jasmine tea.",
    )
    assert _claim_is_grounded(
        "the user prefers mint tea",
        "I don't like coffee; I prefer mint tea.",
    )


async def test_grounded_cognition_creates_a_receipted_memory_and_episode(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await auth_headers(client)
    character = (await client.get("/characters", headers=headers)).json()[0]
    character_id = character["id"]
    conversation = await client.post(
        "/conversations",
        json={"character_id": character_id},
        headers=headers,
    )
    monkeypatch.setattr(
        scheduler,
        "get_llm_provider",
        lambda settings=None: GroundedCognitionProvider(),
    )

    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation.json()["id"],
            "content": (
                "Please remember that my Sunday ritual is jasmine tea because it makes me "
                "feel calm."
            ),
        },
        headers=headers,
    )
    assert chat.status_code == 200

    memories = await client.get(f"/characters/{character_id}/memories", headers=headers)
    assert memories.status_code == 200
    assert len(memories.json()) == 1
    assert memories.json()[0]["claim_key"] == "routine:sunday-tea"
    assert memories.json()[0]["scope"] == "general"
    assert "Paris" not in memories.json()[0]["content"]
    assert memories.json()[0]["emotional_context_json"] == {
        "feeling": "feel calm",
        "meaning": "Sunday ritual",
    }
    entities = await client.get(
        f"/characters/{character_id}/memories/entities",
        headers=headers,
    )
    assert any(
        entity["entity_type"] == "routine" and entity["name"] == "Sunday ritual"
        for entity in entities.json()
    )

    journals = await client.get(f"/characters/{character_id}/journals", headers=headers)
    assert journals.status_code == 200
    assert len(journals.json()) == 1
    assert journals.json()[0]["journal_type"] == "grounded_episode"
    assert journals.json()[0]["scope"] == "general"

    assistant_id = chat.json()["assistant_message"]["id"]
    receipt = await client.get(
        f"/chat/turns/{assistant_id}/continuity",
        headers=headers,
    )
    assert receipt.status_code == 200
    assert receipt.json()["state"] == "ready"
    assert set(receipt.json()["change_labels"]) == {
        "remembered",
        "moment",
        "relationship",
    }


async def test_explicit_grounded_correction_supersedes_a_claim(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await auth_headers(client)
    character = (await client.get("/characters", headers=headers)).json()[0]
    character_id = character["id"]
    conversation = await client.post(
        "/conversations",
        json={"character_id": character_id},
        headers=headers,
    )
    monkeypatch.setattr(
        scheduler,
        "get_llm_provider",
        lambda settings=None: GroundedCognitionProvider(),
    )

    first = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation.json()["id"],
            "content": "Please remember that I prefer jasmine tea.",
        },
        headers=headers,
    )
    assert first.status_code == 200

    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation.json()["id"],
            "content": "Actually, I prefer mint tea rather than jasmine tea.",
        },
        headers=headers,
    )
    assert chat.status_code == 200

    active = await client.get(f"/characters/{character_id}/memories", headers=headers)
    forgotten = await client.get(
        f"/characters/{character_id}/memories?state=forgotten",
        headers=headers,
    )
    assert [item["content"] for item in active.json()] == ["the user prefers mint tea"]
    assert [item["content"] for item in forgotten.json()] == ["the user prefers jasmine tea"]
    assistant_id = chat.json()["assistant_message"]["id"]
    receipt = await client.get(
        f"/chat/turns/{assistant_id}/continuity",
        headers=headers,
    )
    assert "corrected" in receipt.json()["change_labels"]
