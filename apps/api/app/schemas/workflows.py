from datetime import datetime
from typing import Any, Self

from pydantic import ConfigDict, Field, model_validator

from app.schemas.common import ApiModel
from app.schemas.enums import (
    ProtectedAction,
    SiblingFailurePolicy,
    TaskAccess,
    TaskType,
    WorkflowSource,
    WorkflowStatus,
)

MAX_TASKS = 20


class WorkflowPolicy(ApiModel):
    """Budgets and gates. Read from the pinned workflow version, never from memory."""

    model_config = ConfigDict(extra="forbid")

    max_attempts_per_task: int = Field(default=2, ge=1, le=10)
    max_total_attempts: int = Field(default=10, ge=1, le=100)
    task_timeout_ms: int = Field(default=60_000, ge=1_000, le=900_000)
    max_concurrency: int = Field(default=3, ge=1, le=16)
    on_sibling_failure: SiblingFailurePolicy = SiblingFailurePolicy.FINISH_READ_CANCEL_REST
    approval_gates: list[ProtectedAction] = Field(default_factory=list)


class WorkflowTaskDef(ApiModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    type: TaskType
    agent_id: str | None = Field(default=None, max_length=100)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    depends_on: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    access: TaskAccess = TaskAccess.READ
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _agent_required_unless_approval(self) -> Self:
        if self.type is not TaskType.HUMAN_APPROVAL and not self.agent_id:
            raise ValueError("agentId is required for every task except HUMAN_APPROVAL")
        return self


class WorkflowDefinition(ApiModel):
    """Structural validation only. Graph/semantic checks (cycles, unknown agents,
    allowlisted commands) are slice 4's validator."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    goal: str = Field(min_length=1, max_length=4000)
    repository_id: str = Field(min_length=1, max_length=200)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=20)
    tasks: list[WorkflowTaskDef] = Field(min_length=1, max_length=MAX_TASKS)


class PlanRequest(ApiModel):
    goal: str = Field(min_length=1, max_length=4000)
    repository_id: str = Field(min_length=1, max_length=200)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=20)


class WorkflowOut(ApiModel):
    id: str
    name: str
    repository_id: str
    status: WorkflowStatus
    latest_version: int
    created_at: datetime


class WorkflowVersionOut(ApiModel):
    id: str
    workflow_id: str
    version: int
    definition: WorkflowDefinition
    agent_versions: dict[str, str]
    policy: WorkflowPolicy
    policy_hash: str
    goal_fingerprint: str
    source: WorkflowSource
    created_at: datetime
