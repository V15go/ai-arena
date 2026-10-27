"""Legal status transitions. Pure data + checks; no I/O."""

from app.schemas.enums import EventType, RunStatus, TaskStatus

R, T = RunStatus, TaskStatus

RUN_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    R.DRAFT: frozenset({R.QUEUED, R.CANCELLED}),
    R.QUEUED: frozenset({R.RUNNING, R.FAILED, R.CANCELLED}),
    R.RUNNING: frozenset({R.WAITING_APPROVAL, R.SUCCEEDED, R.FAILED, R.CANCELLED}),
    # A run waits for approval only while a specific approval row is PENDING.
    R.WAITING_APPROVAL: frozenset({R.RUNNING, R.FAILED, R.CANCELLED}),
    R.SUCCEEDED: frozenset(),
    R.FAILED: frozenset(),
    R.CANCELLED: frozenset(),
}

TASK_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    T.PENDING: frozenset({T.READY, T.SKIPPED, T.CANCELLED}),
    T.READY: frozenset({T.RUNNING, T.SKIPPED, T.CANCELLED}),
    # RUNNING -> READY is "retry scheduled"; FAILED is final for the task.
    T.RUNNING: frozenset({T.READY, T.WAITING_APPROVAL, T.SUCCEEDED, T.FAILED, T.CANCELLED}),
    T.WAITING_APPROVAL: frozenset({T.RUNNING, T.SUCCEEDED, T.FAILED, T.CANCELLED}),
    T.SUCCEEDED: frozenset(),
    T.FAILED: frozenset(),
    T.SKIPPED: frozenset(),
    T.CANCELLED: frozenset(),
}

TERMINAL_RUN = frozenset(s for s, nxt in RUN_TRANSITIONS.items() if not nxt)
TERMINAL_TASK = frozenset(s for s, nxt in TASK_TRANSITIONS.items() if not nxt)

DEFAULT_RUN_EVENT: dict[RunStatus, EventType] = {
    R.QUEUED: EventType.RUN_QUEUED,
    R.RUNNING: EventType.RUN_STARTED,
    R.WAITING_APPROVAL: EventType.APPROVAL_REQUESTED,
    R.SUCCEEDED: EventType.RUN_SUCCEEDED,
    R.FAILED: EventType.RUN_FAILED,
    R.CANCELLED: EventType.RUN_CANCELLED,
}

DEFAULT_TASK_EVENT: dict[TaskStatus, EventType] = {
    T.READY: EventType.TASK_READY,
    T.RUNNING: EventType.TASK_STARTED,
    T.SUCCEEDED: EventType.TASK_SUCCEEDED,
    T.FAILED: EventType.TASK_FAILED,
}


class InvalidTransitionError(Exception):
    def __init__(self, kind: str, current: str, target: str) -> None:
        super().__init__(f"illegal {kind} transition {current} -> {target}")
        self.kind, self.current, self.target = kind, current, target


def can_transition_run(current: RunStatus, target: RunStatus) -> bool:
    return target in RUN_TRANSITIONS[current]


def can_transition_task(current: TaskStatus, target: TaskStatus) -> bool:
    return target in TASK_TRANSITIONS[current]
