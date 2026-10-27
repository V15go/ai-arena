import type { components, paths } from "./schema";

export type { components, paths };

type Schemas = components["schemas"];

export type RunDetail = Schemas["RunDetail"];
export type RunOut = Schemas["RunOut"];
export type WorkflowOut = Schemas["WorkflowOut"];
export type WorkflowDefinition = Schemas["WorkflowDefinition"];
export type ExecutionEvent = Schemas["ExecutionEventOut"];
export type ApprovalOut = Schemas["ApprovalOut"];
export type AgentOut = Schemas["AgentOut"];
export type MemoryRecord = Schemas["MemoryRecordOut"];
