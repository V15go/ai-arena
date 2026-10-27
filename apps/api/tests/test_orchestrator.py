import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionFactory
from app.models import ExecutionEvent, Task, WorkflowRun
from app.orchestrator import InvalidTransitionError, Orchestrator, append_event
from app.orchestrator import state_machine as sm
from app.schemas.enums import EventType, RunStatus, TaskStatus
from tests.conftest import seed_run


async def events(factory: SessionFactory, run_id: str) -> list[ExecutionEvent]:
    async with factory() as s:
        return list(
            (
                await s.scalars(
                    select(ExecutionEvent)
                    .where(ExecutionEvent.run_id == run_id)
                    .order_by(ExecutionEvent.seq)
                )
            ).all()
        )


async def test_run_transition_writes_status_and_event_together(
    session_factory: SessionFactory,
) -> None:
    run_id, _ = await seed_run(session_factory)
    orch = Orchestrator(session_factory)
    ev = await orch.transition_run(run_id, RunStatus.RUNNING, "go")
    assert (ev.seq, ev.type) == (1, EventType.RUN_STARTED.value)
    await orch.transition_run(run_id, RunStatus.SUCCEEDED, "done")
    async with session_factory() as s:
        run = await s.get(WorkflowRun, run_id)
        assert run is not None
        assert run.status == "SUCCEEDED"
        assert run.started_at is not None and run.finished_at is not None
    log = await events(session_factory, run_id)
    assert [e.seq for e in log] == [1, 2]
    assert log[1].data["from"] == "RUNNING" and log[1].data["to"] == "SUCCEEDED"


async def test_illegal_transition_changes_nothing(session_factory: SessionFactory) -> None:
    run_id, _ = await seed_run(session_factory)
    orch = Orchestrator(session_factory)
    with pytest.raises(InvalidTransitionError):
        await orch.transition_run(run_id, RunStatus.SUCCEEDED, "skip ahead")  # QUEUED -> SUCCEEDED
    async with session_factory() as s:
        run = await s.get(WorkflowRun, run_id)
        assert run is not None and run.status == "QUEUED"
    assert await events(session_factory, run_id) == []


async def test_terminal_states_are_final(session_factory: SessionFactory) -> None:
    run_id, _ = await seed_run(session_factory)
    orch = Orchestrator(session_factory)
    await orch.transition_run(run_id, RunStatus.CANCELLED, "stop")
    with pytest.raises(InvalidTransitionError):
        await orch.transition_run(run_id, RunStatus.RUNNING, "zombie")


async def test_task_transition_uses_run_event_sequence(session_factory: SessionFactory) -> None:
    run_id, task_id = await seed_run(session_factory)
    orch = Orchestrator(session_factory)
    await orch.transition_run(run_id, RunStatus.RUNNING, "go")
    await orch.transition_task(task_id, TaskStatus.READY, "ready")
    ev = await orch.transition_task(task_id, TaskStatus.RUNNING, "start")
    assert ev.seq == 3 and ev.task_id == task_id and ev.type == "TASK_STARTED"
    async with session_factory() as s:
        task = await s.get(Task, task_id)
        assert task is not None and task.started_at is not None


async def test_failed_event_write_rolls_back_the_status_change(
    session_factory: SessionFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id, _ = await seed_run(session_factory)
    orch = Orchestrator(session_factory)
    await orch.transition_run(run_id, RunStatus.RUNNING, "go")

    async def broken_append(*args: object, **kwargs: object) -> None:
        raise RuntimeError("event store unavailable")

    monkeypatch.setattr("app.orchestrator.orchestrator.append_event", broken_append)
    with pytest.raises(RuntimeError):
        await orch.transition_run(run_id, RunStatus.FAILED, "boom")
    async with session_factory() as s:
        run = await s.get(WorkflowRun, run_id)
        assert run is not None
        assert run.status == "RUNNING" and run.finished_at is None  # no status without its event


async def test_duplicate_sequence_numbers_are_rejected_by_the_database(
    session_factory: SessionFactory,
) -> None:
    run_id, _ = await seed_run(session_factory)
    async with session_factory() as s, s.begin():
        s.add(ExecutionEvent(id="evt_a", run_id=run_id, seq=1, type="TASK_LOG", message="a"))
    with pytest.raises(IntegrityError):
        async with session_factory() as s, s.begin():
            s.add(ExecutionEvent(id="evt_b", run_id=run_id, seq=1, type="TASK_LOG", message="b"))


async def test_attempt_budget_is_never_overshot(session_factory: SessionFactory) -> None:
    run_id, _ = await seed_run(session_factory)
    orch = Orchestrator(session_factory)
    results = [await orch.consume_attempt(run_id, 3) for _ in range(5)]
    assert results == [True, True, True, False, False]
    async with session_factory() as s:
        total = await s.scalar(select(WorkflowRun.total_attempts).where(WorkflowRun.id == run_id))
        assert total == 3


async def test_concurrent_budget_consumers_stay_within_limit(
    session_factory: SessionFactory,
) -> None:
    run_id, _ = await seed_run(session_factory)
    orch = Orchestrator(session_factory)
    results = await asyncio.gather(*(orch.consume_attempt(run_id, 4) for _ in range(10)))
    assert sum(results) == 4


async def test_record_event_and_append_helper_keep_seq_gapless(
    session_factory: SessionFactory,
) -> None:
    run_id, task_id = await seed_run(session_factory)
    orch = Orchestrator(session_factory)
    await orch.record_event(run_id, EventType.TASK_LOG, "one", task_id=task_id)
    async with session_factory() as s, s.begin():
        await append_event(s, run_id, EventType.TASK_LOG, "two")
    async with session_factory() as s:
        count = await s.scalar(select(func.count()).select_from(ExecutionEvent))
    assert count == 2
    assert [e.seq for e in await events(session_factory, run_id)] == [1, 2]


def test_state_machine_tables_are_total_and_terminals_are_closed() -> None:
    assert set(sm.RUN_TRANSITIONS) == set(RunStatus)
    assert set(sm.TASK_TRANSITIONS) == set(TaskStatus)
    assert {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED} == sm.TERMINAL_RUN
    # A run may only wait for approval from RUNNING, and can resume only to RUNNING.
    assert sm.can_transition_run(RunStatus.RUNNING, RunStatus.WAITING_APPROVAL)
    assert not sm.can_transition_run(RunStatus.QUEUED, RunStatus.WAITING_APPROVAL)
    assert not sm.can_transition_run(RunStatus.WAITING_APPROVAL, RunStatus.SUCCEEDED)
