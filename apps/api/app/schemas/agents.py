from datetime import datetime

from pydantic import ConfigDict, Field

from app.schemas.common import ApiModel
from app.schemas.enums import AgentStatus, ProtectedAction, TaskType


class AgentPermissions(ApiModel):
    model_config = ConfigDict(extra="forbid")

    sandbox_write: bool = False
    network: bool = False
    protected_actions: list[ProtectedAction] = Field(default_factory=list)


class AgentDefinition(ApiModel):
    """Body of ``agents.definition``. Tool ids are checked against the code-level
    ToolRegistry and permission ceiling when the registry is implemented (slice 4)."""

    model_config = ConfigDict(extra="forbid")

    task_types: list[TaskType] = Field(min_length=1)
    tools: list[str] = Field(default_factory=list)
    permissions: AgentPermissions = Field(default_factory=AgentPermissions)
    model_profile: str = "fast"
    description: str = ""


class AgentOut(ApiModel):
    id: str
    version: str
    status: AgentStatus
    definition: AgentDefinition
    created_by: str
    created_at: datetime
