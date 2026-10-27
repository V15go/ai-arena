from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import ApiModel
from app.schemas.enums import ApprovalDecision, ApprovalStatus, ProtectedAction


class ApprovalOut(ApiModel):
    id: str
    run_id: str
    task_id: str
    action: ProtectedAction
    payload_hash: str
    summary: dict[str, Any]
    status: ApprovalStatus
    requested_at: datetime
    decided_at: datetime | None = None
    decided_by: str | None = None
    comment: str | None = None


class ApprovalDecisionRequest(ApiModel):
    """The decider's identity is taken from the auth context, never from this body."""

    decision: ApprovalDecision
    comment: str | None = Field(default=None, max_length=2000)
