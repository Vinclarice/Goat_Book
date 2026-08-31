import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { MoneyLandingRoute } from "./MoneyLandingRoute";

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

function line(overrides: Record<string, unknown> = {}) {
  return {
    task_id: 1,
    text: "Pay Landlord",
    payee: "Landlord",
    due_date: "2026-08-28",
    amount: "1200.00",
    currency: "USD",
    days: 3,
    ...overrides,
  };
}

function landing(overrides: Record<string, unknown> = {}) {
  return {
    today: "2026-08-25",
    overdue: [],
    due_soon: [],
    renewing_soon: [],
    yearly_totals: {},
    owed_totals: {},
    held_totals: {},
    owed_change: {},
    held_change: {},
    unread_accounts: 0,
    /* **Non-zero by default, and that is the point of them.** These say
       *something has been recorded*, which every other field here is silent
       about -- they all read empty for a person with nothing and for a person
       whose month is quiet. Defaulting them to zero would make every test
       below assert the first-run page by accident. */
    line_count: 3,
    account_count: 1,
    ...overrides,
  };
}

function renderLanding() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/money"]}>
        <Routes>
          <Route path="/money" element={<MoneyLandingRoute />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("MoneyLandingRoute", () => {
  afterEach(() => vi.restoreAllMocks());

  it("says nothing needs you rather than showing an empty page", async () => {
    /* Three absent sections read as broken. "Nothing needs you" is the answer
       somebody came here hoping for, so it is said out loud -- **to somebody
       who has recorded something**, which is what the fixture's counts mean.
       Said to a person with no bills at all it is a tautology, which is the
       defect the three tests below cover. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(landing()),
    );

    renderLanding();

    expect(
      await screen.findByText(/Nothing is overdue, due soon, or about to renew/),
    ).toBeInTheDocument();
  });

  it("offers a way in when nothing has been recorded at all", async () => {
    /* **What Vince arrived at on August 31, 2026**: a heading, three links,
       and "Nothing is overdue, due soon, or about to renew" -- with no way to
       create anything from the module's own front door. The Day page learned
       this in FirstRun: three empty states none of which can be acted on are
       six concepts by another route. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(landing({ line_count: 0, account_count: 0 })),
    );

    renderLanding();

    expect(await screen.findByText(/Nothing recorded yet/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add a bill" })).toHaveAttribute(
      "href",
      "/money/month/2026-08-25",
    );
    expect(screen.getByRole("link", { name: "Add an account" })).toHaveAttribute(
      "href",
      "/money/balances",
    );
    // The tautology does not also appear: it is the wrong answer here, not an
    // additional one.
    expect(screen.queryByText(/Nothing is overdue/)).toBeNull();
  });

  it("points at balances for somebody with bills but no account", async () => {
    /* The half-started state, and the one Vince was actually in after adding
       his first bill. Three screens mention balances; none of them said how to
       have one. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(landing({ line_count: 1, account_count: 0 })),
    );

    renderLanding();

    expect(await screen.findByText(/No balances yet/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add an account" })).toHaveAttribute(
      "href",
      "/money/balances",
    );
    // Not the first-run block: this person has started.
    expect(screen.queryByText(/Nothing recorded yet/)).toBeNull();
  });

  it("points at bills for somebody with an account and nothing owed", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(landing({ line_count: 0, account_count: 2 })),
    );

    renderLanding();

    expect(await screen.findByText(/No bills or income yet/)).toBeInTheDocument();
    expect(screen.queryByText(/Nothing recorded yet/)).toBeNull();
  });

  it("words a delay rather than showing a signed number", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        landing({
          overdue: [line({ days: -4, payee: "Water" })],
          due_soon: [line({ task_id: 2, days: 1, payee: "Internet" })],
        }),
      ),
    );

    renderLanding();

    expect(await screen.findByText("4 days late")).toBeInTheDocument();
    expect(screen.getByText("tomorrow")).toBeInTheDocument();
  });

  it("reads a fall in debt as good news and a fall in savings as bad", async () => {
    /* The decision this page turns on. A page painting every decrease red
       would call paying off a loan a bad month. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        landing({
          owed_totals: { USD: "4200.00" },
          owed_change: { USD: "-300.00" },
          held_totals: { USD: "15000.00" },
          held_change: { USD: "-500.00" },
        }),
      ),
    );

    renderLanding();

    const debtFall = await screen.findByText(/300.00 USD/);
    const savingsFall = screen.getByText(/500.00 USD/);
    /* Both fell; only one of them is good news, and the class says which. */
    expect(debtFall.className).toContain("accent");
    expect(savingsFall.className).toContain("destructive");
  });

  it("counts accounts with no reading rather than carrying last month forward", async () => {
    /* Showing last month's figure as though it were this month's is the one
       thing a balance page must not do. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(landing({ unread_accounts: 3 })),
    );

    renderLanding();

    expect(
      await screen.findByText(/3 accounts have no balance for this month yet/),
    ).toBeInTheDocument();
  });

  it("says what the repeating bills cost over a year", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(landing({ yearly_totals: { USD: "600.00" } })),
    );

    renderLanding();

    expect(await screen.findByText("600.00 USD")).toBeInTheDocument();
    expect(screen.getByText(/a year in repeating bills/)).toBeInTheDocument();
  });

  it("reports a failure rather than an empty dashboard", async () => {
    /* An empty money page and a broken money page look identical, and only one
       of them means you have nothing to worry about. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({}, false, 500),
    );

    renderLanding();

    expect(await screen.findByRole("button", { name: /Try again/i })).toBeInTheDocument();
  });
});
