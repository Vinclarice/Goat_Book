import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { BalancesRoute } from "./BalancesRoute";

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
    // openapi-fetch reads `text()` on some paths and `json()` on others, and a
    // double missing one fails as "response.text is not a function" *rendered
    // as the error message* -- which looks exactly like the route mishandling
    // a refusal. Both are defined here so a gap in the double cannot be
    // mistaken for a gap in the code.
    text: () => Promise.resolve(body),
    clone() {
      return this;
    },
  } as unknown as Response);
}

function accountsData(overrides: Record<string, unknown> = {}) {
  return {
    month_start: "2026-08-01",
    accounts: [
      {
        id: 1,
        name: "Amex",
        kind: "card",
        currency: "USD",
        owes: true,
        balance: null,
        previous: "4500.00",
      },
      {
        id: 2,
        name: "Stocks ISA",
        kind: "investment",
        currency: "USD",
        owes: false,
        balance: null,
        previous: null,
      },
    ],
    owed_totals: {},
    held_totals: {},
    ...overrides,
  };
}

function renderAt(path = "/money/balances/2026-08-01") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/money/balances/:month" element={<BalancesRoute />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("BalancesRoute", () => {
  afterEach(() => vi.restoreAllMocks());

  it("saves every balance in one request", async () => {
    /* The ritual is a batch, so the screen is a batch: six numbers, one
       button. Eight separate saves would be eight chances to be half-done. */
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const request = input as Request;
        if (request.method === "POST") return jsonResponse(accountsData());
        return jsonResponse(accountsData());
      });

    renderAt();

    await userEvent.type(await screen.findByLabelText("Amex"), "4200.00");
    await userEvent.type(screen.getByLabelText("Stocks ISA"), "15300.00");
    await userEvent.click(screen.getByRole("button", { name: "Save balances" }));

    const posted = fetchSpy.mock.calls
      .map(([request]) => request as Request)
      .filter((request) => request.method === "POST");
    await waitFor(() => expect(posted).toHaveLength(1));
  });

  it("shows last month beside the box without filling it in", async () => {
    /* Pre-filling would make an untouched box look like a considered answer,
       and a balance nobody checked is what this screen exists to prevent. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(accountsData()),
    );

    renderAt();

    expect(await screen.findByText(/last month 4500.00 USD/)).toBeInTheDocument();
    expect(screen.getByLabelText("Amex")).toHaveValue("");
  });

  it("keeps what was already recorded for this month", async () => {
    /* Reopening the screen shows your own answer rather than blanks -- which
       is a different thing from inventing one from last month. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        accountsData({
          accounts: [
            {
              id: 1,
              name: "Amex",
              kind: "card",
              currency: "USD",
              owes: true,
              balance: "4200.00",
              previous: "4500.00",
            },
          ],
        }),
      ),
    );

    renderAt();

    expect(await screen.findByLabelText("Amex")).toHaveValue("4200.00");
  });

  it("shows the server's own words when a figure is refused", async () => {
    /* "That is not a number" over six boxes is not a message. The server names
       the account, and the page has to let it through. */
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") {
        return jsonResponse(
          { detail: "Stocks ISA: that is not a number." },
          false,
          409,
        );
      }
      return jsonResponse(accountsData());
    });

    renderAt();

    await userEvent.type(await screen.findByLabelText("Stocks ISA"), "twelve");
    await userEvent.click(screen.getByRole("button", { name: "Save balances" }));

    expect(await screen.findByText(/Stocks ISA: that is not a number/)).toBeInTheDocument();
  });

  it("totals owed and held apart, and never subtracts them", async () => {
    /* A net worth is a different claim from either figure, and not one six
       typed numbers entitle this page to make. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        accountsData({
          owed_totals: { USD: "4200.00" },
          held_totals: { USD: "15300.00" },
        }),
      ),
    );

    renderAt();

    expect(await screen.findByText("4200.00 USD")).toBeInTheDocument();
    expect(screen.getByText("15300.00 USD")).toBeInTheDocument();
    expect(screen.queryByText(/11100/)).not.toBeInTheDocument();
  });

  it("says so when there are no accounts rather than showing an empty form", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(accountsData({ accounts: [] })),
    );

    renderAt();

    expect(await screen.findByText(/No accounts yet/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Save balances" }),
    ).not.toBeInTheDocument();
  });
});
