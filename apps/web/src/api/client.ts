import type { paths } from "@ai-arena/contracts";
import createClient from "openapi-fetch";

/** Typed client; request/response types come from the generated OpenAPI contracts. */
export function createApiClient(options?: { baseUrl?: string; fetch?: typeof fetch }) {
  return createClient<paths>({ baseUrl: options?.baseUrl ?? "", fetch: options?.fetch });
}

export type ApiClient = ReturnType<typeof createApiClient>;
