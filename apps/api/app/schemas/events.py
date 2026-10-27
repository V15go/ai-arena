from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import ApiModel
from app.schemas.enums import EventType


class ExecutionEventOut(ApiModel):
    id: str
    run_id: str
    seq: int = Field(ge=1)
    type: EventType
    task_id: str | None = None
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
