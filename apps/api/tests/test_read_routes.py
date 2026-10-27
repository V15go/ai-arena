from fastapi.testclient import TestClient

from app.db.session import SessionFactory
from app.models import Approval, ExecutionEvent, TaskAttempt, WorkflowRun
from app.orchestrator import Orchestrator
from app.schemas.enums import RunStatus, TaskStatus
from tests.conftest import AUTH, seed_run


async def test_run_detail_includes_tasks_and_attempts(
    client: TestClient, session_factory: SessionFactory
) -> None:
    run_id, task_id = await seed_run(session_factory)
    async with session_factory() as s, s.begin():
        s.add(
            TaskAttempt(
                id="att_1",
                task_id=task_id,
                attempt_no=1,
                status="FAILED",
                failure_class="TEST_FAILURE",
            )
        )
        s.add(
            Approval(
                id="apr_1", run_id=run_id, task_id=task_id, action="EXPORT_PATCH", payload_hash="h"
            )
        )
    res = client.get(f"/api/v1/runs/{run_id}", headers=AUTH)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "QUEUED"
    assert body["pendingApprovalId"] == "apr_1"
    assert body["tasks"][0]["taskKey"] == "investigate"
    assert body["tasks"][0]["attempts"][0]["failureClass"] == "TEST_FAILURE"


async def test_events_are_ordered_and_resumable_by_seq(
    client: TestClient, session_factory: SessionFactory
) -> None:
    run_id, task_id = await seed_run(session_factory)
    orch = Orchestrator(session_factory)
    await orch.transition_run(run_id, RunStatus.RUNNING, "go")
    await orch.transition_task(task_id, TaskStatus.READY, "ready")
    await orch.transition_task(task_id, TaskStatus.RUNNING, "start")
    full = client.get(f"/api/v1/runs/{run_id}/events", headers=AUTH).json()
    assert [e["seq"] for e in full["items"]] == [1, 2, 3]
    resumed = client.get(f"/api/v1/runs/{run_id}/events", headers=AUTH, params={"after": 2}).json()
    assert [e["seq"] for e in resumed["items"]] == [3]
    paged = client.get(f"/api/v1/runs/{run_id}/events", headers=AUTH, params={"limit": 2}).json()
    assert len(paged["items"]) == 2 and paged["nextCursor"] == "2"


async def test_keyset_pagination_over_runs(
    client: TestClient, session_factory: SessionFactory
) -> None:
    await seed_run(session_factory)
    async with session_factory() as s, s.begin():
        for i in range(2, 5):
            s.add(WorkflowRun(id=f"run_{i}", workflow_version_id="wfv_1", idempotency_key=f"k-{i}"))
    first = client.get("/api/v1/runs", headers=AUTH, params={"limit": 2}).json()
    assert [r["id"] for r in first["items"]] == ["run_4", "run_3"]
    second = client.get(
        "/api/v1/runs", headers=AUTH, params={"limit": 2, "cursor": first["nextCursor"]}
    ).json()
    assert [r["id"] for r in second["items"]] == ["run_2", "run_1"]
    assert second["nextCursor"] is None


async def test_approvals_filter_by_status(
    client: TestClient, session_factory: SessionFactory
) -> None:
    run_id, task_id = await seed_run(session_factory)
    async with session_factory() as s, s.begin():
        s.add(
            Approval(
                id="apr_1", run_id=run_id, task_id=task_id, action="EXPORT_PATCH", payload_hash="h"
            )
        )
        s.add(
            Approval(
                id="apr_2",
                run_id=run_id,
                task_id=task_id,
                action="EXPORT_PATCH",
                payload_hash="h",
                status="APPROVED",
            )
        )
    pending = client.get("/api/v1/approvals", headers=AUTH, params={"status": "PENDING"}).json()
    assert [a["id"] for a in pending["items"]] == ["apr_1"]
    assert (
        client.get("/api/v1/approvals", headers=AUTH, params={"status": "BOGUS"}).status_code == 422
    )


async def test_workflow_versions_and_404s(
    client: TestClient, session_factory: SessionFactory
) -> None:
    await seed_run(session_factory)
    wf = client.get("/api/v1/workflows/wf_1", headers=AUTH).json()
    assert wf["repositoryId"] == "sample" and wf["latestVersion"] == 0
    assert client.get("/api/v1/workflows/wf_x/versions", headers=AUTH).status_code == 404
    assert client.get("/api/v1/runs/run_x/events", headers=AUTH).status_code == 404


def test_empty_lists(client: TestClient) -> None:
    for path in ("agents", "workflows", "approvals", "memories"):
        assert client.get(f"/api/v1/{path}", headers=AUTH).json() == {
            "items": [],
            "nextCursor": None,
        }


async def test_event_model_reflects_db_rows(
    client: TestClient, session_factory: SessionFactory
) -> None:
    run_id, _ = await seed_run(session_factory)
    async with session_factory() as s, s.begin():
        s.add(
            ExecutionEvent(
                id="evt_x", run_id=run_id, seq=1, type="TASK_LOG", message="hi", data={"a": 1}
            )
        )
    item = client.get(f"/api/v1/runs/{run_id}/events", headers=AUTH).json()["items"][0]
    assert item["runId"] == run_id and item["data"] == {"a": 1}
