# 26 — Security hardening

**Phase I · Depends on:** 14, 19, 21 · **Status:** not started

## Goal
Prove the security rules in Master §9 hold, and close the remaining gaps.

## Responsibility
Rate limiting, secret hygiene, adversarial tests, config checks. **Non-goals:** multi-user auth (out of scope).

## Design
- Rate limits on `POST /workflows/plan`, `POST /workflows/*/runs`, `POST /evaluations/run` (per token, configurable) so demo traffic cannot burn the model quota; `429` with the standard envelope and `Retry-After`.
- Request body size limits; JSON depth limit.
- Secret scan test: run a full scripted run with canary secrets in settings (`API_AUTH_TOKEN`, model key, Modal token, DB URL) and assert none appear in logs, SSE frames, event `data`, error bodies, prompts sent to the fake model, or sandbox env/exec argv.
- CORS locked to `WEB_ORIGIN`; no wildcard; credentials not allowed.
- Startup checks: production requires strong token, `ALLOW_FAULT_INJECTION=false`, `SANDBOX_PROVIDER=modal` (or explicit override).
- Dependency audit (`pip-audit`, `pnpm audit`) documented in README; fix or record accepted risks.
- Threat-model table in `doc/SECURITY.md` mapping each Master §9 rule to the code and test that enforces it.
- **Accepted risks recorded in `doc/SECURITY.md` (audit L1, M7):** (a) if Modal cannot block egress, code under test could reach the network; mitigated by synthetic fixtures and a secret-free sandbox, not eliminated; (b) one static token means any holder can approve any run; (c) unsupported hardening items from `MODAL_NOTES.md` (non-root, PID limit, read-only root).
- Settings hard caps (`min(policy, settings)`) are covered by a test that a policy above the cap is clamped.

## Adversarial tests
Prompt injection via goal, repository files and test output; path traversal in `apply_patch`; non-allowlisted command; learned memory trying to widen policy; client-supplied approver identity; replayed or stale approval; oversized output; SSE flooding.

## Done when
`SECURITY.md` has a passing test reference for every rule and the canary test is green.
