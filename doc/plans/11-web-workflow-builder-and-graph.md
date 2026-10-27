# 11 — Web: workflow builder and graph

**Phase D · Depends on:** 06 · **Status:** not started

## Goal
A user can describe a task, review the planned workflow as a graph, and save it or pick a saved one.

## Responsibility
Plan form, DAG rendering, save/select workflow. **Non-goals:** live run status (12), approvals (22), editing graphs by hand (deferred).

## Design
- Routing (`react-router`) and app layout: Dashboard, Workflows, Runs, Approvals, Memory, Evaluations (placeholders for later pages, clearly empty rather than mock data).
- **Auth decision (audit M4):** a **Connect screen** asks for the API token. It is kept in `sessionStorage` (cleared when the tab closes), never in `localStorage`, a URL, or the bundle, and is attached to requests by the API client. A `401` returns the user to the Connect screen. The Vite dev server and `vite preview` only proxy `/api` (no token injection, so reaching the port grants nothing); the proxy binds to localhost. The same build can be served from any static host behind a same-origin `/api` proxy, or cross-origin with `WEB_ORIGIN` allowed by CORS.
- TanStack Query for data; typed `openapi-fetch` client already exists.
- **Plan form**: goal, repository id (select from known repositories), acceptance criteria list. Shows "Reused saved workflow (no model call)" vs "Newly planned" using `source`.
- **Graph**: React Flow with automatic layered layout (dagre), node = task (type icon, title, agent id, READ/WRITE badge), edges = `dependsOn`; read-only; accessible list view alternative.
- Validation issues from `422` rendered inline per task.
- Save button -> `POST /workflows`; workflow list with versions; "Run" button is disabled until plan 12 ships.
- Connect screen, token context and an authenticated API client wrapper (reused by plans 12, 22, 24, 25 and the streaming hook).

## Deliverables
`src/routes/*`, `src/components/graph/WorkflowGraph.tsx`, `layout.ts`, query hooks, tests.

## Tests and acceptance
- Component tests with mocked API: plan flow, reused-vs-new badge, 422 issues rendering.
- Graph layout unit test: diamond graph places dependents below parents; no overlapping nodes.
- Keyboard accessible; no horizontal overflow at 1024 px.
- `pnpm typecheck:web`, tests and build green.
- Connect flow: token accepted, `401` returns to Connect, token absent from `localStorage`, URL and built bundle.

## Done when
Planning, reviewing and saving a workflow works in the browser against the real API with the fake model.
