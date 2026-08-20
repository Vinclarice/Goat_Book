import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { BillsRoute } from "./BillsRoute";

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

function billsData(overrides: Record<string, unknown> = {}) {
  return {
    month_start: "2026-08-01",
    previous_month: "2026-07-01",
    next_month: "2026-09-01",
    bills: [
      {
        task_id: 1,
        text: "Rent",
        due_date: "2026-08-01",
        amount: "1200.00",
        currency: "USD",
        payee: "Landlord",
        url: "/api/items/1/",
      },
    ],
    totals: { USD: "1200.00" },
    unpriced: 0,
    ...overrides,
  };
}

function renderAt(path = "/bills/2026-08-14") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/bills/:month" element={<BillsRoute />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("BillsRoute", () => {
  afterEach(() => vi.restoreAllMocks());

  it("says what is due and what it comes to", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(billsData()),
    );

    renderAt();

    // The same figure appears twice with one bill -- once on its row and
    // once as the month's total -- so each is asserted where it belongs
    // rather than by a text match that could match either.
    const row = (await screen.findByText("Rent")).closest("li")!;
    expect(within(row).getByText("1200.00 USD")).toBeInTheDocument();
    expect(screen.getByText(/due this month/)).toBeInTheDocument();
  });

  it("totals each currency apart, never as one number", async () => {
    // Adding 500 USD to 40 GBP produces 540 of nothing.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        billsData({ totals: { USD: "500.00", GBP: "40.00" } }),
      ),
    );

    renderAt();

    expect(await screen.findByText("500.00 USD")).toBeInTheDocument();
    expect(screen.getByText("40.00 GBP")).toBeInTheDocument();
    expect(screen.queryByText("540.00")).not.toBeInTheDocument();
  });

  it("says when a bill is not in the total", async () => {
    // A total that silently omitted it would be a number somebody plans
    // against and should not.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(billsData({ unpriced: 1 })),
    );

    renderAt();

    expect(
      await screen.findByText(/one bill has no amount/i),
    ).toBeInTheDocument();
  });

  it("shows an unpriced bill as having no amount, not as free", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        billsData({
          bills: [
            {
              task_id: 2,
              text: "Water",
              due_date: "2026-08-10",
              amount: null,
              currency: "USD",
              payee: "",
              url: "/api/items/2/",
            },
          ],
          totals: {},
          unpriced: 1,
        }),
      ),
    );

    renderAt();

    expect(await screen.findByText("no amount")).toBeInTheDocument();
    expect(screen.queryByText(/0\.00/)).not.toBeInTheDocument();
  });

  it("says nothing is due rather than showing a zero total", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(billsData({ bills: [], totals: {}, unpriced: 0 })),
    );

    renderAt();

    expect(
      await screen.findByText("No bills due this month."),
    ).toBeInTheDocument();
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
