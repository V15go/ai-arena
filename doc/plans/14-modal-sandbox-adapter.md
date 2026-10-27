# 14 — Modal sandbox adapter

**Phase E · Depends on:** slice 1, S2 · **Status:** not started

## Goal
Run allowlisted commands in a real, disposable, remote Modal sandbox behind the existing `SandboxProvider` interface.

## Responsibility
`ModalSandboxProvider` only. **Non-goals:** changing the interface, tools, evidence.

## First step (blocking) — Spike S2 (run before plan 09)
**Verify the current official Modal SDK** (language bindings available, Sandbox creation, exec with streaming/timeouts, file read/write, image definition, network egress controls, resource and time limits, pricing/free credit). Write findings to `doc/MODAL_NOTES.md`. If the SDK differs from the interface assumptions, adapt `modal.py` only.

**Spike S2 checklist additions (audit H2, H6, L1).** The notes must also answer: (a) does Modal support **filesystem snapshots or forking** of a sandbox (for `snapshot/restore`), or must the adapter use `export_workspace` plus re-upload, (b) can several `exec` calls run concurrently in one sandbox, (c) can the process run as a **non-root** user, (d) PID/process limits, read-only root filesystem with writable `/workspace` and `/tmp`, (e) egress control, (f) creation latency and retry semantics, (g) the SDK language binding used (Python). **Gate:** `doc/MODAL_NOTES.md` must exist before plan 09 starts, because the answers fix the `SandboxProvider` additions (`snapshot`, `restore`, `export_workspace`, `capabilities`). The spike runs at the start of the project, in parallel with plan 01; if it forces interface changes they are made in the interface, the fake and the contract tests first.

## Design
- Pre-built image with Python, git, pytest and the fixture's dependencies baked in; network blocked where supported, otherwise rely on a dependency-complete image.
- `create`: sandbox with timeout, CPU/memory limits; `upload_workspace`: write files under `/workspace`; `_exec`: argv exec (no shell), wall-clock timeout, output capped by the base class; `read_file`/`write_file` with the same path normalisation as the fake; `destroy` idempotent.
- `capabilities.concurrent_exec` set from what Modal supports; otherwise hand out one handle per concurrent task.
- Only the Modal token (API env) is used; **no environment variables are passed into the sandbox**.
- Reaper hook lists/destroys leaked sandboxes by run tag.
- `create_sandbox_provider` returns it when `SANDBOX_PROVIDER=modal`.

- **Hardening (audit L1):** the sandbox runs as a non-root user, with a PID limit and read-only root where Modal supports them; whatever is unsupported is listed in `MODAL_NOTES.md` and carried into the plan 26 threat model as an accepted risk.
- **Retries (audit L5):** `create` and `exec` retry transient provider errors with backoff (max 2); after that the adapter raises `SandboxUnavailable`, which plan 18 classifies as `TRANSIENT_INFRA`.
- **Snapshots:** `snapshot/restore/export_workspace` implemented natively or via export plus re-upload, as decided by the spike, and passing the same contract tests as the fake.

## Tests and acceptance
- Shared **provider contract test suite** run against both fake and Modal (Modal part behind `MODAL_LIVE=1`): lifecycle, allowlist enforcement, truncation, timeout produces `timed_out`, path escape refused, destroy idempotent.
- Unit tests with a mocked Modal client for error mapping.
- Manual smoke: run fixture tests remotely and read the result.
- `whoami` inside the sandbox is not root; a fork-bomb style command is bounded by the PID limit (when supported).
- Snapshot contract test: write A, snapshot, write B, restore gives A only.
- Transient create error is retried and then surfaces as `SandboxUnavailable`.

## Risks
Cold start and cost; keep sandboxes per run, short timeouts, and a fake fallback for the demo.

## Done when
A real remote exec returns exit code and output through the interface, and leaked sandboxes are cleaned up.
