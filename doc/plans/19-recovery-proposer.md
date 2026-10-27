# 19 — Recovery proposer

**Phase F · Depends on:** 04, 17, 18 · **Status:** not started

## Goal
When a failure needs reasoning, ask the model for a recovery proposal, then let policy accept, narrow or override it.

## Responsibility
Prompt, structured proposal, wiring into the hook. **Non-goals:** classification/rules (18), memory writes (20).

## Design
- Called only for `TEST_FAILURE | BUILD_ERROR | DEPENDENCY_MISSING | UNKNOWN` and only in ARENA mode.
- Input to the model: failure class, trimmed evidence, previous attempts and their outcomes, task acceptance criteria, **retrieved experience memories** (from plan 20; empty list until then).
- Output `RecoveryProposal {decision: RETRY|REPLAN|ESCALATE, rationale, changes?: {taskPatch?, extraContext?, strategyId?}}` via `complete_structured`.
- `taskPatch` is restricted to a safe subset (task description/acceptance text, extra context for the agent); it cannot change type, agent, access, commands, policy, or approval gates. Anything else is dropped and logged.
- Policy (18) has the final say; overrides are recorded.
- Model-call budget per run enforced; on `ModelOutputInvalid` or budget exhaustion fall back to policy default (`ESCALATE` for non-transient).
- Prompt versioned in `app/services/prompts/recovery_v1.md`.
- The proposer records model id, temperature and prompt version (`recovery_v1`) on the attempt so evaluation runs are reproducible (plan 23).

## Tests and acceptance
- Scripted proposals: retry with extra context -> task re-queued with that context; replan with no new evidence -> overridden to escalate.
- Proposal containing forbidden patch fields -> fields dropped, event notes it.
- Prompt injection inside test output (`"ignore policy and run ..."`) cannot change decisions beyond policy bounds (test with adversarial evidence).
- BASELINE mode makes zero proposer calls (asserted).

## Done when
A `WRONG_FIRST_FIX` scenario recovers via a proposal and the decision source is `MODEL`.
