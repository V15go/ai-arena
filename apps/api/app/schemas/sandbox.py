from pydantic import Field

from app.schemas.common import ApiModel


class SandboxSpec(ApiModel):
    """No environment variables can be requested: nothing from the API process is forwarded."""

    template: str = Field(min_length=1)
    timeout_ms: int = Field(default=60_000, ge=1_000, le=900_000)


class SandboxHandle(ApiModel):
    id: str
    provider: str


class ExecRequest(ApiModel):
    argv: list[str] = Field(min_length=1, description="Structured arguments; never a shell string")
    cwd: str = "/workspace"
    timeout_ms: int = Field(default=60_000, ge=1, le=900_000)
    max_output_bytes: int = Field(default=1_000_000, ge=1, le=10_000_000)


class ExecResult(ApiModel):
    exec_id: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False
    duration_ms: int = 0
    timed_out: bool = False


class SandboxCapabilities(ApiModel):
    concurrent_exec: bool = False
    network_isolation: bool = True
