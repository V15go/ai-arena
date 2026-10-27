# 15 — Validation engine

**Phase E · Depends on:** 13, 14, 16 · **Status:** not started

## Goal
No success without evidence: convert raw sandbox results into a trusted `Evidence` object.

## Responsibility
Parse test output, hash the diff, build `Evidence`, decide TEST success. **Non-goals:** classifying failures (18), storing lessons (20).

## Design (ARCHITECTURE §4.8)
- `Evidence`: `attemptId`, `sandboxExecId`, `exitCode`, `command`, `testSummary {passed, failed, skipped, failing[]}`, `diffHash`, timestamps.
- Test result parser for pytest (JUnit XML or `-rA` summary; prefer machine-readable output requested via argv from the allowlist).
- `diff_hash` = SHA-256 of `git diff` output computed by the engine from sandbox data, not reported by the agent.
- TEST task is `SUCCEEDED` only if `exitCode == 0` **and** summary has `failed == 0` and at least one test ran. Zero tests collected is a failure.
- REVIEW tasks read the evidence and diff and may **block** but can never mark tests as passing.
- Emits `VALIDATION_COMPLETED` with the evidence (redacted, size-capped).
- Persists to `task_attempts.evidence`; the scheduler's success hook calls the engine.

### Baseline integrity (audit H1)
A passing exit code is not enough. The engine compares each TEST run with the fixture `baseline` from plan 03/16 and records `baselineVerified`:
- every `expectedFailing` test now passes;
- total tests collected is at least `baseline.totalTests`;
- skipped or xfail count is not above `baseline.skippedBaseline`;
- the patch touches no `protectedPaths` (`protectedPathsTouched` must be empty);
- `testSetDelta` (tests added or removed) is empty.
Any violation fails the TEST task even with `exitCode == 0`. `Evidence` gains `baselineVerified`, `protectedPathsTouched` and `testSetDelta`.

### Canonical patch bytes (audit M1)
`diffHash` is the SHA-256 of the canonical patch: `git diff --binary --no-color` with a fixed ordering, produced by the engine from sandbox state. Plan 21 exports **exactly these bytes** and recomputes the hash at export time. The implementation lives in one function used by both plans.

## Deliverables
`app/services/validation/{evidence.py,test_parser.py,diff.py}`, scheduler hook, tests.

## Tests and acceptance
- Table-driven parser tests (all pass, some fail, collection error, zero tests, timeout, truncated output).
- Agent says "all tests pass" while exit code is 1 -> task FAILED.
- Same diff -> same hash; one-byte change -> different hash.
- Evidence is immutable after write (no update path).

- Agent deletes a failing test, skips it, adds `xfail`, or edits `conftest.py`: exit 0 but TEST fails with `baselineVerified=false`.
- A genuine fix that makes the expected failing tests pass sets `baselineVerified=true`.
- Canonical patch bytes are stable across runs for the same change.

## Done when
Every TEST success in a run has persisted evidence that a reviewer can inspect.
