import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { ReviewRoute } from "./ReviewRoute";

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

function weekData(overrides: Record<string, unknown> = {}) {
  return {
    week_start: "2026-07-27",
    week_end: "2026-08-02",
    today: "2026-08-02",
    is_current_week: true,
    previous_week: "2026-07-20",
    next_week: "2026-08-03",
    completed: [],
    planned: { total: 0, met: 0, met_tasks: [], unfinished: [], set_aside: [] },
    ...overrides,
  };
}

function plannedTask(overrides: Record<string, unknown> = {}) {
  return {
    task_id: 1,
    text: "Pay rent",
    day: "2026-07-27",
    due_date: null,
    parent: null,
    age_in_days: 0,
    completed_on: null,
    ...overrides,
  };
}

function completedTask(overrides: Record<string, unknown> = {}) {
  return {
    task_id: 1,
    text: "Pay rent",
    completed_on: "2026-07-29",
    list_id: 3,
    parent: null,
    ...overrides,
  };
}

function renderAt(path: string, stored = weekData()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/review" element={<ReviewRoute />} />
          <Route path="/review/:week" element={<ReviewRoute />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("ReviewRoute", () => {
  it("names the week it is showing", async () => {
    // The default is the week you are in rather than the one before, so the
    // page has to say which one that is -- a number with an unnamed window
    // behind it is the kind of figure this release exists to avoid.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(weekData()),
    );

    renderAt("/review");

    // Order left to the reader's locale, like every other date in the app
    // — the assertion is that both ends of the window are named, not which
    // way round a month and a day go.
    const heading = await screen.findByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent(/(27 July|July 27)/);
    expect(heading).toHaveTextContent(/(2 August|August 2)/);
  });

  it("lists what was finished, with the day it was finished on", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          completed: [
            completedTask(),
            completedTask({ task_id: 2, text: "Book the dentist", completed_on: "2026-07-31" }),
          ],
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("Pay rent")).toBeInTheDocument();
    expect(screen.getByText("Book the dentist")).toBeInTheDocument();
    expect(screen.getByText("Wednesday")).toBeInTheDocument();
    expect(screen.getByText("Friday")).toBeInTheDocument();
  });

  it("says so plainly when nothing was finished", async () => {
    // Not an empty list: a week with nothing in it is a fact, and a blank
    // area reads as a page that failed to load.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(weekData()),
    );

    renderAt("/review");

    expect(
      await screen.findByText(/Nothing was marked finished/),
    ).toBeInTheDocument();
  });

  it("reports the finish rate over what was planned, not over the backlog", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          planned: {
            total: 3,
            met: 2,
            met_tasks: [
              plannedTask({ completed_on: "2026-07-29" }),
              plannedTask({ task_id: 2, text: "Book the dentist", completed_on: "2026-07-31" }),
            ],
            unfinished: [plannedTask({ task_id: 3, text: "Call the bank" })],
            set_aside: [],
          },
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("2 of 3")).toBeInTheDocument();
  });

  it("keeps what was deliberately set aside out of the count and on the page", async () => {
    // released_at's whole purpose: a decommitment is not a failure to
    // finish, and a denominator that counted both would report a number
    // that looks authoritative and is not.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          planned: {
            total: 1,
            met: 1,
            met_tasks: [plannedTask({ completed_on: "2026-07-29" })],
            unfinished: [],
            set_aside: [
              plannedTask({ task_id: 9, text: "Reorganise the shed" }),
            ],
          },
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("1 of 1")).toBeInTheDocument();
    expect(screen.getByText("Reorganise the shed")).toBeInTheDocument();
    expect(screen.getByText(/Set aside/)).toBeInTheDocument();
  });

  it("says how long an unfinished commitment has been waiting", async () => {
    // The Daily Page's wording, from the Daily Page's rule: a fact with no
    // conclusion drawn from it. A red "12 days late!" fails the vision
    // document's test that history be useful without being punishing.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          planned: {
            total: 1,
            met: 0,
            met_tasks: [],
            unfinished: [plannedTask({ age_in_days: 12 })],
            set_aside: [],
          },
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("Added 12 days ago")).toBeInTheDocument();
  });

  it("does not report a rate for a week nobody planned", async () => {
    // A week with no plan is not a week that failed one, and "0 of 0" is
    // the shape of number that invites a conclusion from nothing.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(weekData()),
    );

    renderAt("/review");
    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByText("0 of 0")).toBeNull();
    expect(screen.getByText(/Nothing was pinned/)).toBeInTheDocument();
  });

  it("reaches the week before without editing the URL", async () => {
    // The missing surface this sequence has now shipped twice. A review is
    // written on a Monday about the week that just ended, so the week
    // before has to be one click from the default.
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => jsonResponse(weekData()));

    renderAt("/review");
    await screen.findByRole("heading", { level: 1 });
    await userEvent.click(screen.getByRole("link", { name: /week before/i }));

    expect(
      fetchSpy.mock.calls.some((call) =>
        String((call[0] as Request).url).includes("/api/v1/review/2026-07-20"),
      ),
    ).toBe(true);
  });

  it("offers no way forward from the week in progress", async () => {
    // There is nothing to review in a week that has not started, and a
    // control that leads somewhere empty invites the conclusion that the
    // page is broken.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(weekData({ is_current_week: true })),
    );

    renderAt("/review");
    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByRole("link", { name: /week after/i })).toBeNull();
  });

  it("offers the week after once you are looking at a past one", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(weekData({ is_current_week: false })),
    );

    renderAt("/review/2026-07-27");

    expect(
      await screen.findByRole("link", { name: /week after/i }),
    ).toBeInTheDocument();
  });
});
