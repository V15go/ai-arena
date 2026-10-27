"""Provider-neutral sandbox interface.

The command allowlist, timeout cap and output cap are enforced here, in the base class, so
no adapter (fake, Modal, ...) can skip them. Adapters only implement the ``_``-prefixed hooks.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping

from app.schemas.sandbox import (
    ExecRequest,
    ExecResult,
    SandboxCapabilities,
    SandboxHandle,
    SandboxSpec,
)


class SandboxError(Exception):
    pass


class SandboxNotFoundError(SandboxError):
    pass


class CommandNotAllowedError(SandboxError):
    pass


class PathNotAllowedError(SandboxError):
    pass


class SandboxProvider(ABC):
    name: str
    capabilities: SandboxCapabilities

    def __init__(self, allowed_commands: Iterable[str], max_exec_timeout_ms: int = 900_000) -> None:
        self._allowed = frozenset(allowed_commands)
        self._max_timeout_ms = max_exec_timeout_ms

    def check_command(self, argv: list[str]) -> None:
        if not argv or argv[0] not in self._allowed:
            raise CommandNotAllowedError(f"command not allowlisted: {argv[:1]}")

    async def exec(self, handle: SandboxHandle, request: ExecRequest) -> ExecResult:
        self.check_command(request.argv)
        capped = request.model_copy(
            update={"timeout_ms": min(request.timeout_ms, self._max_timeout_ms)}
        )
        result = await self._exec(handle, capped)
        return self._truncate(result, capped.max_output_bytes)

    @staticmethod
    def _truncate(result: ExecResult, limit: int) -> ExecResult:
        out, err = result.stdout.encode(), result.stderr.encode()
        if len(out) + len(err) <= limit:
            return result
        out_keep = out[:limit]
        err_keep = err[: max(limit - len(out_keep), 0)]
        return result.model_copy(
            update={
                "stdout": out_keep.decode(errors="ignore"),
                "stderr": err_keep.decode(errors="ignore"),
                "truncated": True,
            }
        )

    @abstractmethod
    async def create(self, spec: SandboxSpec) -> SandboxHandle: ...

    @abstractmethod
    async def upload_workspace(self, handle: SandboxHandle, files: Mapping[str, bytes]) -> None: ...

    @abstractmethod
    async def _exec(self, handle: SandboxHandle, request: ExecRequest) -> ExecResult: ...

    @abstractmethod
    async def read_file(self, handle: SandboxHandle, path: str) -> bytes: ...

    @abstractmethod
    async def write_file(self, handle: SandboxHandle, path: str, data: bytes) -> None: ...

    @abstractmethod
    async def destroy(self, handle: SandboxHandle) -> None:
        """Idempotent: destroying an unknown or already-destroyed sandbox is not an error."""
