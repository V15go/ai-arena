# AI ARENA — Final Project Blueprint

**Project:** AI ARENA  
**Category:** Self-healing multi-agent AI workflow platform  
**Hackathon:** Meta Global AI Developer Hackathon  
**Initial use case:** Autonomous software bug fixing  
**Core differentiator:** Persistent workflow memory, adaptive recovery, and evidence-based execution.

> **Decisions made after this blueprint (they supersede the details below; product intent is unchanged).**
> - **Stack:** Python 3.12 + FastAPI + Pydantic + SQLAlchemy/Alembic backend (not Node/Fastify/Zod/Drizzle); React + TypeScript + Vite + Tailwind frontend; Neon PostgreSQL; **Modal** is the sandbox (E2B dropped); no local Docker. See [ARCHITECTURE.md](ARCHITECTURE.md) §0.
> - **Protected action:** the MVP exports a local patch (`EXPORT_PATCH`) behind human approval; GitHub PR creation is deferred (affects §7 step 10).
> - **Agent registry:** database-backed, versioned, with a code-enforced permission ceiling (§6).
> - **Execution:** tasks may run in parallel with READ/WRITE workspace locks and snapshots.
> - **Work order:** [plans/README.md](plans/README.md) replaces §12 as the detailed implementation order.

## 1. Vision

AI ARENA allows users to describe a task in natural language. It selects suitable agents from a predefined registry, generates a workflow, executes it, detects failures, adapts its recovery strategy, and verifies the outcome.

Instead of generating a new plan for every request, AI ARENA saves reusable workflow definitions and verified lessons in persistent memory.

**Product principle: Plan once, reuse intelligently, recover when necessary, verify every result.**

## 2. Problem Statement

Existing AI agents can generate code, analyze errors, and execute tests, but complex workflows may fail because of incorrect changes, unavailable tools, dependency issues, or unsuccessful recovery attempts.

AI ARENA aims to improve reliability by:

- Reusing saved workflow definitions instead of repeatedly generating plans.
- Learning from verified execution outcomes.
- Diagnosing failures before deciding how to recover.
- Validating results with actual execution evidence.
- Keeping protected actions under human control.

## 3. Core Architecture

### Frontend
- React + TypeScript + Vite
- Tailwind CSS
- React Flow for visual workflow graphs
- Live execution timeline and task status
- Workflow memory and execution history views
- Human approval interface

### Backend
- Node.js + TypeScript
- Fastify for REST APIs
- Zod for request and workflow validation
- A workflow orchestrator and state machine
- Server-Sent Events (SSE) for live execution updates

### AI and persistence
- Meta Model API for planning, reasoning, failure diagnosis, and recovery decisions.
- Neon PostgreSQL as the primary persistent database.
- Drizzle ORM for database access and migrations.
- E2B or an eligible Modal service behind a provider-neutral sandbox interface.
- No Docker requirement on the local Windows machine.

### Main components

1. **Agent Registry:** Defines available agents, capabilities, tools, inputs, outputs, and permissions.
2. **Workflow Planner:** Converts natural-language requests into validated workflow graphs.
3. **Workflow Memory Engine:** Stores reusable plans and verified lessons.
4. **Workflow Runtime:** Executes tasks, manages dependencies, and persists state.
5. **Recovery Supervisor:** Classifies failures and chooses whether to retry, replan, or escalate.
6. **Sandbox Runner:** Executes approved commands in an isolated remote environment.
7. **Validation Engine:** Collects test results, exit codes, and diff evidence.
8. **Approval Manager:** Blocks protected actions until the required approval is recorded.
9. **Evaluation Engine:** Measures success rate, recovery rate, retries, latency, and model cost.

## 4. Workflow Memory — The Core Design Decision

AI ARENA will maintain two distinct types of persistent memory.

### A. Workflow Definition Memory

Stores the reusable workflow itself:

- Workflow ID and version
- Agent assignments and configuration
- Task dependencies and execution order
- Tool requirements and approved commands
- Retry limits and timeouts
- Approval gates
- Expected task outputs

When the user selects a saved workflow for a new task, AI ARENA loads its saved graph instead of asking the model to regenerate it.

### B. Experience Memory

Stores verified knowledge from previous executions:

- Failure classifications
- Recovery strategies and their conditions
- Successful and unsuccessful attempts
- Test and build results
- Environment-specific limitations
- Supporting evidence and confidence

Only validated outcomes should become reusable lessons. An agent's unsupported claim of success must not be stored as a verified fact.

### Memory lookup strategy

1. Resolve the selected workflow and version.
2. Load its saved definition from Neon PostgreSQL.
3. Retrieve relevant memories for the workflow and current failure or task context.
4. Execute the existing graph with the new task inputs.
5. Invoke the model only when reasoning, diagnosis, or recovery is necessary.
6. Persist execution results and newly verified lessons.

A saved plan is reused only when its version, agent capabilities, tools, and policies remain compatible with the current environment.

## 5. Database Design

Use Neon PostgreSQL as the single persistent database.

| Table | Purpose |
|---|---|
| `workflows` | Workflow identity, name, owner, and status |
| `workflow_versions` | Versioned DAG, agent configurations, and policies |
| `workflow_memories` | Verified lessons and recovery strategies |
| `workflow_runs` | Individual execution status and outcomes |
| `tasks` | Tasks belonging to a workflow version |
| `task_attempts` | Individual attempts, results, and errors |
| `execution_events` | Persisted execution timeline |
| `approvals` | Human decisions for protected actions |

Use PostgreSQL JSONB for workflow graphs, agent configurations, and structured memory metadata. Add vector search with pgvector only if semantic retrieval becomes necessary.

## 6. Initial Agent Registry

Implement a small, predefined inventory.

| Agent | Responsibility |
|---|---|
| Investigator | Inspect the repository and identify the likely defect |
| Fix Agent | Propose and apply a code patch |
| Test Agent | Run approved tests and analyze failures |
| Review Agent | Inspect the diff and validation evidence |
| Recovery Supervisor | Diagnose execution failures and choose recovery actions |

The model may select and compose these capabilities, but it cannot invent arbitrary executable tools or grant itself permissions.

## 7. Example Execution

User prompt:

"Fix the API bug, run the unit tests, and prepare a pull request for approval."

1. AI ARENA checks for a compatible saved workflow.
2. If none exists, the planner generates a workflow and saves its version.
3. The Investigator identifies the defect.
4. The Fix Agent creates a patch.
5. The Test Agent runs the approved test command in the remote sandbox.
6. If tests fail, the Recovery Supervisor classifies the failure.
7. AI ARENA retries, adapts the plan, or escalates within configured limits.
8. The Validation Engine collects final test results and diff evidence.
9. The Review Agent evaluates the proposed change.
10. AI ARENA requests human approval before creating the pull request.

A failed run remains recorded. The system must not mark a workflow successful merely because an agent reports that it succeeded.

## 8. API Design

Initial REST API:

- `GET /api/v1/health`
- `POST /api/v1/workflows/plan`
- `POST /api/v1/workflows`
- `GET /api/v1/workflows`
- `GET /api/v1/workflows/:workflowId`
- `POST /api/v1/workflows/:workflowId/runs`
- `GET /api/v1/runs/:runId`
- `POST /api/v1/runs/:runId/cancel`
- `GET /api/v1/runs/:runId/events`
- `GET /api/v1/approvals?status=PENDING`
- `POST /api/v1/approvals/:approvalId/decision`
- `GET /api/v1/evaluations/summary`

The API must support workflow versioning, persistent execution state, task-attempt tracking, and failure recovery.

## 9. Security and Reliability

- Execute code only in an isolated remote sandbox.
- Use fixed, allowlisted commands and structured arguments.
- Never allow model output to bypass backend validation.
- Enforce maximum retries, task counts, execution time, and output size.
- Keep API credentials on the backend; never expose them to the browser or sandbox.
- Require approval before protected actions.
- Never let learned memory override authorization policies.
- Do not upload proprietary company code to third-party services without permission.
- Persist execution events so runs can be inspected and debugged.

## 10. Hackathon MVP Scope

Build one polished bug-fixing workflow before expanding into other use cases.

### Must-have
1. Prompt-to-workflow planning.
2. Predefined agent registry.
3. Visual workflow graph.
4. Neon persistence for workflow definitions and versions.
5. Workflow memory lookup and verified recovery lessons.
6. Remote sandbox integration.
7. Test execution and failure injection.
8. Recovery Supervisor with bounded retries.
9. Human approval gate.
10. Execution history and evaluation dashboard.

### Defer until after the core works
- Arbitrary user-created agents.
- Complex multi-project permissions.
- Advanced vector memory.
- Large-scale distributed execution.
- Multiple competing inference providers.
- General-purpose workflow marketplaces.

## 11. Evaluation Strategy

Demonstrate the same synthetic bug-fixing tasks against two approaches:

**Baseline:** Fixed workflow with a conventional retry policy.

**AI ARENA:** Saved workflow plus memory retrieval and adaptive recovery.

Measure:

- Task completion rate
- Recovery success rate
- Test pass rate
- Number of attempts
- Repeated failure rate
- Execution duration
- Model usage and estimated cost
- Protected actions blocked without approval

Report actual results; do not claim improvements until the evaluation supports them.

## 12. Implementation Order

1. Create the monorepo and shared Zod contracts.
2. Build the React dashboard and workflow graph.
3. Implement the Fastify backend and Neon database schema.
4. Implement the agent registry and workflow planner.
5. Persist and reload workflow definitions and versions.
6. Implement the workflow state machine and task-attempt history.
7. Integrate the Meta Model API.
8. Implement the remote sandbox provider interface and adapter.
9. Add the Recovery Supervisor and verified memory writer.
10. Add approvals, evaluation metrics, and failure-injection scenarios.
11. Run end-to-end tests and prepare the demo.

Build the smallest end-to-end flow first. Add each capability only after the preceding flow works.

## Final Product Definition

AI ARENA is a self-healing AI workflow platform that dynamically composes registered agents, persists reusable workflow definitions and verified experience in Neon PostgreSQL, adapts execution when failures occur, and validates results before human-approved actions.

**The hackathon demonstration must prove three things: the workflow can be reused without replanning, a deliberately injected failure can trigger an appropriate recovery decision, and the final result is backed by execution evidence.**
