# 25 — Web: memory view

**Phase H · Depends on:** 06, 20 · **Status:** not started

## Goal
Let a user inspect what the system has saved and learned.

## Responsibility
Read-only views of saved workflows/versions and verified lessons. **Non-goals:** editing or deleting memory (out of scope for MVP).

## Design
- Tab 1 **Workflows**: list, versions, compatibility status badge with reasons, reuse count, "run this version".
- Tab 2 **Lessons**: table with failure class, fingerprint (short), strategy summary, outcome, confidence, successes/failures, last used, and a link to the **evidence** (source attempt, exit code, diff hash).
- Filters by workflow, failure class, outcome.
- Empty state explains that lessons appear only after verified recoveries.
- Text rendered escaped; strategy JSON in a collapsible read-only viewer.

## Tests and acceptance
Component tests for filters, empty state, incompatible-version reasons, evidence link.

## Done when
After the M3 demo the lesson appears with its evidence.
