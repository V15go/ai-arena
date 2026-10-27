# 23 — Evaluation engine

**Phase H · Depends on:** 17, 19, 20, 21 · **Status:** not started

## Goal
Measure BASELINE vs ARENA on the same failure scenarios, from persisted data only.

## Responsibility
Scenario runner, metrics computation, summary endpoint. **Non-goals:** UI (24), changing agent behaviour.

## Design (ARCHITECTURE §4.11, Master §11)
- Tables `evaluation_cases` and `evaluation_results` (exist). A case = fixture + fault scenario + expected recovery class.
- Runner executes each case twice with identical inputs: `mode=BASELINE` (saved workflow, fixed retry policy, memory read/write off, proposer off) and `mode=ARENA`. ARENA is run both **cold** (empty memory) and **warm** (after a lesson exists) so memory's effect is separable.
- Metrics (computed by SQL over `workflow_runs`, `tasks`, `task_attempts`, `execution_events`, `approvals`; never in-memory counters): task completion rate, recovery success rate, test pass rate, attempts per run, repeated-failure rate (same fingerprint failing again), duration, model calls/tokens/estimated cost (only if the provider reports usage), protected actions blocked without approval.
- Repeat each case N times (config) to expose variance; report mean and min/max, not a single run.
- `GET /evaluations/summary` returns per-mode aggregates and per-case rows; `POST /evaluations/run` (admin) starts a batch; results link to run ids.
- Honest reporting: fields without data are `null`, never zero-filled; a "no improvement" result is displayed as is.

### Corrections from the audit (M2, M7)
- **Reproducibility record.** Each result stores the run config from plan 07 (`modelIds`, `promptVersions`, `agentVersions`, `fixtureHash`, `sandboxImage`, `seed`, `scenarioId`, `gitCommit`, `memoryScope`). Migration `0005` adds `evaluation_batches(id, config jsonb, created_at)` and `evaluation_results.batch_id`.
- **Memory isolation.** Every batch uses scope `eval:<batchId>`. BASELINE neither reads nor writes memory. ARENA-cold runs against an empty scope; ARENA-warm runs after one designated seeding run in the same scope. Nothing leaks between batches or into `global`.
- **Determinism.** Model temperature 0 and recorded model id/seed (plan 04), fixed fault seeds (plan 17), N repeats with mean and min/max; non-determinism that remains is reported, not hidden.
- **Blocked actions metric** = count of `PROTECTED_ACTION_BLOCKED` events (plan 21).
- Starting an evaluation needs the same single API token as every other route (no separate admin role).

## Tests and acceptance
- Metric functions verified on hand-built run data with known expected values.
- Baseline never calls the proposer or reads memory (asserted).
- Same seed -> same scenario conditions in both modes.
- Summary excludes runs from other cases and cancelled runs (documented rule).

- Two batches in one database do not see each other's lessons; BASELINE has zero memory reads/writes in the DB.
- A stored result contains the full config and re-running the batch with the same seeds reproduces the scenario conditions.
- Blocked-action count equals the number of `PROTECTED_ACTION_BLOCKED` events for the batch.

## Done when
A batch of >= 5 cases x N repeats produces a stored summary from real runs (**M4** data).
