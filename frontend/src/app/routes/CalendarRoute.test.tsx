import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { CalendarRoute } from "./CalendarRoute";

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

function monthData(overrides: Record<string, unknown> = {}) {
  return {
    month_start: "2026-08-01",
    previous_month: "2026-07-01",
    next_month: "2026-09-01",
    today: "2026-08-14",
    days: [
      { date: "2026-08-01", due: 0, appointments: 0, written: false },
      { date: "2026-08-14", due: 2, appointments: 1, written: true },
    ],
    ...overrides,
  };
}

function renderAt(path = "/calendar/2026-08-14") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/calendar/:month" element={<CalendarRoute />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CalendarRoute", () => {
  afterEach(() => vi.restoreAllMocks());

  it("lands on a day, which is the whole point", async () => {
    // S13's second require: /app/day/:date had no UI entry point at all, so
    // reaching a day twelve weeks back meant clicking "the week before"
    // twelve times.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(monthData()),
    );

    renderAt();

    const square = await screen.findByRole("link", { name: /2026-08-14/ });
    expect(square).toHaveAttribute("href", "/day/2026-08-14");
  });

  it("says what a day holds without listing it", async () => {
    // Counts and a mark, not the rows: a month is for choosing a day to
    // open, and every task on every date would be the Day page thirty-one
    // times over.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(monthData()),
    );

    renderAt();

    expect(await screen.findByText("2 due")).toBeInTheDocument();
    expect(screen.queryByText(/Pay rent/)).not.toBeInTheDocument();
  });

  it("offers both neighbours, so neither needs a typed url", async () => {
    // The rule WeekOut follows: a surface reachable only by editing the
    // address bar is a gap this sequence has already shipped twice.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(monthData()),
    );

    renderAt();

    expect(
      await screen.findByRole("link", { name: /July 2026/ }),
    ).toHaveAttribute("href", "/calendar/2026-07-01");
    expect(screen.getByRole("link", { name: /September 2026/ })).toHaveAttribute(
      "href",
      "/calendar/2026-09-01",
    );
  });

  it("offers the way into the bills month", async () => {
    // An unreachable route is the un-switched-on seam under a nicer name,
    // and the calendar is the other month-shaped surface.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(monthData()),
    );

    renderAt();

    expect(
      await screen.findByRole("link", { name: "Bills this month" }),
    ).toHaveAttribute("href", "/bills/2026-08-01");
  });

  it("reports a failure rather than an empty month", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({}, false, 500),
    );

    renderAt();

    expect(
      await screen.findByRole("button", { name: /try again/i }),
    ).toBeInTheDocument();
  });
});
