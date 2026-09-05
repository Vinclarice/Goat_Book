import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { DayRoute } from "./DayRoute";
import { requestedPaths, sentRequests } from "../../test/fixtures";

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
    suggestions: [],
    action_items: [],
    bills: [],
    // An area by default, because every other test here is about an account
    // that has started. A task belongs to a List and list_summaries filters
    // nothing, so "action items but no areas" -- what this fixture used to
    // say -- is a state the database cannot produce. The empty-areas case is
    // now its own thing: see the first-run tests.
    areas: [dayArea()],
    projects: [],
    shows_action_items: true,
    focus: [],
    draft: { typical: null, proposed: [], available: 0 },
    closing: null,
    brief: { slipped: [], coming: [], gone_quiet: [] },
    compass_purpose: "",
    compass_question: "",
    week_intention: "",
    typical_day: null,
    list_closed_at: null,
    log: [],
    appointments: [],
    appointments_coming: [],
    routines: [],
    routines_are_loggable: true,
    paused_routines: [],
    ...overrides,
  };
}

function standing(overrides: Record<string, unknown> = {}) {
  return {
    routine_id: 1,
    title: "Practice Spanish",
    cadence: "daily",
    period_start: "2026-08-03",
    progress: 2,
    target: 5,
    unit: "lessons",
    outcome: "open",
    is_met: false,
    ...overrides,
  };
}

function focusRow(overrides: Record<string, unknown> = {}) {
  return {
    task_id: 1,
    text: "Pay rent",
    status: "active",
    due_date: "2026-08-03",
    selected_at: "2026-08-03T09:00:00",
    above_the_line: true,
    url: "/api/items/1/",
    ...overrides,
  };
}

function actionItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    text: "Pay rent",
    due_date: "2026-08-03",
    age_in_days: 0,
    area_id: 1,
    project_id: null,
    ...overrides,
  };
}

function dayArea(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    title: "Home",
    url: "/areas/1/",
    color_key: "sky",
    ...overrides,
  };
}

function dayProject(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    title: "Kitchen remodel",
    url: "/areas/1/",
    ...overrides,
  };
}

function emptyPool() {
  return { today: "2026-08-03", open_count: 0, fixed: [], floating: [] };
}

function renderAt(path: string, stored = dayData()) {
  // **The day fetches the pool panel too, since increment 8.** Every test here
  // mocks fetch with the day's own payload, which the panel would then read as
  // a pool and fail on -- so this wraps whatever the test installed and routes
  // the panel's request to an empty pool. The alternative was making the panel
  // tolerate a payload that is not a pool, which is a defensive shape hiding a
  // real one; a test that wants to assert about the panel supplies its own.
  const inner = globalThis.fetch;
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.includes("/api/v1/pool")) return jsonResponse(emptyPool());
    return inner(input as never, init as never);
  });
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
  it("no longer offers anywhere to write the day in prose", async () => {
    // ~~"shows what was already written for the day"~~, ~~"sends only the
    // day's own text when saving"~~, ~~"does not overwrite what is being typed
    // when the query refetches"~~ and ~~"does not lose a half-written day when
    // something is pinned"~~ -- **September 4, 2026, Vince's call**: Intentions,
    // Grateful for and Happenings left the Day page, and the save with them.
    //
    // The page had two ways of writing into it. The composer puts a line in
    // the log as it happens; these asked, at the end, for the same day in
    // prose. Asserted as an absence rather than dropped quietly, because the
    // columns, the API and every read of them are untouched -- what left is
    // the editor, and a stray textarea reappearing here would be the feature
    // coming back by accident.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ intentions: "Finish the slice", gratitude: "Rain" })),
    );

    renderAt("/day/2026-08-03");

    await screen.findByLabelText("Capture a thought");
    for (const label of ["Intentions", "Grateful for", "Happenings"]) {
      expect(screen.queryByLabelText(label)).toBeNull();
    }
    expect(screen.queryByRole("button", { name: "Save the day" })).toBeNull();
  });

  it("labels the day as Today only when the server says it is", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ date: "2026-08-01", today: "2026-08-03" })),
    );

    renderAt("/day/2026-08-01");

    expect(await screen.findByText("Your day")).toBeInTheDocument();
    // The heading, not any occurrence of the word: the composer's destination
    // select has a "Today" option on every day, and it is not a claim about
    // which day this is.
    expect(
      screen.queryByRole("heading", { name: "Today" }),
    ).not.toBeInTheDocument();
  });

  it("asks the server which day it is when the route carries no date", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => jsonResponse(dayData()));

    renderAt("/day");

    await screen.findByLabelText("Capture a thought");
    const url = (fetchSpy.mock.calls[0][0] as Request).url;
    expect(url).toMatch(/\/api\/v1\/day$/);
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

  it("shows a bill on the day, apart from the action items", async () => {
    /* decision 4 in bill-as-a-model-plan.md: paying is a real thing to do on
       a day, so bills stay here even as they stop being tasks. Its own
       section rather than mixed into the action items, because it is not one
       -- there is nothing to pin and no area to file it in. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          action_items: [actionItem({ id: 1, text: "Call the plumber" })],
          bills: [
            {
              id: 9,
              payee: "Landlord",
              due_date: "2026-08-03",
              amount: "1200.00",
              currency: "USD",
              direction: "out",
              repeats: true,
            },
          ],
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    const bill = (await screen.findByText("Landlord")).closest<HTMLElement>("li")!;
    expect(within(bill).getByText("1200.00 USD")).toBeInTheDocument();
    expect(
      within(bill).getByRole("link", { name: "Landlord" }),
    ).toHaveAttribute("href", "/money/bills/9");
    // Not in the action items, and the action items are not empty -- so this
    // is a separation, not a page with nothing on it.
    expect(screen.getByText("Call the plumber")).toBeInTheDocument();
  });

  it("pays a bill from the day", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = input instanceof Request ? input.url : String(input);
      if (url.includes("/pay")) return jsonResponse({});
      return jsonResponse(
        dayData({
          bills: [
            {
              id: 9,
              payee: "Landlord",
              due_date: "2026-08-03",
              amount: "1200.00",
              currency: "USD",
              direction: "out",
              repeats: true,
            },
          ],
        }),
      );
    });

    renderAt("/day/2026-08-03");
    await userEvent.click(await screen.findByRole("button", { name: "Mark paid" }));

    await waitFor(() =>
      expect(
        requestedPaths(fetchMock).some((path) =>
          path.includes("/api/v1/money/bills/entry/9/pay"),
        ),
      ).toBe(true),
    );
  });

  it("shows no bills section on a past day", async () => {
    // The same refusal shows_action_items makes: an unpaid bill today was not
    // necessarily unpaid on the 1st.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          date: "2026-08-01",
          today: "2026-08-03",
          bills: [],
          shows_action_items: false,
        }),
      ),
    );

    renderAt("/day/2026-08-01");

    await screen.findByText(/Only today shows action items/);
    expect(screen.queryByRole("heading", { name: "Bills" })).toBeNull();
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

  it("sends a captured thought to the shared capture endpoint", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.url.includes("/api/v1/capture")) {
        // A node, not an Inbox row -- Heron 4a. The box reads only `error`, so
        // a stale mock would keep passing while lying about the contract.
        return jsonResponse(
          {
            public_id: "2ecb0dba-fc57-4f7e-9891-9b0e938ca344",
            captured_at: "2026-08-03T10:00:00Z",
          },
          true,
          201,
        );
      }
      return jsonResponse(dayData());
    });

    renderAt("/day/2026-08-03");
    await userEvent.type(
      await screen.findByLabelText("Capture a thought"),
      "A thought worth keeping",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    // "Kept as a note." rather than "Kept.": the composer says which of the
    // four destinations it went to, because they are four different places.
    await waitFor(() =>
      expect(screen.getByText("Kept as a note.")).toBeInTheDocument(),
    );
    // And it says where to go and look, which is no longer the Inbox.
    expect(screen.getByRole("link", { name: "See it" })).toHaveAttribute(
      "href",
      "/mind/",
    );
    const posted = fetchSpy.mock.calls
      .map(([input]) => input as Request)
      .find((request) => request.url.includes("/api/v1/capture"));
    // The endpoint the phone already uses, not a daily one.
    expect(posted?.method).toBe("POST");
  });

  it("empties the box only once the thought is actually captured", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.url.includes("/api/v1/capture")) {
        return jsonResponse(
          { public_id: "2ecb0dba-fc57-4f7e-9891-9b0e938ca344", captured_at: "x" },
          true,
          201,
        );
      }
      return jsonResponse(dayData());
    });

    renderAt("/day/2026-08-03");
    const box = await screen.findByLabelText("Capture a thought");
    await userEvent.type(box, "A thought worth keeping");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

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
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

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
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    expect(
      fetchSpy.mock.calls.filter(([input]) =>
        (input as Request).url.includes("/api/v1/capture"),
      ),
    ).toHaveLength(0);
  });

  it("says what the composer's box is for, now that it is the only one", async () => {
    // ~~"keeps capture separate from the day's own save"~~ -- the C2 failure
    // mode was two controls that look alike and mean different things, and
    // there is one control since the day's own save left on September 4, 2026.
    // What the test still holds is the half that survives: the page says what
    // this box does.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData()),
    );

    renderAt("/day/2026-08-03");

    await screen.findByLabelText("Capture a thought");
    expect(screen.getByRole("button", { name: "Add" })).toBeInTheDocument();
    // The sentence changed with the box: it said "goes to the Inbox to sort
    // out later" long after the Inbox was deleted, and now says what the four
    // destinations actually are. What the test is holding is unchanged --
    // that the page tells you this box is not the day's own notes.
    expect(
      screen.getByText(/A note is only words/i),
    ).toBeInTheDocument();
  });

  it("teaches a brand-new account instead of showing it three empty boxes", async () => {
    // product-stories.md S1: the first screen must offer one obvious thing to
    // do rather than six concepts. What it found was Focus saying "choose from
    // your action items below", Action items saying "nothing due today", and
    // Routines explaining what a routine is -- to somebody with none of the
    // three, and no way to act on any of them.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ areas: [] })),
    );

    renderAt("/day/2026-08-03");

    expect(
      await screen.findByRole("heading", { name: /Start with one thing/ }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Nothing pinned yet/)).toBeNull();
    expect(screen.queryByText(/Nothing due today/)).toBeNull();
    expect(screen.queryByText(/No routines yet/)).toBeNull();
  });

  it("offers one action, and it makes a real task", async () => {
    // Not "name your first area": a container is not a thing anyone wants to
    // make. The one form takes the task and the area together, so it leaves
    // somebody with something they actually wrote down.
    //
    // **The contract changed here, deliberately** --
    // coherence-audit-2026-08-30.md F1. This asserted
    // `action="/areas/new"`, a plain Django form POST that reloaded the page
    // out of the SPA. It is `POST /api/v1/areas` now, so what is asserted is
    // the request rather than the markup.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ areas: [] })),
    );

    renderAt("/day/2026-08-03");

    const field = await screen.findByLabelText(/first thing on your plate/i);
    expect(field).toBeRequired();
    expect(field.closest("form")).not.toHaveAttribute("action");
    expect(screen.getByLabelText(/area it belongs to/i)).not.toBeRequired();
  });

  it("sends the first area and its first task to the typed endpoint", async () => {
    // coherence-audit-2026-08-30.md F1. Both fields in one request, which is
    // what keeps FirstRun's promise that leaving the area name empty lets it
    // take the name of the task -- the server decides that, in
    // create_list_with_item, and always has.
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST" && request.url.includes("/api/v1/areas")) {
        // This file's jsonResponse already carries the headers, text() and
        // clone() that openapi-fetch needs, unlike AgendaWorkspace's.
        return jsonResponse({
          id: 4,
          title: "Home",
          create_item_url: "/api/areas/4/items/",
        });
      }
      return jsonResponse(dayData({ areas: [] }));
    });

    renderAt("/day/2026-08-03");

    await user.type(
      await screen.findByLabelText(/first thing on your plate/i),
      "Call the dentist",
    );
    await user.type(screen.getByLabelText(/area it belongs to/i), "Home");
    await user.click(screen.getByRole("button", { name: "Add it" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) => {
          const req = request as Request;
          return req.method === "POST" && req.url.includes("/api/v1/areas");
        }),
      ).toBe(true);
    });
  });

  it("leaves an established account's quiet day alone", async () => {
    // The signal is areas, not emptiness. Somebody with an area and nothing
    // due has an empty day too, and showing them onboarding would be worse
    // than showing them nothing.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ areas: [dayArea()], action_items: [], focus: [] })),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByText(/Nothing pinned yet/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Start with one thing/ })).toBeNull();
  });

  it("invites you to pin something when nothing is chosen yet", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ action_items: [actionItem()] })),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByText(/Nothing pinned yet/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Pin to today" }),
    ).toBeInTheDocument();
  });

  it("shows an action item's area and project, the same way the Agenda does", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          action_items: [
            actionItem({ id: 1, text: "Order cabinets", project_id: 7 }),
            actionItem({ id: 2, text: "Pay rent" }),
          ],
          areas: [dayArea()],
          projects: [dayProject({ id: 7, title: "Kitchen remodel", url: "/areas/1/" })],
        }),
      ),
    );

    renderAt("/day/2026-08-03");
    await screen.findByText("Order cabinets");

    const withProject = screen.getByText("Order cabinets").closest("li")!;
    const withoutProject = screen.getByText("Pay rent").closest("li")!;
    expect(within(withProject).getByRole("link", { name: "Home" })).toHaveAttribute(
      "href",
      "/areas/1/",
    );
    expect(
      within(withProject).getByRole("link", { name: "Kitchen remodel" }),
    ).toHaveAttribute("href", "/areas/1/");
    expect(within(withoutProject).getByRole("link", { name: "Home" })).toBeInTheDocument();
    expect(within(withoutProject).queryByText("Kitchen remodel")).not.toBeInTheDocument();
  });

  it("pins a task through the day's own focus endpoint", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") {
        return jsonResponse(
          dayData({ action_items: [actionItem()], focus: [focusRow()] }),
        );
      }
      return jsonResponse(dayData({ action_items: [actionItem()] }));
    });

    renderAt("/day/2026-08-03");
    await userEvent.click(
      await screen.findByRole("button", { name: "Pin to today" }),
    );

    await waitFor(() =>
      expect(screen.queryByText(/Nothing pinned yet/)).not.toBeInTheDocument(),
    );
    const posted = fetchSpy.mock.calls
      .map(([input]) => input as Request)
      .find((request) => request.method === "POST");
    expect(posted?.url).toContain("/api/v1/day/2026-08-03/focus");
  });

  it("marks a pinned task in the agenda instead of hiding it", async () => {
    // The focus list sits above the agenda rather than carving it up, so
    // the row has to say which it is -- two identical entries would be the
    // C2 confusion again.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ action_items: [actionItem()], focus: [focusRow()] })),
    );

    renderAt("/day/2026-08-03");

    const row = (await screen.findAllByText("Pay rent"))
      .map((node) => node.closest("li")!)
      .find((li) => within(li).queryByText("Pinned"));
    expect(row).toBeTruthy();
    expect(within(row!).getByRole("button", { name: "Unpin" })).toBeInTheDocument();
  });

  it("unpins through the delete endpoint", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "DELETE") {
        return jsonResponse(dayData({ action_items: [actionItem()] }));
      }
      return jsonResponse(
        dayData({ action_items: [actionItem()], focus: [focusRow()] }),
      );
    });

    renderAt("/day/2026-08-03");
    const unpins = await screen.findAllByRole("button", { name: "Unpin" });
    await userEvent.click(unpins[0]);

    await waitFor(() =>
      expect(screen.getByText(/Nothing pinned yet/)).toBeInTheDocument(),
    );
    const deleted = fetchSpy.mock.calls
      .map(([input]) => input as Request)
      .find((request) => request.method === "DELETE");
    expect(deleted?.url).toContain("/api/v1/day/2026-08-03/focus/1");
  });

  it("offers a way to reach another day at all", async () => {
    // The only entrance to the calendar, and therefore to any date that is
    // not this one. Without it the route is a surface nothing reaches.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData()),
    );

    renderAt("/day/2026-08-03");

    expect(
      await screen.findByRole("link", { name: "Another day" }),
    ).toHaveAttribute("href", "/calendar/2026-08-03");
  });

  it("says what slipped, what is coming and what has gone quiet", async () => {
    // The awareness half. Everything in it is deliberately something this
    // page does not already show: overdue work is here, the fact that he
    // *chose* one of them yesterday is not.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          brief: {
            slipped: [{ id: 1, text: "Call the plumber", due_date: null }],
            coming: [{ id: 2, text: "Property tax", due_date: "2026-08-08" }],
            gone_quiet: [{ id: 3, title: "The book", quiet_for_days: 40 }],
          },
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByText("Call the plumber")).toBeInTheDocument();
    expect(screen.getByText("Property tax")).toBeInTheDocument();
    expect(screen.getByText(/The book/)).toBeInTheDocument();
  });

  it("says nothing at all on a quiet day", async () => {
    // Not an empty dashboard. A brief that filled three sections every
    // morning would be skipped by the end of the week, which is why short or
    // absent is the correct output rather than a failure.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({ brief: { slipped: [], coming: [], gone_quiet: [] } }),
      ),
    );

    renderAt("/day/2026-08-03");

    await screen.findByLabelText("Capture a thought");
    expect(screen.queryByText("Since yesterday")).not.toBeInTheDocument();
  });

  it("asks him to close the day, with what the day held", async () => {
    // S5's missing half. The record and the morning's choice were already
    // good; nothing ever asked for the first.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          closing: closing({ chosen: 3, finished: 2, unfinished: 1, released: 1 }),
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByText(/2 of 3/)).toBeInTheDocument();
    expect(screen.getByText(/1 you set aside/i)).toBeInTheDocument();
  });

  it("does not ask when the server has not said it is time", async () => {
    // The hour is the server's call, in the owner's own zone -- the client
    // has none of its own to reason about, which is why this is a null rather
    // than a time the page compares against.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ closing: null })),
    );

    renderAt("/day/2026-08-03");

    await screen.findByLabelText("Capture a thought");
    expect(screen.queryByText(/close the day/i)).not.toBeInTheDocument();
  });

  it("offers to plan the day, and pins what it showed", async () => {
    // The daily loop's whole write surface was write_entry, pin_task and
    // unpin_task -- nothing that proposes. One decision instead of five.
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") return jsonResponse(dayData());
      return jsonResponse(
        dayData({
          draft: {
            typical: 2,
            available: 5,
            proposed: [
              { id: 1, text: "Pay rent", due_date: "2026-08-03" },
              { id: 2, text: "Call the plumber", due_date: null },
            ],
          },
        }),
      );
    });

    renderAt("/day/2026-08-03");
    await userEvent.click(
      await screen.findByRole("button", { name: "Plan my day" }),
    );

    await waitFor(() => {
      const posted = fetchSpy.mock.calls
        .map(([input]) => input as Request)
        .find((req) => req.url.includes("/focus/draft"));
      expect(posted).toBeTruthy();
    });
  });

  it("says what it left out rather than quietly showing less", async () => {
    // Bounding the proposal is not hiding the work: the number is what lets
    // the page say "two of five" instead of showing two and meaning nine.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          draft: {
            typical: 2,
            available: 5,
            proposed: [
              { id: 1, text: "Pay rent", due_date: "2026-08-03" },
              { id: 2, text: "Call the plumber", due_date: null },
            ],
          },
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByText(/2 of 5/)).toBeInTheDocument();
  });

  it("offers no draft when there is not enough history to justify one", async () => {
    // null is not zero. "No evidence yet" and "you have room" call for
    // opposite responses, and a proposal of nothing would say the second.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({ draft: { typical: null, proposed: [], available: 4 } }),
      ),
    );

    renderAt("/day/2026-08-03");

    await screen.findByText(/Nothing pinned yet/);
    expect(
      screen.queryByRole("button", { name: "Plan my day" }),
    ).not.toBeInTheDocument();
  });

  it("says why it has nothing to propose, rather than saying nothing", async () => {
    // Found by looking at the page rather than at a test: with six candidates
    // and no capacity figure the draft rendered as blank space, which is
    // indistinguishable from broken to somebody who has never seen it work.
    // The count is the proof it is not broken; the second sentence is what
    // unblocks it. The five-day floor is `TYPICAL_DAY_MINIMUM_SAMPLE` and is
    // deliberately not restated here -- a mirrored constant is a constant that
    // will disagree later.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({ draft: { typical: null, proposed: [], available: 4 } }),
      ),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByText(/4 could have a claim on today/)).
      toBeInTheDocument();
    expect(screen.getByText(/plan a few days by hand/i)).toBeInTheDocument();
  });

  it("stays silent when there is nothing it could have proposed", async () => {
    // No capacity *and* no candidates is not a gap worth explaining, and a
    // sentence every morning on an empty day is how a page stops being read.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({ draft: { typical: null, proposed: [], available: 0 } }),
      ),
    );

    renderAt("/day/2026-08-03");

    await screen.findByText(/Nothing pinned yet/);
    expect(screen.queryByText(/could have a claim/)).not.toBeInTheDocument();
  });

  it("completes a pinned task through the task's own endpoint", async () => {
    // principles.md, *the main surface can do the main thing*: the vision
    // document calls this the main working surface and it could not tick
    // anything off. The endpoint is the one the Agenda already completes
    // through -- naming the authority rather than growing a second one,
    // which is what the read-only comment here was protecting against.
    // Two client layers on one page, so a call is read rather than cast.
    // Everything else here goes through `apiV1`, which builds a `Request`;
    // `updateTaskStatus` is the hand-written client and passes a string URL
    // with an init object. `commercial-blueprint.md` Part 4 names that
    // duplication; this is what it looks like from a test.
    const called = (input: unknown, init?: RequestInit) =>
      typeof input === "string"
        ? { url: input, method: init?.method }
        : { url: (input as Request).url, method: (input as Request).method };

    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input, init) => {
        const { url, method } = called(input, init);
        if (method === "PATCH" && url.includes("/api/v1/tasks/1")) {
          return jsonResponse({
            task: { ...focusRow(), status: "completed" },
            spawned: null,
            spawned_checklist_steps: [],
          });
        }
        return jsonResponse(dayData({ focus: [focusRow()] }));
      });

    renderAt("/day/2026-08-03");
    await userEvent.click(
      await screen.findByRole("button", { name: "Complete Pay rent" }),
    );

    await waitFor(() => {
      const patched = fetchSpy.mock.calls
        .map(([input, init]) => called(input, init))
        .find((call) => call.method === "PATCH");
      expect(patched?.url).toContain("/api/v1/tasks/1");
    });
  });

  it("chooses a pinned task for tomorrow without touching its due date", async () => {
    // S2's second verb: "moves one task to tomorrow", in bed, on a phone.
    //
    // **It moved the due date until September 3, 2026.**
    // superlists-2.0-plan.md rule 7 is *never a move* and increment 5 says
    // *never a date move*: a due date is a promise to somebody, and choosing
    // to work on something tomorrow is not the same act as re-promising it.
    // Leaving both behaviours on one page would have meant the word
    // "Tomorrow" doing two opposite things a few inches apart.
    //
    // Not carry-forward either way. daily-operating-system-vision.md forbids
    // rescheduling *automatically*; "one item, one decision" is exactly this.
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const request = input as Request;
        if (request.method === "POST") return jsonResponse(dayData());
        return jsonResponse(dayData({ focus: [focusRow()] }));
      });

    renderAt("/day/2026-08-03");
    await userEvent.click(
      await screen.findByRole("button", { name: "Move Pay rent to tomorrow" }),
    );

    await waitFor(async () => {
      const sent = await sentRequests(fetchSpy);
      expect(
        sent.some(
          (call) =>
            call.method === "POST" &&
            call.path.includes("/api/v1/day/2026-08-03/leftovers/1") &&
            JSON.parse(String(call.body)).decision === "tomorrow",
        ),
      ).toBe(true);
      // And nothing re-promised it.
      expect(sent.some((call) => call.method === "PATCH")).toBe(false);
    });
  });

  it("gives the compass link a thumb-sized target like every button has", async () => {
    // What this can prove: the shared utility is applied. What it cannot:
    // that the box measures 44px, which needs a coarse pointer no suite here
    // emulates. roadmap.md's mobile entry names links as the half of the
    // August 18 fix that was left -- "Edit your compass" is the one on this
    // page, and it is a control that happens to be an anchor.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ compass_purpose: "Build the thing" })),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByRole("link", { name: "Edit your compass" }))
      .toHaveClass("touch-target");
  });

  it("offers no complete button for a pin whose task has been deleted", async () => {
    // The record of having planned something outlives the task, so the row
    // stays -- but there is nothing left to address. Same reasoning as the
    // missing Unpin on that row.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({ focus: [focusRow({ task_id: null, url: null })] }),
      ),
    );

    renderAt("/day/2026-08-03");

    await screen.findByText("Pay rent");
    expect(
      screen.queryByRole("button", { name: /^Complete/ }),
    ).not.toBeInTheDocument();
  });

  it("shows a pinned task whose task has been deleted, without an unpin", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          focus: [
            focusRow({ task_id: null, text: "Something since deleted", status: null }),
          ],
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    const row = (await screen.findByText("Something since deleted")).closest("li")!;
    expect(within(row).queryByRole("button", { name: "Unpin" })).toBeNull();
  });

  it("shows the compass above the day", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          compass_purpose: "Build something worth maintaining.",
          compass_question: "What is the most I can do?",
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    expect(
      await screen.findByText("Build something worth maintaining."),
    ).toBeInTheDocument();
    expect(screen.getByText("What is the most I can do?")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Edit your compass/ }),
    ).toBeInTheDocument();
  });

  it("says what a typical day holds while the day is still being planned", async () => {
    // product-stories.md S3, at the grain the story asks for: "the day says so
    // while he is still planning". kestrel shipped this a week wide and on the
    // review; D2's worked example was always a Tuesday.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          typical_day: 3,
          focus: [
            focusRow(),
            focusRow({ task_id: 2, text: "Call the bank" }),
            focusRow({ task_id: 3, text: "Book the dentist" }),
            focusRow({ task_id: 4, text: "Email the builder" }),
            focusRow({ task_id: 5, text: "Renew the parking permit" }),
          ],
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    expect(
      await screen.findByText(/You have finished 3 on a typical day/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/more than the day usually holds/),
    ).toBeInTheDocument();
  });

  it("states capacity without grading the person", async () => {
    // The assertion that matters is the *absence*. "You only finish three" is
    // a verdict about a person where "you have finished three" is a fact about
    // the days, and daily-operating-system-vision.md asks that history be
    // useful without making missed work punishing -- a planner being the
    // surface most able to break that. The week-grain signal carries the same
    // test for the same reason.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({ typical_day: 3, focus: [focusRow(), focusRow({ task_id: 2 })] }),
      ),
    );

    renderAt("/day/2026-08-03");

    await screen.findByText(/You have finished 3 on a typical day/);
    expect(screen.queryByText(/only finish/)).toBeNull();
    expect(screen.queryByText(/too many/)).toBeNull();
  });

  it("says nothing about capacity when there is too little history", async () => {
    // Null is not zero. A day that rendered "you have finished 0 on a typical
    // day" would be making a claim about a person that no evidence supports.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ typical_day: null, focus: [focusRow()] })),
    );

    renderAt("/day/2026-08-03");

    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByText(/on a typical day/)).toBeNull();
  });

  it("says nothing about capacity on a day already lived", async () => {
    // Planning is the point of it. On a past day the same sentence is a
    // verdict on a day that cannot be changed, and the page already holds
    // that only today is actionable -- shows_action_items is day == today.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          date: "2026-07-30",
          today: "2026-08-03",
          shows_action_items: false,
          typical_day: 3,
          focus: [focusRow(), focusRow({ task_id: 2 })],
        }),
      ),
    );

    renderAt("/day/2026-07-30");

    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByText(/on a typical day/)).toBeNull();
  });

  it("says nothing about capacity before anything is pinned", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ typical_day: 3, focus: [] })),
    );

    renderAt("/day/2026-08-03");

    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByText(/on a typical day/)).toBeNull();
  });

  it("shows what the week is for, on a Wednesday", async () => {
    // S9's sentence, asserted on the page rather than on the payload. The
    // API has carried `week_intention` since 8b02c1b and no component read
    // it, so "on Wednesday the day knows" was true of the response and false
    // of the thing a person looks at.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ week_intention: "Get the booking form shipped." })),
    );

    renderAt("/day/2026-08-03");

    expect(
      await screen.findByText("Get the booking form shipped."),
    ).toBeInTheDocument();
  });

  it("says nothing at all when the week has no intention", async () => {
    // Blank is a value, so this is not an error state and gets no empty
    // frame -- a heading over nothing teaches you to scroll past it.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ week_intention: "" })),
    );

    renderAt("/day/2026-08-03");

    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByText("This week")).toBeNull();
  });

  it("shows the same compass on a past day", async () => {
    // It is stored on the person, not the day, so a day written in July
    // renders whatever the compass says now.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          date: "2026-07-30",
          today: "2026-08-03",
          shows_action_items: false,
          compass_purpose: "A purpose written later",
        }),
      ),
    );

    renderAt("/day/2026-07-30");

    expect(await screen.findByText("A purpose written later")).toBeInTheDocument();
  });

  it("takes no room when no compass has been written", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData()),
    );

    renderAt("/day/2026-08-03");

    await screen.findByLabelText("Capture a thought");
    expect(screen.queryByText(/Edit your compass/)).not.toBeInTheDocument();
  });

  it("shows how far each routine has got", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ routines: [standing()] })),
    );

    renderAt("/day/2026-08-03");

    const row = (await screen.findByText("Practice Spanish")).closest("li")!;
    expect(within(row).getByText("2 of 5 lessons")).toBeInTheDocument();
  });

  it("reads a yes-or-no routine as done rather than as a count", async () => {
    // crane-plan.md §3 left this to Crane 2: a blank unit means the target
    // is a plain yes/no, and "1 of 1" is a strange way to say you moved.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          routines: [
            standing({ title: "Move today", target: 1, unit: "", progress: 0 }),
          ],
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    const row = (await screen.findByText("Move today")).closest("li")!;
    expect(within(row).getByText("Not yet")).toBeInTheDocument();
    expect(within(row).queryByText("0 of 1")).toBeNull();
  });

  it("logs a unit against the routine endpoint", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.url.includes("/log")) {
        return jsonResponse({
          today: "2026-08-03",
          standings: [standing({ progress: 3 })],
        });
      }
      return jsonResponse(dayData({ routines: [standing()] }));
    });

    renderAt("/day/2026-08-03");
    await userEvent.click(
      await screen.findByRole("button", { name: "Log one for Practice Spanish" }),
    );

    await waitFor(() =>
      expect(screen.getByText("3 of 5 lessons")).toBeInTheDocument(),
    );
    expect(
      fetchSpy.mock.calls
        .map(([input]) => (input as Request).url)
        .some((url) => url.includes("/api/v1/routines/1/log")),
    ).toBe(true);
  });

  it("offers no way to take back a routine at nothing", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ routines: [standing({ progress: 0 })] })),
    );

    renderAt("/day/2026-08-03");

    await screen.findByText("Practice Spanish");
    expect(
      screen.queryByRole("button", { name: /Undo one/ }),
    ).toBeNull();
  });

  it("skips through its own endpoint, not the log one", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.url.includes("/skip")) {
        return jsonResponse({
          today: "2026-08-03",
          standings: [standing({ outcome: "skipped" })],
        });
      }
      return jsonResponse(dayData({ routines: [standing()] }));
    });

    renderAt("/day/2026-08-03");
    await userEvent.click(await screen.findByRole("button", { name: "Skip" }));

    await waitFor(() => expect(screen.getByText("Skipped")).toBeInTheDocument());
    expect(
      fetchSpy.mock.calls
        .map(([input]) => (input as Request).url)
        .some((url) => url.includes("/api/v1/routines/1/skip")),
    ).toBe(true);
  });

  it("shows a past day's routines without any way to change them", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          date: "2026-08-01",
          today: "2026-08-03",
          shows_action_items: false,
          routines: [standing({ progress: 3 })],
          routines_are_loggable: false,
        }),
      ),
    );

    renderAt("/day/2026-08-01");

    expect(await screen.findByText("3 of 5 lessons")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Log one/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Keep a routine" })).toBeNull();
  });

  it("keeps a new routine from the day page", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") {
        return jsonResponse({ today: "2026-08-03", standings: [standing()] });
      }
      return jsonResponse(dayData());
    });

    renderAt("/day/2026-08-03");
    await userEvent.click(
      await screen.findByRole("button", { name: "Keep a routine" }),
    );
    await userEvent.type(screen.getByLabelText("Routine"), "Practice Spanish");
    await userEvent.click(screen.getByRole("button", { name: "Keep it" }));

    await waitFor(() =>
      expect(screen.getByText("Practice Spanish")).toBeInTheDocument(),
    );
    expect(
      fetchSpy.mock.calls
        .map(([input]) => (input as Request).url)
        .some((url) => url.endsWith("/api/v1/routines")),
    ).toBe(true);
  });

  it("says what a routine is when there are none", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData()),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByText(/rather than a task you finish once/)).toBeInTheDocument();
  });

  it("pauses a routine through its own endpoint", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.url.includes("/pause")) {
        return jsonResponse({
          today: "2026-08-03",
          standings: [],
          paused: [
            {
              routine_id: 1,
              title: "Practice Spanish",
              cadence: "daily",
              target: 5,
              unit: "lessons",
            },
          ],
        });
      }
      return jsonResponse(dayData({ routines: [standing()] }));
    });

    renderAt("/day/2026-08-03");
    await userEvent.click(
      await screen.findByRole("button", { name: "Pause Practice Spanish" }),
    );

    await waitFor(() => expect(screen.getByText("Paused")).toBeInTheDocument());
    expect(
      fetchSpy.mock.calls
        .map(([input]) => (input as Request).url)
        .some((url) => url.includes("/api/v1/routines/1/pause")),
    ).toBe(true);
  });

  it("calls a period enough through its own endpoint", async () => {
    // Crane 3 slice 8. Its own control because it is its own statement:
    // "I did some and that was enough" is not "I chose not to".
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.url.includes("/enough")) {
        return jsonResponse({
          today: "2026-08-03",
          standings: [standing({ outcome: "partial", progress: 3 })],
          paused: [],
        });
      }
      return jsonResponse(dayData({ routines: [standing({ progress: 3 })] }));
    });

    renderAt("/day/2026-08-03");
    await userEvent.click(
      await screen.findByRole("button", { name: "Call it enough for Practice Spanish" }),
    );

    await waitFor(() =>
      expect(screen.getByText("3 of 5 lessons — enough")).toBeInTheDocument(),
    );
    expect(
      fetchSpy.mock.calls
        .map(([input]) => (input as Request).url)
        .some((url) => url.includes("/api/v1/routines/1/enough")),
    ).toBe(true);
  });

  it("does not offer enough for a period with nothing done yet", async () => {
    // "I did some of it" needs some of it. With nothing logged the honest
    // statement is a skip, which already has its own control.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ routines: [standing({ progress: 0 })] })),
    );

    renderAt("/day/2026-08-03");
    await screen.findByText("Practice Spanish");

    expect(screen.queryByRole("button", { name: /enough/i })).toBeNull();
  });

  it("does not offer enough for a period already met", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          routines: [
            standing({ progress: 5, outcome: "completed", is_met: true }),
          ],
        }),
      ),
    );

    renderAt("/day/2026-08-03");
    await screen.findByText("Practice Spanish");

    expect(screen.queryByRole("button", { name: /enough/i })).toBeNull();
  });

  it("keeps a paused routine findable so it can be resumed", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          routines: [],
          paused_routines: [
            {
              routine_id: 1,
              title: "Practice Spanish",
              cadence: "daily",
              target: 5,
              unit: "lessons",
            },
          ],
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    expect(
      await screen.findByRole("button", { name: "Resume Practice Spanish" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/starts from today rather than filling in the gap/))
      .toBeInTheDocument();
  });

  it("resumes through the resume endpoint", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.url.includes("/resume")) {
        return jsonResponse({
          today: "2026-08-03",
          standings: [standing()],
          paused: [],
        });
      }
      return jsonResponse(
        dayData({
          routines: [],
          paused_routines: [
            {
              routine_id: 1,
              title: "Practice Spanish",
              cadence: "daily",
              target: 5,
              unit: "lessons",
            },
          ],
        }),
      );
    });

    renderAt("/day/2026-08-03");
    await userEvent.click(
      await screen.findByRole("button", { name: "Resume Practice Spanish" }),
    );

    await waitFor(() =>
      expect(screen.getByText("2 of 5 lessons")).toBeInTheDocument(),
    );
    expect(
      fetchSpy.mock.calls
        .map(([input]) => (input as Request).url)
        .some((url) => url.includes("/api/v1/routines/1/resume")),
    ).toBe(true);
  });

  it("does not offer pausing or resuming on a past day", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          date: "2026-08-01",
          today: "2026-08-03",
          routines: [standing()],
          routines_are_loggable: false,
          paused_routines: [
            {
              routine_id: 2,
              title: "Guitar practice",
              cadence: "weekly",
              target: 3,
              unit: "sessions",
            },
          ],
        }),
      ),
    );

    renderAt("/day/2026-08-01");

    await screen.findByText("2 of 5 lessons");
    expect(screen.queryByRole("button", { name: /Pause/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Resume/ })).toBeNull();
  });

  it("says how long an old task has been waiting", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({ action_items: [actionItem({ age_in_days: 12 })] }),
      ),
    );

    renderAt("/day/2026-08-03");

    const row = (await screen.findByText("Pay rent")).closest("li")!;
    expect(within(row).getByText("Added 12 days ago")).toBeInTheDocument();
  });

  it("reports the age rather than scolding about it", async () => {
    // The acceptance for this slice is a tone test: the vision document
    // asks that history be useful "without making missed work feel like
    // punishment", and a red "12 days late!" is the thing that fails it.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({ action_items: [actionItem({ age_in_days: 40 })] }),
      ),
    );

    renderAt("/day/2026-08-03");

    const label = await screen.findByText("Added 40 days ago");
    expect(label.className).toContain("text-muted-foreground");
    expect(label.className).not.toContain("destructive");
    expect(label.textContent).not.toMatch(/late|overdue|!/i);
  });

  it("stays quiet about a task that is merely a few days old", async () => {
    // A task made on Tuesday and still open on Thursday is not
    // carry-forward, it is Thursday.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ action_items: [actionItem({ age_in_days: 3 })] })),
    );

    renderAt("/day/2026-08-03");

    await screen.findByText("Pay rent");
    expect(screen.queryByText(/Added \d+ days ago/)).toBeNull();
  });

  it("shows age alongside the due label rather than instead of it", async () => {
    // They answer different questions, and a snoozed task is exactly the
    // case where only one of them says anything.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          action_items: [
            actionItem({ age_in_days: 30, due_date: "2026-08-03" }),
          ],
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    const row = (await screen.findByText("Pay rent")).closest("li")!;
    expect(within(row).getByText("Added 30 days ago")).toBeInTheDocument();
    expect(within(row).getByText("Today")).toBeInTheDocument();
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

  /* Suggestions read out of the writing -- planning-assistant-plan.md
     increment 2, slice D. The card answers five questions, and the fourth
     is the one no surface in this application has ever answered. */
  const SUGGESTION = {
    id: 7,
    text: "I still need to ask Maya about the venue.",
    reason: "reads as a commitment",
    effect: "Creates a task with no due date",
  };

  it("offers what it read as a commitment, with the sentence it read", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ suggestions: [SUGGESTION] })),
    );

    renderAt("/day/2026-08-03");

    expect(
      await screen.findByText(/still need to ask Maya about the venue/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/reads as a commitment/i)).toBeInTheDocument();
  });

  it("says what confirming will do before you confirm it", async () => {
    /* The Effect field. "Creates a task" and "creates a task due 4 June" are
       different things to agree to, and a person told neither is approving
       something they were not shown. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ suggestions: [SUGGESTION] })),
    );

    renderAt("/day/2026-08-03");

    expect(
      await screen.findByText("Creates a task with no due date"),
    ).toBeInTheDocument();
  });

  it("creates the task when you accept", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      if (request.method === "POST" && url.includes("/confirm")) {
        return jsonResponse(dayData({ suggestions: [] }));
      }
      return jsonResponse(dayData({ suggestions: [SUGGESTION] }));
    });

    renderAt("/day/2026-08-03");
    await screen.findByText(/still need to ask Maya/i);
    await user.click(screen.getByRole("button", { name: /add to tasks/i }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) => {
          const req = request as Request;
          return (
            req.method === "POST" &&
            req.url.includes("/api/v1/suggestions/7/confirm")
          );
        }),
      ).toBe(true);
    });
  });

  it("says no without creating anything", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      if (request.method === "POST" && url.includes("/dismiss")) {
        return jsonResponse(dayData({ suggestions: [] }));
      }
      return jsonResponse(dayData({ suggestions: [SUGGESTION] }));
    });

    renderAt("/day/2026-08-03");
    await screen.findByText(/still need to ask Maya/i);
    await user.click(screen.getByRole("button", { name: /not a task/i }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) => {
          const req = request as Request;
          return (
            req.method === "POST" &&
            req.url.includes("/api/v1/suggestions/7/dismiss")
          );
        }),
      ).toBe(true);
    });
  });

  it("shows nothing at all when it read nothing", async () => {
    /* No empty heading. "Nothing was read as a commitment" and "this section
       failed to load" look identical as a blank panel, and a day that always
       carries an empty box teaches you to stop seeing the box. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData()),
    );

    renderAt("/day/2026-08-03");
    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByText(/reads as a commitment/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /add to tasks/i })).toBeNull();
  });
});

describe("DayRoute, the line under the list", () => {
  // superlists-2.0-plan.md increment 2. The morning's set is protected and the
  // day can still take things in below it -- rule 4, *the line is a boundary,
  // not a wall*.

  it("says the list is still open when no line has been drawn", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ focus: [focusRow()], list_closed_at: null })),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByText(/still open/i)).toBeInTheDocument();
  });

  it("draws the line and says when the day's work began", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          focus: [focusRow()],
          list_closed_at: "2026-08-03T08:12:00+00:00",
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByRole("separator")).toBeInTheDocument();
  });

  it("shows what joined below the line, counted apart", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          focus: [
            focusRow({ task_id: 1, text: "Chosen", above_the_line: true }),
            focusRow({ task_id: 2, text: "Joined", above_the_line: false }),
          ],
          list_closed_at: "2026-08-03T08:12:00+00:00",
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByText("Chosen")).toBeInTheDocument();
    expect(screen.getByText("Joined")).toBeInTheDocument();
    // The count is what makes it "counted apart" rather than merely listed.
    expect(screen.getByText(/1 joined below the line/i)).toBeInTheDocument();
  });

  it("measures capacity against what was chosen, not what joined later", async () => {
    // The plan's *The composer*: below-the-line pins are reported, never used
    // as evidence of what a day can hold. Two pins, one of them below the
    // line, against a typical day of two is not over-committed.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          focus: [
            focusRow({ task_id: 1, text: "Chosen", above_the_line: true }),
            focusRow({ task_id: 2, text: "Joined", above_the_line: false }),
          ],
          list_closed_at: "2026-08-03T08:12:00+00:00",
          typical_day: 1,
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByText(/1 chosen for today/)).toBeInTheDocument();
    expect(
      screen.queryByText(/more than the day usually holds/),
    ).not.toBeInTheDocument();
  });
});

function logLine(overrides: Record<string, unknown> = {}) {
  return {
    at: "2026-08-03T09:15:00+00:00",
    kind: "written",
    text: "Neighbour asked about the fence",
    detail: "",
    subject_withheld: false,
    ...overrides,
  };
}

describe("DayRoute, the log", () => {
  // superlists-2.0-plan.md rule 6: the log is a read, not a table -- and rule
  // 5, a tick is a log line with a time.

  it("shows what happened, with the time it happened", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ log: [logLine()] })),
    );

    renderAt("/day/2026-08-03");

    const line = (await screen.findByText("Neighbour asked about the fence")).closest(
      "li",
    )!;
    expect(line).toHaveTextContent(/\d{1,2}:\d{2}/);
  });

  it("says which kind of thing each line was", async () => {
    // "each saying which it is" -- a tick, a note and a payment read the same
    // without it, and the log stops being a record of anything in particular.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          log: [
            logLine({ kind: "completed", text: "Fix the fence latch" }),
            logLine({ kind: "bill", text: "Car insurance", detail: "412.00 USD" }),
          ],
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    const latch = (await screen.findByText("Fix the fence latch")).closest("li")!;
    expect(latch).toHaveTextContent(/done/i);
    const bill = screen.getByText("Car insurance").closest("li")!;
    expect(bill).toHaveTextContent(/paid/i);
    expect(bill).toHaveTextContent("412.00 USD");
  });

  it("keeps a completion that was later reopened", async () => {
    // Rule 6's correction. A read from `completed_at` would show only the
    // reopen, and what actually happened must never change retroactively.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          log: [
            logLine({
              kind: "completed",
              text: "Fix the fence latch",
              at: "2026-08-03T14:02:00+00:00",
            }),
            logLine({
              kind: "reopened",
              text: "Fix the fence latch",
              at: "2026-08-03T14:05:00+00:00",
            }),
          ],
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    const lines = await screen.findAllByText("Fix the fence latch");
    expect(lines).toHaveLength(2);
    expect(lines[0].closest("li")).toHaveTextContent(/done/i);
    expect(lines[1].closest("li")).toHaveTextContent(/reopened/i);
  });

  it("keeps a line whose subject is gone rather than dropping it", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          log: [
            logLine({ kind: "completed", text: null, subject_withheld: true }),
          ],
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByText(/no longer/i)).toBeInTheDocument();
  });

  it("says nothing rather than showing an empty log", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ log: [] })),
    );

    renderAt("/day/2026-08-03");

    await screen.findByLabelText("Capture a thought");
    expect(screen.queryByRole("heading", { name: "Log" })).toBeNull();
  });
});

describe("DayRoute, the composer", () => {
  // superlists-2.0-plan.md increment 4: one box, four destinations. It is the
  // capture box grown a question, not a second box beside it -- "one composer"
  // is what the page says.

  it("offers all four destinations", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse(dayData()));

    renderAt("/day/2026-08-03");

    const box = await screen.findByLabelText(/Where this goes/i);
    expect(
      [...box.querySelectorAll("option")].map((each) => each.textContent),
    ).toEqual(["Note", "Did", "Today", "Pool"]);
  });

  it("defaults to Note, so nothing becomes a task by accident", async () => {
    // D9 is open and this is the reversible answer: Did manufactures a
    // completed task for every line, and the argument against it is written
    // down and unrebutted.
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse(dayData()));

    renderAt("/day/2026-08-03");

    expect(await screen.findByLabelText(/Where this goes/i)).toHaveValue("note");
  });

  it("sends the destination it was set to", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") {
        return jsonResponse({ public_id: "x", captured_at: "2026-08-03T09:00:00Z" }, true, 201);
      }
      return jsonResponse(dayData());
    });

    renderAt("/day/2026-08-03");
    await userEvent.type(
      await screen.findByLabelText("Capture a thought"),
      "Fix the fence latch",
    );
    await userEvent.selectOptions(screen.getByLabelText(/Where this goes/i), "did");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => {
      const posts = fetchSpy.mock.calls
        .map(([sent]) => sent as Request)
        .filter((request) => request.method === "POST");
      expect(posts).toHaveLength(1);
    });
  });

  it("says where the line went, and says something different per destination", async () => {
    // A confirmation naming the wrong place is worse than none, because
    // somebody will go and look there -- which this box has already been
    // wrong about once, when it said "Sent to your Inbox."
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") {
        return jsonResponse({ public_id: "x", captured_at: "2026-08-03T09:00:00Z" }, true, 201);
      }
      return jsonResponse(dayData());
    });

    renderAt("/day/2026-08-03");
    await userEvent.type(
      await screen.findByLabelText("Capture a thought"),
      "Ring the fencing people",
    );
    await userEvent.selectOptions(screen.getByLabelText(/Where this goes/i), "pool");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    // Not `/pool/i`, which also matches the select's own option.
    expect(await screen.findByText("In the pool.")).toBeInTheDocument();
  });

  it("keeps the thought when the line cannot be written", async () => {
    // principles.md: capture is durable before it is clever. The box empties
    // on success and never on the way there.
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") return jsonResponse({ detail: "no" }, false, 500);
      return jsonResponse(dayData());
    });

    renderAt("/day/2026-08-03");
    const box = await screen.findByLabelText("Capture a thought");
    await userEvent.type(box, "Half a thought");
    await userEvent.selectOptions(screen.getByLabelText(/Where this goes/i), "did");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => expect(screen.getByText(/still here/i)).toBeInTheDocument());
    expect(box).toHaveValue("Half a thought");
  });
});

function closing(overrides: Record<string, unknown> = {}) {
  return {
    chosen: 2,
    finished: 1,
    unfinished: 1,
    released: 0,
    joined: 0,
    joined_finished: 0,
    leftovers: [],
    ...overrides,
  };
}

function leftover(overrides: Record<string, unknown> = {}) {
  return {
    task_id: 1,
    text: "Book dentist",
    above_the_line: true,
    moved_to_tomorrow: false,
    ...overrides,
  };
}

describe("DayRoute, the evening", () => {
  // superlists-2.0-plan.md rule 7: leftovers get one decision each, never a
  // move. daily-operating-system-vision.md underneath it: never automatically
  // reschedule everything left incomplete.

  it("offers three moves on each thing left over", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ closing: closing({ leftovers: [leftover()] }) })),
    );

    renderAt("/day/2026-08-03");

    await screen.findByText("The day, read back");
    for (const name of [
      /Book dentist to tomorrow/i,
      /Book dentist back to the pool/i,
      /Let go of Book dentist/i,
    ]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
  });

  it("offers no way to decide about all of them at once", async () => {
    // The vision document's first rule is a shape, not a warning: there is no
    // sweep, so there is no button for one.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          closing: closing({
            leftovers: [leftover(), leftover({ task_id: 2, text: "Call Sam" })],
          }),
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    await screen.findByText("The day, read back");
    // Three buttons per row and no fourth for the set. `/all/i` matched the
    // per-row ones, which is what the first version of this got wrong.
    expect(
      screen.getAllByRole("button").map((each) => each.getAttribute("aria-label")),
    ).not.toContain("Move everything to tomorrow");
    expect(screen.queryByText(/all of these|move them all/i)).toBeNull();
  });

  it("sends one decision for one task", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") return jsonResponse(dayData());
      return jsonResponse(dayData({ closing: closing({ leftovers: [leftover()] }) }));
    });

    renderAt("/day/2026-08-03");
    await userEvent.click(
      await screen.findByRole("button", { name: /Book dentist to tomorrow/i }),
    );

    await waitFor(() => {
      const posts = fetchSpy.mock.calls
        .map(([sent]) => sent as Request)
        .filter((request) => request.method === "POST");
      expect(
        posts.some((r) => r.url.includes("/api/v1/day/2026-08-03/leftovers/1")),
      ).toBe(true);
    });
  });

  it("says which ones are still waiting, and stops when none are", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          closing: closing({
            leftovers: [
              leftover(),
              leftover({ task_id: 2, text: "Call Sam", moved_to_tomorrow: true }),
            ],
          }),
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByText(/1 still waiting/i)).toBeInTheDocument();
  });

  it("reports what joined below the line apart from what was chosen", async () => {
    // Rule 4, at the end of the day: three chosen and four unplanned done is a
    // good day, and this is where the page can say so.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          closing: closing({ chosen: 3, finished: 3, joined: 4, joined_finished: 4 }),
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByText(/4 of 4 below the line/i)).toBeInTheDocument();
  });

  it("draws no conclusion from any of the numbers", async () => {
    // Rule 12. The S3 precedent: a test asserts the scolding phrasing is
    // absent, not merely that the describing one is present.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ closing: closing({ chosen: 5, finished: 0 }) })),
    );

    renderAt("/day/2026-08-03");

    const heading = await screen.findByText("The day, read back");
    // Scoped to the closing block: "only" appears in prose elsewhere on the
    // page, and what rule 12 forbids is a verdict *about the numbers*.
    const block = heading.closest("section")!;
    expect(block.textContent).not.toMatch(/only|failed|behind|streak|well done/i);
  });
});

function appointment(overrides: Record<string, unknown> = {}) {
  return {
    public_id: "aaaaaaaa-0000-0000-0000-000000000001",
    text: "Call with the accountant",
    starts_on: "2026-08-03",
    ends_on: null,
    starts_at: "14:00:00",
    ends_at: null,
    location: "phone",
    notes: "",
    cancelled: false,
    ...overrides,
  };
}

describe("DayRoute, appointments", () => {
  // superlists-2.0-plan.md increment 7. Something that happens at a time
  // whether or not you act -- so it is never ticked, never picked, and never
  // in the chosen count.

  it("shows what is on today, with its time and where", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ appointments: [appointment()] })),
    );

    renderAt("/day/2026-08-03");

    const row = (await screen.findByText("Call with the accountant")).closest("li")!;
    expect(row).toHaveTextContent("phone");
    expect(row).toHaveTextContent(/2:00|14:00/);
  });

  it("says all day rather than inventing a time", async () => {
    // The Dutch Wonderland case, and the reason the record is dates plus an
    // optional time rather than a pair of instants.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          appointments: [
            appointment({
              text: "Dutch Wonderland",
              starts_at: null,
              ends_on: "2026-08-04",
              location: "Lancaster, PA",
            }),
          ],
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    const row = (await screen.findByText("Dutch Wonderland")).closest("li")!;
    expect(row).toHaveTextContent(/all day/i);
  });

  it("keeps a cancelled one on its day, struck", async () => {
    // Rule 6: a cancelled Thursday afternoon is a fact about that Thursday,
    // and a row that vanished would make it unanswerable a month later.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ appointments: [appointment({ cancelled: true })] })),
    );

    renderAt("/day/2026-08-03");

    const text = await screen.findByText("Call with the accountant");
    expect(text.className).toMatch(/line-through/);
  });

  it("never offers to tick one", async () => {
    // It happens whether or not you act, which is the whole of why it has its
    // own model rather than being a task with a date.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ appointments: [appointment()] })),
    );

    renderAt("/day/2026-08-03");

    await screen.findByText("Call with the accountant");
    expect(
      screen.queryByRole("button", { name: /Complete Call with the accountant/i }),
    ).toBeNull();
  });

  it("shows what is coming up, apart from what is on today", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          appointments: [appointment()],
          appointments_coming: [
            appointment({
              public_id: "aaaaaaaa-0000-0000-0000-000000000002",
              text: "Parents' evening",
              starts_on: "2026-08-05",
            }),
          ],
        }),
      ),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByText(/Coming up/i)).toBeInTheDocument();
    expect(screen.getByText("Parents' evening")).toBeInTheDocument();
  });

  it("writes one down", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") return jsonResponse(appointment(), true, 201);
      return jsonResponse(dayData());
    });

    renderAt("/day/2026-08-03");
    // The form is behind a button: a diary form open on every day page would
    // be six inputs competing with the day's own writing.
    await userEvent.click(
      await screen.findByRole("button", { name: "Add an appointment" }),
    );
    await userEvent.type(
      screen.getByLabelText("What is happening"),
      "Call with the accountant",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add to the day" }));

    await waitFor(() => {
      const posts = fetchSpy.mock.calls
        .map(([sent]) => sent as Request)
        .filter((request) => request.method === "POST");
      expect(posts.some((r) => r.url.includes("/api/v1/appointments"))).toBe(true);
    });
  });

  it("cancels one rather than deleting it", async () => {
    // Two buttons, because they are two facts. A surface with one would make
    // "the parents' evening was cancelled" unanswerable a month later.
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") return jsonResponse(appointment({ cancelled: true }));
      return jsonResponse(dayData({ appointments: [appointment()] }));
    });

    renderAt("/day/2026-08-03");
    await userEvent.click(
      await screen.findByRole("button", { name: /Cancel Call with the accountant/i }),
    );

    await waitFor(() => {
      const posts = fetchSpy.mock.calls
        .map(([sent]) => sent as Request)
        .filter((request) => request.method === "POST");
      expect(posts.some((r) => r.url.includes("/cancel"))).toBe(true);
    });
  });
});

