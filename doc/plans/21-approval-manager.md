# 21 — Approval manager

**Phase G · Depends on:** 09, 10, 15 · **Status:** not started

## Goal
Protected actions can only happen after a persisted, valid, human approval bound to exactly what the reviewer saw.

## Responsibility
Approval creation, decision, server-side enforcement, protected export action. **Non-goals:** UI (22), real GitHub PR creation (deferred).

## Design (ARCHITECTURE §4.9)
- Protected actions are a code enum (`EXPORT_PATCH`, `CREATE_PR`); a task of type `HUMAN_APPROVAL` precedes any task performing one (validator rule from plan 03).
- Flow: gate reached -> `approvals` row `PENDING` with `payload_hash` = diff hash and a summary (diff stats, test evidence) -> run `WAITING_APPROVAL` + `APPROVAL_REQUESTED` -> decision -> run resumes.
- `POST /approvals/{id}/decision` `{decision, comment}`; **`decided_by` comes from the auth context**, never the body. Repeated identical decision is an idempotent `200`; a conflicting one is `409`.
- `ApprovalManager.assert_approved(action, run_id, payload_hash)` is called **inside the same transaction** that performs the protected action; it re-reads the row `FOR UPDATE`.
- A changed diff (hash mismatch) invalidates the approval: the run needs a new approval.
- Reject, expiry or missing approval -> action never runs; run ends `FAILED(APPROVAL_REJECTED)`, recorded not hidden.
- `EXPORT_PATCH` writes the patch as a local artifact under a configured artifacts directory (path-checked); only after `assert_approved`.
- Approval timeout configurable; expiry handled by the scheduler.

### Corrections from the audit (M1, M2)
- **Hash is recomputed, not supplied.** `EXPORT_PATCH` derives the canonical patch bytes itself from the sandbox workspace at action time (the plan 15 function), hashes them, passes that hash to `assert_approved`, and writes exactly those bytes. A caller can never pass a hash it did not compute from the artifact.
- **Frozen workspace.** The approval gate holds the workspace lock from request to export (plan 09), so the reviewed diff cannot change in between; any change still invalidates the approval.
- **Expiry.** Migration `0004` adds `approvals.expires_at`; the scheduler expires overdue approvals and cancel (plan 10) expires pending ones.
- **Blocked actions are recorded.** A refused protected action emits `PROTECTED_ACTION_BLOCKED` (reason: missing, rejected, expired, hash mismatch) with the run and approval ids; the evaluation metric counts these events. `EventType` gains the member; contracts are regenerated.
- **Invariant:** a run is `WAITING_APPROVAL` if and only if a `PENDING` approval exists for it; the Orchestrator enforces both directions in the transition transactions.
- **Authorization:** the single API token decides approvals; any token holder may approve any run, including their own. This is an accepted hackathon limitation, recorded in ARCHITECTURE.md §12.

## Orchestrator change
New transitions `RUNNING <-> WAITING_APPROVAL` already exist; add `request_approval` / `resolve_approval` methods so the Orchestrator stays the sole writer.

## Tests and acceptance
- Export without approval, with rejected, expired, or hash-mismatched approval -> blocked (each a test).
- Race: approve and cancel simultaneously -> consistent final state.
- Client-supplied identity ignored.
- Approval after the run was cancelled -> `409`.
- Event log shows request and decision with the right seq order.

- A caller-supplied hash is ignored: exporting a patch whose recomputed hash differs from the approval is blocked and emits `PROTECTED_ACTION_BLOCKED`.
- Run cannot enter `WAITING_APPROVAL` without a pending approval, and a pending approval cannot be left behind when the run leaves that state.
- Approve, cancel and expiry races are `pg_required` (plan 01).

## Done when
A run pauses at the gate, resumes on approve, and fails cleanly on reject; protected-actions-blocked counter is queryable for plan 23.
