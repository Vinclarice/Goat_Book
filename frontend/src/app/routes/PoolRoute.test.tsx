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
        picked_for: [],
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
    floating: [
      {
        task: task(),
        age_in_days: 9,
        picked_for: [],
        unpicked_for_days: 9,
        asks_to_be_kept: false,
      },
    ],
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
      jsonResponse(
        poolData({
          floating: [
            {
              task: task(),
              age_in_days: 0,
              picked_for: [],
              unpicked_for_days: 0,
              asks_to_be_kept: false,
            },
          ],
        }),
      ),
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

describe("PoolRoute, picking a line for a day", () => {
  // superlists-2.0-plan.md increment 2: the pool is where tomorrow's list is
  // made, and where an existing line joins today below the line.

  afterEach(() => vi.restoreAllMocks());

  it("picks a floating line for today", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => jsonResponse(poolData()));

    renderPool();
    await userEvent.click(
      await screen.findByRole("button", { name: /Pick Book dentist for today/i }),
    );

    await waitFor(() => {
      const posts = fetchSpy.mock.calls
        .map(([sent]) => sent as Request)
        .filter((request) => request.method === "POST");
      expect(posts.some((r) => r.url.includes("/api/v1/day/2026-09-03/focus"))).toBe(
        true,
      );
    });
  });

  it("picks it for tomorrow, which is the day the list is written for", async () => {
    // Rule 2: the list is written *for* a day, never *on* it. The evening
    // before is the ordinary case, not the edge one.
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => jsonResponse(poolData()));

    renderPool();
    await userEvent.click(
      await screen.findByRole("button", {
        name: /Pick Book dentist for tomorrow/i,
      }),
    );

    await waitFor(() => {
      const posts = fetchSpy.mock.calls
        .map(([sent]) => sent as Request)
        .filter((request) => request.method === "POST");
      expect(posts.some((r) => r.url.includes("/api/v1/day/2026-09-04/focus"))).toBe(
        true,
      );
    });
  });

  it("says a line is already picked rather than offering it again", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        poolData({
          floating: [
            {
              task: task(),
              age_in_days: 9,
              picked_for: ["2026-09-03"],
              unpicked_for_days: 0,
              asks_to_be_kept: false,
            },
          ],
        }),
      ),
    );

    renderPool();

    expect(await screen.findByText(/Picked for today/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Pick Book dentist for today/i }),
    ).toBeNull();
    // Tomorrow is still on offer -- one pick is not the other.
    expect(
      screen.getByRole("button", { name: /Pick Book dentist for tomorrow/i }),
    ).toBeInTheDocument();
  });

  it("offers no pick on a bill, which cannot be chosen at all", async () => {
    // A bill is not an `Item`, so `DailyFocus` has nothing to point at.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(poolData({ floating: [] })),
    );

    renderPool();

    await screen.findByText("Rent");
    expect(screen.queryByRole("button", { name: /^Pick /i })).toBeNull();
  });
});

function stale(overrides: Record<string, unknown> = {}) {
  return {
    task: task({ text: "Sort the garage shelves" }),
    age_in_days: 24,
    picked_for: [],
    unpicked_for_days: 24,
    asks_to_be_kept: true,
    ...overrides,
  };
}

describe("PoolRoute, the pool pruning itself", () => {
  // superlists-2.0-plan.md rule 8: a floating line unpicked for a stated
  // number of days asks one question -- still want this? -- and let go
  // archives the task and retires its facet while the node stays.

  afterEach(() => vi.restoreAllMocks());

  it("asks about a line nobody has touched, and says for how long", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(poolData({ floating: [stale()] })),
    );

    renderPool();

    expect(await screen.findByText(/unpicked for 24 days/i)).toBeInTheDocument();
  });

  it("asks nothing about a line that is not stale", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(poolData()),
    );

    renderPool();

    await screen.findByText("Book dentist");
    expect(screen.queryByText(/still want it/i)).toBeNull();
  });

  it("does not decide which lines are stale for itself", async () => {
    // D8: the threshold stays in one language. A client comparing
    // `unpicked_for_days` against a number of its own would be the mirrored
    // constant arriving by the back door -- so a long-unpicked line the server
    // did not flag is not flagged here either.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        poolData({
          floating: [stale({ unpicked_for_days: 400, asks_to_be_kept: false })],
        }),
      ),
    );

    renderPool();

    await screen.findByText("Sort the garage shelves");
    expect(screen.queryByText(/still want it/i)).toBeNull();
  });

  it("keeps it", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") return jsonResponse(poolData());
      return jsonResponse(poolData({ floating: [stale()] }));
    });

    renderPool();
    await userEvent.click(await screen.findByRole("button", { name: "Keep" }));

    await waitFor(() => {
      const posts = fetchSpy.mock.calls
        .map(([sent]) => sent as Request)
        .filter((request) => request.method === "POST");
      expect(
        posts.some((r) => r.url.includes("/api/v1/pool/1/still-wanted")),
      ).toBe(true);
    });
  });

  it("lets it go, and says the thought is not lost with it", async () => {
    // Rule 8's whole argument: paper could not drop a task without losing the
    // idea, and a person will not press this if they think it deletes what
    // they wrote.
    // Stateful, because the page refetches after the write rather than
    // rendering the response: a mock that kept serving the stale row would be
    // testing a server that had not done anything.
    let gone = false;
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") {
        gone = true;
        return jsonResponse(poolData({ floating: [] }));
      }
      return jsonResponse(poolData({ floating: gone ? [] : [stale()] }));
    });

    renderPool();

    await screen.findByText(/still want it/i);
    expect(screen.getByText(/the note stays/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Let go" }));

    // The row, not any mention of the words: the prompt names the line too.
    await waitFor(() =>
      expect(
        screen.queryByRole("link", { name: "Sort the garage shelves" }),
      ).toBeNull(),
    );
  });
});

