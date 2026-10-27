# 18 — Recovery policy and classifier

**Phase F · Depends on:** 09, 15 · **Status:** not started

## Goal
Deterministically classify every failure and enforce the hard rules that no model or memory can override.

## Responsibility
`classifier.py` and `policy.py`, plus the scheduler's `RecoveryHook` implementation. **Non-goals:** model proposals (19), lesson storage (20).

## Design (ARCHITECTURE §4.5)
- **Classifier** (pure): from exit code, parsed output, provider errors and timeouts -> `FailureClass` in `TRANSIENT_INFRA | TEST_FAILURE | BUILD_ERROR | DEPENDENCY_MISSING | TIMEOUT | POLICY_VIOLATION | UNKNOWN`, plus a normalized failure **fingerprint** (`sha256(workflowId | taskType | failureClass | normalizedSignal)`; signal strips paths, line numbers, timestamps, hex ids).
- **Policy** (pure): `decide(failure, history, budgets, proposal?) -> RecoveryDecision`.
  - Never retry `POLICY_VIOLATION`, invalid approvals, sandbox-security failures -> `ESCALATE`.
  - `TRANSIENT_INFRA` / `TIMEOUT` -> `RETRY` within per-task and total budgets.
  - `TEST_FAILURE`/`BUILD_ERROR`/`DEPENDENCY_MISSING`/`UNKNOWN` -> needs a proposal; `REPLAN` allowed only with **new evidence** (different fingerprint or new diff hash); otherwise `ESCALATE`.
  - Budget exhausted -> `ESCALATE` with a human-readable report.
  - Records the final decision, `decisionSource`, and any override reason on `task_attempts`; emits `RECOVERY_PLANNED`.
- **BASELINE mode**: classifier runs, but policy returns plain bounded `RETRY` for every non-fatal class (the "conventional retry policy" in Master §11).
- Hook wiring: scheduler asks the hook after each failed attempt; hook returns RETRY (task back to READY, `TASK_RETRY_SCHEDULED`) / REPLAN (task patch applied) / ESCALATE (task FAILED).

### Corrections from the audit (H4, L2, L5)
- **Every proposal goes through policy, whatever its source.** `decide(failure, history, budgets, proposal?)` receives `proposal.source in {MODEL, MEMORY}`. A memory hit is converted into a proposal and evaluated by exactly the same rules; fingerprint equality never skips `decide()`. A hit on a `POLICY_VIOLATION`, security failure or exhausted budget is still `ESCALATE`.
- `INTERRUPTED` attempts (crash or lease loss, plan 10) classify as `TRANSIENT_INFRA` and consume budget like any retry.
- All budget kinds (attempts, model calls, run seconds, output bytes) produce `ESCALATE` with reason `BUDGET_EXHAUSTED`.
- **Escalation report:** on escalation the Orchestrator writes `workflow_runs.outcome = {reason, report, lastFailure, budgetsUsed}` (human-readable), shown by plan 12.

## Tests and acceptance
- Table-driven classification for every class incl. ambiguous output -> `UNKNOWN`.
- Fingerprint stable across path/line-number/timestamp noise, different for different failures.
- Policy truth table, including: proposal asking to retry a policy violation is overridden; replan without new evidence becomes escalate; budget exhaustion escalates.
- Property test: policy never returns a decision that exceeds budgets.
- Memory proposal for `POLICY_VIOLATION` is overridden to `ESCALATE`; memory proposal for `TEST_FAILURE` with no new evidence is also overridden.
- `INTERRUPTED` maps to `TRANSIENT_INFRA`; escalation writes `outcome.report`.

## Done when
The injected scenarios from plan 17 produce the expected class and decision with no model involved.
