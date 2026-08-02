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
    focus: [],
    compass_purpose: "",
    compass_question: "",
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
    parent: null,
    selected_at: "2026-08-03T09:00:00",
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
