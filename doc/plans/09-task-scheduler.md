# 09 — Task scheduler

**Phase D · Depends on:** 07, 08, Spike S2 notes (plan 14) · **Status:** not started

## Goal
Drive a run to completion: pick ready tasks, run them (in parallel where safe), and move state only through the Orchestrator.

## Responsibility
Dependency resolution, concurrency, workspace locks, budgets, attempt bookkeeping. **Non-goals:** what an agent does (13), recovery decisions (18-19), cancel/resume (10).

## Design (ARCHITECTURE §4.4)
- A run loop (asyncio task per run, started by a `RunWorker` that claims `QUEUED` runs via `FOR UPDATE SKIP LOCKED` and sets `lease_owner`).
- `ready_set(tasks)`: `PENDING` tasks whose dependencies are all `SUCCEEDED`.
- Concurrency: up to `policy.maxConcurrency`. `WRITE` tasks take an exclusive workspace lock; `READ` tasks may overlap. Parallel `TEST` tasks run on a workspace snapshot taken after the last WRITE.
- Each attempt: `consume_attempt` (run budget) -> create `task_attempts` row -> call `TaskExecutor` (interface; fake executor in this plan) -> record outcome -> transition task. Per-attempt timeout from policy.
- Sibling failure handled per `policy.onSiblingFailure`.
- On task failure the scheduler calls a `RecoveryHook` (no-op stub here: "no retry" -> task FAILED -> run FAILED). Plan 18-19 replace the stub.
- Run succeeds only when all required tasks `SUCCEEDED` **and** validation evidence exists for TEST tasks (the check is a hook; real in plan 15).
- Event `seq` stays total per run (advisory lock in `append_event`).

### Corrections from the audit (H2, H3, H5)
**Hard caps.** The scheduler enforces `min(policy.x, settings.x)` for concurrency, attempts, model calls, run seconds and output bytes; a policy can only tighten.

**Transactional run budgets.** Alongside `consume_attempt` (exists), the Orchestrator gains `consume_model_call(run_id, max)` and `add_output_bytes(run_id, n, max)`, each a single conditional UPDATE that returns False when the cap would be exceeded, plus `check_deadline(run)` using `started_at + maxRunSeconds`. Any exhausted budget makes the recovery hook return `ESCALATE` with reason `BUDGET_EXHAUSTED`. Migration `0002` adds `workflow_runs.output_bytes`.

**Snapshot consistency.** `SandboxProvider` gains `snapshot(handle) -> SnapshotHandle`, `restore(snapshot) -> SandboxHandle`, `export_workspace(handle) -> Mapping[str, bytes]` and `capabilities.snapshot`. The fake implements all three first. Rules:
- After every WRITE task completes, the scheduler takes a snapshot (or, when `capabilities.snapshot` is false, captures `export_workspace` and uploads it into fresh sandboxes).
- Every TEST or READ task that starts after a WRITE runs on a sandbox restored from the **latest** snapshot, never on the live write sandbox; its `snapshotId` is recorded in `TASK_STARTED` event data.
- Snapshots are immutable and destroyed with the run.
- While a WRITE task holds the exclusive lock nothing else starts, and the approval gate (plan 21) holds the same lock from request to export so the reviewed workspace cannot change.

## Deliverables
`app/orchestrator/scheduler.py`, `worker.py`, `executor.py` (interface + `ScriptedExecutor`), lock manager, tests.

## Tests and acceptance
- Linear, diamond, fan-out graphs complete with expected order.
- Two WRITE tasks never overlap; two READ tasks do (deliberately slow scripted tasks, timing asserted by ordering of events).
- Total attempts never exceed budget under 10-way concurrency.
- A failing task fails the run with `RUN_FAILED` and sibling policy applied.
- Authority test still green: scheduler changes state only through `Orchestrator`.
- A parallel TEST started after a WRITE sees exactly the post-WRITE files; a later WRITE does not change an already-restored snapshot.
- Fallback path (no native snapshot) gives the same result as the native path in the contract test.
- `consume_model_call` and `add_output_bytes` never overshoot under 20-way concurrency; an expired deadline escalates the run.
- Policy values above settings caps are clamped, and a test proves the clamp.
- Budget, event-order and lock-exclusivity tests are `pg_required` (plan 01).

## Risks
Parallelism complicates ordering; keep a deterministic mode (`maxConcurrency=1`) for debugging and tests.

## Done when
**Milestone M1** is reachable: a scripted full run finishes with a replayable event log.
