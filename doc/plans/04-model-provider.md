# 04 — Model provider (Meta Model API)

**Phase C · Depends on:** slice 1, S1 · **Status:** not started

## Goal
One narrow interface through which the whole system calls an LLM, with usage accounting and strict output handling.

## Responsibility
Transport, auth, retries, structured-output parsing, token/cost accounting. **Non-goals:** prompts and decisions (plans 05, 19), memory.

## First step (blocking) — Spike S1 (run before any other plan work)
**Verify the real Meta Model API from the event documentation**: base URL, auth scheme, model IDs, request/response schema, structured-output/JSON mode support, rate limits, usage fields. Record findings in `doc/META_API_NOTES.md`. Do not guess endpoints or model IDs.

**Spike S1 checklist additions (audit H6).** Besides endpoint, auth, model ids, schema, JSON mode, rate limits and usage fields, the notes must answer: (a) does the API support **native tool/function calling** (plan 13 assumes structured tool calls; if not, plan 13 uses a JSON action protocol validated identically), (b) context-window and max-output limits per model, (c) whether temperature 0 and a seed give repeatable output (plan 23 relies on this), (d) pricing or usage reporting for cost estimates, (e) streaming support. **Gate:** `doc/META_API_NOTES.md` must exist and be reviewed before the Meta adapter is written and before plan 13 starts. The spike runs at the very start of the project, in parallel with plan 01, not when plan 04 is reached.

## Design
- `ModelProvider` protocol: `complete(request: ModelRequest) -> ModelResponse` and `complete_structured(request, schema: type[BaseModel]) -> ParsedResponse[T]`.
- `ModelRequest`: profile (`planner|fast`), messages, max_tokens, temperature (0 by default), timeout.
- `complete_structured` parses JSON, validates with Pydantic, allows **one** repair round with validation errors, then raises `ModelOutputInvalid`.
- Errors: `ModelTransientError` (retried with backoff, max 2), `ModelAuthError`, `ModelOutputInvalid`, `ModelBudgetExceeded`.
- Usage returned on every response; callers record it on the run (`model_calls`, `tokens_in/out`, `est_cost_usd` — cost only when the API reports usage/pricing).
- `FakeModelProvider` for tests: scripted responses, records prompts, deterministic.
- Per-run call cap is enforced by the caller through `Orchestrator.consume_model_call(run_id, max)` (a conditional UPDATE introduced in plan 09), not by the provider; the provider raises `ModelBudgetExceeded` when it returns False.
- Every response records model id, temperature, seed (if supported) and prompt version, so plan 23 can reproduce a run.
- `MODEL_PROVIDER=meta|fake` setting selects the provider (used by the demo fallback, plan 27).
- Secrets never logged; prompts logged only as hashes + length by default.

## Deliverables
`app/model/provider.py`, `meta.py`, `fake.py`, `usage.py`, settings for base URL/model ids, `META_API_NOTES.md`.

## Tests and acceptance
- Fake: structured parse success, one repair then success, repair exhausted -> `ModelOutputInvalid`.
- Meta adapter tested against recorded HTTP fixtures (httpx `MockTransport`): auth header, retry on 5xx/429, no retry on 4xx, usage parsed, API key absent from logs.
- Optional live smoke test behind `META_LIVE=1`.
- A refused `consume_model_call` surfaces as `ModelBudgetExceeded` without calling the API.
- Usage record contains model id, temperature and prompt version.

## Risks
Meta API may lack JSON mode: then enforce via prompt + parser and measure repair rate.

## Done when
Interface frozen, adapter verified against the real docs, fake used by all later tests.
