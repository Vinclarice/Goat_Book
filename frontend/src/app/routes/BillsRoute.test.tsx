import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
        paid: false,
        repeats: true,
      },
    ],
    due_totals: { USD: "1200.00" },
    paid_totals: {},
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
    expect(screen.getByText(/still to pay/)).toBeInTheDocument();
  });

  it("keeps a paid bill in the month and says so", async () => {
    /* The defect this increment exists for. `bills_for` filtered to open
       tasks, borrowing the agenda's definition -- so rent paid on the 1st was
       gone from the page on the 2nd, and there was no way to confirm from here
       that it had been paid at all. See bills-page-plan.md, defect 3. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        billsData({
          bills: [
            {
              task_id: 1,
              text: "Rent",
              due_date: "2026-08-01",
              amount: "1200.00",
              currency: "USD",
              payee: "Landlord",
              url: "/api/items/1/",
              paid: true,
              repeats: false,
            },
          ],
          due_totals: {},
          paid_totals: { USD: "1200.00" },
        }),
      ),
    );

    renderAt();

    expect(await screen.findByText("Rent")).toBeInTheDocument();
    expect(screen.getByText("paid")).toBeInTheDocument();
    expect(screen.getByText("Everything this month is paid.")).toBeInTheDocument();
  });

  it("says what the month cost apart from what is left to pay", async () => {
    /* One number could not answer both, and the one it answered was the
       remainder while the word above it said total: a month that cost 1264.99
       reported 64.99. */
    /* Two bills on each side, so neither total equals a single row's amount:
       with one bill per bucket the figure appears on the row *and* in the
       total, and a bare text match cannot say which one it found. */
    const bill = (
      text: string,
      amount: string,
      paid: boolean,
      task_id: number,
    ) => ({
      task_id,
      text,
      due_date: "2026-08-10",
      amount,
      currency: "USD",
      payee: "Someone",
      url: `/api/items/${task_id}/`,
      paid,
      repeats: false,
    });
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        billsData({
          bills: [
            bill("Rent", "1200.00", true, 1),
            bill("Insurance", "300.00", true, 2),
            bill("Internet", "64.99", false, 3),
            bill("Water", "35.01", false, 4),
          ],
          due_totals: { USD: "100.00" },
          paid_totals: { USD: "1500.00" },
        }),
      ),
    );

    renderAt();

    expect(await screen.findByText("100.00 USD")).toBeInTheDocument();
    expect(screen.getByText("still to pay")).toBeInTheDocument();
    expect(screen.getByText("1500.00 USD")).toBeInTheDocument();
    expect(screen.getByText("already paid")).toBeInTheDocument();
  });

  it("totals each currency apart, never as one number", async () => {
    // Adding 500 USD to 40 GBP produces 540 of nothing.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        billsData({ due_totals: { USD: "500.00", GBP: "40.00" } }),
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

  it("does not say \"that total\" while showing one per currency", async () => {
    // Found in a browser with two currencies on screen: "it is not in that
    // total" points at whichever of the two the reader happened to be looking
    // at, and the honest claim is about both.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        billsData({ due_totals: { USD: "500.00", GBP: "40.00" }, unpriced: 1 }),
      ),
    );

    renderAt();

    expect(await screen.findByText(/not counted above/i)).toBeInTheDocument();
    expect(screen.queryByText(/that total/i)).not.toBeInTheDocument();
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
          due_totals: {},
          paid_totals: {},
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
      jsonResponse(billsData({ bills: [], due_totals: {}, paid_totals: {}, unpriced: 0 })),
    );

    renderAt();

    expect(
      await screen.findByText("Nothing in this month yet. Add one above."),
    ).toBeInTheDocument();
  });

  it("adds a bill without ever asking for a task", async () => {
    /* The defect this increment exists for: the page named after the concept
       could not produce one. The only route was to create a *task* elsewhere,
       open its detail page and fill in amount and payee. */
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const request = input as Request;
        if (request.method === "POST") {
          return jsonResponse({}, true, 201);
        }
        return jsonResponse(billsData());
      });

    renderAt();

    await userEvent.type(await screen.findByLabelText("Who it goes to"), "Landlord");
    await userEvent.type(screen.getByLabelText("Amount"), "1200.00");
    await userEvent.click(screen.getByRole("button", { name: "Add bill" }));

    const posted = fetchSpy.mock.calls
      .map(([request]) => request as Request)
      .filter((request) => request.method === "POST");
    await waitFor(() => expect(posted).toHaveLength(1));

    /* No title field, because the name comes from the payee on the server.
       If this ever finds one, the form has started asking a person to know
       that a bill is a task. */
    expect(screen.queryByLabelText(/title/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/task/i)).not.toBeInTheDocument();
  });

  it("offers a way in when the month is empty", async () => {
    /* The old empty state was "No bills due this month." and two links, both
       to other months, which were also empty. A dead end on the page a person
       arrives at wanting to add a bill. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        billsData({ bills: [], due_totals: {}, paid_totals: {}, unpriced: 0 }),
      ),
    );

    renderAt();

    expect(await screen.findByLabelText("Who it goes to")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add bill" })).toBeInTheDocument();
  });

  it("corrects a bill without leaving the page", async () => {
    /* Increment 3. Changing an amount used to mean opening the task's detail
       page, editing there, and coming back -- which is the same silo the add
       form closed, in the other direction. */
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const request = input as Request;
        if (request.method === "PATCH") return jsonResponse({});
        return jsonResponse(billsData());
      });

    renderAt();

    await userEvent.click(await screen.findByRole("button", { name: /Edit Landlord/ }));
    /* Scoped to the row being edited: the add form above uses the same labels,
       correctly -- "Amount" is what both boxes are -- so an unscoped query
       finds two and the duplication is the page working, not a bug. */
    const row = screen.getByRole("button", { name: "Save" }).closest("li")!;
    const amount = within(row).getByLabelText("Amount");
    await userEvent.clear(amount);
    await userEvent.type(amount, "1250.00");
    await userEvent.click(within(row).getByRole("button", { name: "Save" }));

    const patched = fetchSpy.mock.calls
      .map(([request]) => request as Request)
      .filter((request) => request.method === "PATCH");
    await waitFor(() => expect(patched).toHaveLength(1));
  });

  it("lets an edit be abandoned", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(billsData()),
    );

    renderAt();

    await userEvent.click(await screen.findByRole("button", { name: /Edit Landlord/ }));
    const row = screen.getByRole("button", { name: "Cancel" }).closest("li")!;
    expect(within(row).getByLabelText("Who it goes to")).toBeInTheDocument();
    await userEvent.click(within(row).getByRole("button", { name: "Cancel" }));

    /* Back to a row. The add form's own payee box is still on the page, which
       is why the assertion above is scoped to the row and this one is not. */
    expect(screen.getByRole("button", { name: /Edit Landlord/ })).toBeInTheDocument();
  });

  it("asks which bill is meant before deleting a repeating one", async () => {
    /* Deleting August's rent is not the same act as stopping rent, and only
       one of them can be undone by adding a bill back. */
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const request = input as Request;
        if (request.method === "DELETE") return jsonResponse({}, true, 204);
        return jsonResponse(billsData());
      });

    renderAt();

    await userEvent.click(
      await screen.findByRole("button", { name: /Delete Landlord/ }),
    );
    /* Nothing has been sent yet: the question comes first. */
    expect(
      fetchSpy.mock.calls.filter(
        ([request]) => (request as Request).method === "DELETE",
      ),
    ).toHaveLength(0);

    await userEvent.click(screen.getByRole("button", { name: "just this month" }));

    const deleted = fetchSpy.mock.calls
      .map(([request]) => request as Request)
      .filter((request) => request.method === "DELETE");
    await waitFor(() => expect(deleted).toHaveLength(1));
    expect(deleted[0].url).toContain("whole_series=false");
  });

  it("deletes a one-off bill without asking anything", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const request = input as Request;
        if (request.method === "DELETE") return jsonResponse({}, true, 204);
        return jsonResponse(
          billsData({
            bills: [
              {
                task_id: 1,
                text: "Plumber",
                due_date: "2026-08-04",
                amount: "90.00",
                currency: "USD",
                payee: "Plumber",
                url: "/api/items/1/",
                paid: false,
                repeats: false,
              },
            ],
          }),
        );
      });

    renderAt();

    await userEvent.click(
      await screen.findByRole("button", { name: /Delete Plumber/ }),
    );

    const deleted = fetchSpy.mock.calls
      .map(([request]) => request as Request)
      .filter((request) => request.method === "DELETE");
    await waitFor(() => expect(deleted).toHaveLength(1));
    /* No question, because there is only one thing it could mean. */
    expect(
      screen.queryByRole("button", { name: "the standing bill" }),
    ).not.toBeInTheDocument();
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
