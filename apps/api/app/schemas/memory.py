from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from app.schemas.common import ApiModel
from app.schemas.enums import FailureClass, MemoryOutcome


class Evidence(ApiModel):
    """Proof produced by the Validation Engine. Agent self-reports are never evidence."""

    attempt_id: str
    sandbox_exec_id: str
    exit_code: int
    command: list[str] = Field(default_factory=list)
    test_summary: dict[str, Any] = Field(default_factory=dict)
    diff_hash: str | None = None


class MemoryRecordOut(ApiModel):
    id: str
    workflow_id: str
    fingerprint: str
    failure_class: FailureClass
    strategy: dict[str, Any]
    outcome: MemoryOutcome
    evidence: Evidence
    source_attempt_id: str
    success_count: int
    failure_count: int
    confidence: Decimal
    env_constraints: dict[str, Any]
    created_at: datetime
    last_used_at: datetime | None = None
