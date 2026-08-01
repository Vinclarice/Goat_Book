import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TaskWorkspace } from "./TaskWorkspace";
import { task } from "./test/fixtures";
import type { Task } from "./types";

function jsonResponse(data: object, ok = true) {
  return Promise.resolve({
    ok,
    status: ok ? 200 : 400,
    json: () => Promise.resolve(data),
  } as Response);
}

describe("TaskWorkspace", () => {
  beforeEach(() => {
    document.cookie = "csrftoken=test-token";
    vi.restoreAllMocks();
  });

  it("filters tasks and displays live counts", async () => {
    const user = userEvent.setup();
    render(
      <TaskWorkspace
        initialData={{
          list: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/lists/1/items/",
            reorder_url: "/api/lists/1/items/reorder/",
          },
          items: [
            task(),
            task({ id: 2, text: "Finished", status: "completed" }),
          ],
        }}
      />,
    );

    expect(screen.getByRole("button", { name: /Open 1/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Completed 1/ }));

    expect(screen.getByText("Finished")).toBeInTheDocument();
    expect(screen.queryByText("Write tests")).not.toBeInTheDocument();
  });

  it("searches task text without changing the live counts", async () => {
    const user = userEvent.setup();
    render(
      <TaskWorkspace
        initialData={{
          list: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/lists/1/items/",
            reorder_url: "/api/lists/1/items/reorder/",
          },
          items: [task(), task({ id: 2, text: "Review migrations" })],
        }}
      />,
    );

    await user.type(screen.getByRole("searchbox"), "migration");

    expect(screen.getByText("Review migrations")).toBeInTheDocument();
    expect(screen.queryByText("Write tests")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /All 2/ })).toBeInTheDocument();
  });

  it("waits for the server before marking a task complete", async () => {
    const user = userEvent.setup();
    const completed = task({
      status: "completed",
      completed_at: "2026-07-24T12:30:00-04:00",
    });
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      jsonResponse({ data: completed }),
    );
    render(
      <TaskWorkspace
        initialData={{
          list: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/lists/1/items/",
            reorder_url: "/api/lists/1/items/reorder/",
          },
          items: [task()],
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Mark complete" }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Reopen" })).toBeInTheDocument(),
    );
    expect(fetch).toHaveBeenCalledWith(
      "/api/items/1/",
      expect.objectContaining({ method: "PATCH" }),
    );
  });

  it("disables the affected task while a server change is pending", async () => {
    const user = userEvent.setup();
    let finishRequest!: (response: Response) => void;
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      new Promise<Response>((resolve) => {
        finishRequest = resolve;
      }),
    );
    render(
      <TaskWorkspace
        initialData={{
          list: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/lists/1/items/",
            reorder_url: "/api/lists/1/items/reorder/",
          },
          items: [task()],
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Mark complete" }));
    expect(screen.getByRole("button", { name: "Mark complete" })).toBeDisabled();
    expect(screen.getByText("Write tests")).toBeInTheDocument();

    finishRequest(
      await jsonResponse({
        data: task({
          status: "completed",
          completed_at: "2026-07-24T12:30:00-04:00",
        }),
      }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Reopen" })).toBeInTheDocument(),
    );
  });

  it("keeps the previous task text when editing fails", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      jsonResponse({ errors: { text: ["Duplicate task."] } }, false),
    );
    render(
      <TaskWorkspace
        initialData={{
          list: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/lists/1/items/",
            reorder_url: "/api/lists/1/items/reorder/",
          },
          items: [task()],
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Edit" }));
    const input = screen.getByRole("textbox", { name: "Edit task" });
    await user.clear(input);
    await user.type(input, "Duplicate");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Duplicate task.")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Duplicate")).toBeInTheDocument();
  });

  it("flags an active task with a past due date as overdue", () => {
    render(
      <TaskWorkspace
        initialData={{
          list: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/lists/1/items/",
            reorder_url: "/api/lists/1/items/reorder/",
          },
          items: [task({ due_date: "2000-01-01" })],
        }}
      />,
    );

    expect(screen.getByText(/Overdue:/)).toBeInTheDocument();
  });

  it("sends a due date update when the due date field changes", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      jsonResponse({ data: task({ due_date: "2026-08-01" }) }),
    );
    render(
      <TaskWorkspace
        initialData={{
          list: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/lists/1/items/",
            reorder_url: "/api/lists/1/items/reorder/",
          },
          items: [task()],
        }}
      />,
    );

    const dueDateInput = screen.getByLabelText("Change due date for Write tests");
    await user.type(dueDateInput, "2026-08-01");

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/items/1/",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ due_date: "2026-08-01" }),
        }),
      ),
    );
  });

  it("reorders tasks on drag and drop and posts the new order", async () => {
    const first = task({ id: 1, text: "First" });
    const second = task({ id: 2, text: "Second" });
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      jsonResponse({ data: [second, first] }),
    );
    render(
      <TaskWorkspace
        initialData={{
          list: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/lists/1/items/",
            reorder_url: "/api/lists/1/items/reorder/",
          },
          items: [first, second],
        }}
      />,
    );

    fireEvent.dragStart(screen.getByText("First").closest("article")!);
    fireEvent.drop(screen.getByText("Second").closest("article")!);

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/lists/1/items/reorder/",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ ordered_ids: [2, 1] }),
        }),
      ),
    );
  });

  it("filters tasks by tag", async () => {
    const user = userEvent.setup();
    render(
      <TaskWorkspace
        initialData={{
          list: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/lists/1/items/",
            reorder_url: "/api/lists/1/items/reorder/",
          },
          items: [
            task({ id: 1, text: "Buy milk", tags: ["groceries"] }),
            task({ id: 2, text: "Write tests", tags: ["work"] }),
          ],
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "groceries" }));

    expect(screen.getByText("Buy milk")).toBeInTheDocument();
    expect(screen.queryByText("Write tests")).not.toBeInTheDocument();
  });

  it("adds the spawned next occurrence when a recurring task is completed", async () => {
    const user = userEvent.setup();
    const original = task({ id: 1, text: "Take out trash", recurrence: "weekly" });
    const archived = task({
      id: 1,
      text: "Take out trash",
      recurrence: "weekly",
      status: "archived",
    });
    const spawned = task({
      id: 2,
      text: "Take out trash",
      recurrence: "weekly",
      status: "active",
    });
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      jsonResponse({ data: archived, spawned }),
    );
    render(
      <TaskWorkspace
        initialData={{
          list: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/lists/1/items/",
            reorder_url: "/api/lists/1/items/reorder/",
          },
          items: [original],
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Mark complete" }));

    expect(await screen.findByText(/next occurrence added/)).toBeInTheDocument();
    expect(screen.getByText("Take out trash")).toBeInTheDocument();
  });

  it("sends tags on task creation", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      jsonResponse({ data: task({ tags: ["groceries", "home"] }) }),
    );
    render(
      <TaskWorkspace
        initialData={{
          list: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/lists/1/items/",
            reorder_url: "/api/lists/1/items/reorder/",
          },
          items: [],
        }}
      />,
    );

    await user.type(screen.getByLabelText(/Add another item/), "Buy milk");
    await user.type(screen.getByLabelText(/Tags/), "groceries, home");
    await user.click(screen.getByRole("button", { name: "Add item" }));

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/lists/1/items/",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            text: "Buy milk",
            due_date: null,
            tags: ["groceries", "home"],
            recurrence: "none",
          }),
        }),
      ),
    );
  });
});

describe("TaskWorkspace subtasks", () => {
  const LIST = {
    id: 1,
    title: "Travel",
    create_item_url: "/api/lists/1/items/",
    reorder_url: "/api/lists/1/items/reorder/",
  };

  function renderNested(extra: Task[] = []) {
    const parent = task({
      id: 1,
      text: "Plan Japan trip",
      subtask_counts: { total: 2, done: 1 },
    });
    const child = task({
      id: 2,
      text: "Book flights",
      parent: { id: 1, text: "Plan Japan trip" },
    });
    const done = task({
      id: 3,
      text: "Book hotel",
      status: "completed",
      parent: { id: 1, text: "Plan Japan trip" },
    });
    return render(
      <TaskWorkspace
        initialData={{ list: LIST, items: [parent, child, done, ...extra] }}
      />,
    );
  }

  beforeEach(() => {
    document.cookie = "csrftoken=test-token";
    vi.restoreAllMocks();
  });

  it("renders children under their parent with a done count", () => {
    renderNested();

    expect(
      screen.getByRole("button", { name: "Hide subtasks of Plan Japan trip" }),
    ).toHaveTextContent("1/2");
    expect(screen.getByText("Book flights")).toBeInTheDocument();
  });

  it("collapses and re-expands a parent's children", async () => {
    const user = userEvent.setup();
    renderNested();

    await user.click(
      screen.getByRole("button", { name: "Hide subtasks of Plan Japan trip" }),
    );

    expect(screen.queryByText("Book flights")).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Show subtasks of Plan Japan trip" }),
    );

    expect(screen.getByText("Book flights")).toBeInTheDocument();
  });

  it("sends the parent id when adding a subtask from a row", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() =>
        jsonResponse({
          data: task({
            id: 9,
            text: "Book trains",
            parent: { id: 1, text: "Plan Japan trip" },
          }),
        }),
      );
    renderNested();

    await user.click(screen.getAllByRole("button", { name: "Add subtask" })[0]);
    await user.type(screen.getByLabelText(/New subtask under/), "Book trains");
    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() =>
      expect(fetchSpy).toHaveBeenCalledWith(
        "/api/lists/1/items/",
        expect.objectContaining({
          // always_recurs rides along at its default -- the list row has no
          // control for it, so opting out happens from the detail view.
          body: JSON.stringify({
            text: "Book trains",
            parent: 1,
            always_recurs: true,
          }),
        }),
      ),
    );
  });

  it("offers promote on a subtask instead of add subtask", () => {
    renderNested();

    // One level only: a child has nowhere to put children of its own.
    expect(screen.getAllByRole("button", { name: "Add subtask" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Promote" })).toHaveLength(2);
  });

  it("refuses a drag that would cross nesting levels", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    renderNested();

    const rows = document.querySelectorAll("article.list-item");
    fireEvent.dragStart(rows[1]); // the child
    fireEvent.drop(rows[0]); // onto its parent

    expect(
      await screen.findByText(/Drag reorders within one group/),
    ).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("scopes a sibling reorder to that group", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => jsonResponse({ data: [] }));
    renderNested();

    const rows = document.querySelectorAll("article.list-item");
    fireEvent.dragStart(rows[2]); // "Book hotel"
    fireEvent.drop(rows[1]); // onto its sibling "Book flights"

    await waitFor(() =>
      expect(fetchSpy).toHaveBeenCalledWith(
        "/api/lists/1/items/reorder/",
        expect.objectContaining({
          // Only the sibling group, and the parent scope travels with it.
          body: JSON.stringify({ ordered_ids: [3, 2], parent: 1 }),
        }),
      ),
    );
  });

  it("takes the children off screen when a recurring parent archives itself", async () => {
    // "Book hotel" was already done before its parent came round again, so
    // the server archives it alongside the still-open "Book flights". Left
    // here, it would keep rendering -- and rows() would promote it to the top
    // level, its parent having gone, so it would read as a root task.
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      jsonResponse({
        data: task({ id: 1, text: "Plan Japan trip", status: "archived" }),
        spawned: task({ id: 4, text: "Plan Japan trip", status: "active" }),
        cascaded: [
          task({
            id: 2,
            text: "Book flights",
            status: "archived",
            parent: { id: 1, text: "Plan Japan trip" },
          }),
          task({
            id: 3,
            text: "Book hotel",
            status: "archived",
            parent: { id: 1, text: "Plan Japan trip" },
          }),
        ],
      }),
    );
    renderNested();

    await user.click(
      screen.getAllByRole("button", { name: "Mark complete" })[0],
    );

    expect(await screen.findByText(/next occurrence added/)).toBeInTheDocument();
    expect(screen.queryByText("Book flights")).not.toBeInTheDocument();
    expect(screen.queryByText("Book hotel")).not.toBeInTheDocument();
    // The next occurrence took the old one's place, under the same text.
    expect(screen.getByText("Plan Japan trip")).toBeInTheDocument();
  });

  it("marks the children done when a plain parent completes", async () => {
    // No archiving here, so nothing leaves the list -- the open child just
    // stops being open, and has to say so without waiting for a reload.
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      jsonResponse({
        data: task({ id: 1, text: "Plan Japan trip", status: "completed" }),
        cascaded: [
          task({
            id: 2,
            text: "Book flights",
            status: "completed",
            parent: { id: 1, text: "Plan Japan trip" },
          }),
        ],
      }),
    );
    renderNested();

    await user.click(
      screen.getAllByRole("button", { name: "Mark complete" })[0],
    );

    await waitFor(() =>
      // Three tasks, all of them done: the filter counts local state, so it
      // only reads 3 once the cascaded child has been folded in.
      expect(
        screen.getByRole("button", { name: /Completed 3/ }),
      ).toBeInTheDocument(),
    );
  });
});
