from __future__ import annotations

from sqlalchemy import inspect, text

from src.paths import RuntimePaths
from src.services.persistence.database import Database
from src.services.persistence.migrations import upgrade_database


async def _table_names(database: Database) -> set[str]:
    async with database.engine.connect() as connection:
        return await connection.run_sync(lambda sync_connection: set(inspect(sync_connection).get_table_names()))


async def test_empty_database_migrates_idempotently_and_has_expected_schema(empty_database: Database) -> None:
    assert await _table_names(empty_database) == set()
    await upgrade_database(empty_database.engine)
    await upgrade_database(empty_database.engine)
    assert await _table_names(empty_database) == {
        "alembic_version",
        "branches",
        "belief_evidence",
        "beliefs",
        "canon_facts",
        "character_states",
        "characters",
        "claim_links",
        "derived_jobs",
        "derived_artifacts",
        "emotional_tensions",
        "event_participants",
        "events",
        "knowledge_claims",
        "jobs",
        "memory_embeddings",
        "narrative_hooks",
        "narrative_threads",
        "observations",
        "outbox_events",
        "playthroughs",
        "relationship_changes",
        "relationships",
        "retrieval_traces",
        "snapshots",
        "turns",
        "worlds",
    }

    async with empty_database.engine.connect() as connection:
        assert (await connection.scalar(text("PRAGMA foreign_keys"))) == 1
        assert (await connection.scalar(text("PRAGMA journal_mode"))).lower() == "wal"
        assert (await connection.scalar(text("PRAGMA busy_timeout"))) == 5_000


def test_runtime_paths_are_project_anchored_and_test_overridable(tmp_path) -> None:
    paths = RuntimePaths(tmp_path / "runtime")
    paths.ensure_directories()

    assert paths.root == (tmp_path / "runtime").resolve()
    assert paths.game_db == paths.root / "game.db"
    assert paths.checkpoints_db == paths.root / "checkpoints.db"
    assert paths.logs.is_dir()
    assert paths.exports.is_dir()
