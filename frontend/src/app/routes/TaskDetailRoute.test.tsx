import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { TaskDetailRoute } from "./TaskDetailRoute";
import { task } from "../../test/fixtures";

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
    list: { id: 1, title: "Programming" },
    subtasks: [],
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
          <Route path="/lists/:listId" element={<p>List page</p>} />
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

    expect(await screen.findByText("Something went wrong.")).toBeInTheDocument();
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

  it("lists subtasks with their done count", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        taskDetailData({
          subtasks: [
            task({ id: 2, text: "Book flights", status: "completed" }),
            task({ id: 3, text: "Book hotel" }),
          ],
        }),
      ),
    );

    renderAt("1");

    expect(await screen.findByText("Book flights")).toBeInTheDocument();
    expect(screen.getByText("1/2")).toBeInTheDocument();
  });

  it("adds a subtask under the current task", async () => {
    const user = userEvent.setup();
    let posted: Record<string, unknown> | null = null;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (typeof input !== "string") return jsonResponse(taskDetailData());
      if (init?.method === "POST") {
        posted = JSON.parse((init?.body as string) ?? "{}");
        return jsonResponse({ data: task({ id: 5, text: "Book flights" }) });
      }
      return jsonResponse({ data: task() });
    });

    renderAt("1");
    await screen.findByDisplayValue("Write tests");

    await user.type(screen.getByLabelText("New subtask"), "Book flights");
    await user.click(screen.getByRole("button", { name: "Add" }));

    expect(await screen.findByText("Subtask added.")).toBeInTheDocument();
    // The parent id has to travel with it, or it lands as a root task.
    expect(posted).toEqual({ text: "Book flights", parent: 1 });
  });

  it("shows a subtask its parent and offers to promote it", async () => {
    const user = userEvent.setup();
    let patched: Record<string, unknown> | null = null;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (typeof input !== "string") {
        return jsonResponse(
          taskDetailData({
            task: task({ parent: { id: 9, text: "Plan Japan trip" } }),
          }),
        );
      }
      patched = JSON.parse((init?.body as string) ?? "{}");
      return jsonResponse({ data: task({ parent: null }) });
    });

    renderAt("1");
    await screen.findByText("Plan Japan trip");

    await user.click(screen.getByRole("button", { name: "Promote" }));

    expect(
      await screen.findByText("Promoted to a task of its own."),
    ).toBeInTheDocument();
    expect(patched).toEqual({ parent: null });
  });

  it("doesn't offer a subtask section on a task that is itself a subtask", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        taskDetailData({
          task: task({ parent: { id: 9, text: "Plan Japan trip" } }),
        }),
      ),
    );

    renderAt("1");
    await screen.findByText("Plan Japan trip");

    // One level only -- a subtask has nowhere to put children.
    expect(screen.queryByLabelText("New subtask")).not.toBeInTheDocument();
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
      expect(screen.getByText("List page")).toBeInTheDocument();
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
      expect(screen.getByText("List page")).toBeInTheDocument();
    });
  });
});
