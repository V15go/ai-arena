from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import AuthDep, CursorParam, LimitParam, SessionDep
from app.models import Approval, ExecutionEvent, Task, TaskAttempt, WorkflowRun
from app.repositories.base import get_or_404, list_page
from app.schemas.common import Page
from app.schemas.enums import ApprovalStatus
from app.schemas.events import ExecutionEventOut
from app.schemas.runs import RunDetail, RunOut, TaskAttemptOut, TaskOut

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=Page[RunOut], operation_id="listRuns")
async def list_runs(
    _: AuthDep, session: SessionDep, limit: LimitParam = 20, cursor: CursorParam = None
) -> Page[RunOut]:
    rows, next_cursor = await list_page(
        session, WorkflowRun, WorkflowRun.id, limit=limit, cursor=cursor
    )
    return Page[RunOut](items=[RunOut.model_validate(r) for r in rows], next_cursor=next_cursor)


@router.get("/{run_id}", response_model=RunDetail, operation_id="getRun")
async def get_run(run_id: str, _: AuthDep, session: SessionDep) -> RunDetail:
    run = await get_or_404(session, WorkflowRun, run_id, "Run")
    tasks = (
        await session.scalars(select(Task).where(Task.run_id == run_id).order_by(Task.position))
    ).all()
    attempts_by_task: dict[str, list[TaskAttemptOut]] = defaultdict(list)
    if tasks:
        attempts = await session.scalars(
            select(TaskAttempt)
            .where(TaskAttempt.task_id.in_([t.id for t in tasks]))
            .order_by(TaskAttempt.attempt_no)
        )
        for attempt in attempts:
            attempts_by_task[attempt.task_id].append(TaskAttemptOut.model_validate(attempt))
    pending_id = await session.scalar(
        select(Approval.id).where(
            Approval.run_id == run_id, Approval.status == ApprovalStatus.PENDING.value
        )
    )
    detail = RunDetail.model_validate(run)
    detail.tasks = [
        TaskOut.model_validate(t).model_copy(update={"attempts": attempts_by_task[t.id]})
        for t in tasks
    ]
    detail.pending_approval_id = pending_id
    return detail


@router.get(
    "/{run_id}/events", response_model=Page[ExecutionEventOut], operation_id="listRunEvents"
)
async def list_run_events(
    run_id: str,
    _: AuthDep,
    session: SessionDep,
    after: Annotated[int, Query(ge=0, description="Return events with seq greater than this")] = 0,
    limit: LimitParam = 100,
) -> Page[ExecutionEventOut]:
    """Persisted event log, ordered by seq. The SSE stream (slice 7) replays from this table."""
    await get_or_404(session, WorkflowRun, run_id, "Run")
    rows = (
        await session.scalars(
            select(ExecutionEvent)
            .where(ExecutionEvent.run_id == run_id, ExecutionEvent.seq > after)
            .order_by(ExecutionEvent.seq)
            .limit(limit + 1)
        )
    ).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return Page[ExecutionEventOut](
        items=[ExecutionEventOut.model_validate(r) for r in rows],
        next_cursor=str(rows[-1].seq) if has_more else None,
    )
