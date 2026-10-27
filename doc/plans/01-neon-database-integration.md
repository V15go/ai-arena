# 01 — Neon database integration

**Phase B · Depends on:** slice 1 · **Status:** not started

## Goal
Show that the schema, migration and async session layer work on real Neon PostgreSQL, not just SQLite.

## Responsibility
Verify and harden the persistence layer against Postgres. **Non-goals:** new tables, business logic, seeding agents (plan 02).

## Design
- Use a dedicated Neon **branch** per developer and one for CI; never run tests against the main branch.
- App uses the **pooled** URL (PgBouncer transaction mode, `statement_cache_size=0` already set); Alembic uses the **direct** URL.
- Integration tests run only when `TEST_DATABASE_URL` is set; they create an isolated schema per test session and drop it afterwards.
- Check Postgres-only behaviour SQLite cannot show: JSONB round-trip, `TEXT[]` for `tasks.depends_on`, `timestamptz`, `pg_advisory_xact_lock` in `append_event`, `SELECT ... FOR UPDATE`, composite FK `(agent_id, agent_version)`.
- **Two Postgres test tiers (audit H3).** `@pytest.mark.pg` tests are optional and skip without a database. `@pytest.mark.pg_required` marks every test whose result depends on Postgres semantics: advisory locks, `FOR UPDATE`, `SKIP LOCKED`, conditional-UPDATE budgets, lease takeover, concurrent lesson updates, approval races. Plans 08, 09, 10, 20 and 21 must use it. SQLite results are **never** accepted as evidence for lock or race behaviour.
- `REQUIRE_PG=1` turns a missing database or a skipped `pg_required` test into a **failure**. Pre-merge for plans 08-10, 20 and 21 runs with `REQUIRE_PG=1` against a Neon branch or a local Postgres.
- **Migration discipline (audit M6).** One Alembic migration per plan that needs schema, numbered in the order listed in the README migration table; a test asserts a single Alembic head and no model/migration drift. Parallel plans that both add a migration renumber on rebase before merge.

## Deliverables
- `tests/integration/` with a `pg` fixture (marker `@pytest.mark.pg`), skipped without a URL.
- `pnpm test:api:pg` script and README section "Running against Neon".
- Fixes for anything the Postgres run reveals (e.g. `TextArray` default handling, Numeric rounding).
- Verified `alembic upgrade head` / `downgrade base` on a clean Neon branch.

## Tests and acceptance
- Concurrency test: 20 concurrent `append_event` calls on one run produce `seq` 1..20 with no gaps or duplicates.
- Concurrency test: 50 concurrent `consume_attempt(max=10)` succeed exactly 10 times.
- Migration drift check also passes with a Postgres connection (`compare_metadata` is empty).
- The whole existing suite still passes on SQLite.
- A `pg_required` test deliberately skipped makes `REQUIRE_PG=1` fail (test of the guard itself).
- `alembic heads` returns exactly one head.

## Risks and open questions
- Neon cold starts add latency to first connection: set generous `pool_timeout`, keep `pool_pre_ping`.
- Free-tier connection limits: cap pool size.

## Done when
Integration suite is green on a real Neon branch, and README explains how to run it.
