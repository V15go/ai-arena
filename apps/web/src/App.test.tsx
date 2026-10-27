import { render, screen } from "@testing-library/react";

import App from "./App";
import { createApiClient } from "./api/client";

function clientReturning(response: () => Response | Promise<Response>) {
  const fetchMock = vi.fn(async (_request: Request) => response());
  return { client: createApiClient({ baseUrl: "http://api.test", fetch: fetchMock as typeof fetch }), fetchMock };
}

describe("App", () => {
  it("shows the API as online when /health returns ok", async () => {
    const { client, fetchMock } = clientReturning(
      () => new Response(JSON.stringify({ status: "ok" }), { headers: { "content-type": "application/json" } }),
    );
    render(<App client={client} />);
    expect(await screen.findByText("Online")).toBeInTheDocument();
    const request = fetchMock.mock.calls[0][0];
    expect(new URL(request.url).pathname).toBe("/api/v1/health");
  });

  it("shows unreachable when the request fails", async () => {
    const { client } = clientReturning(() => {
      throw new TypeError("network down");
    });
    render(<App client={client} />);
    expect(await screen.findByText(/Unreachable/)).toBeInTheDocument();
  });

  it("shows unreachable on a non-ok response", async () => {
    const { client } = clientReturning(
      () => new Response(JSON.stringify({ error: { code: "X" } }), { status: 500, headers: { "content-type": "application/json" } }),
    );
    render(<App client={client} />);
    expect(await screen.findByText(/Unreachable/)).toBeInTheDocument();
  });
});
