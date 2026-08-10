import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
            reorder_url: "/api/areas/1/items/reorder/",
          },
          project: null,
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

  it("shows every task's project when its area belongs to one", () => {
    // project-workspace-plan.md 2: a task's project is derived through its
    // Area now, so every task on one Area's page shares the same answer --
    // there's no more per-task variation within a single render.
    render(
      <TaskWorkspace
        initialData={{
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
            reorder_url: "/api/areas/1/items/reorder/",
          },
          project: { id: 7, title: "Kitchen remodel", url: "/app/projects/7" },
          items: [
            task({ id: 1, text: "Order cabinets", project_id: 7 }),
            task({ id: 2, text: "Order tile", project_id: 7 }),
          ],
        }}
      />,
    );

    const first = screen.getByText("Order cabinets").closest("article")!;
    const second = screen.getByText("Order tile").closest("article")!;
    expect(within(first).getByText("Kitchen remodel")).toBeInTheDocument();
    expect(within(second).getByText("Kitchen remodel")).toBeInTheDocument();
  });

  it("shows no project pill when the area belongs to none", () => {
    render(
      <TaskWorkspace
        initialData={{
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
            reorder_url: "/api/areas/1/items/reorder/",
          },
          project: null,
          items: [task({ id: 1, text: "Unrelated task" })],
        }}
      />,
    );

    expect(screen.queryByText("Kitchen remodel")).not.toBeInTheDocument();
  });

  it("searches task text without changing the live counts", async () => {
    const user = userEvent.setup();
    render(
      <TaskWorkspace
        initialData={{
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
            reorder_url: "/api/areas/1/items/reorder/",
          },
          project: null,
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
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
            reorder_url: "/api/areas/1/items/reorder/",
          },
          project: null,
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
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
            reorder_url: "/api/areas/1/items/reorder/",
          },
          project: null,
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
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
            reorder_url: "/api/areas/1/items/reorder/",
          },
          project: null,
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
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
            reorder_url: "/api/areas/1/items/reorder/",
          },
          project: null,
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
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
            reorder_url: "/api/areas/1/items/reorder/",
          },
          project: null,
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
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
            reorder_url: "/api/areas/1/items/reorder/",
          },
          project: null,
          items: [first, second],
        }}
      />,
    );

    fireEvent.dragStart(screen.getByText("First").closest("article")!);
    fireEvent.drop(screen.getByText("Second").closest("article")!);

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/areas/1/items/reorder/",
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
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
            reorder_url: "/api/areas/1/items/reorder/",
          },
          project: null,
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
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
            reorder_url: "/api/areas/1/items/reorder/",
          },
          project: null,
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
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
            reorder_url: "/api/areas/1/items/reorder/",
          },
          project: null,
          items: [],
        }}
      />,
    );

    await user.type(screen.getByLabelText(/Add another item/), "Buy milk");
    await user.type(screen.getByLabelText(/Tags/), "groceries, home");
    await user.click(screen.getByRole("button", { name: "Add item" }));

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/areas/1/items/",
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
