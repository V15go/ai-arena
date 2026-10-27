"""Schema/migration drift and OpenAPI contract drift checks. Synchronous on purpose:
Alembic's env.py starts its own event loop."""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db.base import Base
from app.models import Agent  # noqa: F401
from app.scripts.export_openapi import build_openapi, render

API_DIR = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "agents",
    "workflows",
    "workflow_versions",
    "workflow_runs",
    "tasks",
    "task_attempts",
    "execution_events",
    "approvals",
    "workflow_memories",
    "evaluation_cases",
    "evaluation_results",
}


def _config(url: str) -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_migration_matches_models_with_no_drift(tmp_path: Path) -> None:
    db = tmp_path / "m.db"
    command.upgrade(_config(f"sqlite+aiosqlite:///{db.as_posix()}"), "head")
    engine = create_engine(f"sqlite:///{db.as_posix()}")
    try:
        assert set(inspect(engine).get_table_names()) >= EXPECTED_TABLES
        with engine.connect() as conn:
            diff = compare_metadata(
                MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata
            )
        assert diff == [], f"models and migrations drifted: {diff}"
    finally:
        engine.dispose()


def test_downgrade_removes_everything(tmp_path: Path) -> None:
    db = tmp_path / "d.db"
    url = f"sqlite+aiosqlite:///{db.as_posix()}"
    command.upgrade(_config(url), "head")
    command.downgrade(_config(url), "base")
    engine = create_engine(f"sqlite:///{db.as_posix()}")
    try:
        assert EXPECTED_TABLES.isdisjoint(set(inspect(engine).get_table_names()))
    finally:
        engine.dispose()


def test_postgres_offline_sql_uses_jsonb_and_arrays(capsys: pytest.CaptureFixture[str]) -> None:
    command.upgrade(_config("postgresql://u:p@localhost/db"), "head", sql=True)
    sql = capsys.readouterr().out
    assert "JSONB" in sql and "TEXT[]" in sql
    for table in EXPECTED_TABLES:
        assert f"CREATE TABLE {table}" in sql


def test_memory_table_requires_evidence_and_source_attempt() -> None:
    cols = Base.metadata.tables["workflow_memories"].c
    assert not cols["evidence"].nullable and not cols["source_attempt_id"].nullable


def test_committed_openapi_is_current(repo_root: Path) -> None:
    committed = repo_root / "packages" / "contracts" / "openapi.json"
    assert committed.exists(), "run `pnpm contracts:generate`"
    assert committed.read_text(encoding="utf-8") == render(build_openapi()), (
        "packages/contracts/openapi.json is stale; run `pnpm contracts:generate`"
    )


def test_openapi_covers_the_resource_schemas() -> None:
    schemas = set(build_openapi()["components"]["schemas"])
    for name in (
        "AgentOut",
        "WorkflowVersionOut",
        "RunDetail",
        "ExecutionEventOut",
        "ApprovalOut",
        "MemoryRecordOut",
        "TaskAttemptOut",
    ):
        assert name in schemas
