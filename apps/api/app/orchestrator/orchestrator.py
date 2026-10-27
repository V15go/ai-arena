"""The sole writer of run/task status, budget counters and execution events.

Every public method is exactly one database transaction: the state change and its event
commit together or not at all. Nothing else in the codebase may assign ``.status`` on
``WorkflowRun``/``Task`` (enforced by tests/test_orchestrator_authority.py).

Slice 1 provides this transactional core only; scheduling, agents and recovery arrive in
slice 7+.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.ids import new_id
from app.db.session import SessionFactory
from app.models import ExecutionEvent, Task, WorkflowRun
from app.orchestrator import state_machine as sm
from app.schemas.enums import EventType, RunStatus, TaskStatus


def _now() -> datetime:
    return datetime.now(UTC)


async def append_event(
    session: AsyncSession,
    run_id: str,
    event_type: EventType,
    message: str,
    *,
    task_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> ExecutionEvent:
    """Allocate the next per-run sequence number and insert the event (caller owns the txn)."""
    if session.bind.dialect.name == "postgresql":
        # Serialises writers per run so seq stays gap-free; released at commit/rollback.
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"run-events:{run_id}"}
        )
    next_seq = await session.scalar(
        select(func.coalesce(func.max(ExecutionEvent.seq), 0) + 1).where(
            ExecutionEvent.run_id == run_id
        )
    )
    event = ExecutionEvent(
        id=new_id("event"),
        run_id=run_id,
        seq=next_seq or 1,
        type=event_type.value,
        task_id=task_id,
        message=message,
        data=data or {},
    )
    session.add(event)
    await session.flush()
    return event


class Orchestrator:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._factory = session_factory

    async def transition_run(
        self,
        run_id: str,
        target: RunStatus,
        message: str,
        *,
        event_type: EventType | None = None,
        data: dict[str, Any] | None = None,
    ) -> ExecutionEvent:
        async with self._factory() as session, session.begin():
            run = await session.get(WorkflowRun, run_id, with_for_update=True)
            if run is None:
                raise NotFoundError("Run")
            current = RunStatus(run.status)
            if not sm.can_transition_run(current, target):
                raise sm.InvalidTransitionError("run", current, target)
            run.status = target.value
            now = _now()
            if target is RunStatus.RUNNING and run.started_at is None:
                run.started_at = now
            if target in sm.TERMINAL_RUN:
                run.finished_at = now
            return await append_event(
                session,
                run_id,
                event_type or sm.DEFAULT_RUN_EVENT[target],
                message,
                data={"from": current.value, "to": target.value, **(data or {})},
            )

    async def transition_task(
        self,
        task_id: str,
        target: TaskStatus,
        message: str,
        *,
        event_type: EventType | None = None,
        data: dict[str, Any] | None = None,
    ) -> ExecutionEvent:
        async with self._factory() as session, session.begin():
            task = await session.get(Task, task_id, with_for_update=True)
            if task is None:
                raise NotFoundError("Task")
            current = TaskStatus(task.status)
            if not sm.can_transition_task(current, target):
                raise sm.InvalidTransitionError("task", current, target)
            task.status = target.value
            now = _now()
            if target is TaskStatus.RUNNING and task.started_at is None:
                task.started_at = now
            if target in sm.TERMINAL_TASK:
                task.finished_at = now
            return await append_event(
                session,
                task.run_id,
                event_type or sm.DEFAULT_TASK_EVENT.get(target, EventType.TASK_LOG),
                message,
                task_id=task_id,
                data={"from": current.value, "to": target.value, **(data or {})},
            )

    async def record_event(
        self,
        run_id: str,
        event_type: EventType,
        message: str,
        *,
        task_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> ExecutionEvent:
        """Append a non-transition event (log lines, memory hits, ...) in its own transaction."""
        async with self._factory() as session, session.begin():
            return await append_event(
                session, run_id, event_type, message, task_id=task_id, data=data
            )

    async def consume_attempt(self, run_id: str, max_total_attempts: int) -> bool:
        """Atomically take one unit of the run's attempt budget. False means exhausted.

        One conditional UPDATE, so concurrent tasks can never jointly overshoot the budget.
        """
        async with self._factory() as session, session.begin():
            result = await session.execute(
                update(WorkflowRun)
                .where(WorkflowRun.id == run_id, WorkflowRun.total_attempts < max_total_attempts)
                .values(total_attempts=WorkflowRun.total_attempts + 1)
            )
            return result.rowcount == 1  # type: ignore[attr-defined,no-any-return]
