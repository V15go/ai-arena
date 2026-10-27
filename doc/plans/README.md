# AI ARENA — Feature Plans and Work Order

Each file in this folder plans **one** feature with **one** responsibility. Implement them in the order below; a feature may start only when everything in its *Depends on* list is done. Source of truth for design: [../ARCHITECTURE.md](../ARCHITECTURE.md). Product intent: [../Master.md](../Master.md).

**Slice 1 (foundation) is already done**: monorepo, FastAPI app, models + first Alembic migration, Pydantic schemas, bearer auth, logging/errors, orchestrator transactional core, `SandboxProvider` + fake, React shell, generated TypeScript contracts.

Stack (final): Python 3.12 + FastAPI + Pydantic + SQLAlchemy/Alembic + pytest; React + TypeScript + Vite + Tailwind; Neon PostgreSQL; Modal sandbox (fake for tests). SQLite appears only as the fast unit-test database and is never evidence for lock or race behaviour (plan 01).

## Working rules (apply to every plan)
1. One feature = one branch/PR. Do not pull work from a later plan forward.
2. Tests first for logic that carries an invariant (state, budgets, validation, approvals, memory).
3. Build against fakes (fake sandbox, scripted model) until the plan says "real".
4. After any API change run `pnpm contracts:generate` and commit the output.
5. Run `pnpm check` before calling a feature done; report anything that could not run.
6. Never claim an improvement the evaluation (plan 23) has not measured.
7. **Postgres-required tests.** Tests of locks, budgets, leases, ordering and races are marked `pg_required` and must run with `REQUIRE_PG=1` against Neon or local Postgres (plan 01). A skipped one fails the gate.
8. **One migration per plan that needs schema**, numbered per the migration table below; one Alembic head, no drift.
9. **Sole writer.** Only `app/orchestrator` changes run/task status, budgets, leases and events; every plan that adds such a write adds an `Orchestrator` method, and the authority test stays green.

## Spikes (not new plans: the first step of plans 04 and 14, run at project start)
| Spike | Source | Output | Gates |
|---|---|---|---|
| **S1** Meta Model API | first step of plan 04 | `doc/META_API_NOTES.md` | plan 04 adapter code, plan 13 |
| **S2** Modal SDK | first step of plan 14 | `doc/MODAL_NOTES.md` | plan 09 (it fixes the `SandboxProvider` snapshot additions), plan 14 adapter code |

Run S1 and S2 in parallel with plan 01. If a spike changes the interface, change the interface, the fake and the contract tests first.

## Work order

Rows are in implementation order. Note Phase E: **16 before 15**.

| # | Plan | Single responsibility | Depends on | Master step |
|---|---|---|---|---|
| **Phase B — Data and contracts** |
| 01 | [neon-database-integration](01-neon-database-integration.md) | Prove the schema and migrations on real Neon Postgres; define the `pg_required` tier | slice 1 | 3 |
| 02 | [agent-registry](02-agent-registry.md) | DB-backed, versioned, permission-capped agent definitions | 01 | 4 |
| 03 | [workflow-graph-validator](03-workflow-graph-validator.md) | Semantic validation of any workflow DAG; owns the repository allowlist schema and loader | 02 | 4 |
| **Phase C — Planning and reuse** |
| 04 | [model-provider](04-model-provider.md) | The only code that talks to the Meta Model API | slice 1, S1 | 7 |
| 05 | [workflow-planner](05-workflow-planner.md) | Natural-language goal to validated draft workflow | 03, 04 | 4 |
| 06 | [workflow-versioning-and-definition-memory](06-workflow-versioning-and-definition-memory.md) | Persist, version, find and reuse saved workflows | 05 | 5 |
| **Phase D — Execution core (fakes only)** |
| 07 | [run-creation](07-run-creation.md) | Create an idempotent run from a pinned workflow version; record the run config | 06 | 6 |
| 08 | [event-store-and-sse](08-event-store-and-sse.md) | Ordered, replayable event stream to clients | 07 | 6 |
| 09 | [task-scheduler](09-task-scheduler.md) | Pick next tasks with locks, snapshots and transactional budgets | 07, 08, S2 | 6 |
| 10 | [run-lifecycle-cancel-resume](10-run-lifecycle-cancel-resume.md) | Cancellation, heartbeats, restart recovery | 09 | 6 |
| 11 | [web-workflow-builder-and-graph](11-web-workflow-builder-and-graph.md) | Connect screen, plan/save workflows, render the DAG | 06 | 2 |
| 12 | [web-run-inspector](12-web-run-inspector.md) | Live run view (SSE) and execution history page | 08, 09, 10, 11 | 2, 10 |
| **Phase E — Real agents and sandbox** |
| 13 | [tool-registry-and-agent-runtime](13-tool-registry-and-agent-runtime.md) | Run an agent role with only its allowed typed tools; protect test files | 02, 03, 04, 09, S1 | 4, 7 |
| 14 | [modal-sandbox-adapter](14-modal-sandbox-adapter.md) | Real remote sandbox behind `SandboxProvider` | slice 1, S2 | 8 |
| 16 | [fixture-repos](16-fixture-repos.md) | Synthetic buggy repositories with baselines | 03, 14 | 7 |
| 15 | [validation-engine](15-validation-engine.md) | Turn sandbox output into trusted, baseline-checked evidence | 13, 14, 16 | 7 |
| **Phase F — Recovery and learning** |
| 17 | [failure-injection](17-failure-injection.md) | Deterministic, reproducible failures | 15, 16 | 10 |
| 18 | [recovery-policy-and-classifier](18-recovery-policy-and-classifier.md) | Classify failures; policy judges every proposal, whatever its source | 09, 15 | 9 |
| 19 | [recovery-proposer](19-recovery-proposer.md) | Model-proposed recovery, bounded by policy | 04, 17, 18 | 9 |
| 20 | [experience-memory-and-lesson-writer](20-experience-memory-and-lesson-writer.md) | Store and retrieve only verified, baseline-checked lessons | 15, 18, 19 | 5, 9 |
| **Phase G — Human control** |
| 21 | [approval-manager](21-approval-manager.md) | Approvals bound to the recomputed diff hash, gating protected actions | 09, 10, 15 | 10 |
| 22 | [web-approvals](22-web-approvals.md) | Approval inbox and decision UI | 12, 21 | 10 |
| **Phase H — Measurement and visibility** |
| 23 | [evaluation-engine](23-evaluation-engine.md) | Reproducible baseline vs ARENA metrics from persisted data | 17, 19, 20, 21 | 10 |
| 24 | [web-evaluation-dashboard](24-web-evaluation-dashboard.md) | Side-by-side results and history | 23 | 10 |
| 25 | [web-memory-view](25-web-memory-view.md) | Inspect saved workflows and lessons | 06, 20 | 2 |
| **Phase I — Hardening and demo** |
| 26 | [security-hardening](26-security-hardening.md) | Rate limits, secret hygiene, accepted-risk register, security tests | 14, 19, 21 | 9 |
| 27 | [e2e-demo-and-fallbacks](27-e2e-demo-and-fallbacks.md) | Prove the three Master claims (API and browser E2E), with fallbacks | all | 11 |

## Migration table
| Migration | Plan | Change |
|---|---|---|
| `0001` | slice 1 | all 11 initial tables |
| `0002` | 09 | `workflow_runs.output_bytes` |
| `0003` | 20 | `workflow_memories.scope` (default `global`) and index `(scope, workflow_id, fingerprint)` |
| `0004` | 21 | `approvals.expires_at` |
| `0005` | 23 | `evaluation_batches` table, `evaluation_results.batch_id` |

Applied in this order. If plans that add migrations run in parallel (for example 20 and 21), renumber on rebase before merging. A plan that discovers a new schema need adds the next number and updates this table.

## Parallelism
- S1, S2 and plan 01 start together.
- After 06, the web plan 11 can run alongside the backend chain 07 -> 10; plan 12 waits for 10.
- Plan 14 (adapter code) can overlap with 09/10 once S2 is done, because both use the `SandboxProvider` contract; plan 16 can start once 03 and 14 exist.
- 17 and 18 can run in parallel; **19 needs 17 and 18; 20 needs 19.** Plans 21 and 22 can start after 10/15.
- Plans that edit the same area must not run in parallel: 09, 10, 13, 18, 19, 20 and 21 all touch `orchestrator/` or the recovery hook.

## Milestones and gates
| Milestone | After | Gate (must be true) |
|---|---|---|
| **M0** | S1, S2, 01 | `META_API_NOTES.md` and `MODAL_NOTES.md` reviewed; `pg_required` tests run green with `REQUIRE_PG=1` on Neon |
| **M1** | 10 (+12 for the UI) | A full run completes on the fake sandbox with a scripted model; event log replays; snapshot, budget, lease and cancel tests green on Postgres |
| **M2** | 15 | The same run executes real tests in Modal and records baseline-verified evidence |
| **M3** | 20 | An injected failure is recovered; a verified lesson is stored and reused through policy |
| **M4** | 24 | Baseline vs ARENA numbers from a stored, reproducible batch are visible |
| **M5** | 27 | API and browser E2E green on fakes in CI; live run passed twice; runbook reviewed |

## Decisions recorded here
- **Authorization:** one static API token, and it is the admin. Any holder can approve any run, including their own (accepted limitation, documented in `SECURITY.md`).
- **Web auth:** Connect screen with the token in `sessionStorage`; the dev proxy forwards `/api` and injects nothing.
- **Deviation from Master §7:** protected action is a local patch export (`EXPORT_PATCH`); GitHub PR creation (`CREATE_PR`) is deferred.
- **Code comments say "slice N"** (ARCHITECTURE.md §10 numbering). Mapping to plans: slice 1-2 = done; 3 = plan 01; 4 = plans 02-03; 5 = plans 04-05; 6 = plan 06; 7 = plans 07-10; 8 = plans 11-12; 9 = plans 13-16; 10 = plans 17-20; 11 = plans 21-22; 12 = plans 23-25; 13 = plans 26-27.

## Plan file template
Goal · Responsibility and non-goals · Depends on · Design · Contracts and data · Deliverables · Tests and acceptance · Risks and open questions · Done when. Sections headed "Corrections from the audit" carry the requirements added by the plan audit.
