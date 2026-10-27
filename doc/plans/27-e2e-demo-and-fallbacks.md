# 27 — End-to-end demo and fallbacks

**Phase I · Depends on:** all · **Status:** not started

## Goal
Reliably demonstrate Master's three claims, even if a network dependency fails on stage.

## Responsibility
Scripted demo path, E2E tests, offline fallbacks, runbook. **Non-goals:** new features.

## The three proofs (ARCHITECTURE §11)
1. **Reuse without replanning** — run the same goal twice; second shows "plan reused — 0 planner calls" (`PLAN_REUSED`, `planner_calls = 0`).
2. **Injected failure -> appropriate recovery** — scenario `WRONG_FIRST_FIX`: classify `TEST_FAILURE`, proposal with new evidence (source `MODEL`); run again: lesson applied directly (source `MEMORY`, `MEMORY_HIT`).
3. **Result backed by evidence** — final panel shows exit code, test summary, diff hash, sandbox exec id; approval bound to that hash; reject path blocks the export.

## Design
- `scripts/demo_seed.py`: seeds agents, one saved workflow, optional pre-warmed lesson.
- `scripts/demo_run.py`: drives the API through the whole story and prints a verification table (each proof PASS/FAIL with the DB facts behind it).
- **Fallback modes** (switchable by env): `FakeSandboxProvider` with scripted results, `FakeModelProvider` with recorded responses, pre-seeded lesson. The UI shows a visible "fallback mode" banner so nothing is passed off as live.
- Backend E2E test (pytest) runs the whole story on fakes in CI. A separate manual checklist covers the live Meta + Modal run.
- Runbook `doc/DEMO.md`: pre-flight checks (health, Neon branch, Modal token, Meta key, fixtures), timings, what to say, what to do if each dependency fails.
- Final evaluation snapshot from plan 23 attached; claims in the demo are limited to what it shows.

## Tests and acceptance
- E2E on fakes: all three proofs verified by DB queries, not by UI text.
- Chaos check: kill API mid-run (plan 10) and the demo still completes.
- Dry run of the live path twice with timings recorded.

### Corrections from the audit (M4, DB fallback)
- **Browser-level E2E (Playwright):** against the built web app and the API in fallback mode (fake model, fake sandbox, seeded Postgres), a test connects with the token, plans a goal, saves, runs, watches the run complete, sees the history row, approves, rejects a second run, and opens the evaluation and memory pages. It asserts DB facts through the API, not just on-screen text.
- **System banner:** `GET /api/v1/system` (authenticated) reports provider modes (`model`, `sandbox`, `faultInjection`); the UI shows a visible fallback banner whenever a fake provider is active.
- **Database outage:** `/health/ready` is part of pre-flight; the runbook covers a cold or unreachable Neon branch (warm it, switch to the pre-warmed backup branch).
- CI runs the Playwright E2E on fakes; the live Meta + Modal run stays a manual checklist.

## Done when
**M5:** the demo passes on fakes in CI and live at least twice, with a runbook anyone can follow.
