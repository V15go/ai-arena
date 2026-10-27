# 22 — Web: approvals

**Phase G · Depends on:** 12, 21 · **Status:** not started

## Goal
A human can review what is about to happen and approve or reject it.

## Responsibility
Approval inbox, detail view, decision submission. **Non-goals:** the approval logic (21).

## Design
- Inbox: `GET /approvals?status=PENDING`, polled/refetched and also pushed by run events.
- Detail: action, diff (syntax-highlighted, read-only, rendered as text), diff hash, test evidence (exit code, summary, sandbox exec id), review agent verdict, run link.
- Decision form: Approve / Reject with optional comment; confirms what exactly is approved (shows the hash). Disabled while submitting; handles `409` (already decided / diff changed) with a clear message and refresh.
- Run inspector (12) shows "Waiting for approval" with a link.
- No identity field; the UI never sends who decided.
- Diff and logs are escaped text, never HTML.

## Tests and acceptance
- Component tests: pending list, approve success, reject with comment, 409 handling, hash displayed.
- Accessible: focus management on dialog, keyboard shortcuts do not auto-approve.

## Done when
The M1/M3 demo run can be approved and rejected from the browser.
