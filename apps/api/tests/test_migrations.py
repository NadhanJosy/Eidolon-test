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
        journal_table_exists = (
            await connection.execute(
                text("select to_regclass('public.episodic_journals') is not null")
            )
        ).scalar_one()

    assert revision == "0002_level2_state"
    assert {"importance", "pinned", "contradiction_group"}.issubset(memory_columns)
    assert {"mood", "conflict_state", "repair_needed", "tags_json"}.issubset(relationship_columns)
    assert journal_table_exists is True
