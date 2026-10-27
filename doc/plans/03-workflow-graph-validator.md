# 03 — Workflow graph validator

**Phase B · Depends on:** 02 · **Status:** not started

## Goal
Any workflow definition, from the model or a human, is proven structurally and semantically safe before it is stored or run.

## Responsibility
Pure, deterministic validation of a `WorkflowDefinition` + `WorkflowPolicy` against the registry and allowlists. **Non-goals:** generating workflows (05), persisting (06).

## Design (ARCHITECTURE §4.2 step 4)
Return a list of typed `ValidationIssue(code, taskId, message)`; valid means empty list.
Checks:
1. Unique task ids; every `dependsOn` exists; no self-dependency.
2. Acyclic (Kahn's algorithm); report one cycle path.
3. Task count ≤ `MAX_WORKFLOW_TASKS`; per-field limits (already Pydantic).
4. `agentId` exists, ACTIVE, and its `taskTypes` include the task's type.
5. `access` consistent with the agent's `sandboxWrite` permission (a WRITE task needs a write-capable agent).
6. Every protected action reachable in the graph has a `HUMAN_APPROVAL` task as an ancestor.
7. Every command referenced in `config` is in the repository allowlist (structured argv, no shell strings).
8. Policy bounds (attempts, concurrency, timeouts) within hard caps from settings.
9. At least one terminal REVIEW task for bug-fix workflows (configurable rule, off by default).

### Ownership of the repository allowlist (audit M5)
This plan owns the **schema and loader** of `fixtures/repositories.yaml`, so plans 13 and 16 do not depend on each other's files:
- `RepositoryConfig` (Pydantic): `path`, `commands` (argv arrays), `suites` (suite id to argv), `protectedPaths` (test dirs, `conftest.py`, test config; read-only for agents), `baseline` (`totalTests`, `expectedFailing[]`, `skippedBaseline`), resource limits.
- `RepositoryRegistry.load()` validates the YAML; unknown commands or empty `protectedPaths` for a fixture with tests are rejected.
- A minimal `fixtures/sample` repository (one failing test, one fix) ships with this plan so plans 13-15 have a workspace before plan 16 adds the full set.
- Rule 8 is extended with run budgets: `maxRunSeconds`, `maxModelCalls`, `maxOutputBytes` added to `WorkflowPolicy`, each bounded by hard caps from settings (`min(policy, settings)` is what the scheduler enforces, see plan 09).

## Contracts
No endpoints. Used by planner (05) and `POST /workflows` (06). Issues are returned in `422` details.

## Deliverables
`app/services/graph_validator.py`, `ValidationIssue` schema, table-driven tests.

## Tests and acceptance
One failing case per rule above, plus: valid linear, diamond, and parallel-branch graphs pass; 20-task graph passes, 21 fails; cycle error names the tasks; validator never mutates input; runtime under 50 ms for 20 tasks.
- `RepositoryConfig` rejects a suite whose argv is not allowlisted and a fixture without `protectedPaths`.
- A policy value above the settings hard cap fails validation with a typed issue.

## Risks
The allowlist format is defined here (see Ownership of the repository allowlist) and reused by plans 13, 14 and 16.

## Done when
All rules covered by tests and wired as the only gate used by later plans.
