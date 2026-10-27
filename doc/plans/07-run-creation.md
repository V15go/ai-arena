# 07 — Run creation

**Phase D · Depends on:** 06 · **Status:** not started

## Goal
Create a run from a pinned workflow version, exactly once per idempotency key.

## Responsibility
Materialize the run and its task rows, record `RUN_QUEUED`. **Non-goals:** executing anything (plan 09).

## Design
- `POST /workflows/{id}/runs` body `CreateRunRequest(idempotencyKey, version?, mode, inputs)` -> `202 {runId, status: QUEUED}`.
- One transaction: compatibility check (plan 06) -> insert `workflow_runs` (status via Orchestrator `create_run`, the only creator of runs) -> insert `tasks` from the version definition (task_key, type, agent_id/version, access, depends_on, position) -> `RUN_QUEUED` event (and `PLAN_REUSED` when the version came from memory).
- Idempotency: unique `idempotency_key`; same key + same payload returns the original run (`202`); same key + different payload `409`.
- `mode` = `ARENA | BASELINE` is stored now; behaviour differences arrive in plans 18-20.
- Inputs validated against the workflow's declared input schema (max size limit).
- **Run config snapshot (audit M2).** At creation the orchestrator stores `inputs["_config"]` = `{modelIds, promptVersions, agentVersions, fixtureHash, sandboxImage, gitCommit, seed, scenarioId, memoryScope}`. Plans 17, 20 and 23 read it; it makes a run reproducible without any schema change. `fixtureHash` comes from the fixture loader (plan 03). `memoryScope` defaults to `global`.

## Orchestrator change
Add `Orchestrator.create_run(...)` so that run/task creation remains inside the sole-writer module; the authority test must still pass.

## Contracts
`POST /workflows/{id}/runs`, `GET /runs` filters (`status`, `workflowId`), regenerated contracts.

## Tests and acceptance
- Replay with the same key creates one run, one set of tasks, one `RUN_QUEUED`.
- Incompatible version -> `409 INCOMPATIBLE_WORKFLOW` with reasons, nothing written.
- Concurrent duplicate requests -> exactly one run.
- Task rows exactly mirror the definition, `PENDING`.
- `_config` is present on every run and identical for two runs created from the same version and inputs.
- `GET /runs` supports `status`, `workflowId`, `mode` filters and keyset pagination (used by the history page, plan 12).

## Done when
A queued run with its tasks exists and is visible via `GET /runs/{id}`.
