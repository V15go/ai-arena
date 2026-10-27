# 12 — Web: run inspector

**Phase D · Depends on:** 08, 09, 10, 11 · **Status:** not started

## Goal
Watch a run live: graph colours, timeline, attempts, and evidence, with reliable reconnect.

## Responsibility
Start a run, stream events, render run/task state. **Non-goals:** approval decisions (22), evaluation (24).

## Design
- "Run" button -> `POST /workflows/{id}/runs` with a client-generated idempotency key (safe on double click).
- `useRunEvents(runId)`: streams SSE from `GET /runs/{id}/stream` with `fetch` + `ReadableStream`, using the token from the auth context (plan 11) (EventSource cannot send the Authorization header and the token must not go in the URL); tracks last `seq`; reconnects with `Last-Event-ID`; de-duplicates by `seq`.
- State derived from events plus an initial `GET /runs/{id}` snapshot; the server snapshot wins on conflict.
- Views: graph with status colours (PENDING/READY/RUNNING/WAITING_APPROVAL/SUCCEEDED/FAILED/CANCELLED), timeline list, task drawer (attempts, failure class, recovery decision and its source POLICY/MEMORY/MODEL, evidence: exit code, test summary, diff hash, sandbox exec id), run header (status, counters: attempts, model calls, planner calls, tokens/cost when available).
- Cancel button -> `POST /runs/{id}/cancel`.
- Badges: "plan reused — 0 planner calls", "memory hit".
- Never render raw secrets; logs shown as plain text, not HTML.
- **Execution history page (audit M3, Master §10.10):** a Runs list over `GET /runs` with filters (status, workflow, mode), keyset "load more", and columns for status, workflow and version, mode, started, duration, attempts, a "plan reused" badge and the outcome reason. Each row links to the inspector.
- **Outcome report (audit L5):** failed or escalated runs show `outcome.report` (why it stopped, last failure class, budgets used) written by plan 18.

## Tests and acceptance
- Hook test with a fake stream: ordering, duplicate suppression, reconnect resumes at last seq.
- Component test: events drive node colours; terminal event stops the stream.
- Failed run shows failure class and recovery history.
- History page tests: filters, pagination, empty state, links to the inspector.

## Done when
A scripted run (M1) can be watched end to end in the browser.
