"""Deterministic in-memory sandbox for local development and tests.

Exec results are scripted by argv prefix; nothing is ever run on the host.
"""

import posixpath
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from app.sandbox.provider import (
    PathNotAllowedError,
    SandboxNotFoundError,
    SandboxProvider,
)
from app.schemas.sandbox import (
    ExecRequest,
    ExecResult,
    SandboxCapabilities,
    SandboxHandle,
    SandboxSpec,
)

ExecScript = ExecResult | Callable[[ExecRequest, dict[str, bytes]], ExecResult]
WORKSPACE = "/workspace"


@dataclass
class _Script:
    prefix: tuple[str, ...]
    result: ExecScript
    remaining: int | None  # None = unlimited


@dataclass
class _Sandbox:
    spec: SandboxSpec
    files: dict[str, bytes] = field(default_factory=dict)


def normalize_path(path: str) -> str:
    """Resolve to an absolute path inside /workspace or refuse."""
    joined = path if path.startswith("/") else posixpath.join(WORKSPACE, path)
    normal = posixpath.normpath(joined)
    if normal != WORKSPACE and not normal.startswith(WORKSPACE + "/"):
        raise PathNotAllowedError(f"path escapes workspace: {path}")
    return normal


class FakeSandboxProvider(SandboxProvider):
    name = "fake"
    capabilities = SandboxCapabilities(concurrent_exec=True, network_isolation=True)

    def __init__(self, allowed_commands: Iterable[str] = (), max_exec_timeout_ms: int = 900_000):
        super().__init__(allowed_commands, max_exec_timeout_ms)
        self._boxes: dict[str, _Sandbox] = {}
        self._scripts: list[_Script] = []
        self._counter = 0
        self.exec_log: list[tuple[str, list[str]]] = []

    def script(
        self, argv_prefix: Iterable[str], result: ExecScript, times: int | None = None
    ) -> None:
        """Register a result for commands starting with ``argv_prefix`` (first match wins)."""
        self._scripts.append(_Script(tuple(argv_prefix), result, times))

    def _next(self, kind: str) -> str:
        self._counter += 1
        return f"fake-{kind}-{self._counter:06d}"

    def _box(self, handle: SandboxHandle) -> _Sandbox:
        try:
            return self._boxes[handle.id]
        except KeyError:
            raise SandboxNotFoundError(handle.id) from None

    async def create(self, spec: SandboxSpec) -> SandboxHandle:
        handle = SandboxHandle(id=self._next("sbx"), provider=self.name)
        self._boxes[handle.id] = _Sandbox(spec=spec)
        return handle

    async def upload_workspace(self, handle: SandboxHandle, files: Mapping[str, bytes]) -> None:
        box = self._box(handle)
        for path, data in files.items():
            box.files[normalize_path(path)] = data

    async def _exec(self, handle: SandboxHandle, request: ExecRequest) -> ExecResult:
        box = self._box(handle)
        exec_id = self._next("exec")
        self.exec_log.append((handle.id, list(request.argv)))
        for script in self._scripts:
            if tuple(request.argv[: len(script.prefix)]) != script.prefix:
                continue
            if script.remaining == 0:
                continue
            if script.remaining is not None:
                script.remaining -= 1
            raw = script.result(request, box.files) if callable(script.result) else script.result
            return raw.model_copy(update={"exec_id": exec_id})
        return ExecResult(exec_id=exec_id, exit_code=127, stderr="command not scripted in fake")

    async def read_file(self, handle: SandboxHandle, path: str) -> bytes:
        box = self._box(handle)
        try:
            return box.files[normalize_path(path)]
        except KeyError:
            raise FileNotFoundError(path) from None

    async def write_file(self, handle: SandboxHandle, path: str, data: bytes) -> None:
        self._box(handle).files[normalize_path(path)] = data

    async def destroy(self, handle: SandboxHandle) -> None:
        self._boxes.pop(handle.id, None)

    @property
    def live_sandboxes(self) -> int:
        return len(self._boxes)
