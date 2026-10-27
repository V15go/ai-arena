# AI ARENA — Target Architecture

Sources: `doc/Master.md` (product blueprint, authoritative) and `ai-arena-starter.zip` (scaffold: pnpm monorepo, Fastify, shared Zod contracts, empty React shell).
Rule used to reconcile them: **Master.md wins on product and infrastructure; the starter wins on repo mechanics and safety invariants.**

---

## 0. Stack decision: Python backend (supersedes the TypeScript details below)

Final stack: **React + TypeScript + Vite + Tailwind** frontend; **Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2 (async) + Alembic + pytest** backend; **Neon PostgreSQL** (JSONB, no pgvector); **Modal** sandbox behind a Python `SandboxProvider` with a deterministic fake; **no Docker, no E2B**.

Everything in this document that says Fastify, Zod, Drizzle, Vitest (backend) or `.ts` should be read through this mapping. Architecture, invariants, data model and flows are unchanged.

| Was | Now |
|---|---|
| Fastify routes | FastAPI routers under `/api/v1` (`app/api/v1`) |
| Zod schemas in `packages/shared` | Pydantic schemas in `app/schemas` are **authoritative**; `packages/contracts` holds TypeScript types **generated** from FastAPI's OpenAPI (`pnpm contracts:generate`); a pytest fails if the committed `openapi.json` is stale |
| Drizzle schema + drizzle-kit | SQLAlchemy 2 models in `app/models` + Alembic migrations in `apps/api/migrations` |
| Vitest (backend) | pytest + pytest-asyncio (SQLite for unit tests, Postgres/Neon for integration) |
| `ToolRegistry` Zod arg validation | Pydantic models per tool |

Schema amendments made while implementing slice 1 (all additive to §5):
- `workflow_runs.created_at` (needed for ordering/pagination) and `workflow_runs.total_attempts` (the transactional run-level attempt budget, §4.4).
- `tasks.agent_id` / `agent_version` are nullable: `HUMAN_APPROVAL` tasks have no agent. `(agent_id, agent_version)` is a composite FK to `agents`.
- `UNIQUE(run_id, task_key)` on `tasks`, `UNIQUE(task_id, attempt_no)` on `task_attempts`.
- JSONB/array columns use SQLAlchemy `JSON().with_variant(JSONB)` so unit tests can run on SQLite; production is Postgres.
- Wire format is camelCase (`repositoryId`), Python attributes are snake_case.

---

## 1. Analysis: where the starter and Master disagree

| Area | Starter | Master.md | Decision |
|---|---|---|---|
| Database | SQLite + Drizzle | Neon PostgreSQL (Master also said Drizzle; superseded by SQLAlchemy + Alembic, §0) | **Neon.** `DATABASE_URL` (pooled) and `DATABASE_URL_DIRECT` (migrations). |
| Sandbox | Local Docker, "fail closed" | E2B/Modal behind provider interface, no local Docker | **`SandboxProvider` interface**, **Modal adapter (primary)** + in-memory fake for tests. Keep the starter's policy list as the interface contract. |
| Agents | Task types only (`INVESTIGATE/FIX/TEST/REVIEW`) | Agent Registry with capabilities, tools, permissions | **Add registry.** Task type stays; each task binds to an `agentId`. |
| Versioning | One immutable definition per workflow | `workflows` + `workflow_versions` | **Add versions.** Runs pin a `workflowVersionId`. |
| Memory | None | Definition memory + Experience memory | **New module**, the core differentiator. |
| Recovery | One-paragraph policy | Recovery Supervisor with classify → retry/replan/escalate | **Keep starter's policy as hard rules, add the Supervisor on top.** |
| Evaluation | `GET /evaluations/summary` stub | Baseline vs ARENA comparison | **Run `mode` flag (`BASELINE` / `ARENA`)**, same orchestrator, memory switched off for baseline. |
| Tables | Unspecified | 8 tables | Adopted as-is, plus `lessons`-evidence fields and `evaluation_cases` (§5). |

Things in the starter worth keeping unchanged: modular monolith, Orchestrator as sole writer of state, "model output is untrusted", persisted event sequence numbers, SSE with `Last-Event-ID`, idempotent run creation, approval re-checked immediately before the protected action, secrets redaction.

Gaps neither document covers (addressed below): how runs survive a restart, how SSE works over Neon's pooled connections, what makes a lesson "verified", how a failure is fingerprinted for lookup, how the "no replanning" claim is proven in the demo.

---

## 2. System overview

```
                 ┌──────────────────────── apps/web (React · Vite · Tailwind · React Flow) ───────────────────────┐
                 │ Planner/Builder · Workflow graph · Live run inspector · Memory view · Approvals · Eval dashboard │
                 └──────────────┬───────────────────────────────────────────────────────▲──────────────────────────┘
                         REST /api/v1                                          SSE /runs/:id/events
                 ┌──────────────▼───────────────────────────────────────────────────────┴──────────────────────────┐
                 │                         apps/api  — FastAPI modular monolith (single process)                    │
                 │                                                                                                  │
                 │  api/ ── routes, Pydantic      , error mapper, auth guard, SSE                                  │
                 │                                                                                                  │
                 │  ┌─ Planner ──┐  ┌─ Memory Engine ─┐   ┌────────── Orchestrator (state machine) ──────────┐      │
                 │  │ prompt→DAG │  │ definition mem  │◄─►│ scheduler · transitions · budgets · cancel       │      │
                 │  │ + validate │  │ experience mem  │   │ SOLE writer of run/task status                   │      │
                 │  └─────┬──────┘  └────────▲────────┘   └──┬──────────┬───────────┬──────────┬─────────────┘      │
                 │        │                  │               │          │           │          │                    │
                 │  ┌─────▼──────┐   ┌───────┴───────┐  ┌────▼─────┐ ┌──▼───────┐ ┌─▼────────┐ ┌▼───────────┐       │
                 │  │ModelProvider│  │ Recovery      │  │AgentRuntime│ │Validation│ │Approval  │ │ EventStore │       │
                 │  │ (Meta API)  │  │ Supervisor    │  │+ToolRegistry│ │Engine    │ │Manager   │ │ + SSE hub  │       │
                 │  └─────────────┘  └───────────────┘  └────┬─────┘ └──▲───────┘ └──────────┘ └────────────┘       │
                 │                                           │          │                                           │
                 │                                    ┌──────▼──────────┴─┐        ┌──────────────────────┐          │
                 │                                    │  SandboxProvider   │        │ Evaluation Engine    │          │
                 │                                    │  (interface)       │        │ (reads events/runs)  │          │
                 │                                    └──────┬─────────────┘        └──────────────────────┘          │
                 └───────────────────────────────────────────┼───────────────────────────────┬─────────────────────────┘
                                                             │                               │ SQLAlchemy  
                                                  ┌──────────▼─────────┐             ┌───────▼────────┐
                                                  │   Modal sandbox     │             │ Neon PostgreSQL │
                                                  │ (remote, disposable)│             └────────────────┘
                                                  └────────────────────┘
```

**Style:** Python (FastAPI) modular monolith. Modules talk through typed interfaces, never reach into each other's tables. No queue broker, no microservices — the run loop is in-process and its state lives in Postgres.

---

## 3. Repository layout

`[x]` = exists after slice 1; the rest arrives in the slice noted in §10.

```
ai-arena/
├── apps/
│   ├── web/                        React + Vite + Tailwind (src/api/client.ts = typed openapi-fetch client)
│   └── api/
│       ├── app/
│       │   ├── main.py             [x] create_app(): CORS, request-id middleware, error handlers, routers
│       │   ├── api/v1/             [x] health, agents, workflows, runs (+events), approvals, memories (read-only)
│       │   ├── core/               [x] config.py (pydantic-settings), logging.py, errors.py, security.py, ids.py
│       │   ├── db/                 [x] base.py (Base, JSONB variants), session.py (lazy async engine, Neon pooler-safe)
│       │   ├── models/             [x] SQLAlchemy tables = §5
│       │   ├── schemas/            [x] Pydantic contracts (enums, agents, workflows, runs, events, approvals, memory, sandbox)
│       │   ├── repositories/       [x] read helpers + keyset pagination (no status writes)
│       │   ├── orchestrator/       [x] state_machine.py, orchestrator.py (transactional core)  → scheduler/recovery: slices 7, 10
│       │   ├── sandbox/            [x] provider.py (allowlist/timeout/output caps in the base class), fake.py → modal.py: slice 9
│       │   ├── services/           planner, validation, approvals, evaluation   (slices 5-12)
│       │   ├── agents/             registry repo + seed, runtime, tools          (slice 4, 9)
│       │   ├── memory/             definition + experience memory, fingerprint, lesson writer (slices 6, 10)
│       │   └── scripts/            [x] export_openapi.py
│       ├── migrations/             [x] Alembic (async env, prefers DATABASE_URL_DIRECT)
│       └── tests/                  [x] pytest
├── packages/contracts/             [x] openapi.json (committed) + generated src/schema.d.ts
├── fixtures/                       synthetic buggy repos (slice 9)
├── doc/                            Master.md, ARCHITECTURE.md
└── .env.example, README.md
```

Dependency rule (enforced by `tests/test_orchestrator_authority.py` for the first clause, by review for the rest): **only `app/orchestrator` writes run/task status, budget counters or events**; `api` depends on `repositories`/`services`/`orchestrator`; `agents → {tools, model}`; `tools → sandbox`; only `model/` knows Meta API details; only `sandbox/modal.py` knows Modal.

---

## 4. Core components

### 4.1 Agent Registry (DB-backed, human-managed)
Stored in Neon (`agents` table, §5) so agents can be added, versioned and disabled without a redeploy. The five built-in agents are inserted by `seed.py` (idempotent upsert on `(id, version)`).

Guardrails, because the registry now holds mutable data:
- **The model has no write path to it.** Only seed scripts and an authenticated admin route (`/api/v1/agents`, human token) can write; the Planner and Supervisor get a read-only repo.
- **Rows are immutable per version.** Changing an agent inserts a new `(id, version)`; `workflow_versions.agent_versions` pins exact versions, so old workflows keep running with the agents they were planned against.
- **Permissions can't exceed the code ceiling.** `tools` must be a subset of the tool IDs compiled into `ToolRegistry`, and `permissions` are validated against a max-permission constant in code at write time *and* load time. A DB row can select tools; it cannot create one or grant `network`/protected actions beyond the ceiling.
- Disabled/deprecated agents make dependent versions fail `checkCompatible`, surfaced to the user.

Shape of a row (`definition` jsonb, validated by the Pydantic `AgentDefinition` schema):

```python
AgentDefinition = {
  id: "investigator" | "fix" | "test" | "review" | "recovery-supervisor",
  version: "1.0.0",
  taskTypes: TaskType[],                 // which task types it may serve
  tools: ToolId[],                       // subset of ToolRegistry
  inputs / outputs: PydanticModel,       // structured I/O per task
  promptVersion: "investigator@1",        // behaviour is versioned with the agent
  permissions: { sandboxWrite: boolean, network: false, protectedActions: [] },
  modelProfile: "planner" | "fast"
}
```
Planner may only reference `agentId`s that exist and whose `taskTypes` match. Capabilities/permissions are checked again at run time (§7, "compatibility").

### 4.2 Planner
1. Input: goal, `repositoryId`, acceptance criteria.
2. **Memory first:** ask Definition Memory for a compatible saved version → if found, return it with `source: "memory"` and **zero model calls**.
3. Else call `ModelProvider` with the registry summary and a JSON-only schema.
4. Validate: Pydantic parse → graph checks (unique ids, deps exist, acyclic, ≤ `MAX_WORKFLOW_TASKS`, agent/taskType match, protected tasks have an approval gate upstream, every command referenced is on the allowlist).
5. One bounded repair round (feed validation errors back to the model) then fail with `422`.
6. Persist as `workflow_versions` row only when the user saves (`POST /workflows`); `plan` itself returns a draft.

### 4.3 Workflow Memory Engine
Two stores, two interfaces, deliberately separate:

**Definition memory** – `workflows` + `workflow_versions`. Lookup key: `(workflowId, version)` for explicit reuse, or `(repositoryId, goalFingerprint)` for suggested reuse. Compatibility check before reuse (`checkCompatible(version, env)`): registry agent versions satisfy `agentVersionRange`, every tool/command still on allowlist, policy hash unchanged or loosened-by-human only. Incompatible → surfaced to the user, never silently replanned.

**Experience memory** – `workflow_memories`. Lookup key is the **failure fingerprint**:
```
fingerprint = sha256( workflowId | taskType | failureClass | normalizedSignal )
normalizedSignal = failing test name + first N lines of assertion message, with paths/line numbers/timestamps/hex ids stripped
```
Deterministic string matching first; pgvector deferred, as Master specifies. Retrieval returns top-k by (exact fingerprint, same failureClass, recency × confidence).

**Verified-lesson rule (enforced in code, not prompt):** a lesson row can only be created by `lesson_writer.py`, which requires an `evidence` object produced by the Validation Engine: `{ attemptId, sandboxExecId, exitCode, testSummary, diffHash }`. Pass condition = a *later* attempt that applied the proposed strategy ended with `exitCode == 0` and the target tests green. Agent self-reports never reach the writer. Failed strategies are also stored (`outcome: "FAILED"`) so they are not proposed again. Confidence = successes / (successes + failures) with a floor on sample size.

Memory can inform the Supervisor's *proposal*; it can never alter policy, budgets, or approvals (Master §9). A memory hit is turned into a `RecoveryProposal(source=MEMORY)` and goes through `policy.decide()` like a model proposal; a fingerprint match never bypasses policy. The lesson writer also requires `baselineVerified`, an empty `protectedPathsTouched`/`testSetDelta`, and a later attempt whose `recovery_decision.strategyId` matches the lesson. `workflow_memories.scope` (default `global`) isolates evaluation batches.

### 4.4 Orchestrator (deterministic, sole state writer)
- Loads the pinned `workflow_version`, materialises `tasks` rows for the run, computes ready set by dependencies.
- Each transition = one DB transaction: `UPDATE status` (with optimistic `WHERE status = expected`), `INSERT execution_events` with `seq = max+1` for the run. This makes the event log the audit trail and the SSE source.
- Executes ready tasks **in parallel** up to `policy.maxConcurrency` (default 3, hard cap from env). Rules that keep this safe and deterministic:
  - A task declares `access: "READ" | "WRITE"` on the run workspace (from its agent/type). `READ` tasks (e.g. INVESTIGATE branches, REVIEW) may overlap; a `WRITE` task (FIX, patch apply) takes an exclusive workspace lock — nothing else runs alongside it. Parallelism is therefore mainly for investigation/analysis branches and independent test suites on snapshots.
  - Parallel `TEST` tasks run in separate sandboxes **restored from an immutable snapshot** taken after the last WRITE task (`SandboxProvider.snapshot/restore`, or `export_workspace` + re-upload when the provider has no native snapshot). The snapshot id is recorded in the `TASK_STARTED` event. The approval gate holds the workspace lock from request to export so the reviewed diff cannot change.
  - Budgets (total attempts, model calls, output bytes, wall-clock deadline) are run-level counters updated by single conditional UPDATEs through `Orchestrator.consume_attempt / consume_model_call / add_output_bytes / check_deadline`, so concurrent tasks can't jointly overshoot them. Effective limits are `min(policy, settings)`; an exhausted budget escalates with reason `BUDGET_EXHAUSTED`.
  - Event `seq` allocation stays per-run serialized (single `INSERT … seq = max+1` under a per-run advisory lock), so ordering in SSE is total.
  - If one branch fails, siblings get cancelled or allowed to finish per `policy.onSiblingFailure` (default: finish READ tasks, cancel the rest); recovery for the failed task proceeds while the lock rules still hold.
  - Run state ownership is unchanged: one orchestrator loop owns all transitions; tasks run as concurrent promises but report results back to that loop.
- Enforces budgets per run: max attempts per task, max total attempts, max wall-clock, max sandbox output bytes, max model calls.
- Crash safety: `workflow_runs.heartbeat_at` + `lease_owner`. On boot, the orchestrator resumes `RUNNING` runs whose lease expired: a task caught mid-attempt is marked `FAILED(INTERRUPTED)` and goes through normal recovery. Approvals waiting in `WAITING_APPROVAL` need no resume — they are just rows.
- Cancel: sets `cancel_requested`; the loop checks between steps, kills the sandbox exec, transitions to `CANCELLED`.

### 4.5 Recovery Supervisor
Two layers so safety is never delegated to the model:

1. **Policy (code, `policy.py`)** – hard rules from the starter: never retry policy violation / invalid approval / sandbox-security failure; retry transient infra errors within budget; replan only with new evidence; stop on budget exhaustion with a readable report.
2. **Classifier + proposer** – `classifier.py` deterministically tags the failure (`TRANSIENT_INFRA | TEST_FAILURE | BUILD_ERROR | DEPENDENCY_MISSING | TIMEOUT | POLICY_VIOLATION | UNKNOWN`) from exit codes and parsed output. Only for `TEST_FAILURE / BUILD_ERROR / DEPENDENCY_MISSING / UNKNOWN` does the model get called, with: evidence, previous attempts, and relevant experience memories. It returns a `RecoveryProposal`:
   ```python
   { decision: "RETRY" | "REPLAN" | "ESCALATE",
     rationale: string,
     changes?: { taskPatch?: …, extraContext?: string, strategyId?: string } }
   ```
   `policy.py` then accepts, narrows, or overrides the proposal (e.g. a `REPLAN` with no new evidence becomes `ESCALATE`). The final decision and the reasons for overriding are persisted in `task_attempts.recovery_decision` and emitted as `RECOVERY_PLANNED`.

If a high-confidence experience memory matches the fingerprint, the Supervisor may skip the model call and submit the stored strategy to policy as a memory proposal (`decisionSource: "MEMORY"`) — this is what makes the "learned" recovery observable in the demo.

### 4.6 AgentRuntime + ToolRegistry
- Agent = role prompt + allowed tools + output schema. The model returns **structured tool calls**; the runtime validates args with Pydantic and dispatches to a typed tool. There is no `runShell(string)` tool.
- Tool examples: `listFiles`, `readFile`, `searchCode`, `applyPatch(unifiedDiff)`, `runTests(suiteId)`, `gitDiff`. `runTests` maps `suiteId → fixed argv` from a per-repository allowlist; arguments are structured, not shell strings.
- Patch application validates paths stay inside the workspace and size limits.

### 4.7 SandboxProvider (provider-neutral)
```python
class SandboxProvider(ABC):
  create(spec)  # template + timeout; no environment variables can be requested
  upload_workspace(h, files: Mapping[str, bytes])
  snapshot(h) -> SnapshotHandle            # immutable; or capabilities.snapshot == False
  restore(snapshot) -> SandboxHandle
  export_workspace(h) -> Mapping[str, bytes]
  exec(h, request)  # argv list, cwd, timeout, output cap -> {exit_code, stdout, stderr, truncated, duration_ms, exec_id}
  read_file(h, path) / write_file(h, path, data)
  destroy(h)                               # idempotent
```
- `ModalSandboxProvider` (primary; maps `create/exec/readFile/destroy` onto Modal Sandboxes with a pre-built image, no inbound network, outbound blocked where Modal supports it), `FakeSandboxProvider` (deterministic, in-memory, for unit tests and offline demo fallback). Verify the current Modal Sandbox SDK surface (language, exec streaming, file API, limits) against Modal's docs before writing the adapter; adapt only `modal.py`; interface changes (if the spike forces any) are made in the interface, the fake and the contract tests first.
- With parallel tasks, `exec` must be safe to call concurrently on one handle, or the provider hands out one handle per concurrent task; the adapter declares which via `capabilities.concurrentExec`.
- The `SandboxProvider` base class (`provider.py`) rejects any `argv[0]` not in the approved list *before* the adapter is called. Provider API keys live only in the API process environment. Nothing from the API environment is forwarded to the sandbox.
- Only the committed `fixtures/` repo is uploaded in the hackathon build (satisfies "no proprietary code to third parties").
- Sandbox lifetime = one run; destroyed in a `finally` and by a reaper for orphaned handles.
- Hardening per Spike S2 (`doc/MODAL_NOTES.md`): non-root user, PID limit, read-only root with writable `/workspace` and `/tmp`, egress control where supported; whatever is unsupported is an accepted risk in `doc/SECURITY.md`.

### 4.8 Validation Engine
Produces the **evidence object** every success claim must cite: raw `exitCode`, parsed test summary (passed/failed/skipped, failing names), `git diff` stat + hash, command executed, sandbox `execId`, timestamps. The Orchestrator only moves a `TEST` task to `SUCCEEDED` if validation says so — the Test Agent's text output is informational. `REVIEW` reads this evidence and the diff; it can *block* but cannot mark tests as passed.

**Baseline integrity.** Exit code 0 is not sufficient. Each repository declares `protectedPaths` (tests, `conftest.py`, test config) and a `baseline` (`totalTests`, `expectedFailing`, `skippedBaseline`) in `fixtures/repositories.yaml`. A TEST succeeds only if the expected failing tests now pass, the test count has not dropped, skips/xfails are not above baseline, and the patch touches no protected path (`baselineVerified`, `protectedPathsTouched`, `testSetDelta` in `Evidence`). Agents cannot write protected paths at all (`apply_patch`), so deleting or skipping tests can neither pass a task nor become a lesson.

### 4.9 Approval Manager
- Protected actions are a code-level enum (`EXPORT_PATCH`, `CREATE_PR`, …) declared in `protected_actions.py`; the Planner must place a `HUMAN_APPROVAL` task before any task that performs one.
- Flow: task reaches gate → `approvals` row `PENDING` + run `WAITING_APPROVAL` → user decision via API → decision row written with `decided_by` taken from the **server-side auth context**, never the request body.
- **At execution time** the protected tool calls `approvalManager.assertApproved(actionId, runId, payloadHash)` inside the same transaction that performs the action. The approval is bound to the *diff hash* shown to the reviewer, so a changed patch invalidates it. The hash is **recomputed at action time** from the canonical patch bytes (`git diff --binary --no-color`, one shared function with the Validation Engine), and the export writes exactly those bytes; a caller never supplies the hash. A refused action emits `PROTECTED_ACTION_BLOCKED`. A run is `WAITING_APPROVAL` if and only if a `PENDING` approval exists. `approvals.expires_at` drives expiry.
- Reject or timeout → action never runs; run ends `FAILED(APPROVAL_REJECTED)` (recorded, not hidden).
- MVP "protected action" = export the patch/commit to a local artifact. Real GitHub PR creation stays deferred, matching the starter's advice.

### 4.10 Event store, SSE
- `execution_events(run_id, seq, type, task_id, data jsonb, created_at)` with `UNIQUE(run_id, seq)`.
- SSE handler at `GET /runs/{id}/stream` (the JSON list stays at `GET /runs/{id}/events`): replay from `Last-Event-ID`/`?after=` from the table, then tail. Because Neon pooled connections don't support `LISTEN/NOTIFY` reliably, the hub is **in-process pub/sub fed by the orchestrator after commit**, with a 1-second DB poll as a fallback for gaps. Heartbeat comment every 15 s. Payloads go through a redaction step.

### 4.11 Evaluation Engine
- `evaluation_cases`: scenario id, fixture repo, injected failure type, expected recovery class.
- Failure injection is a property of the **sandbox/fixture layer**, not the agents: scenarios flip a fixture variant (e.g., "flaky first run", "missing dependency", "wrong first fix") or wrap `SandboxProvider` with a `FaultInjectingProvider` that fails the Nth exec. The agents under test are unchanged.
- Runner executes each scenario twice — `mode=BASELINE` (saved workflow, fixed retry, memory read/write disabled, no Supervisor proposer) and `mode=ARENA` — and stores run ids side by side. Metrics are computed from persisted runs/attempts/events only (never from in-memory counters), covering all eight metrics in Master §11. Report real numbers, including where ARENA doesn't win. Reproducibility: every run stores `inputs._config` (model ids, prompt versions, agent versions, fixture hash, sandbox image, seed, scenario id, git commit, memory scope); each batch has its own memory scope `eval:<batchId>` (BASELINE never touches memory, ARENA-cold starts empty, ARENA-warm follows one seeding run); model temperature is 0 and ids/seeds are recorded; results keep N repeats with mean and min/max; "protected actions blocked" counts `PROTECTED_ACTION_BLOCKED` events.

---

## 5. Data model (Neon PostgreSQL, SQLAlchemy + Alembic)

Master's eight tables + the columns that make them useful. IDs are prefixed text (`wf_`, `wfv_`, `run_`, …) generated server-side (ULID).

```
workflows            id, name, owner_id, repository_id, status(ACTIVE|ARCHIVED), latest_version, created_at
workflow_versions    id, workflow_id→, version int, definition jsonb, agent_versions jsonb, policy jsonb,
                     policy_hash, goal_fingerprint, source(MODEL|MEMORY|MANUAL), created_at   UNIQUE(workflow_id, version)
workflow_runs        id, workflow_version_id→, mode(ARENA|BASELINE), status, inputs jsonb, idempotency_key UNIQUE,
                     started_at, finished_at, heartbeat_at, lease_owner, cancel_requested,
                     planner_calls int, model_calls int, tokens_in/out int, est_cost_usd numeric, outcome jsonb,
                     created_at, total_attempts int, output_bytes int (0002)   -- inputs jsonb carries `_config`
agents               id, version, definition jsonb, status(ACTIVE|DEPRECATED|DISABLED), created_by, created_at   PK(id, version)
tasks                id, run_id→, task_key (id from definition), type, agent_id, agent_version, access(READ|WRITE), status,
                     depends_on text[], position, config jsonb, started_at, finished_at
task_attempts        id, task_id→, attempt_no, status, started_at, finished_at, input jsonb, output jsonb,
                     error jsonb, failure_class, fingerprint, recovery_decision jsonb, decision_source(POLICY|MEMORY|MODEL),
                     evidence jsonb  -- exitCode, test summary, diff hash, execId
execution_events     id, run_id→, seq, type, task_id, message, data jsonb, created_at   UNIQUE(run_id, seq)
approvals            id, run_id→, task_id→, action(enum), payload_hash, summary jsonb, status(PENDING|APPROVED|REJECTED|EXPIRED),
                     requested_at, decided_at, decided_by, comment, expires_at (0004)
workflow_memories    id, workflow_id→, fingerprint, failure_class, strategy jsonb, outcome(SUCCEEDED|FAILED),
                     evidence jsonb NOT NULL, source_attempt_id→ NOT NULL, success_count, failure_count, confidence,
                     env_constraints jsonb, scope text default 'global' (0003), created_at, last_used_at
evaluation_cases     id, name, fixture_id, injection jsonb, expected jsonb
evaluation_batches   id, config jsonb, created_at   (0005)
evaluation_results   id, case_id→, batch_id→ (0005), mode, run_id→, metrics jsonb, created_at
```
Indexes: `workflow_memories(scope, workflow_id, fingerprint)`, `task_attempts(task_id, attempt_no)`, `execution_events(run_id, seq)`, `approvals(status)`.
`workflow_memories.evidence NOT NULL` + FK to a real attempt is the database-level backstop for the verified-lesson rule.
Migrations via Alembic (one migration per plan, see the plans README migration table); use Neon's **pooled** URL for the app and the **direct** URL for migrations. Dev uses a Neon branch per developer.

---

## 6. Shared contracts (Pydantic in `app/schemas`, generated into `packages/contracts`) — required additions

The starter has task/run/event/approval schemas. Add:
- `AgentIdSchema`, `WorkflowTaskSchema.agentId` (and make `config` per-task-type discriminated rather than `record<unknown>`).
- `WorkflowVersionSchema`, `WorkflowPolicySchema` (`maxAttemptsPerTask`, `maxTotalAttempts`, `taskTimeoutMs`, `approvalGates`, `maxConcurrency`, `onSiblingFailure`, `maxRunSeconds`, `maxModelCalls`, `maxOutputBytes`), `AgentDefinitionSchema` + `AgentStatusSchema`, task `access: READ|WRITE`.
- `RunModeSchema`, `FailureClassSchema`, `RecoveryProposalSchema`, `RecoveryDecisionSchema`, `EvidenceSchema`.
- `MemoryLessonSchema`, `EvaluationSummarySchema`.
- Events: add `MEMORY_HIT`, `MEMORY_WRITTEN`, `PLAN_REUSED`, `VALIDATION_COMPLETED`, `TASK_RETRY_SCHEDULED`, `PROTECTED_ACTION_BLOCKED`.
- API: `RunDetailSchema`, `ApprovalSchema`, cursor pagination envelope. `API.md` response types should be generated from these, not hand-maintained.

---

## 7. Key flows

**Plan and reuse**
```
POST /workflows/plan ─► Memory.findCompatible(repo, goalFp)
        ├─ hit  ─► return {source:"memory", version}      (planner_calls = 0)
        └─ miss ─► Model.plan ─► validate ─► (one repair) ─► draft
POST /workflows ─► insert workflow + version N
POST /workflows/:id/runs {version?, idempotencyKey} ─► checkCompatible ─► create run QUEUED ─► 202
```

**Run loop (ARENA mode)**
```
for ready tasks:
   TASK_STARTED → agent runs tools in sandbox → Validation builds evidence
   ok?  → TASK_SUCCEEDED
   fail → classify → Policy gate
            ├ Memory.lookup(fingerprint)  ─ high confidence ─► memory proposal ─► Policy.decide (source=MEMORY)
            ├ else Supervisor.propose (model) ─► Policy narrows/overrides
            └ RETRY | REPLAN(task patch, new evidence) | ESCALATE(run → FAILED with report)
   after a later success: LessonWriter(evidence) → workflow_memories  (MEMORY_WRITTEN)
REVIEW → approval gate → run WAITING_APPROVAL → decision → assertApproved → export patch → SUCCEEDED
```

**Run states** (starter's machine, kept): `DRAFT → QUEUED → RUNNING ⇄ WAITING_APPROVAL → SUCCEEDED`, with `FAILED`/`CANCELLED` from `RUNNING|WAITING_APPROVAL`. `WAITING_APPROVAL` only when a specific `approvals` row is `PENDING`. A run is `SUCCEEDED` only if the final validation evidence passes **and** acceptance criteria checks are met.

---

## 8. Security & reliability checklist (merged)

1. Model output → Pydantic → semantic validation → policy gate. Never straight to a tool, a DB write, or a sandbox.
2. Commands: `suiteId`/tool-based; argv arrays; allowlist enforced twice (tool layer and sandbox layer).
3. Secrets (Meta key, Neon URL, Modal token) only in API env; redacted in logs and SSE; never in sandbox env or prompts.
4. Sandbox is remote and disposable; network egress denied if the provider supports it, otherwise only a template with dependencies pre-baked.
5. Budgets: tasks ≤ 20, attempts per task, total attempts, wall-clock, output bytes, model calls — all in `workflow_versions.policy`, enforced by Orchestrator (not by agents).
6. Approvals bound to payload hash, identity server-side; single-user hackathon auth = static bearer token from env checked by `core/security.py` (not trusting any user id in the body).
7. Learned memory cannot widen allowlists, budgets, or approval requirements (policy is read from the version, not from memory).
8. Idempotent run creation; transactional state+event writes; resumable after restart.
9. Fixtures are synthetic; no proprietary code leaves the machine.
10. Agents cannot write `protectedPaths`; TEST success requires baseline-verified evidence (§4.8).
11. Hard caps from settings clamp every policy value (`min(policy, settings)`).
12. Accepted risks (single token = admin; unsupported sandbox hardening) are listed in `doc/SECURITY.md`.
13. Rate-limit the plan and run endpoints (`slowapi` or an equivalent ASGI middleware) so demo traffic cannot burn the model quota.

---

## 9. Adjusting the starter's Muse Code prompts

The starter's `MUSE_CODE_PROMPTS.md` hard-codes "SQLite/Drizzle" and "restricted local Docker sandbox". Before using them, replace with: *Python/FastAPI, Neon PostgreSQL with SQLAlchemy + Alembic, SandboxProvider interface with Modal adapter and Fake adapter, no Docker; DB-backed agent registry; parallel task execution with workspace locks. Superseded by the feature plans in `doc/plans/`.* Also add the registry, memory, and evaluation steps, which the starter prompts omit. `.env.example` changes:

```
DATABASE_URL=postgres://…neon…/ai_arena?sslmode=require      # pooled
DATABASE_URL_DIRECT=postgres://…                              # migrations
SANDBOX_PROVIDER=modal|fake
MODAL_TOKEN_ID=
MODAL_TOKEN_SECRET=
MODAL_SANDBOX_IMAGE=
MAX_CONCURRENCY=3
API_AUTH_TOKEN=
MAX_MODEL_CALLS_PER_RUN=
# remove: SANDBOX_IMAGE
```

---

## 10. Build order (Master §12, with the starter folded in)

| # | Slice | Done when |
|---|---|---|
| 1 | Monorepo, Pydantic contracts, generated TS contracts, models + Alembic, health/auth/errors/logging, state-machine core, sandbox interface + fake | **done** — see README for the checks |
| 2 | (folded into slice 1) | — |
| 3 | Apply the Alembic migration to a real Neon branch; repository tests against Postgres | `alembic upgrade head` succeeds on Neon; pytest integration suite green |
| 4 | Agent registry + graph validator | rejects cycles/unknown agents/over-limit graphs |
| 5 | ModelProvider (verify Meta endpoint/model IDs from event docs first) + Planner | a prompt yields a valid persisted version; mocked-model tests |
| 6 | Definition memory + reuse path | second run of same goal makes **0 planner calls** (asserted) |
| 7 | Orchestrator + state machine + events + SSE (all with FakeSandbox + scripted fake agents) | full INVESTIGATE→FIX→TEST→REVIEW run end-to-end, restart-resume test |
| 8 | Web: graph + live run inspector | graph colours update from SSE |
| 9 | Modal adapter + real tools + Validation Engine | real fixture tests run remotely; evidence stored |
| 10 | Supervisor (policy → classifier → proposer) + experience memory + lesson writer | injected failure → recovery decision → verified lesson row |
| 11 | Approval manager + protected export | reject path blocks; changed diff invalidates approval |
| 12 | Evaluation runner (BASELINE vs ARENA) + dashboard | metrics computed from DB; side-by-side view |
| 13 | E2E demo script + fallbacks (FakeSandbox, pre-seeded memory) | the three demo proofs in §11 pass |

**Slice to plan mapping** (the feature plans in `doc/plans/README.md` are the detailed work order; code comments say "slice N"): 1-2 = done; 3 = plan 01; 4 = plans 02-03; 5 = plans 04-05; 6 = plan 06; 7 = plans 07-10; 8 = plans 11-12; 9 = plans 13-16; 10 = plans 17-20; 11 = plans 21-22; 12 = plans 23-25; 13 = plans 26-27. Spikes S1 (Meta API) and S2 (Modal SDK) run at project start, before plan 09.

Steps 7 and 10 are intentionally done against fakes first: the orchestrator and recovery logic are the product, and they should be testable without the model or Modal being reachable. Parallel scheduling and workspace locks (§4.4) are tested in step 7 with the fake sandbox using deliberately slow scripted tasks.

---

## 11. Demo proof mapping (Master's three claims)

| Claim | How it's shown | Backed by |
|---|---|---|
| Workflow reused without replanning | Run the same goal twice; UI badge "plan reused — 0 planner calls" | `PLAN_REUSED` event, `workflow_runs.planner_calls = 0` |
| Injected failure → appropriate recovery | Scenario makes the first fix fail a test; Supervisor classifies `TEST_FAILURE`, proposes retry with new evidence; on a repeat run, memory supplies the strategy directly | `RECOVERY_PLANNED` event with `decision_source`, `task_attempts` rows, `MEMORY_HIT` |
| Result backed by execution evidence | Final panel shows exit code, test summary, diff hash, sandbox exec id; approval is bound to that diff hash | `task_attempts.evidence`, `approvals.payload_hash` |

---

## 12. Decisions worth confirming

1. **Modal** is the primary sandbox (decided); E2B dropped. Verify the Modal Sandbox SDK first (Spike S2, before plan 09; see `doc/plans/README.md`).
2. **Parallel task execution** (decided) with `maxConcurrency`, workspace READ/WRITE locks, and snapshot-based parallel tests.
3. **DB-backed agent registry** (decided), with immutable versions, a code-level permission ceiling, and no model write access.
4. **Single static bearer token, and it is the admin**; multi-user is out of scope per Master. Any token holder can approve any run, including their own (accepted, recorded in `SECURITY.md`).
5. **Fingerprint-based memory lookup**, no pgvector, until retrieval misses justify it. A hit is only a proposal to policy.
6. **Web auth:** Connect screen, token in `sessionStorage`, dev proxy injects nothing.
7. **Deviation from Master §7:** the protected action is a local patch export (`EXPORT_PATCH`); GitHub PR creation (`CREATE_PR`) is deferred.
8. **Postgres semantics:** SQLite is only the fast unit-test database; lock/race/budget tests are `pg_required` and must run on Postgres (plan 01).
9. **Spikes S1/S2 gate** plans 04/13 and 09 respectively.
