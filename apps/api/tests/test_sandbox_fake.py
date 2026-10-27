import asyncio

import pytest

from app.sandbox import FakeSandboxProvider, create_sandbox_provider
from app.sandbox.provider import (
    CommandNotAllowedError,
    PathNotAllowedError,
    SandboxNotFoundError,
)
from app.schemas.sandbox import ExecRequest, ExecResult, SandboxSpec
from tests.conftest import make_settings


def provider() -> FakeSandboxProvider:
    return FakeSandboxProvider(allowed_commands=["pytest", "git"])


async def test_lifecycle_upload_exec_read_destroy() -> None:
    fake = provider()
    fake.script(["pytest"], ExecResult(exec_id="", exit_code=1, stdout="1 failed"))
    h = await fake.create(SandboxSpec(template="py"))
    await fake.upload_workspace(h, {"app.py": b"print(1)"})
    assert await fake.read_file(h, "/workspace/app.py") == b"print(1)"
    res = await fake.exec(h, ExecRequest(argv=["pytest", "-q"]))
    assert (res.exit_code, res.stdout) == (1, "1 failed")
    assert res.exec_id.startswith("fake-exec-")
    await fake.destroy(h)
    await fake.destroy(h)  # idempotent
    assert fake.live_sandboxes == 0
    with pytest.raises(SandboxNotFoundError):
        await fake.read_file(h, "app.py")


async def test_allowlist_is_enforced_before_the_adapter_runs() -> None:
    fake = provider()
    h = await fake.create(SandboxSpec(template="py"))
    for argv in (["rm", "-rf", "/"], ["sh", "-c", "pytest"], ["python", "-c", "import os"]):
        with pytest.raises(CommandNotAllowedError):
            await fake.exec(h, ExecRequest(argv=argv))
    assert fake.exec_log == []  # nothing reached the provider


async def test_default_allowlist_is_empty_fail_closed() -> None:
    fake = FakeSandboxProvider()
    h = await fake.create(SandboxSpec(template="py"))
    with pytest.raises(CommandNotAllowedError):
        await fake.exec(h, ExecRequest(argv=["pytest"]))


async def test_paths_cannot_escape_workspace() -> None:
    fake = provider()
    h = await fake.create(SandboxSpec(template="py"))
    for bad in ("../etc/passwd", "/etc/passwd", "/workspace/../etc/passwd"):
        with pytest.raises(PathNotAllowedError):
            await fake.write_file(h, bad, b"x")


async def test_output_is_truncated_to_cap() -> None:
    fake = provider()
    fake.script(["git"], ExecResult(exec_id="", exit_code=0, stdout="x" * 100))
    h = await fake.create(SandboxSpec(template="py"))
    res = await fake.exec(h, ExecRequest(argv=["git", "diff"], max_output_bytes=10))
    assert res.truncated and len(res.stdout) == 10


async def test_unscripted_command_and_scripted_times_and_callable() -> None:
    fake = provider()
    fake.script(["pytest"], ExecResult(exec_id="", exit_code=1), times=1)
    fake.script(
        ["pytest"], lambda req, files: ExecResult(exec_id="", exit_code=0, stdout=str(len(files)))
    )
    h = await fake.create(SandboxSpec(template="py"))
    first = await fake.exec(h, ExecRequest(argv=["pytest"]))
    second = await fake.exec(h, ExecRequest(argv=["pytest"]))
    assert (first.exit_code, second.exit_code) == (1, 0)
    assert (await fake.exec(h, ExecRequest(argv=["git", "log"]))).exit_code == 127


async def test_concurrent_exec_is_safe_and_ids_unique() -> None:
    fake = provider()
    fake.script(["pytest"], ExecResult(exec_id="", exit_code=0))
    h = await fake.create(SandboxSpec(template="py"))
    results = await asyncio.gather(*(fake.exec(h, ExecRequest(argv=["pytest"])) for _ in range(5)))
    assert len({r.exec_id for r in results}) == 5


def test_factory_returns_fake_and_refuses_unimplemented_modal() -> None:
    assert create_sandbox_provider(make_settings()).name == "fake"
    modal = make_settings(
        sandbox_provider="modal",
        modal_token_id="i",
        modal_token_secret="s",
        modal_sandbox_image="img",
    )
    with pytest.raises(NotImplementedError):
        create_sandbox_provider(modal)
