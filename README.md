# AI ARENA

Self-healing multi-agent workflow platform (initial use case: autonomous bug fixing).
Product blueprint: [doc/Master.md](doc/Master.md). Architecture: [doc/ARCHITECTURE.md](doc/ARCHITECTURE.md).

**Status: slice 1 (foundation and API contracts).** No planner, agent runtime, scheduler or real
sandbox yet. The API exposes health and read-only resource endpoints; the orchestrator has its
transactional state core only.

## Stack
- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic, pytest — `apps/api`
- Database: Neon PostgreSQL (JSONB, no pgvector)
- Frontend: React, TypeScript, Vite, Tailwind — `apps/web`
- Contracts: Pydantic schemas are authoritative; TypeScript types are generated from the OpenAPI
  document into `packages/contracts`
- Sandbox: `SandboxProvider` interface + deterministic fake (Modal adapter comes in slice 9). No Docker.

## Prerequisites
- Python 3.12+ and [uv](https://docs.astral.sh/uv/) (`pip install uv`)
- Node 22+ and pnpm 10 (`npm i -g pnpm`)

On Windows PowerShell, call `pnpm.cmd` if script execution is restricted.

## Setup
```bash
pnpm install                         # frontend + contracts
uv sync --directory apps/api         # backend
cp .env.example .env                 # then fill in values; never commit .env
```
`/api/v1/health` works with an empty `.env`. For protected endpoints set `API_AUTH_TOKEN`; for
anything touching data set `DATABASE_URL` (Neon pooled URL, pasted as-is) and
`DATABASE_URL_DIRECT` (used by migrations).

## Run
```bash
pnpm dev:api     # FastAPI on http://127.0.0.1:8000  (docs at /docs)
pnpm dev:web     # Vite on http://localhost:5173, proxies /api to the backend
pnpm migrate     # alembic upgrade head against DATABASE_URL_DIRECT
```
The dev server proxies `/api`, so the bearer token is never bundled into the browser build.

## Contracts (backend -> frontend types)
```bash
pnpm contracts:generate
```
Exports `packages/contracts/openapi.json` from the FastAPI app, then regenerates
`packages/contracts/src/schema.d.ts`. Commit both. A pytest fails if `openapi.json` is stale.

## Checks
```bash
pnpm lint:api        # ruff + mypy (strict)
pnpm test:api        # pytest
pnpm typecheck:web   # tsc
pnpm test:web        # vitest
pnpm build:web       # vite build
pnpm check           # all of the above
```
Backend unit tests run on in-memory SQLite and a test that applies the Alembic migration and
diffs it against the models. They do **not** exercise Postgres; run `pnpm migrate` against a Neon
branch to validate the real database.

## Safety rules (from the architecture)
- Model output is untrusted; validate with Pydantic, then semantic checks, then policy.
- Only `app/orchestrator` changes run/task status, budgets or events, and each change commits with
  its event in one transaction.
- Sandbox commands are allowlisted argv arrays, enforced in the provider base class; nothing from
  the API environment is forwarded into a sandbox.
- Secrets stay on the backend and are redacted from logs.
