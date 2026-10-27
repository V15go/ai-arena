from ulid import ULID

PREFIXES = {
    "workflow": "wf",
    "workflow_version": "wfv",
    "run": "run",
    "task": "task",
    "attempt": "att",
    "event": "evt",
    "approval": "apr",
    "memory": "mem",
    "eval_case": "evc",
    "eval_result": "evr",
    "request": "req",
}


def new_id(kind: str) -> str:
    """Prefixed, time-sortable id, e.g. ``run_01J...``. IDs are opaque to clients."""
    return f"{PREFIXES[kind]}_{ULID()}"
