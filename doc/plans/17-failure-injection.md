# 17 — Failure injection

**Phase F · Depends on:** 15, 16 · **Status:** not started

## Goal
Reproduce specific failures on demand so recovery behaviour can be demonstrated and measured fairly.

## Responsibility
Inject faults at the sandbox/fixture layer. **Non-goals:** deciding how to recover (18-19), metrics (23).

## Design (ARCHITECTURE §4.11)
- Faults live **outside the agents** so both BASELINE and ARENA face identical conditions.
- `FaultInjectingProvider(SandboxProvider)` wraps any provider; a `FaultPlan` lists rules `{match: argv/prefix or Nth exec, effect}`.
- Effects: `TRANSIENT_ERROR` (exit 75 / provider error once), `FLAKY_TEST` (fail first run, pass after), `WRONG_FIRST_FIX` (fixture variant whose obvious fix breaks a second test), `MISSING_DEPENDENCY` (module not found until a documented fix is applied), `TIMEOUT`, `POLICY_VIOLATION_ATTEMPT` (agent tries a non-allowlisted command; must be blocked, not retried).
- Fault plans are named scenarios in `fixtures/scenarios/*.yaml`, seeded and deterministic; the plan id is stored on the run `inputs` for traceability.
- Only enabled when `ALLOW_FAULT_INJECTION=true` and never in production config.

## Tests and acceptance
- Each effect triggers exactly as specified, the same way every time.
- Wrapper preserves the interface contract (contract tests from plan 14 pass through it with an empty plan).
- Policy-violation scenario is blocked by the allowlist, and the run records `POLICY_VIOLATION`.
- Scenarios carry a `seed`; scenario id and seed are stored in the run config (plan 07 `inputs._config`) so BASELINE and ARENA runs of one case face identical faults.
- `FaultInjectingProvider` forwards `snapshot`, `restore` and `export_workspace` untouched, and a contract test proves it with an empty fault plan.

## Done when
Scenarios exist for every failure class that plan 18 classifies, and a run can be started with a named scenario.
