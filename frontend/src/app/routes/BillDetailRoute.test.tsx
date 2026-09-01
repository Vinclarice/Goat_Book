import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { BillDetailRoute } from "./BillDetailRoute";
import { apiResponse, sentRequests } from "../../test/fixtures";

function bill(overrides: Record<string, unknown> = {}) {
  return {
    task_id: 7,
    text: "Pay Landlord",
    due_date: "2026-08-01",
    amount: "1200.00",
    currency: "USD",
    payee: "Landlord",
    url: "/api/items/7/",
    paid: false,
    paid_amount: null,
    repeats: true,
    category: null,
    category_id: null,
    direction: "out",
    recurrence: "monthly",
    lead_days: 0,
    ...overrides,
  };
}

function renderBill() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/money/bills/7"]}>
        <Routes>
          <Route path="/money/bills/:taskId" element={<BillDetailRoute />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("BillDetailRoute", () => {
  /* A bill borrowed the task detail page until August 31, 2026, and that page
     spent a morning being taught to call itself Bill detail, hide Priority,
     Area and Checklist, and link back to Money -- every change an admission
     that a bill was on the wrong screen. bill-as-a-model-plan.md makes the
     borrowing impossible rather than awkward, so the surface moves first. */
  it("shows what a bill is, and none of what a task is", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      apiResponse(bill()),
    );

    renderBill();

    expect(await screen.findByRole("heading", { name: "Landlord" })).toBeInTheDocument();
    expect(screen.getByText("1200.00 USD")).toBeInTheDocument();
    expect(screen.getByText("August 1, 2026")).toBeInTheDocument();
    // The fields the task page had to be told to hide are simply absent here.
    expect(screen.queryByText("Priority")).toBeNull();
    expect(screen.queryByText("Area")).toBeNull();
    expect(screen.queryByText("Checklist")).toBeNull();
  });

  it("says an unpriced bill is unpriced rather than showing a zero", async () => {
    // "The water bill, whatever it comes to" is a real state, and a zero is a
    // number somebody would plan against.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      apiResponse(bill({ amount: null, payee: "Water" })),
    );

    renderBill();

    expect(await screen.findByText("Not priced")).toBeInTheDocument();
  });

  it("reports what was actually paid beside what was expected", async () => {
    /* The one figure this page has that the month row does not, and the reason
       paid_amount is a second column rather than an overwrite. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      apiResponse(bill({ paid: true, paid_amount: "1275.40" })),
    );

    renderBill();

    expect(await screen.findByText("1275.40 USD")).toBeInTheDocument();
    expect(screen.getByText("1200.00 USD")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Mark paid" }),
    ).toBeNull();
  });

  it("says so when a bill settled without a figure", async () => {
    // Reachable: pay_bill defaults the amount to what was expected, and an
    // unpriced bill has none. Found in real data by increment 2.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      apiResponse(bill({ amount: null, paid: true, paid_amount: null })),
    );

    renderBill();

    expect(await screen.findByText("Recorded, amount unknown")).toBeInTheDocument();
  });

  it("pays a bill from its own page", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      apiResponse(bill()),
    );

    renderBill();
    await user.click(await screen.findByRole("button", { name: "Mark paid" }));

    await waitFor(async () =>
      expect(
        (await sentRequests(fetchMock)).some(
          (sent) =>
            sent.method === "POST" &&
            sent.path === "/api/v1/money/bills/entry/7/pay",
        ),
      ).toBe(true),
    );
  });

  it("says mark received for money coming in", async () => {
    // A salary is settled too, and calling that "paid" reads as backwards.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      apiResponse(bill({ direction: "in", payee: "Work" })),
    );

    renderBill();

    expect(
      await screen.findByRole("button", { name: "Mark received" }),
    ).toBeInTheDocument();
  });

  it("offers two removals for a repeating bill and one for a one-off", async () => {
    /* Removing August's rent is not the same act as stopping rent, which is
       what delete_bill's whole_series flag exists for. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      apiResponse(bill({ repeats: true })),
    );

    renderBill();

    expect(
      await screen.findByRole("button", { name: "Just this one" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Stop this bill entirely" }),
    ).toBeInTheDocument();
  });

  it("offers a plain delete when it does not repeat", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      apiResponse(bill({ repeats: false })),
    );

    renderBill();

    expect(await screen.findByRole("button", { name: "Delete" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Stop this bill entirely" }),
    ).toBeNull();
  });
});
