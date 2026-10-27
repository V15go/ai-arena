import { useEffect, useState } from "react";

import { createApiClient, type ApiClient } from "./api/client";

type ApiState = "checking" | "online" | "unreachable";

const defaultClient = createApiClient();

export default function App({ client = defaultClient }: { client?: ApiClient }) {
  const [state, setState] = useState<ApiState>("checking");

  useEffect(() => {
    let cancelled = false;
    client
      .GET("/api/v1/health")
      .then(({ data }) => {
        if (!cancelled) setState(data?.status === "ok" ? "online" : "unreachable");
      })
      .catch(() => {
        if (!cancelled) setState("unreachable");
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-3xl font-semibold">AI ARENA</h1>
      <p className="mt-2 text-slate-600">
        Plan once, reuse intelligently, recover when necessary, verify every result.
      </p>
      <section className="mt-8 rounded-lg border border-slate-200 p-4" aria-label="API status">
        <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500">API</h2>
        <p role="status" className="mt-1 text-lg">
          {state === "checking" && "Checking…"}
          {state === "online" && "Online"}
          {state === "unreachable" && "Unreachable — is the backend running on port 8000?"}
        </p>
      </section>
    </main>
  );
}
