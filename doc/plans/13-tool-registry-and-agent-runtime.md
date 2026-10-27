# 13 — Tool registry and agent runtime

**Phase E · Depends on:** 02, 03, 04, 09, Spike S1 notes · **Status:** not started

## Goal
Execute an agent role (Investigator, Fix, Test, Review) using only typed, allowlisted tools.

## Responsibility
`ToolRegistry`, per-tool Pydantic arguments, the agent loop, the concrete `TaskExecutor`. **Non-goals:** sandbox implementation (14), evidence building (15), recovery (18-19).

## Design (ARCHITECTURE §4.6)
- **Tools** (each a Pydantic arg model + async handler + required permission): `list_files`, `read_file`, `search_code`, `apply_patch(unified_diff)`, `run_tests(suite_id)`, `git_diff`. **No `run_shell(string)`.** `run_tests` maps `suite_id` to a fixed argv from the repository allowlist.
- `apply_patch` rejects paths outside the workspace, binary files, patches over a size cap, and any path in a denylist (`.git/`, `.env`).
- **Agent loop**: role prompt + allowed tools + output schema; model returns structured tool calls; runtime validates args, checks agent permission and task `access`, dispatches, feeds back truncated results; bounded steps (`max_steps`) and bounded model calls.
- Agent output is validated against its output schema; result becomes the attempt's `output`. **Agent claims of success are informational** (evidence comes from plan 15).
- `AgentExecutor` implements the scheduler's `TaskExecutor`; selects agent by task `agent_id/version`.
- Sandbox lifecycle: one sandbox per run, created lazily, workspace uploaded from the fixture, destroyed in `finally`.
- Prompts versioned in `app/agents/prompts/`.
- **Protected paths (audit H1).** `apply_patch` rejects any patch touching a `protectedPaths` entry from the repository config (plan 03): test directories, `conftest.py`, pytest/tox config, CI config. The attempt is recorded as `POLICY_VIOLATION` and is never retried. Agents therefore cannot make tests pass by editing or deleting them.
- **Tool-calling mode** follows Spike S1: native tool calling if the Meta API supports it, otherwise a JSON action protocol parsed and validated by the same Pydantic models.
- Agent prompt files are referenced by `promptVersion` from the agent definition (plan 02); an executor refuses an agent whose prompt file version does not match.
- The workspace is loaded through the plan 03 fixture loader.

## Deliverables
`app/agents/tools/*`, `runtime.py`, `executor.py`, prompts, tests (fake sandbox + `FakeModelProvider`).

## Tests and acceptance
- Unknown tool or invalid args -> rejected, recorded, loop continues or fails per policy.
- Agent without `sandboxWrite` cannot call `apply_patch` (permission test).
- Path traversal and denylisted paths refused.
- Step/model-call budgets stop a looping agent.
- Scripted model drives INVESTIGATE -> FIX -> TEST -> REVIEW on the fake sandbox through the scheduler.

- Patch touching a protected test file, a deleted test file, or a renamed one into a protected path is rejected and recorded as `POLICY_VIOLATION`.
- A patch to a non-protected file succeeds; patch path normalisation cannot bypass the protected list (`../`, symlink, case variants).

## Done when
A full bug-fix workflow executes against the fake sandbox with a scripted model, using real tool code.
