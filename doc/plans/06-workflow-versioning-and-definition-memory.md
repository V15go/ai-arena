# 06 — Workflow versioning and definition memory

**Phase C · Depends on:** 05 · **Status:** not started

## Goal
Saved workflows are immutable versions that can be found and **reused without calling the model**.

## Responsibility
Persist workflows/versions, compute fingerprints, look up compatible saved versions, check compatibility. **Non-goals:** experience/lesson memory (plan 20), creating runs (07).

## Design (ARCHITECTURE §4.3 "Definition memory")
- `POST /workflows` validates with the graph validator, then inserts `workflows` (if new) and `workflow_versions` (N+1) in one transaction; `latest_version` updated; `policy_hash` = SHA-256 of canonical JSON policy; `agent_versions` pinned from the registry.
- `goal_fingerprint` = SHA-256 of normalized (lowercase, collapsed whitespace, stop-words removed) goal + `repositoryId`. Deterministic, no embeddings.
- `find_compatible(repositoryId, goal)`: exact fingerprint first, then same repo with token-set Jaccard ≥ threshold (configurable); returns candidates with a score. Never auto-selects below an exact match; UI asks the user.
- `check_compatible(version, env)`: every pinned agent ACTIVE and version satisfied, every tool/command still allowlisted, policy not wider than current caps. Returns reasons when incompatible; **never silently replans**.
- Planner integration: `POST /workflows/plan` first calls `find_compatible`; on exact hit returns `{source: "MEMORY", versionId}` with zero model calls and emits `PLAN_REUSED` when a run starts.

## Contracts
`POST /workflows`, `GET /workflows`, `GET /workflows/{id}`, `GET /workflows/{id}/versions` (exists), `GET /workflows/{id}/versions/{n}`, `POST /workflows/{id}/check-compatibility`.

## Deliverables
`app/memory/definition_memory.py`, `fingerprint.py`, service, routes, tests.

## Tests and acceptance
- Saving the same workflow twice makes version 2 only when content differs (or explicit flag).
- Concurrent saves never create duplicate `(workflow_id, version)`.
- Same goal phrased with different casing/whitespace -> same fingerprint; different repo -> different.
- Reuse path: second plan request makes **0** provider calls (asserted on `FakeModelProvider`).
- Disabling an agent flips compatibility to false with a reason.

## Risks
Fuzzy matching can mis-reuse; default to exact-only and surface fuzzy matches as suggestions.

## Done when
Plan -> save -> plan again returns the saved version with no model call.
