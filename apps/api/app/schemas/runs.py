from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from app.schemas.common import ApiModel
from app.schemas.enums import (
    AttemptStatus,
    DecisionSource,
    FailureClass,
    RecoveryAction,
    RunMode,
    RunStatus,
    TaskAccess,
    TaskStatus,
    TaskType,
)
from app.schemas.memory import Evidence


class RecoveryDecision(ApiModel):
    decision: RecoveryAction
    rationale: str
    overridden_reason: str | None = None


class TaskAttemptOut(ApiModel):
    id: str
    task_id: str
    attempt_no: int
    status: AttemptStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: dict[str, Any] | None = None
    failure_class: FailureClass | None = None
    fingerprint: str | None = None
    recovery_decision: RecoveryDecision | None = None
    decision_source: DecisionSource | None = None
    evidence: Evidence | None = None


class TaskOut(ApiModel):
    id: str
    run_id: str
    task_key: str
    type: TaskType
    agent_id: str | None = None
    agent_version: str | None = None
    access: TaskAccess
    status: TaskStatus
    depends_on: list[str]
    position: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    attempts: list[TaskAttemptOut] = Field(default_factory=list)


class RunOut(ApiModel):
    id: str
    workflow_version_id: str
    mode: RunMode
    status: RunStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    cancel_requested: bool
    total_attempts: int
    planner_calls: int
    model_calls: int
    tokens_in: int
    tokens_out: int
    est_cost_usd: Decimal
    outcome: dict[str, Any] | None = None


class RunDetail(RunOut):
    tasks: list[TaskOut] = Field(default_factory=list)
    pending_approval_id: str | None = None


class CreateRunRequest(ApiModel):
    """Run creation lands with the orchestrator (slice 7); the contract is fixed now."""

    idempotency_key: str = Field(min_length=8, max_length=200)
    version: int | None = Field(default=None, ge=1)
    mode: RunMode = RunMode.ARENA
    inputs: dict[str, Any] = Field(default_factory=dict)
