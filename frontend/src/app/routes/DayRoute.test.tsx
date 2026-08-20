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
    suggestions: [],
    action_items: [],
    // An area by default, because every other test here is about an account
    // that has started. A task belongs to a List and list_summaries filters
    // nothing, so "action items but no areas" -- what this fixture used to
    // say -- is a state the database cannot produce. The empty-areas case is
    // now its own thing: see the first-run tests.
    areas: [dayArea()],
    projects: [],
    new_area_url: "/areas/new",
    shows_action_items: true,
    focus: [],
    draft: { typical: null, proposed: [], available: 0 },
    closing: null,
    compass_purpose: "",
    compass_question: "",
    week_intention: "",
    typical_day: null,
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
    await userEvent.click(screen.getByRole("button", { name: "Capture" }));

    await waitFor(() => expect(screen.getByText("Kept.")).toBeInTheDocument());
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
    // make. new_list takes the task and the area together, so the one form
    // leaves somebody with something they actually wrote down.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ areas: [] })),
    );

    renderAt("/day/2026-08-03");

    const field = await screen.findByLabelText(/first thing on your plate/i);
    expect(field).toBeRequired();
    expect(field.closest("form")).toHaveAttribute("action", "/areas/new");
    expect(screen.getByLabelText(/area it belongs to/i)).not.toBeRequired();
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

  it("asks him to close the day, with what the day held", async () => {
    // S5's missing half. The record and the morning's choice were already
    // good; nothing ever asked for the first.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        dayData({
          closing: { chosen: 3, finished: 2, unfinished: 1, released: 1 },
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

    await screen.findByLabelText("Happenings");
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
        if (method === "PATCH" && url.includes("/api/items/1/")) {
          return jsonResponse({ data: { ...focusRow(), status: "completed" } });
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
      expect(patched?.url).toContain("/api/items/1/");
    });
  });

  it("moves a pinned task to tomorrow without leaving the day", async () => {
    // S2's second verb: "moves one task to tomorrow", in bed, on a phone.
    // The date comes from `snoozePresets`, the client-side authority the
    // Agenda already uses, rather than an inline today+1 -- that would be a
    // third copy of a rule already mirrored twice.
    //
    // Not carry-forward. daily-operating-system-vision.md forbids rewriting
    // due dates *automatically*; "one item, one decision" is exactly this.
    const called = (input: unknown, init?: RequestInit) =>
      typeof input === "string"
        ? { url: input, method: init?.method, body: init?.body }
        : {
            url: (input as Request).url,
            method: (input as Request).method,
            body: undefined,
          };

    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input, init) => {
        const { url, method } = called(input, init);
        if (method === "PATCH" && url.includes("/api/items/1/")) {
          return jsonResponse({ data: focusRow({ due_date: "2026-08-04" }) });
        }
        return jsonResponse(dayData({ focus: [focusRow()] }));
      });

    renderAt("/day/2026-08-03");
    await userEvent.click(
      await screen.findByRole("button", { name: "Move Pay rent to tomorrow" }),
    );

    await waitFor(() => {
      const patched = fetchSpy.mock.calls
        .map(([input, init]) => called(input, init))
        .find((call) => call.method === "PATCH");
      expect(patched?.url).toContain("/api/items/1/");
      expect(JSON.parse(String(patched?.body))).toEqual({
        due_date: "2026-08-04",
      });
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

  it("does not lose a half-written day when something is pinned", async () => {
    // Pinning returns the whole day, which lands in the cache. If that
    // reseeded the form it would silently discard whatever was being typed.
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") {
        return jsonResponse(
          dayData({ action_items: [actionItem()], focus: [focusRow()] }),
        );
      }
      return jsonResponse(dayData({ action_items: [actionItem()] }));
    });

    renderAt("/day/2026-08-03");
    const intentions = await screen.findByLabelText("Intentions");
    await userEvent.type(intentions, "Half a thought");
    await userEvent.click(screen.getByRole("button", { name: "Pin to today" }));

    await waitFor(() =>
      expect(screen.queryByText(/Nothing pinned yet/)).not.toBeInTheDocument(),
    );
    expect(intentions).toHaveValue("Half a thought");
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

    await screen.findByLabelText("Intentions");
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
