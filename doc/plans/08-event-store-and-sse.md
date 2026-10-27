# 08 — Event store and SSE

**Phase D · Depends on:** 07 · **Status:** not started

## Goal
Clients see run progress live and can resume after a disconnect without missing or duplicating events.

## Responsibility
Serve the persisted event log as Server-Sent Events, with an in-process hub. **Non-goals:** writing events (Orchestrator already does, transactionally).

## Design (ARCHITECTURE §4.10)
- **Separate path (audit L3):** `GET /runs/{id}/stream` serves SSE; the JSON list endpoint `GET /runs/{id}/events` is unchanged. This keeps the OpenAPI document and generated client accurate (OpenAPI cannot describe both on one path); the web app uses a hand-written streaming hook for the stream path.
- Resume: honour `Last-Event-ID` header or `?after=<seq>`; replay from `execution_events` where `seq > after`, then tail.
- `EventHub`: per-run in-memory pub/sub; the Orchestrator publishes **after commit**. A 1-second DB poll fills gaps (missed publish, multi-process dev) and de-duplicates by `seq`.
- SSE frame: `id: <seq>`, `event: <type>`, `data: <ExecutionEventOut JSON>`; heartbeat comment every 15 s; stream closes after a terminal run event once drained.
- Payload redaction: pass `data` through `redact()`; never include secrets or raw sandbox env.
- Backpressure: bounded queue per client; slow client is disconnected (it can resume by seq).
- Auth: same bearer token. Since browsers' `EventSource` cannot set headers, the web app uses `fetch` streaming (documented in plan 12) rather than putting the token in a URL.

## Deliverables
`app/services/events/hub.py`, `sse.py`, route, tests, API notes.

## Tests and acceptance
- Subscriber receives events in `seq` order, none missing, none twice.
- Reconnect with `Last-Event-ID: 5` gets 6.. only.
- Events written by another connection (not via hub) arrive through the poll.
- Heartbeat appears on idle; stream ends after `RUN_SUCCEEDED/FAILED/CANCELLED`.
- Token absent -> 401; token never appears in any frame or log line.
- Ordering and no-gap tests are `pg_required` (plan 01): the advisory lock that guarantees commit order exists only on Postgres.

## Risks
Neon pooler lacks LISTEN/NOTIFY: that is why the poll fallback exists.

## Done when
A scripted run's events stream to a test client and survive a forced disconnect.
