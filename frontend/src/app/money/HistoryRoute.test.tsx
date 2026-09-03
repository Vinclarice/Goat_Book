import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { HistoryRoute } from "./HistoryRoute";

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

const MONTHS = ["2026-06-01", "2026-07-01", "2026-08-01"];

function history(overrides: Record<string, unknown> = {}) {
  return {
    months: MONTHS,
    rows: [
      {
        account_id: 1,
        name: "Car loan",
        currency: "USD",
        owes: true,
        balances: ["8000.00", "7750.00", "7500.00"],
        projection: {
          months: [
            ["2026-09-01", "7250.00"],
            ["2026-10-01", "7000.00"],
          ],
          monthly_change: "-250.00",
          readings_used: 3,
          clears_on: null,
        },
      },
    ],
    ...overrides,
  };
}

function renderHistory() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/money/history"]}>
        <Routes>
          <Route path="/money/history" element={<HistoryRoute />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("HistoryRoute", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows each account's months in order", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse(history()));

    renderHistory();

    /* Scoped to the table: the account is named again in the projection
       summary below, correctly -- a row and a sentence about that row are two
       places a person expects to see it. */
    const table = await screen.findByRole("table");
    expect(within(table).getByText("Car loan")).toBeInTheDocument();
    expect(within(table).getByText("8000.00")).toBeInTheDocument();
    expect(within(table).getByText("7500.00")).toBeInTheDocument();
  });

  it("shows a gap as a dash rather than a zero", async () => {
    /* Nothing recorded and nothing owed are different facts, and only one of
       them is a number. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        history({
          rows: [
            {
              account_id: 1,
              name: "Amex",
              currency: "USD",
              owes: true,
              balances: [null, "500.00", "400.00"],
              projection: null,
            },
          ],
        }),
      ),
    );

    renderHistory();

    expect(await screen.findByText("—")).toBeInTheDocument();
    expect(screen.queryByText("0.00")).not.toBeInTheDocument();
  });

  it("says why there is no projection instead of hiding it", async () => {
    /* The refusal is the thing keeping the other projections worth believing,
       so it is stated rather than left as an absence. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        history({
          rows: [
            {
              account_id: 1,
              name: "Amex",
              currency: "USD",
              owes: true,
              balances: [null, "500.00", "400.00"],
              projection: null,
            },
          ],
        }),
      ),
    );

    renderHistory();

    expect(await screen.findByText(/not enough history yet/)).toBeInTheDocument();
  });

  it("shows what the projection was drawn from", async () => {
    /* A projection whose derivation is invisible is a claim rather than an
       estimate. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse(history()));

    renderHistory();

    expect(await screen.findByText(/from 3 readings/)).toBeInTheDocument();
    expect(screen.getByText(/falling about 250.00 USD a month/)).toBeInTheDocument();
  });

  it("names the month a debt clears when it does", async () => {
    /* The one output worth more than the six figures behind it. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        history({
          rows: [
            {
              account_id: 1,
              name: "Car loan",
              currency: "USD",
              owes: true,
              balances: ["900.00", "600.00", "300.00"],
              projection: {
                months: [["2026-09-01", "0.00"]],
                monthly_change: "-300.00",
                readings_used: 3,
                clears_on: "2026-09-01",
              },
            },
          ],
        }),
      ),
    );

    renderHistory();

    expect(await screen.findByText(/Clear by September 2026/)).toBeInTheDocument();
  });

  it("says out loud that the projections are arithmetic", async () => {
    /* A projection presented without this line is a forecast pretending to be
       a fact, which is the easiest untruth a money tool can tell. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse(history()));

    renderHistory();

    expect(
      await screen.findByText(/These are arithmetic, not predictions/),
    ).toBeInTheDocument();
  });

  it("reports a failure rather than an empty table", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({}, false, 500),
    );

    renderHistory();

    expect(
      await screen.findByRole("button", { name: /Try again/i }),
    ).toBeInTheDocument();
  });
});
