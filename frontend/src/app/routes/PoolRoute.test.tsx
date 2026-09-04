import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";

import { PoolRoute } from "./PoolRoute";

function jsonResponse(data: object, ok = true, status = ok ? 200 : 500) {
  const body = JSON.stringify(data);
  return Promise.resolve({
    ok,
    status,
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

function task(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    text: "Book dentist",
    status: "active",
    created_at: "2026-08-25T09:00:00+00:00",
    updated_at: "2026-08-25T09:00:00+00:00",
    completed_at: null,
    archived_at: null,
    due_date: null,
    position: 0,
    tags: [],
    recurrence: "none",
    priority: "none",
    lead_days: 0,
    notes: "",
    area_id: null,
    project_id: null,
    url: "/api/v1/tasks/1",
    ...overrides,
  };
}

function poolData(overrides: Record<string, unknown> = {}) {
  return {
    today: "2026-09-03",
    open_count: 2,
    fixed: [
      {
        kind: "bill",
        due_date: "2026-09-05",
        days_until: 2,
        task: null,
        bill: {
          id: 7,
          payee: "Rent",
          due_date: "2026-09-05",
          amount: "950.00",
          currency: "USD",
          direction: "out",
          repeats: true,
        },
      },
    ],
    floating: [{ task: task(), age_in_days: 9 }],
    ...overrides,
  };
}

function renderPool() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PoolRoute />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PoolRoute", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows every open line, filed or not, in one list", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(poolData()),
    );

    renderPool();

    expect(await screen.findByText("Book dentist")).toBeInTheDocument();
    expect(screen.getByText("Rent")).toBeInTheDocument();
  });

  it("says how old a floating line is, as a fact", async () => {
    // superlists-2.0-plan.md rule 1: age is shown as a fact, never as debt --
    // so no warning colour and no word about lateness, which is also rule 12.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(poolData()),
    );

    renderPool();

    expect(await screen.findByText("Added 9 days ago")).toBeInTheDocument();
  });

  it("says a floating line was added today rather than saying nothing", async () => {
    // The Day page's AGE_WORTH_MENTIONING threshold does not apply here: the
    // pool sorts by age, so an unlabelled row would read as unordered.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(poolData({ floating: [{ task: task(), age_in_days: 0 }] })),
    );

    renderPool();

    expect(await screen.findByText("Added today")).toBeInTheDocument();
  });

  it("keeps the two halves apart and names them", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(poolData()),
    );

    renderPool();

    expect(
      await screen.findByRole("heading", { name: /fixed/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /floating/i })).toBeInTheDocument();
  });

  it("asks the server again when the search changes, and does not filter here", async () => {
    // The server owns what matching means and what order the answer comes
    // back in -- filtering the rows already on screen would be a second
    // definition of the pool living in the browser.
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => jsonResponse(poolData()));

    renderPool();
    await screen.findByText("Book dentist");
    await userEvent.type(screen.getByRole("searchbox"), "fenc");

    await waitFor(() => {
      // openapi-fetch hands fetch a Request, not a URL string.
      const urls = fetchSpy.mock.calls.map(([sent]) => (sent as Request).url);
      expect(urls.some((url) => url.includes("q=fenc"))).toBe(true);
    });
  });

  it("counts the whole pool, not the search", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(poolData({ open_count: 14 })),
    );

    renderPool();

    expect(await screen.findByText(/14 open/)).toBeInTheDocument();
  });

  it("says the pool is empty rather than showing nothing at all", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(poolData({ open_count: 0, fixed: [], floating: [] })),
    );

    renderPool();

    expect(await screen.findByText(/nothing open/i)).toBeInTheDocument();
  });

  it("opens a task from its row", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(poolData()),
    );

    renderPool();

    expect(await screen.findByRole("link", { name: "Book dentist" })).toHaveAttribute(
      "href",
      "/tasks/1",
    );
  });

  it("sends a bill to Money rather than pretending it is a task", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(poolData()),
    );

    renderPool();

    expect(await screen.findByRole("link", { name: "Rent" })).toHaveAttribute(
      "href",
      "/money/bills/7",
    );
  });
});
