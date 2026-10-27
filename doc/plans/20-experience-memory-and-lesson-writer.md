# 20 — Experience memory and lesson writer

**Phase F · Depends on:** 15, 18, 19 · **Status:** not started

## Goal
Remember only **verified** recoveries and reuse them, so a repeated failure is fixed without asking the model.

## Responsibility
Lesson creation, retrieval by fingerprint, confidence. **Non-goals:** definition memory (06), vector search (deferred).

## Design (ARCHITECTURE §4.3 "Experience memory")
- **Lesson writer is the only path to `workflow_memories`.** It requires an `Evidence` object produced by the validation engine and a real `source_attempt_id`; the DB columns are NOT NULL as a backstop.
- **Verified** = a *later* attempt that applied the proposed strategy ended with `exitCode == 0` and target tests green. Agent self-reports never reach the writer.
- Failed strategies are stored too (`outcome=FAILED`) so they are not proposed again.
- `confidence = successes / (successes + failures)` with a minimum sample floor (below it, confidence is capped).
- `lookup(workflowId, fingerprint, failureClass)` ranks by exact fingerprint, same class, then recency x confidence; returns top-k.
- Supervisor integration (audit H4): a match above the confidence threshold lets the Supervisor **skip the model call**, but the stored strategy is converted into a `RecoveryProposal` with `source=MEMORY` and passed through `policy.decide()` (plan 18) like any other proposal; policy can still narrow or override it. Below the threshold it is passed to the proposer as context. A fingerprint match never bypasses policy.
- `MEMORY_WRITTEN` event on creation. `last_used_at` updated on hit.
- **Memory never changes policy, budgets, allowlists or approval requirements**; strategy fields use the same safe subset as plan 19.
- Environment constraints stored (`env_constraints`: sandbox image, agent versions) and checked on retrieval so stale lessons are ignored.
- **Evidence integrity (audit H1).** The writer rejects a lesson unless the evidence has `baselineVerified=true`, empty `protectedPathsTouched` and empty `testSetDelta` (plan 15), so a pass obtained by editing or skipping tests can never become a lesson.
- **Strategy linkage.** The succeeding attempt must be a *later* attempt of the same task and fingerprint whose recorded `recovery_decision.strategyId` equals the lesson's strategy; otherwise the writer refuses.
- **Memory scope (audit M2).** `workflow_memories.scope` (default `global`) isolates evaluation batches: lookup and writes filter by the run's `memoryScope` (plan 07 config). Migration `0003` adds `scope` and indexes `(scope, workflow_id, fingerprint)`.
- Counter updates (`success_count`, `failure_count`, `confidence`) are single atomic UPDATEs; concurrent-update tests are `pg_required` (plan 01).

## Contracts
`GET /memories` (exists; add `fingerprint`, `failureClass` filters).

## Tests and acceptance
- Attempt without evidence or with a self-reported success cannot create a lesson (writer rejects; DB constraint also tested).
- Run 1 recovers via proposal -> lesson stored; run 2 of the same failure applies it with **0 proposer calls**.
- A lesson that later fails lowers confidence and can drop below the apply threshold.
- Incompatible `env_constraints` -> not applied.
- Lesson text cannot widen policy (adversarial strategy payload test).

- A memory hit on a `POLICY_VIOLATION` fingerprint is escalated by policy; a hit never skips `decide()` (asserted by spying on policy).
- Evidence with `baselineVerified=false` or non-empty `protectedPathsTouched` cannot create a lesson (writer and an adversarial test).
- Lesson whose strategy id does not match the succeeding attempt is refused.
- Lessons written in scope `eval:<batch>` are invisible to scope `global` and to other batches.
- 20 concurrent outcome updates give correct success and failure counts.

## Done when
**Milestone M3:** inject failure -> recover -> store lesson -> repeat run uses memory.
