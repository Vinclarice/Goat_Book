import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { DayRoute } from "./DayRoute";

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

function dayData(overrides: Record<string, unknown> = {}) {
  return {
    date: "2026-08-03",
    intentions: "",
    gratitude: "",
    happenings: "",
    today: "2026-08-03",
    action_items: [],
    shows_action_items: true,
    ...overrides,
  };
}

function actionItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    text: "Pay rent",
    due_date: "2026-08-03",
    parent: null,
    ...overrides,
  };
}

function renderAt(path: string, stored = dayData()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/day" element={<DayRoute />} />
          <Route path="/day/:date" element={<DayRoute />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("DayRoute", () => {
  it("shows what was already written for the day", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ intentions: "Finish the slice", gratitude: "Rain" })),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByLabelText("Intentions")).toHaveValue(
      "Finish the slice",
    );
    expect(screen.getByLabelText("Grateful for")).toHaveValue("Rain");
  });

  it("sends only the day's own text when saving", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const request = input as Request;
        if (request.method === "PATCH") {
          return jsonResponse(dayData({ intentions: "Ship it" }));
        }
        return jsonResponse(dayData());
      });

    renderAt("/day/2026-08-03");
    const intentions = await screen.findByLabelText("Intentions");
    await userEvent.type(intentions, "Ship it");
    await userEvent.click(screen.getByRole("button", { name: "Save the day" }));

    await waitFor(() => expect(screen.getByText("Saved.")).toBeInTheDocument());
    const patch = fetchSpy.mock.calls
      .map(([input]) => input as Request)
      .find((request) => request.method === "PATCH");
    expect(patch?.url).toContain("/api/v1/day/2026-08-03");
  });

  it("labels the day as Today only when the server says it is", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ date: "2026-08-01", today: "2026-08-03" })),
    );

    renderAt("/day/2026-08-01");

    expect(await screen.findByText("Your day")).toBeInTheDocument();
    expect(screen.queryByText("Today")).not.toBeInTheDocument();
  });

  it("asks the server which day it is when the route carries no date", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => jsonResponse(dayData()));

    renderAt("/day");

    await screen.findByLabelText("Intentions");
    const url = (fetchSpy.mock.calls[0][0] as Request).url;
    expect(url).toMatch(/\/api\/v1\/day$/);
  });

  it("does not overwrite what is being typed when the query refetches", async () => {
    // The bug PreferencesRoute already had: an alt-tab refetch that seeds
    // the form again silently restores the stored text over an edit in
    // progress, and the save that follows reports success for the wrong
    // value.
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ intentions: "Stored text" })),
    );

    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/day/2026-08-03"]}>
          <Routes>
            <Route path="/day/:date" element={<DayRoute />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const intentions = await screen.findByLabelText("Intentions");
    await userEvent.clear(intentions);
    await userEvent.type(intentions, "Half a thought");
    await client.refetchQueries({ queryKey: ["day", "2026-08-03"] });

    await waitFor(() => expect(intentions).toHaveValue("Half a thought"));
  });

  it("lists today's action items with the agenda's own due labels", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          action_items: [
            actionItem({ id: 1, text: "Pay rent" }),
            actionItem({ id: 2, text: "Call the plumber", due_date: "2026-08-01" }),
          ],
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    const rent = (await screen.findByText("Pay rent")).closest("li")!;
    const plumber = screen.getByText("Call the plumber").closest("li")!;

    // dueLabel's wording, not a second date format invented in this route.
    // Scoped to the rows: the page header also says "Today", which is a
    // different statement about a different thing.
    expect(within(rent).getByText("Today")).toBeInTheDocument();
    expect(within(plumber).getByText("2 days overdue")).toBeInTheDocument();
  });

  it("says nothing is due rather than showing an empty box", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ action_items: [], shows_action_items: true })),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByText(/Nothing due today/)).toBeInTheDocument();
  });

  it("explains why a past day shows no action items", async () => {
    // Empty-because-done and empty-because-not-today are different, and the
    // page has to say which one it means.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          date: "2026-08-01",
          today: "2026-08-03",
          action_items: [],
          shows_action_items: false,
        }),
      ),
    );

    renderAt("/day/2026-08-01");

    expect(
      await screen.findByText(/Only today shows action items/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Nothing due today/)).not.toBeInTheDocument();
  });

  it("shows a subtask's parent so the row can be placed", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          action_items: [
            actionItem({ text: "Book flights", parent: { id: 9, text: "Trip" } }),
          ],
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByText(/Trip/)).toBeInTheDocument();
    expect(screen.getByText("Book flights")).toBeInTheDocument();
  });

  it("sends a captured thought to the shared capture endpoint", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.url.includes("/api/v1/capture")) {
        return jsonResponse({ id: 1, created_at: "2026-08-03T10:00:00" }, true, 201);
      }
      return jsonResponse(dayData());
    });

    renderAt("/day/2026-08-03");
    await userEvent.type(
      await screen.findByLabelText("Capture a thought"),
      "A thought worth keeping",
    );
    await userEvent.click(screen.getByRole("button", { name: "Capture" }));

    await waitFor(() =>
      expect(screen.getByText("Sent to your Inbox.")).toBeInTheDocument(),
    );
    const posted = fetchSpy.mock.calls
      .map(([input]) => input as Request)
      .find((request) => request.url.includes("/api/v1/capture"));
    // The endpoint the Inbox and the phone already use, not a daily one.
    expect(posted?.method).toBe("POST");
  });

  it("empties the box only once the thought is actually captured", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.url.includes("/api/v1/capture")) {
        return jsonResponse({ id: 1, created_at: "x" }, true, 201);
      }
      return jsonResponse(dayData());
    });

    renderAt("/day/2026-08-03");
    const box = await screen.findByLabelText("Capture a thought");
    await userEvent.type(box, "A thought worth keeping");
    await userEvent.click(screen.getByRole("button", { name: "Capture" }));

    await waitFor(() => expect(box).toHaveValue(""));
  });

  it("keeps the thought when the capture fails", async () => {
    // principles.md: capture is durable before it is clever. Losing a
    // half-typed thought to a failed request is the failure people blame
    // on themselves.
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.url.includes("/api/v1/capture")) {
        return jsonResponse({ detail: "nope" }, false, 500);
      }
      return jsonResponse(dayData());
    });

    renderAt("/day/2026-08-03");
    const box = await screen.findByLabelText("Capture a thought");
    await userEvent.type(box, "Do not eat this");
    await userEvent.click(screen.getByRole("button", { name: "Capture" }));

    await waitFor(() =>
      expect(screen.getByText(/It's still here/)).toBeInTheDocument(),
    );
    expect(box).toHaveValue("Do not eat this");
  });

  it("does not capture an empty thought", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => jsonResponse(dayData()));

    renderAt("/day/2026-08-03");
    await screen.findByLabelText("Capture a thought");
    await userEvent.click(screen.getByRole("button", { name: "Capture" }));

    expect(
      fetchSpy.mock.calls.filter(([input]) =>
        (input as Request).url.includes("/api/v1/capture"),
      ),
    ).toHaveLength(0);
  });

  it("keeps capture separate from the day's own save", async () => {
    // The C2 failure mode, refused on new surface: two controls that look
    // alike and mean different things.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData()),
    );

    renderAt("/day/2026-08-03");

    await screen.findByLabelText("Capture a thought");
    expect(screen.getByRole("button", { name: "Capture" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Save the day" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/not into this day/i),
    ).toBeInTheDocument();
  });

  it("offers a way out when the day cannot be loaded", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({ detail: "nope" }, false, 500),
    );

    renderAt("/day/2026-08-03");

    expect(
      await screen.findByRole("button", { name: /try again/i }),
    ).toBeInTheDocument();
  });
});
