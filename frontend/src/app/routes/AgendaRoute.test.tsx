import type { ReactElement } from "react";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";

import { AgendaRoute } from "./AgendaRoute";
import { agendaData, agendaArea, task } from "../../test/fixtures";

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
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AgendaRoute", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    document.cookie = "csrftoken=test-token";
  });

  it("renders the real agenda workspace once the query resolves", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        agendaData({
          items: [task({ text: "Ship the migration" })],
          areas: [agendaArea()],
        }),
      ),
    );

    renderWithClient(<AgendaRoute />);

    expect(await screen.findByText("Ship the migration")).toBeInTheDocument();
  });

  it("shows an error state when the request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({ detail: "nope" }, false),
    );

    renderWithClient(<AgendaRoute />);

    // B2.1: a 500 is the retryable kind of failure, so the person is
    // offered a retry rather than told their work is gone.
    expect(await screen.findByText(/Couldn't reach Clarice/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });
});
