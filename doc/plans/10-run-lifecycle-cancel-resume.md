# 10 — Run lifecycle: cancel, heartbeat, resume

**Phase D · Depends on:** 09 · **Status:** not started

## Goal
Runs can be cancelled promptly and survive an API restart without corruption.

## Responsibility
`cancel_requested` handling, lease heartbeats, startup resume, orphan reaping. **Non-goals:** approval waiting logic (plan 21) beyond not breaking it.

## Design
- `POST /runs/{id}/cancel` -> sets `cancel_requested` (idempotent) -> `202`. The scheduler checks between steps; on seeing it, it cancels running attempts, asks the sandbox to kill the exec, marks tasks `CANCELLED`, run `CANCELLED`, destroys the sandbox in `finally`.
- Heartbeat: the owning worker updates `heartbeat_at` every N seconds in its own short transaction.
- Startup resume: runs `RUNNING` with `heartbeat_at` older than lease timeout are re-claimed. A task caught mid-attempt gets its attempt marked `INTERRUPTED`, the task goes through normal recovery (counts against budgets). `WAITING_APPROVAL` runs need nothing.
- Lease takeover is a single conditional UPDATE so two workers never run the same run.
- Reaper: destroys sandboxes belonging to terminal runs that still have a live handle.
- Cancel flags, heartbeats, lease claims and orphan marking are all written **by `Orchestrator` methods** (sole-writer rule); the authority test must stay green.
- Lease takeover, heartbeat and the two-workers race tests are `pg_required` (plan 01): they rely on `FOR UPDATE SKIP LOCKED` semantics.
- Cancelling a run that is `WAITING_APPROVAL` expires its pending approval in the same transaction.

## Contracts
`POST /runs/{id}/cancel` (`202`, `409` if already terminal).

## Tests and acceptance
- Cancel during a slow task stops within the poll interval; final state `CANCELLED`; `finished_at` set; sandbox destroyed.
- Simulated crash (stop worker, expire lease, start new worker) completes the run exactly once; interrupted attempt recorded.
- Two workers racing for one stale run: exactly one wins.
- Cancel on terminal run -> 409.

## Done when
Killing the API mid-run and restarting it finishes or fails the run cleanly, with a coherent event log.
