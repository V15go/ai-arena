from app.core.config import Settings
from app.sandbox.fake import FakeSandboxProvider
from app.sandbox.provider import SandboxProvider


def create_sandbox_provider(settings: Settings) -> SandboxProvider:
    if settings.sandbox_provider == "fake":
        return FakeSandboxProvider()
    # Slice 9: verify the current Modal Sandbox SDK against Modal's docs, then add modal.py.
    raise NotImplementedError("Modal sandbox adapter is not implemented yet (slice 9)")


__all__ = ["FakeSandboxProvider", "SandboxProvider", "create_sandbox_provider"]
