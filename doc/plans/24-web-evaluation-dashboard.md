# 24 — Web: evaluation dashboard

**Phase H · Depends on:** 23 · **Status:** not started

## Goal
Show BASELINE vs ARENA results clearly and honestly.

## Responsibility
Display evaluation summaries and drill-downs. **Non-goals:** computing metrics (23).

## Design
- Summary cards per metric with BASELINE, ARENA-cold, ARENA-warm side by side and the sample size (n) shown next to every number.
- Per-case table with links to the underlying runs (opens the run inspector).
- Charts: small bar charts with explicit axes and uncertainty (min/max); `null` metrics shown as "not available", never 0.
- "Run evaluation" button (requires the same API token as every other action; no separate admin role) with progress from run events.
- A visible note when sample size is small; no wording such as "improves" unless the data shows it (copy is generated from the numbers).

## Tests and acceptance
- Component tests with fixtures: null handling, small-n note, a case where ARENA is worse renders neutrally.
- Responsive and keyboard accessible; colour not the only encoding.

## Done when
Dashboard renders the real stored summary from plan 23.
