import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { TaskDetailRoute } from "./TaskDetailRoute";
import { checklistStep, task } from "../../test/fixtures";

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
    create_checklist_step_url: "/api/tasks/1/checklist-steps/",
    ...overrides,
  };
}

function renderAt(taskId: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/tasks/${taskId}`]}>
        <Routes>
          <Route path="/tasks/:taskId" element={<TaskDetailRoute />} />
          <Route path="/areas/:areaId" element={<p>Area page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TaskDetailRoute", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    document.cookie = "csrftoken=test-token";
  });

  it("renders the task's fields once the query resolves", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(taskDetailData({ task: task({ text: "Write tests", tags: ["work"] }) })),
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
    expect(await screen.findByText(/Couldn't reach Clarice/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("saves a text edit", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (typeof input !== "string") return jsonResponse(taskDetailData());
      const body = JSON.parse((init?.body as string) ?? "{}");
      if ("text" in body) {
        return jsonResponse({ data: task({ text: body.text }) });
      }
      return jsonResponse({ data: task() });
    });

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.clear(screen.getByLabelText("Task"));
    await user.type(screen.getByLabelText("Task"), "Write more tests");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Task updated.")).toBeInTheDocument();
  });

  it("saves notes on blur and reports it", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (typeof input !== "string") return jsonResponse(taskDetailData());
      const body = JSON.parse((init?.body as string) ?? "{}");
      if ("notes" in body) {
        return jsonResponse({ data: task({ notes: body.notes.trim() }) });
      }
      return jsonResponse({ data: task() });
    });

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.type(screen.getByLabelText("Notes"), "Bring the receipt");
    await user.tab();

    expect(await screen.findByText("Notes saved.")).toBeInTheDocument();
  });

  it("says notes were cleared when the textarea is emptied", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (typeof input !== "string") {
        return jsonResponse(taskDetailData({ task: task({ notes: "Old note" }) }));
      }
      const body = JSON.parse((init?.body as string) ?? "{}");
      if ("notes" in body) {
        return jsonResponse({ data: task({ notes: body.notes.trim() }) });
      }
      return jsonResponse({ data: task() });
    });

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
        jsonResponse(taskDetailData({ task: task({ notes: "Bring the receipt" }) })),
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
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (typeof input !== "string") return jsonResponse(taskDetailData());
      if (init?.method === "POST") {
        posted = JSON.parse((init?.body as string) ?? "{}");
        return jsonResponse({ data: checklistStep({ id: 5, text: "Book flights" }) });
      }
      return jsonResponse({ data: task() });
    });

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.type(screen.getByLabelText("New checklist step"), "Book flights");
    await user.click(screen.getByRole("button", { name: "Add" }));

    expect(await screen.findByText("Checklist step added.")).toBeInTheDocument();
    expect(posted).toEqual({
      text: "Book flights",
      carries_forward: true,
    });
  });

  it("keeps the carries-forward controls off a task that doesn't repeat", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        taskDetailData({ checklist_steps: [checklistStep({ id: 2, text: "Book hotel" })] }),
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
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (typeof input !== "string") {
        return jsonResponse(taskDetailData({ task: task({ recurrence: "weekly" }) }));
      }
      if (init?.method === "POST") {
        posted = JSON.parse((init?.body as string) ?? "{}");
        return jsonResponse({
          data: checklistStep({ id: 5, text: "Renew passport", carries_forward: false }),
        });
      }
      return jsonResponse({ data: task() });
    });

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.type(screen.getByLabelText("New checklist step"), "Renew passport");
    await user.click(
      screen.getByLabelText("Bring this back on the next occurrence"),
    );
    await user.click(screen.getByRole("button", { name: "Add" }));

    expect(await screen.findByText("Checklist step added.")).toBeInTheDocument();
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
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (typeof input !== "string") {
        return jsonResponse(
          taskDetailData({
            task: task({ recurrence: "weekly" }),
            checklist_steps: [checklistStep({ id: 2, text: "Book hotel" })],
          }),
        );
      }
      patched = JSON.parse((init?.body as string) ?? "{}");
      return jsonResponse({
        data: checklistStep({ id: 2, text: "Book hotel", carries_forward: false }),
      });
    });

    renderAt("1");
    const toggle = await screen.findByLabelText("Carry Book hotel forward next time");
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
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (typeof input !== "string") {
        return jsonResponse(
          taskDetailData({
            checklist_steps: [checklistStep({ id: 2, text: "Book hotel" })],
          }),
        );
      }
      if (init?.method === "POST") {
        return jsonResponse({ data: task({ id: 9, text: "Book hotel" }) });
      }
      return jsonResponse({ data: task() });
    });

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
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (typeof input !== "string") {
        return jsonResponse(
          taskDetailData({
            checklist_steps: [checklistStep({ id: 2, text: "Book hotel" })],
          }),
        );
      }
      if (init?.method === "DELETE") {
        return jsonResponse({ data: { deleted: 2 } });
      }
      return jsonResponse({ data: task() });
    });

    renderAt("1");
    await screen.findByText("Book hotel");

    await user.click(screen.getByLabelText("Remove Book hotel"));

    await waitFor(() =>
      expect(screen.queryByText("Book hotel")).not.toBeInTheDocument(),
    );
  });

  it("surfaces a conflict error from a duplicate rename", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (typeof input !== "string") return jsonResponse(taskDetailData());
      const body = JSON.parse((init?.body as string) ?? "{}");
      if ("text" in body) {
        return jsonResponse(
          { errors: { conflict: ["That task already exists in this list."] } },
          false,
          409,
        );
      }
      return jsonResponse({ data: task() });
    });

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText("That task already exists in this list."),
    ).toBeInTheDocument();
  });

  it("updates the due date immediately on change", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (typeof input !== "string") return jsonResponse(taskDetailData());
      const body = JSON.parse((init?.body as string) ?? "{}");
      if ("due_date" in body) {
        return jsonResponse({ data: task({ due_date: body.due_date }) });
      }
      return jsonResponse({ data: task() });
    });

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    fireEvent.change(screen.getByLabelText("Due date"), {
      target: { value: "2026-08-01" },
    });

    expect(await screen.findByText("Due date updated.")).toBeInTheDocument();
  });

  it("commits a tags change on blur", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (typeof input !== "string") return jsonResponse(taskDetailData());
      const body = JSON.parse((init?.body as string) ?? "{}");
      if ("tags" in body) {
        return jsonResponse({ data: task({ tags: body.tags }) });
      }
      return jsonResponse({ data: task() });
    });

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
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (typeof input !== "string") return jsonResponse(taskDetailData());
      const body = JSON.parse((init?.body as string) ?? "{}");
      if (body.status === "archived") {
        return jsonResponse({ data: task({ status: "archived" }) });
      }
      return jsonResponse({ data: task() });
    });

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.click(screen.getByRole("button", { name: "Move to archive" }));

    await waitFor(() => {
      expect(screen.getByText("Area page")).toBeInTheDocument();
    });
  });

  it("navigates away when completing a recurring task auto-archives it", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (typeof input !== "string") {
        return jsonResponse(taskDetailData({ task: task({ recurrence: "daily" }) }));
      }
      const body = JSON.parse((init?.body as string) ?? "{}");
      if (body.status === "completed") {
        return jsonResponse({
          data: task({ status: "archived", recurrence: "daily" }),
          spawned: task({ id: 2, recurrence: "daily" }),
        });
      }
      return jsonResponse({ data: task() });
    });

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.click(screen.getByRole("button", { name: "Mark complete" }));

    await waitFor(() => {
      expect(screen.getByText("Area page")).toBeInTheDocument();
    });
  });

  describe("its project", () => {
    /* Assignment lives here rather than on the Area page's project panel,
       for the same reason due date, tags, recurrence and notes do: it is a
       single-field edit of a task, and the task's own page is where those
       already are. */
    function withProjects(projects: object[]) {
      return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
        if (typeof input === "string") return jsonResponse({ data: task() });
        if ((input as Request).url.includes("/api/v1/projects")) {
          return jsonResponse(projects);
        }
        return jsonResponse(taskDetailData());
      });
    }

    const websiteRelaunch = {
      id: 4,
      title: "Website Relaunch",
      area_id: 1,
      due_date: null,
      is_completed: false,
      completed_at: null,
      created_at: "2026-08-03T09:00:00-04:00",
      open_task_count: 0,
    };

    it("offers the projects in this task's own area", async () => {
      withProjects([websiteRelaunch]);

      renderAt("1");

      const select = await screen.findByLabelText("Project");
      expect(
        within(select).getByRole("option", { name: "Website Relaunch" }),
      ).toBeInTheDocument();
      // Always available, because taking a task out of a project has to be
      // as reachable as putting it in.
      expect(
        within(select).getByRole("option", { name: "No project" }),
      ).toBeInTheDocument();
    });

    it("asks only for projects in the area the task belongs to", async () => {
      const fetchMock = withProjects([websiteRelaunch]);

      renderAt("1");
      await screen.findByLabelText("Project");

      const asked = fetchMock.mock.calls
        .map(([input]) => (input as Request).url ?? String(input))
        .filter((url) => url.includes("/api/v1/projects"));
      expect(asked[0]).toContain("area_id=1");
    });

    it("puts the task into the project that was chosen", async () => {
      const user = userEvent.setup();
      let patchedBody: unknown;
      vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
        // api.ts calls fetch(url, init) with a string; openapi-fetch calls
        // fetch(request). The task PATCH goes through the first, the project
        // list through the second, so this has to read both.
        if (typeof input === "string") {
          if ((init as RequestInit)?.method === "PATCH") {
            patchedBody = JSON.parse(String((init as RequestInit).body));
            return jsonResponse({ data: task({ project_id: 4 }) });
          }
          return jsonResponse({ data: task() });
        }
        if ((input as Request).url.includes("/api/v1/projects")) {
          return jsonResponse([websiteRelaunch]);
        }
        return jsonResponse(taskDetailData());
      });

      renderAt("1");
      const select = await screen.findByLabelText("Project");

      await user.selectOptions(select, "4");

      await waitFor(() => expect(patchedBody).toBeDefined());
      expect(patchedBody).toEqual({ project_id: 4 });
    });

    it("takes the task back out again", async () => {
      const user = userEvent.setup();
      let patchedBody: unknown;
      vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
        if (typeof input === "string") {
          if ((init as RequestInit)?.method === "PATCH") {
            patchedBody = JSON.parse(String((init as RequestInit).body));
            return jsonResponse({ data: task({ project_id: null }) });
          }
          return jsonResponse({ data: task() });
        }
        if ((input as Request).url.includes("/api/v1/projects")) {
          return jsonResponse([websiteRelaunch]);
        }
        return jsonResponse(taskDetailData({ task: task({ project_id: 4 }) }));
      });

      renderAt("1");
      const select = await screen.findByLabelText("Project");

      await user.selectOptions(select, "");

      await waitFor(() => expect(patchedBody).toBeDefined());
      expect(patchedBody).toEqual({ project_id: null });
    });

    it("says nothing about projects when the area has none", async () => {
      withProjects([]);

      renderAt("1");
      await screen.findByDisplayValue("Write tests");

      expect(screen.queryByLabelText("Project")).toBeNull();
    });
  });
});
