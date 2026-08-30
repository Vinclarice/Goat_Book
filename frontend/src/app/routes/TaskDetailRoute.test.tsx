import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Link, MemoryRouter, Route, Routes } from "react-router";

import { TaskDetailRoute } from "./TaskDetailRoute";
import {
  checklistStep,
  routeRequests,
  task,
  taskWrite,
} from "../../test/fixtures";

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

function taskDetailData(overrides: Record<string, unknown> = {}) {
  return {
    task: task(),
    area: { id: 1, title: "Programming" },
    checklist_steps: [],
    ...overrides,
  };
}

function renderAt(taskId: string) {
  // Mirrors main.tsx: retry off, everything else left at TanStack's defaults.
  // The default staleTime of 0 is what makes a background refetch possible at
  // all, so pinning it here would prove nothing about the real app.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/tasks/${taskId}`]}>
          <Routes>
            <Route path="/tasks/:taskId" element={<TaskDetailRoute />} />
            <Route path="/areas/:areaId" element={<p>Area page</p>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
}

describe("TaskDetailRoute", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    document.cookie = "csrftoken=test-token";
  });

  it("renders the task's fields once the query resolves", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        taskDetailData({ task: task({ text: "Write tests", tags: ["work"] }) }),
      ),
    );

    renderAt("1");

    expect(await screen.findByDisplayValue("Write tests")).toBeInTheDocument();
    expect(screen.getByDisplayValue("work")).toBeInTheDocument();
    expect(screen.getByText("← Back to Programming")).toBeInTheDocument();
  });

  it("shows an error state when the request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({ detail: "nope" }, false),
    );

    renderAt("1");

    // B2.1: a 500 is the retryable kind of failure, so the person is
    // offered a retry rather than told their work is gone.
    expect(
      await screen.findByText(/Couldn't reach Clarice/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /try again/i }),
    ).toBeInTheDocument();
  });

  it("saves a text edit", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") return jsonResponse(taskDetailData());
        if ("text" in body) {
          return taskWrite(task({ text: body.text as string }));
        }
        return taskWrite(task());
      }),
    );

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.clear(screen.getByLabelText("Task"));
    await user.type(screen.getByLabelText("Task"), "Write more tests");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Task updated.")).toBeInTheDocument();
  });

  it("records what a bill comes to", async () => {
    const user = userEvent.setup();
    let sent: unknown = null;
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") {
          if (path.includes("/api/v1/nav")) {
            return jsonResponse({ areas: [], projects: [], archived_count: 0 });
          }
          return jsonResponse(taskDetailData());
        }
        if ("bill" in body) sent = body.bill;
        return taskWrite(
          task({
            bill: { amount: "500.00", currency: "USD", payee: "County" },
          }),
        );
      }),
    );

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.click(screen.getByRole("button", { name: "This is a bill" }));

    await waitFor(() => expect(sent).not.toBeNull());
    expect(await screen.findByLabelText("Amount")).toHaveValue("500.00");
  });

  it("stops a task being a bill without touching the task", async () => {
    const user = userEvent.setup();
    let sent: unknown = "untouched";
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") {
          if (path.includes("/api/v1/nav")) {
            return jsonResponse({ areas: [], projects: [], archived_count: 0 });
          }
          return jsonResponse(
            taskDetailData({
              task: task({
                bill: { amount: "500.00", currency: "USD", payee: "County" },
              }),
            }),
          );
        }
        if ("bill" in body) sent = body.bill;
        return taskWrite(task());
      }),
    );

    renderAt("1");

    await user.click(await screen.findByRole("button", { name: "Not a bill" }));

    await waitFor(() => expect(sent).toBeNull());
  });

  it("marks a task as pressing", async () => {
    const user = userEvent.setup();
    let sent: unknown = null;
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") {
          if (path.includes("/api/v1/nav")) {
            return jsonResponse({ areas: [], projects: [], archived_count: 0 });
          }
          return jsonResponse(taskDetailData());
        }
        if ("priority" in body) sent = body.priority;
        return taskWrite(task({ priority: "high" }));
      }),
    );

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.selectOptions(await screen.findByLabelText("Priority"), "high");

    await waitFor(() => expect(sent).toBe("high"));
    expect(await screen.findByText("Priority updated.")).toBeInTheDocument();
  });

  it("offers no middle value, because an unmarked task already is one", async () => {
    // The design decision, held by a test rather than only by a docstring:
    // offering "medium" beside "no priority" invites the distinction every
    // to-do app collapses into, where everything is medium.
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (
          path.includes("/api/v1/nav")
        ) {
          return jsonResponse({ areas: [], projects: [], archived_count: 0 });
        }
        return jsonResponse(taskDetailData());
      }),
    );

    renderAt("1");

    const select = await screen.findByLabelText("Priority");
    expect(
      Array.from(select.querySelectorAll("option")).map((o) => o.textContent),
    ).toEqual(["No priority", "Pressing", "Whenever"]);
  });

  it("moves a task into another of your areas", async () => {
    const user = userEvent.setup();
    let moved: unknown = null;
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") {
          // Two apiV1 GETs on this page now: the task, and the nav that says
          // which areas exist to move it into.
          if (path.includes("/api/v1/nav")) {
            return jsonResponse({
              areas: [
                {
                  id: 1,
                  title: "Programming",
                  open_count: 0,
                  overdue_count: 0,
                  color_key: "slate",
                },
                {
                  id: 2,
                  title: "Home",
                  open_count: 0,
                  overdue_count: 0,
                  color_key: "slate",
                },
              ],
              projects: [],
              archived_count: 0,
            });
          }
          return jsonResponse(taskDetailData());
        }
        // `area_id` on the wire since coherence-audit-2026-08-30.md F5 --
        // the old endpoint sent the ORM's column name, `list`.
        if ("area_id" in body) moved = body.area_id;
        return taskWrite(task());
      }),
    );

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.selectOptions(await screen.findByLabelText("Area"), "2");

    await waitFor(() => expect(moved).toBe(2));
  });

  it("saves notes on blur and reports it", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") return jsonResponse(taskDetailData());
        if ("notes" in body) {
          return taskWrite(task({ notes: (body.notes as string).trim() }));
        }
        return taskWrite(task());
      }),
    );

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.type(screen.getByLabelText("Notes"), "Bring the receipt");
    await user.tab();

    expect(await screen.findByText("Notes saved.")).toBeInTheDocument();
  });

  it("says notes were cleared when the textarea is emptied", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") {
          return jsonResponse(
            taskDetailData({ task: task({ notes: "Old note" }) }),
          );
        }
        if ("notes" in body) {
          return taskWrite(task({ notes: (body.notes as string).trim() }));
        }
        return taskWrite(task());
      }),
    );

    renderAt("1");
    await screen.findByDisplayValue("Old note");

    await user.clear(screen.getByLabelText("Notes"));
    await user.tab();

    expect(await screen.findByText("Notes cleared.")).toBeInTheDocument();
  });

  it("doesn't send a request when the notes haven't actually changed", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() =>
        jsonResponse(
          taskDetailData({ task: task({ notes: "Bring the receipt" }) }),
        ),
      );

    renderAt("1");
    await screen.findByDisplayValue("Bring the receipt");
    const callsAfterLoad = fetchSpy.mock.calls.length;

    // Trailing whitespace only -- the server trims, so this is a no-op edit.
    await user.type(screen.getByLabelText("Notes"), "   ");
    await user.tab();

    expect(fetchSpy.mock.calls.length).toBe(callsAfterLoad);
  });

  it("lists checklist steps with their done count", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        taskDetailData({
          checklist_steps: [
            checklistStep({ id: 2, text: "Book flights", is_done: true }),
            checklistStep({ id: 3, text: "Book hotel" }),
          ],
        }),
      ),
    );

    renderAt("1");

    expect(await screen.findByText("Book flights")).toBeInTheDocument();
    expect(screen.getByText("1/2")).toBeInTheDocument();
  });

  it("adds a checklist step under the current task", async () => {
    const user = userEvent.setup();
    let posted: Record<string, unknown> | null = null;
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") return jsonResponse(taskDetailData());
        if (method === "POST") {
          posted = body;
          return jsonResponse(checklistStep({ id: 5, text: "Book flights" }));
        }
        return taskWrite(task());
      }),
    );

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.type(
      screen.getByLabelText("New checklist step"),
      "Book flights",
    );
    await user.click(screen.getByRole("button", { name: "Add" }));

    expect(
      await screen.findByText("Checklist step added."),
    ).toBeInTheDocument();
    expect(posted).toEqual({
      text: "Book flights",
      carries_forward: true,
    });
  });

  it("keeps the carries-forward controls off a task that doesn't repeat", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        taskDetailData({
          checklist_steps: [checklistStep({ id: 2, text: "Book hotel" })],
        }),
      ),
    );

    renderAt("1");
    await screen.findByText("Book hotel");

    // Nothing to repeat with, so the question isn't worth asking.
    expect(
      screen.queryByLabelText("Carry Book hotel forward next time"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Bring this back on the next occurrence"),
    ).not.toBeInTheDocument();
  });

  it("adds a checklist step opted out of the next occurrence", async () => {
    const user = userEvent.setup();
    let posted: Record<string, unknown> | null = null;
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") {
          return jsonResponse(
            taskDetailData({ task: task({ recurrence: "weekly" }) }),
          );
        }
        if (method === "POST") {
          posted = body;
          return jsonResponse(
            checklistStep({
              id: 5,
              text: "Renew passport",
              carries_forward: false,
            }),
          );
        }
        return taskWrite(task());
      }),
    );

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.type(
      screen.getByLabelText("New checklist step"),
      "Renew passport",
    );
    await user.click(
      screen.getByLabelText("Bring this back on the next occurrence"),
    );
    await user.click(screen.getByRole("button", { name: "Add" }));

    expect(
      await screen.findByText("Checklist step added."),
    ).toBeInTheDocument();
    expect(posted).toEqual({
      text: "Renew passport",
      carries_forward: false,
    });
  });

  it("tells the two questions on a step row apart by control type", async () => {
    /* The last clause of C2's original complaint that was still true.
     * ui-second-pass-plan.md F1: release-d-plan.md 4 predicted this would be
     * mechanical once is_done was the row's only boolean, and it was not --
     * carries_forward stayed on the row as a second <input type="checkbox">
     * beside the completion one, which is the shape C2 objected to. A switch
     * reads as a persistent setting; a checkbox reads as "tick when done".
     */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        taskDetailData({
          task: task({ recurrence: "weekly" }),
          checklist_steps: [checklistStep({ id: 2, text: "Book hotel" })],
        }),
      ),
    );

    renderAt("1");
    await screen.findByText("Book hotel");

    const row = screen.getByRole("listitem");
    expect(within(row).getAllByRole("checkbox")).toHaveLength(1);
    expect(within(row).getByRole("switch")).toBeInTheDocument();
  });

  it("toggles whether an existing checklist step comes back", async () => {
    const user = userEvent.setup();
    let patched: Record<string, unknown> | null = null;
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") {
          return jsonResponse(
            taskDetailData({
              task: task({ recurrence: "weekly" }),
              checklist_steps: [checklistStep({ id: 2, text: "Book hotel" })],
            }),
          );
        }
        patched = body;
        return jsonResponse(
          checklistStep({ id: 2, text: "Book hotel", carries_forward: false }),
        );
      }),
    );

    renderAt("1");
    const toggle = await screen.findByLabelText(
      "Carry Book hotel forward next time",
    );
    expect(toggle).toBeChecked();

    await user.click(toggle);

    expect(patched).toEqual({ carries_forward: false });
    await waitFor(() =>
      expect(
        screen.getByLabelText("Carry Book hotel forward next time"),
      ).not.toBeChecked(),
    );
  });

  it("promotes a checklist step to a task of its own", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") {
          return jsonResponse(
            taskDetailData({
              checklist_steps: [checklistStep({ id: 2, text: "Book hotel" })],
            }),
          );
        }
        if (method === "POST") {
          return taskWrite(task({ id: 9, text: "Book hotel" }));
        }
        return taskWrite(task());
      }),
    );

    renderAt("1");
    await screen.findByText("Book hotel");

    await user.click(screen.getByLabelText("Promote Book hotel"));

    expect(
      await screen.findByText('"Book hotel" is now a task of its own.'),
    ).toBeInTheDocument();
    expect(screen.queryByText("Book hotel")).not.toBeInTheDocument();
  });

  it("removes a checklist step", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") {
          return jsonResponse(
            taskDetailData({
              checklist_steps: [checklistStep({ id: 2, text: "Book hotel" })],
            }),
          );
        }
        if (method === "DELETE") {
          return jsonResponse({ deleted: 2 });
        }
        return taskWrite(task());
      }),
    );

    renderAt("1");
    await screen.findByText("Book hotel");

    await user.click(screen.getByLabelText("Remove Book hotel"));

    await waitFor(() =>
      expect(screen.queryByText("Book hotel")).not.toBeInTheDocument(),
    );
  });

  it("surfaces a conflict error from a duplicate rename", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") return jsonResponse(taskDetailData());
        if ("text" in body) {
          // Ninja's shape now, not the hand-rolled field-keyed one.
          return jsonResponse(
            { detail: "That task already exists in this list." },
            false,
            409,
          );
        }
        return taskWrite(task());
      }),
    );

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText("That task already exists in this list."),
    ).toBeInTheDocument();
  });

  it("updates the due date immediately on change", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") return jsonResponse(taskDetailData());
        if ("due_date" in body) {
          return taskWrite(task({ due_date: body.due_date as string | null }));
        }
        return taskWrite(task());
      }),
    );

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    fireEvent.change(screen.getByLabelText("Due date"), {
      target: { value: "2026-08-01" },
    });

    expect(await screen.findByText("Due date updated.")).toBeInTheDocument();
  });

  it("commits a tags change on blur", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") return jsonResponse(taskDetailData());
        if ("tags" in body) {
          return taskWrite(task({ tags: body.tags as string[] }));
        }
        return taskWrite(task());
      }),
    );

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    const tagsInput = screen.getByLabelText("Tags");
    await user.clear(tagsInput);
    await user.type(tagsInput, "urgent, work");
    await user.tab();

    expect(await screen.findByText("Tags updated.")).toBeInTheDocument();
  });

  it("moves the task to archive and navigates back to its list", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") return jsonResponse(taskDetailData());
        if (body.status === "archived") {
          return taskWrite(task({ status: "archived" }));
        }
        return taskWrite(task());
      }),
    );

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.click(screen.getByRole("button", { name: "Move to archive" }));

    await waitFor(() => {
      expect(screen.getByText("Area page")).toBeInTheDocument();
    });
  });

  it("navigates away when completing a recurring task auto-archives it", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") {
          return jsonResponse(
            taskDetailData({ task: task({ recurrence: "daily" }) }),
          );
        }
        if (body.status === "completed") {
          return taskWrite(task({ status: "archived", recurrence: "daily" }), {
            spawned: task({ id: 2, recurrence: "daily" }),
          });
        }
        return taskWrite(task());
      }),
    );

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.click(screen.getByRole("button", { name: "Mark complete" }));

    await waitFor(() => {
      expect(screen.getByText("Area page")).toBeInTheDocument();
    });
  });

  it("seeds the second task when navigating straight from one to another", async () => {
    // The guard above is keyed on the task id, not a bare boolean, and this
    // is what needs it: React Router reuses the mounted component when only
    // the :taskId param changes, so a boolean would leave the first task's
    // text sitting in the form over the second task's data.
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        const url = path;
        if (url.includes("/api/v1/tasks/2")) {
          return jsonResponse(
            taskDetailData({ task: task({ id: 2, text: "Renew passport" }) }),
          );
        }
        return jsonResponse(taskDetailData());
      }),
    );

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/tasks/1"]}>
          {/* Outside Routes, so following it swaps the param without
              unmounting the route -- which is the case under test. */}
          <Link to="/tasks/2">Open the next task</Link>
          <Routes>
            <Route path="/tasks/:taskId" element={<TaskDetailRoute />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await screen.findByDisplayValue("Write tests");

    await user.click(screen.getByRole("link", { name: "Open the next task" }));

    expect(
      await screen.findByDisplayValue("Renew passport"),
    ).toBeInTheDocument();
  });

  it("tells the side nav its counts have moved", async () => {
    // Completing from the detail page moves the same counts completing from
    // the workspace does, and this route invalidated nothing either.
    const user = userEvent.setup();
    // The detail read goes through openapi-fetch (a Request object); the
    // status write goes through the legacy api layer, which calls
    // fetch(url, init) with a string. Splitting on that is the idiom the
    // recurring-task test above already uses.
    const nav = { areas: [], projects: [], archived_count: 0 };
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method === "GET") {
          if (path.includes("/api/v1/nav"))
            return jsonResponse(nav);
          return jsonResponse(taskDetailData());
        }
        return taskWrite(task({ status: "completed" }));
      }),
    );
    const navRequests = () =>
      fetchSpy.mock.calls.filter(([sent]) =>
        (sent as Request).url.includes("/api/v1/nav"),
      ).length;

    renderAt("1");
    await screen.findByDisplayValue("Write tests");
    const before = navRequests();

    await user.click(screen.getByRole("button", { name: "Mark complete" }));

    // Asserts the refetch rather than the `isInvalidated` flag. Since this
    // route gained a nav observer (the Area control needs to know which areas
    // exist), invalidating refetches immediately and the flag clears again --
    // so it was reading a state that is now transient. The effect is the
    // stronger claim anyway: the nav was actually asked again.
    await waitFor(() => expect(navRequests()).toBeGreaterThan(before));
  });

  it("keeps unsaved notes when the query refetches underneath them", async () => {
    // The reported bug, and the third time this project has fixed it:
    // PreferencesRoute and DayRoute already carry the same guard. Seeding
    // form state from inside the queryFn means the setters re-run on every
    // refetch, and refetchOnWindowFocus is on -- so alt-tabbing away from a
    // half-written note and back replaced every character with the server's
    // value. No message, no undo, and the save that followed would then
    // report success having written the old value back.
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(taskDetailData()),
    );

    const { queryClient } = renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.type(screen.getByLabelText("Notes"), "Bring the receipt");
    // Wrapped in act so the refetch's state update is flushed before the
    // assertion. Without it the update is still pending, the DOM still shows
    // the edit, and the test passes over a value that is already lost.
    await act(async () => {
      await queryClient.refetchQueries({ queryKey: ["task", 1] });
    });

    expect(screen.getByLabelText("Notes")).toHaveValue("Bring the receipt");
  });

  it("keeps an unsaved task title and tags across a refetch", async () => {
    // Same guard, the other two editable fields on this page. Tags matter
    // separately: the draft is a comma-joined string, so a reseed does not
    // merely revert it, it discards a tag that was mid-word.
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(taskDetailData({ task: task({ tags: ["work"] }) })),
    );

    const { queryClient } = renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.clear(screen.getByLabelText("Task"));
    await user.type(screen.getByLabelText("Task"), "Write more tests");
    await user.type(screen.getByLabelText("Tags"), ", urgent");

    await act(async () => {
      await queryClient.refetchQueries({ queryKey: ["task", 1] });
    });

    expect(screen.getByLabelText("Task")).toHaveValue("Write more tests");
    expect(screen.getByLabelText("Tags")).toHaveValue("work, urgent");
  });

  it("has no per-task project control", async () => {
    // project-workspace-plan.md 2 dropped the task-level override -- a
    // task's project now comes from its Area, changed on the Area's own
    // page, not repeated here.
    vi.spyOn(globalThis, "fetch").mockImplementation(
      routeRequests(({ path, method, body }) => {
        if (method !== "GET") return taskWrite(task());
        return jsonResponse(taskDetailData());
      }),
    );

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    expect(screen.queryByLabelText("Project")).toBeNull();
  });
});
