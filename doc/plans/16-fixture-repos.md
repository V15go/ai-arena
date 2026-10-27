# 16 — Fixture repositories

**Phase E · Depends on:** 03, 14 · **Status:** not started

## Goal
Committed synthetic buggy repos with known fixes, so demos and evaluation are reproducible and no proprietary code leaves the machine.

## Responsibility
Fixture content, metadata, loader. **Non-goals:** injecting failures at runtime (17).

## Design
- `fixtures/<id>/` each a tiny Python project with a deterministic failing test and a known minimal fix (kept outside the repo workspace, e.g. `solution.patch`, for evaluation only; never uploaded to the sandbox).
- Initial set (5): off-by-one pagination, wrong status code mapping, null/None handling, date boundary, dependency-order bug. Difficulty labels easy/medium.
- `fixtures/repositories.yaml`: per repository id — path, allowed commands (argv arrays), test suite ids -> argv, resource limits, expected failing test names. This is the allowlist source used by plans 03, 13 and 14.
- `FixtureLoader.load(repository_id) -> Mapping[str, bytes]` for `upload_workspace`; refuses paths outside `fixtures/`.
- A script `verify_fixtures` runs each fixture's tests before and after applying `solution.patch` and asserts fail -> pass (in the fake or local Python, not the Modal sandbox).
- Plan 03 owns the `repositories.yaml` **schema**; this plan supplies the content for each fixture: commands, suites, `protectedPaths`, `baseline`.
- `fixture_hash(repository_id)` = SHA-256 of the fixture tree (excluding `solution.patch`), recorded in the run config (plan 07).

## Tests and acceptance
- Each fixture fails before and passes after its reference patch.
- Loader excludes `solution.patch` and `.git`.
- YAML schema validated by Pydantic; unknown commands rejected.
- `verify_fixtures` also checks each fixture's baseline numbers and that `protectedPaths` covers every test file.
- A patch that edits a protected path is flagged by the config check.

## Done when
Five fixtures verified, and the Modal image (plan 14) builds with their dependencies.
