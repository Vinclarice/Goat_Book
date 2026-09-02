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
        next_payment: null,
      },
      {
        id: 2,
        name: "Stocks ISA",
        kind: "investment",
        currency: "USD",
        owes: false,
        balance: null,
        previous: null,
        next_payment: null,
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
              next_payment: null,
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

  it("lets you make the first account here, rather than naming a page that cannot", async () => {
    /* **The defect this page shipped with.** `POST /api/v1/money/accounts`
       existed, was tested, and had no caller anywhere in the SPA -- so this
       screen and the history screen both told somebody to add an account and
       neither could, and the link one of them offered went to a third page
       that could not either. `principles.md`: a slice is not closed while
       nothing calls it.

       Here rather than on the landing page because this is where somebody is
       already trying to record a balance, which is the only reason to want an
       account in the first place. */
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") {
        return jsonResponse(
          {
            id: 9,
            name: "Dell Community",
            kind: "card",
            currency: "USD",
            owes: true,
            balance: null,
            previous: null,
            next_payment: null,
          },
          true,
          201,
        );
      }
      return jsonResponse(accountsData({ accounts: [] }));
    });

    renderAt();

    await user.type(
      await screen.findByLabelText("Account name"),
      "Dell Community",
    );
    await user.click(screen.getByRole("button", { name: "Add account" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([sent]) => {
          const request = sent as Request;
          return (
            request.method === "POST" &&
            new URL(request.url).pathname === "/api/v1/money/accounts"
          );
        }),
      ).toBe(true);
    });
  });

  it("offers the same form when accounts already exist", async () => {
    // A second account is the same act as the first. Hiding the form once one
    // exists would make "add another" the thing with no door.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(accountsData()),
    );

    renderAt();

    expect(await screen.findByLabelText("Account name")).toBeInTheDocument();
  });
});

describe("BalancesRoute, tied to the bills that pay it", () => {
  /* Increment 7 of bill-as-a-model-plan.md, and the disconnect Vince reported
     in his own words: *"I've added Dell Commenity and its showing up but now
     there's a disconnect. Like it should be tied to the payments."* This
     screen showed a card, a figure and nothing about how it gets paid. */
  it("names what pays an account down, and links to it", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        accountsData({
          accounts: [
            {
              id: 1,
              name: "Dell Community",
              kind: "card",
              currency: "USD",
              owes: true,
              balance: "220.00",
              previous: "300.00",
              next_payment: {
                bill_id: 9,
                payee: "Dell Community",
                due_date: "2026-08-20",
                amount: "80.00",
                currency: "USD",
              },
            },
          ],
        }),
      ),
    );

    renderAt();

    // Found by the label rather than by the name: the card and the bill that
    // pays it are both called "Dell Community", which is what somebody would
    // actually type and is exactly the case this feature is for.
    await screen.findAllByText("Dell Community");
    const row = screen
      .getByLabelText("Dell Community")
      .closest<HTMLElement>("li")!;
    expect(within(row).getByText(/80\.00 USD/)).toBeInTheDocument();
    expect(within(row).getByRole("link", { name: /Dell Community/ })).toHaveAttribute(
      "href",
      "/money/bills/9",
    );
  });

  it("says nothing rather than showing an empty row when nothing is filed", async () => {
    /* Null is a real state -- most accounts will have none -- and a blank
       slot reads as a figure that failed to load. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(accountsData()),
    );

    renderAt();

    await screen.findByText("Amex");
    expect(screen.queryByText(/Paid by/)).toBeNull();
  });

  it("says fed rather than paid for something held", async () => {
    // An ISA is not paid down. The wording follows the direction the same way
    // the pay button already does.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        accountsData({
          accounts: [
            {
              id: 2,
              name: "Stocks ISA",
              kind: "investment",
              currency: "USD",
              owes: false,
              balance: "1000.00",
              previous: null,
              next_payment: {
                bill_id: 4,
                payee: "Monthly contribution",
                due_date: "2026-08-20",
                amount: "200.00",
                currency: "USD",
              },
            },
          ],
        }),
      ),
    );

    renderAt();

    const row = (await screen.findByText("Stocks ISA")).closest<HTMLElement>("li")!;
    expect(within(row).getByText(/Fed by/)).toBeInTheDocument();
  });
});
