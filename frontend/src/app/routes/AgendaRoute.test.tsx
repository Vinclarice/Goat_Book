import type { ReactElement } from "react";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AgendaRoute } from "./AgendaRoute";

function jsonResponse(data: object, ok = true) {
  const body = JSON.stringify(data);
  return Promise.resolve({
    ok,
    status: ok ? 200 : 500,
    // openapi-fetch falls back to .text() when Content-Length is absent,
    // so both need to agree with the real body -- see its src/index.js.
    headers: new Headers({
      "content-type": "application/json",
      "content-length": String(body.length),
    }),
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(body),
    clone() {
      return this;
    },
  } as unknown as Response);
}

function renderWithClient(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("AgendaRoute", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the agenda payload once it loads", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({ username: "vince", items: [] }),
    );

    renderWithClient(<AgendaRoute />);

    expect(await screen.findByText(/"username": "vince"/)).toBeInTheDocument();
  });

  it("shows an error state when the request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({ detail: "nope" }, false),
    );

    renderWithClient(<AgendaRoute />);

    expect(await screen.findByText("Something went wrong.")).toBeInTheDocument();
  });
});
