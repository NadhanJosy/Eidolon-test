from __future__ import annotations

from sqlalchemy import text

from app.db.session import engine


async def test_database_is_at_head_with_level2_columns() -> None:
    async with engine.connect() as connection:
        revision = (
            await connection.execute(text("select version_num from alembic_version"))
        ).scalar_one()
        memory_columns = {
            row[0]
            for row in (
                await connection.execute(
                    text(
                        "select column_name from information_schema.columns "
                        "where table_name = 'memory_items'"
                    )
                )
            )
        }
        relationship_columns = {
            row[0]
            for row in (
                await connection.execute(
                    text(
                        "select column_name from information_schema.columns "
                        "where table_name = 'relationship_states'"
                    )
                )
            )
        }
        character_columns = {
            row[0]
            for row in (
                await connection.execute(
                    text(
                        "select column_name from information_schema.columns "
                        "where table_name = 'characters'"
                    )
                )
            )
        }
        conversation_columns = {
            row[0]
            for row in (
                await connection.execute(
                    text(
                        "select column_name from information_schema.columns "
                        "where table_name = 'conversations'"
                    )
                )
            )
        }
        journal_table_exists = (
            await connection.execute(
                text("select to_regclass('public.episodic_journals') is not null")
            )
        ).scalar_one()
        auth_throttle_columns = {
            row[0]
            for row in (
                await connection.execute(
                    text(
                        "select column_name from information_schema.columns "
                        "where table_name = 'auth_throttles'"
                    )
                )
            )
        }
        diagnostic_columns = {
            row[0]
            for row in (
                await connection.execute(
                    text(
                        "select column_name from information_schema.columns "
                        "where table_name = 'diagnostic_events'"
                    )
                )
            )
        }
        continuity_thread_columns = {
            row[0]
            for row in (
                await connection.execute(
                    text(
                        "select column_name from information_schema.columns "
                        "where table_name = 'continuity_threads'"
                    )
                )
            )
        }
        memory_evidence_exists = (
            await connection.execute(
                text("select to_regclass('public.memory_evidence') is not null")
            )
        ).scalar_one()
        memory_entities_exists = (
            await connection.execute(
                text("select to_regclass('public.memory_entities') is not null")
            )
        ).scalar_one()
        memory_entity_links_exists = (
            await connection.execute(
                text("select to_regclass('public.memory_entity_links') is not null")
            )
        ).scalar_one()

        legacy_login_throttle_exists = (
            await connection.execute(
                text("select to_regclass('public.login_throttles') is not null")
            )
        ).scalar_one()

    assert revision == "0012_living_memory"
    assert {
        "importance",
        "pinned",
        "contradiction_group",
        "forgotten_at",
        "scope",
        "claim_key",
        "retention_tier",
        "lifecycle_state",
        "sensitivity",
        "emotional_context_json",
        "novelty",
        "future_relevance",
        "reinforcement_count",
        "last_reinforced_at",
        "last_evidence_at",
        "superseded_by_id",
    }.issubset(memory_columns)
    assert memory_evidence_exists is True
    assert memory_entities_exists is True
    assert memory_entity_links_exists is True
    assert {
        "mood",
        "conflict_state",
        "repair_needed",
        "tags_json",
        "emotional_state_json",
    }.issubset(relationship_columns)
    assert "soul_json" in character_columns
    assert {"metadata_json", "last_read_at"}.issubset(conversation_columns)
    assert journal_table_exists is True
    assert auth_throttle_columns == {
        "fingerprint",
        "failed_attempts",
        "window_started_at",
        "blocked_until",
        "last_attempt_at",
    }
    assert diagnostic_columns == {
        "id",
        "user_id",
        "character_id",
        "conversation_id",
        "source",
        "operation",
        "code",
        "provider",
        "safe_message",
        "created_at",
    }
    assert {
        "id",
        "user_id",
        "character_id",
        "conversation_id",
        "source_message_id",
        "thread_kind",
        "content",
        "status",
        "salience",
        "confidence",
        "dedupe_key",
        "last_referenced_at",
        "last_proactive_at",
        "resolved_at",
        "metadata_json",
        "created_at",
        "updated_at",
    } == continuity_thread_columns
    assert legacy_login_throttle_exists is False
