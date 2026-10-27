from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.db.session import SessionFactory
from app.main import create_app
from app.models import Agent, Task, Workflow, WorkflowRun, WorkflowVersion  # registers tables

TOKEN = "test-token-for-unit-tests"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {"app_env": "test", "api_auth_token": SecretStr(TOKEN)}
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> SessionFactory:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def client(session_factory: SessionFactory) -> Iterator[TestClient]:
    app = create_app(make_settings())
    app.state.session_factory = session_factory
    with TestClient(app) as c:
        yield c


@pytest.fixture
def bare_client() -> Iterator[TestClient]:
    """App with no database configured at all."""
    with TestClient(create_app(make_settings())) as c:
        yield c


async def seed_run(factory: SessionFactory, *, run_status: str = "QUEUED") -> tuple[str, str]:
    """Insert a workflow, version, run and one task; return (run_id, task_id)."""
    async with factory() as s, s.begin():
        s.add(
            Agent(
                id="investigator",
                version="1.0.0",
                definition={"taskTypes": ["INVESTIGATE"]},
                created_by="seed",
            )
        )
        s.add(Workflow(id="wf_1", name="Fix bug", owner_id="admin", repository_id="sample"))
        s.add(
            WorkflowVersion(
                id="wfv_1",
                workflow_id="wf_1",
                version=1,
                definition={},
                agent_versions={},
                policy={},
                policy_hash="h",
                goal_fingerprint="g",
                source="MODEL",
            )
        )
        s.add(
            WorkflowRun(
                id="run_1", workflow_version_id="wfv_1", status=run_status, idempotency_key="k-1"
            )
        )
        s.add(
            Task(
                id="task_1",
                run_id="run_1",
                task_key="investigate",
                type="INVESTIGATE",
                agent_id="investigator",
                agent_version="1.0.0",
                status="PENDING",
                depends_on=[],
            )
        )
    return "run_1", "task_1"


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
