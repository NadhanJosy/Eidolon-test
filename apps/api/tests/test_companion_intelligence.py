from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from helpers import auth_headers
from httpx import AsyncClient

from app.companion.domain import CharacterSoul, ResponseCheckContext, ResponsePlan
from app.companion.emotion import (
    apply_emotional_turn,
    emotional_posture,
    project_emotional_state,
)
from app.companion.perception import infer_turn_perception
from app.companion.planning import plan_response, relationship_behavioral_stage
from app.companion.quality import evaluate_response
from app.models import Character, Message, RelationshipState, User
from app.services.companion_evaluation import EVALUATION_DIMENSIONS, score_companion_reply
from app.services.memory import analyze_memory_candidate
from app.services.prompt import assemble_prompt


@pytest.mark.parametrize(
    ("message", "intent", "tone"),
    (
        ("Hey.", "connect", "neutral"),
        ("Haha, that was shameless. Tease me again.", "play", "playful"),
        ("I am overwhelmed and exhausted.", "support", "anxious"),
        ("I am angry at you for what you said.", "conflict", "sharp"),
        ("I'm sorry. That was my fault.", "repair", "neutral"),
        ("Good news, I got the role!", "celebrate", "bright"),
        ("What should I do about this choice?", "advise", "neutral"),
    ),
)
def test_turn_perception_covers_core_companion_moments(
    message: str,
    intent: str,
    tone: str,
) -> None:
    perception = infer_turn_perception(message, recent_messages=[], journals=[])

    assert perception.intent == intent
    assert perception.tone == tone


def test_response_planning_varies_strategy_and_prevents_interrogation() -> None:
    relationship = RelationshipState(
        user_id=uuid.uuid4(),
        character_id=uuid.uuid4(),
        familiarity=8,
        trust=2,
        emotional_state_json={},
        metadata_json={"evidence_counts": {"exchanges": 12, "meaningful_events": 2}},
    )
    recent = [
        Message(conversation_id=uuid.uuid4(), role="assistant", content="What happened?"),
        Message(conversation_id=uuid.uuid4(), role="assistant", content="What mattered most?"),
    ]
    perception = infer_turn_perception(
        "I am exhausted and do not want advice.",
        recent_messages=recent,
        journals=[],
    )
    plan = plan_response(
        soul=CharacterSoul(),
        perception=perception,
        emotion=project_emotional_state(relationship),
        relationship=relationship,
        memories=[],
        journals=[],
        recent_messages=recent,
        content_mode="sfw",
        safety_status={"effective_mode": "sfw"},
    )

    assert plan.strategy == "listen"
    assert plan.secondary_strategy == "comfort"
    assert plan.should_ask_question is False
    assert plan.desired_length == "short"
    assert "ending with a question" in plan.avoid


@pytest.mark.parametrize(
    ("message", "strategy"),
    (
        ("Don't just agree with me; push back.", "challenge"),
        ("Tell me what you think about quiet cities.", "disclose"),
        ("I'm angry at you for what you said.", "apologise"),
    ),
)
def test_requested_distinctive_strategies_are_selected(
    message: str,
    strategy: str,
) -> None:
    relationship = RelationshipState(emotional_state_json={})
    perception = infer_turn_perception(message, recent_messages=[], journals=[])

    plan = plan_response(
        soul=CharacterSoul(),
        perception=perception,
        emotion=project_emotional_state(relationship),
        relationship=relationship,
        memories=[],
        journals=[],
        recent_messages=[],
        content_mode="sfw",
        safety_status={"effective_mode": "sfw"},
    )

    assert plan.strategy == strategy


def test_emotional_continuity_is_bounded_decays_and_repairs_gradually() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    relationship = RelationshipState(
        user_id=uuid.uuid4(),
        character_id=uuid.uuid4(),
        emotional_state_json={},
    )
    conflict = infer_turn_perception(
        "I am angry at you for what you said.",
        recent_messages=[],
        journals=[],
        now=now,
    )
    hurt = apply_emotional_turn(relationship, conflict, now=now)
    apology = infer_turn_perception(
        "I'm sorry. That was my fault.",
        recent_messages=[],
        journals=[],
        now=now + timedelta(hours=1),
    )
    repairing = apply_emotional_turn(relationship, apology, now=now + timedelta(hours=1))
    decayed = project_emotional_state(relationship, now=now + timedelta(days=30))

    assert 0 < repairing.hurt < hurt.hurt
    assert repairing.guardedness < hurt.guardedness
    assert repairing.repair_openness > hurt.repair_openness
    assert "hurt but open" in emotional_posture(repairing, repair_needed=False)
    assert decayed.hurt < repairing.hurt
    assert all(
        0 <= value <= 1
        for value in (
            decayed.amusement,
            decayed.concern,
            decayed.warmth,
            decayed.hurt,
            decayed.guardedness,
            decayed.repair_openness,
        )
    )


@pytest.mark.parametrize(
    ("message", "memory_type"),
    (
        ("Remember that my friend Rowan lives nearby.", "person"),
        ("Remember that I keep overcommitting when work gets loud.", "theme"),
        ("Remember that our ritual is tea after difficult meetings.", "shared_lore"),
        ("Please remember my boundary: do not give advice unless I ask.", "boundary"),
        ("Remember that I promise to finish the draft on Friday.", "promise"),
        ("Remember that my favorite weather is quiet rain.", "preference"),
    ),
)
def test_durable_memory_categories_are_separate(message: str, memory_type: str) -> None:
    decision = analyze_memory_candidate(message)

    assert decision.accepted is True
    assert decision.memory_type == memory_type


def test_prompt_compiles_soul_modules_without_raw_json_or_emotion_meters() -> None:
    user_id = uuid.uuid4()
    soul = CharacterSoul(
        identity="A stubborn night-owl cartographer.",
        worldview="Maps matter because attention changes a place.",
        temperament="Restless, perceptive, and slow to concede a point.",
        humour="Wry and fond of precise absurdity.",
        speech_rhythm="Clipped when amused; winding when curious.",
        affection_style="Shows care by noticing overlooked details.",
        conflict_style="Argues plainly, then returns to repair without theatrics.",
        initiative_style="Introduces odd observations and small thought experiments.",
    )
    character = Character(
        owner_user_id=user_id,
        name="Mara",
        soul_json=soul.model_dump(mode="json"),
        boundaries_json={"secret_raw_field": "must never be dumped"},
    )
    bundle = assemble_prompt(
        user=User(id=user_id, email="soul@example.com", password_hash="unused"),
        character=character,
        relationship=RelationshipState(
            user_id=user_id,
            character_id=uuid.uuid4(),
            emotional_state_json={"warmth": 0.9, "hurt": 0.2},
        ),
        memories=[],
        recent_messages=[],
        current_message="The city feels different tonight.",
        content_mode="sfw",
    )

    assert "A stubborn night-owl cartographer" in bundle.prompt
    assert "Clipped when amused" in bundle.prompt
    assert "secret_raw_field" not in bundle.prompt
    assert '"warmth": 0.9' not in bundle.prompt
    assert "/100" not in bundle.prompt


def test_long_absence_and_relationship_progression_are_behavioural() -> None:
    now = datetime(2026, 6, 1, tzinfo=UTC)
    recent = [
        Message(
            conversation_id=uuid.uuid4(),
            role="assistant",
            content="Take care tonight.",
            created_at=now - timedelta(days=30),
        )
    ]
    perception = infer_turn_perception(
        "Hey, it has been a while.",
        recent_messages=recent,
        journals=[],
        now=now,
    )
    relationship = RelationshipState(
        familiarity=9,
        trust=5,
        metadata_json={"evidence_counts": {"exchanges": 31, "meaningful_events": 5}},
    )
    plan = plan_response(
        soul=CharacterSoul(),
        perception=perception,
        emotion=project_emotional_state(relationship, now=now),
        relationship=relationship,
        memories=[],
        journals=[],
        recent_messages=recent,
        content_mode="sfw",
        safety_status={},
    )

    assert perception.time_gap == "long_absence"
    assert "no guilt" in plan.opening
    assert "claims of waiting or offline awareness" in plan.avoid
    assert relationship_behavioral_stage(relationship).startswith("established bond")


def test_response_checks_catch_repetition_questions_and_invented_memory() -> None:
    plan = ResponsePlan(
        strategy="share_the_moment",
        secondary_strategy=None,
        should_ask_question=False,
        desired_length="short",
        rhythm="steady",
        opening="begin concretely",
    )
    context = ResponseCheckContext(
        plan=plan,
        recent_assistant_messages=("I am glad you are here. We can take this slowly.",),
        recent_transcript=(),
        selected_memory_contents=(),
        uncertain_memory_contents=(),
        current_user_message="Hello.",
        known_character_name="Mara",
    )
    evaluation = evaluate_response(
        "I am glad you are here. I remember when we spent our anniversary by the lake?",
        context,
    )
    scores = score_companion_reply(
        "I am glad you are here. I remember when we spent our anniversary by the lake?",
        context,
    )

    assert "repeated_opening" in evaluation.violations
    assert "unplanned_trailing_question" in evaluation.violations
    assert "unsupported_memory_claim" in evaluation.violations
    assert evaluation.passed is False
    assert set(EVALUATION_DIMENSIONS).issubset(scores.as_dict())
    assert scores.memory_precision == 0
    assert scores.repetition <= 0.5


def test_response_check_requires_uncertainty_for_conflicting_memory() -> None:
    plan = ResponsePlan(
        strategy="reminisce",
        secondary_strategy=None,
        should_ask_question=False,
        desired_length="short",
        rhythm="steady",
        opening="use the selected callback carefully",
    )
    context = ResponseCheckContext(
        plan=plan,
        recent_assistant_messages=(),
        recent_transcript=(),
        selected_memory_contents=("User prefers coffee every morning.",),
        uncertain_memory_contents=("User prefers coffee every morning.",),
        current_user_message="What do I usually drink?",
        known_character_name="Mara",
    )

    asserted = evaluate_response("You prefer coffee every morning.", context)
    qualified = evaluate_response(
        "Maybe it is coffee in the mornings, but I am not certain.", context
    )

    assert "unqualified_memory_contradiction" in asserted.violations
    assert asserted.passed is False
    assert "unqualified_memory_contradiction" not in qualified.violations


def test_response_check_detects_obvious_tone_drift() -> None:
    context = ResponseCheckContext(
        plan=ResponsePlan(
            strategy="comfort",
            secondary_strategy="listen",
            should_ask_question=False,
            desired_length="short",
            rhythm="quiet",
            opening="notice one specific cue",
            tone="quietly concerned",
        ),
        recent_assistant_messages=(),
        recent_transcript=(),
        selected_memory_contents=(),
        uncertain_memory_contents=(),
        current_user_message="I feel awful.",
        known_character_name="Mara",
    )

    evaluation = evaluate_response("Woohoo!! Cheer up, it is not a big deal!", context)

    assert "tone_drift" in evaluation.violations
    assert evaluation.tone_aligned is False


async def test_character_soul_is_editable_and_returned_as_a_typed_profile(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    character = (await client.get("/characters", headers=headers)).json()[0]

    response = await client.patch(
        f"/characters/{character['id']}",
        json={
            "soul_json": {
                "identity": "A patient but stubborn amateur astronomer.",
                "worldview": "Attention is a form of devotion.",
                "temperament": "Watchful, curious, and willing to disagree.",
                "humour": "Dry, specific, and occasionally ridiculous.",
                "speech_rhythm": "Brief when moved; more expansive when fascinated.",
                "affection_style": "Shows care through remembered details.",
                "conflict_style": "Names hurt plainly and repairs without theatrics.",
                "initiative_style": "Brings back unfinished ideas and odd observations.",
                "relationship_path": "friendship",
            }
        },
        headers=headers,
    )

    assert response.status_code == 200
    soul = response.json()["soul_json"]
    assert soul["worldview"] == "Attention is a form of devotion."
    assert soul["temperament"].endswith("willing to disagree.")
    assert soul["relationship_path"] == "friendship"


async def test_multiturn_companion_pipeline_keeps_plan_private_and_varies_questions(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    turns = (
        "Hey.",
        "Haha, that was shameless. Tease me again.",
        "I am overwhelmed and do not want advice.",
        "I am angry and upset about how that went.",
        "I'm sorry. That was my fault.",
        "Remember that my favorite weather is quiet rain.",
    )
    replies: list[dict] = []
    for turn in turns:
        response = await client.post(
            "/chat/messages",
            json={"conversation_id": conversation_id, "content": turn},
            headers=headers,
        )
        assert response.status_code == 200
        assistant = response.json()["assistant_message"]
        replies.append(assistant)
        assert "Private response plan" not in assistant["content"]
        assert "response_plan" not in assistant["metadata_json"]
        assert assistant["metadata_json"]["response_quality"]["boundary_safe"] is True

    trailing_questions = sum(reply["content"].rstrip().endswith("?") for reply in replies)
    assert trailing_questions < len(replies) / 2

    debug = await client.get(f"/debug/conversation/{conversation_id}", headers=headers)
    assert debug.status_code == 200
    orchestration = debug.json()["last_assembled_context"]["context_manifest"]["orchestration"]
    assert orchestration["intent"] in {"connect", "support"}
    assert orchestration["strategy"] in {"reminisce", "share_the_moment"}
    assert orchestration["question_planned"] is False
