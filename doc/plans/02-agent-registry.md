# 02 — Agent registry

**Phase B · Depends on:** 01 · **Status:** not started

## Goal
A database-backed catalogue of agents the planner may use, that the model can read but never write.

## Responsibility
Store, version, seed and read agent definitions; enforce the permission ceiling. **Non-goals:** running agents (plan 13), picking agents for a goal (plan 05).

## Design (ARCHITECTURE §4.1)
- Table `agents`, PK `(id, version)`, rows immutable per version; changes insert a new version; status `ACTIVE | DEPRECATED | DISABLED`.
- Five built-ins seeded idempotently: `investigator`, `fix`, `test`, `review`, `recovery-supervisor`.
- `AgentDefinition` (already a Pydantic schema): `taskTypes`, `tools`, `permissions {sandboxWrite, network, protectedActions}`, `modelProfile`.
- **Code-level ceiling** (`agents/ceiling.py`): the set of known tool ids and the maximum permissions per task type. A row may select tools but cannot add one, enable `network`, or grant a protected action beyond the ceiling. Checked at write time **and** at load time.
- Read-only `AgentRegistry` service handed to Planner/Supervisor; the only write paths are the seed script and an authenticated admin route.
- Compatibility helper: `check_compatible(agent_versions: dict[str,str])` for plan 06.
- **Behaviour is versioned with the agent (audit M2).** `AgentDefinition` gains `promptVersion` (for example `investigator@1`, a file under `app/agents/prompts/`). Same `(id, version)` must mean same behaviour, so changing a prompt requires a new agent version. No schema change (JSON column).
- **Authorization model (audit M7).** There is one static bearer token and it is the admin: `POST /agents` requires it like every other route. No second role exists in the hackathon build; this is recorded in ARCHITECTURE.md §12.

## Contracts and data
- New: `POST /api/v1/agents` (admin token; creates a new version), `GET /api/v1/agents` (exists), `GET /api/v1/agents/{id}/versions`.
- No schema change.

## Deliverables
`app/agents/registry.py`, `ceiling.py`, `seed.py`, `app/scripts/seed_agents.py`, admin route, regenerated contracts.

## Tests and acceptance
- Seeding twice leaves five rows.
- Definition naming an unknown tool, `network: true`, or a protected action above the ceiling is rejected (write and load).
- Attempt to update an existing `(id, version)` fails; creating a new version succeeds.
- Disabled agent makes `check_compatible` fail.
- Planner-facing registry object has no write methods (asserted by test).
- `promptVersion` is required; seeding the same `(id, version)` with a different `promptVersion` is rejected.

## Risks
Ceiling and tool registry (plan 13) share ids; keep ids in one module to avoid drift.

## Done when
Built-ins are seeded in Neon and the ceiling tests pass.
