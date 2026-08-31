import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// A router, because each row links to the task page since
// coherence-audit-2026-08-30.md F4. Memory rather than browser: these
// tests are about the component, not about where a click lands.
import { MemoryRouter } from "react-router";

import { TaskWorkspace as BareTaskWorkspace } from "./TaskWorkspace";
import {
  apiResponse,
  requestedPaths,
  sentRequests,
  task,
  taskWrite,
} from "./test/fixtures";
import type { Task } from "./types";


const NAV_SEED = {
  areas: [],
  projects: [],
  archived_count: 0,
  settings_url: "/accounts/settings/",
};

/** Every test renders through a provider, because a write here invalidates the
 *  side nav's `["nav"]` query — its counts are what the write just moved.
 *  Shadowing the import keeps the twenty existing render calls untouched;
 *  a test that needs to assert on the client builds its own below. */
function TaskWorkspace(props: React.ComponentProps<typeof BareTaskWorkspace>) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <BareTaskWorkspace {...props} />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("TaskWorkspace", () => {
  beforeEach(() => {
    document.cookie = "csrftoken=test-token";
    vi.restoreAllMocks();
  });

  it("opens a task's own page from its row", async () => {
    // coherence-audit-2026-08-30.md F4. This page could change seven of a
    // task's fields and had no route at all to the page holding the other
    // four -- so priority, notes, lead days and the bill were unreachable
    // from the surface somebody actually works in.
    render(
      <TaskWorkspace
        initialData={{
          area: { id: 1, title: "Programming", create_item_url: "/api/areas/1/items/" },
          project: null,
          items: [task({ id: 42, text: "Write tests" })],
        }}
      />,
    );

    expect(screen.getByRole("link", { name: "Write tests" })).toHaveAttribute(
      "href",
      "/tasks/42",
    );
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

  it("tells the side nav its counts have moved", async () => {
    // SideNav is mounted once in AppLayout, outside the <Outlet/>, so it does
    // not remount when a route does. Its query is the only thing that refreshes
    // it, and completing a task here moves open_count, overdue_count and the
    // archive badge without touching that query -- so the numbers beside every
    // area stayed wrong for as long as somebody kept working in the tab.
    // Seven other files already invalidate ["nav"] after a write; these three
    // were the ones that did not.
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      taskWrite(task({ status: "completed" })),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    queryClient.setQueryData(["nav"], NAV_SEED);

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <BareTaskWorkspace
            initialData={{
              area: {
                id: 1,
                title: "Programming",
                create_item_url: "/api/areas/1/items/",
              },
              project: null,
              items: [task()],
            }}
          />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Mark complete" }));

    await waitFor(() =>
      expect(queryClient.getQueryState(["nav"])?.isInvalidated).toBe(true),
    );
  });

  it("waits for the server before marking a task complete", async () => {
    const user = userEvent.setup();
    const completed = task({
      status: "completed",
      completed_at: "2026-07-24T12:30:00-04:00",
    });
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      taskWrite(completed),
    );
    render(
      <TaskWorkspace
        initialData={{
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
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
    expect(requestedPaths(fetch as never)).toContain("/api/v1/tasks/1");
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
      await taskWrite(
        task({
          status: "completed",
          completed_at: "2026-07-24T12:30:00-04:00",
        }),
      ),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Reopen" })).toBeInTheDocument(),
    );
  });

  it("keeps the previous task text when editing fails", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      apiResponse({ detail: "Duplicate task." }, false),
    );
    render(
      <TaskWorkspace
        initialData={{
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
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
          },
          project: null,
          items: [task({ due_date: "2000-01-01" })],
        }}
      />,
    );

    // task-list-redesign-plan.md 2: the separate "Overdue: <date>" text is
    // gone -- the due-date pill (the real input, styled) shows it in red on
    // its own, so this checks the marker that drives that styling instead.
    const article = screen.getByText("Write tests").closest("article")!;
    expect(article.className).toMatch(/is-overdue/);
  });

  it("sends a due date update when the due date field changes", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      taskWrite(task({ due_date: "2026-08-01" })),
    );
    render(
      <TaskWorkspace
        initialData={{
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
          },
          project: null,
          items: [task()],
        }}
      />,
    );

    const dueDateInput = screen.getByLabelText("Change due date for Write tests");
    await user.type(dueDateInput, "2026-08-01");

    await waitFor(async () =>
      expect(await sentRequests(fetch as never)).toContainEqual({
        path: "/api/v1/tasks/1",
        method: "PATCH",
        body: JSON.stringify({ due_date: "2026-08-01" }),
      }),
    );
  });

  it("reorders tasks on drag and drop and posts the new order", async () => {
    const first = task({ id: 1, text: "First" });
    const second = task({ id: 2, text: "Second" });
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      apiResponse([second, first]),
    );
    render(
      <TaskWorkspace
        initialData={{
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
          },
          project: null,
          items: [first, second],
        }}
      />,
    );

    fireEvent.dragStart(screen.getByText("First").closest("article")!);
    fireEvent.drop(screen.getByText("Second").closest("article")!);

    await waitFor(async () =>
      expect(await sentRequests(fetch as never)).toContainEqual({
        path: "/api/v1/areas/1/tasks/reorder",
        method: "POST",
        body: JSON.stringify({ ordered_ids: [2, 1] }),
      }),
    );
  });

  it("sorts tasks by due date ascending with undated tasks last, then restores manual order", async () => {
    const user = userEvent.setup();
    const dated = task({ id: 1, text: "Later task", due_date: "2026-08-20" });
    const undated = task({ id: 2, text: "No due date" });
    const soon = task({ id: 3, text: "Sooner task", due_date: "2026-08-01" });
    render(
      <TaskWorkspace
        initialData={{
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
          },
          project: null,
          items: [dated, undated, soon],
        }}
      />,
    );

    const taskTexts = () =>
      Array.from(document.querySelectorAll(".task-text")).map(
        (el) => el.textContent,
      );

    expect(taskTexts()).toEqual(["Later task", "No due date", "Sooner task"]);

    await user.selectOptions(screen.getByLabelText("Sort tasks"), "due_date");

    expect(taskTexts()).toEqual(["Sooner task", "Later task", "No due date"]);

    await user.selectOptions(screen.getByLabelText("Sort tasks"), "manual");

    expect(taskTexts()).toEqual(["Later task", "No due date", "Sooner task"]);
  });

  it("disables dragging while sorted by due date", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const first = task({ id: 1, text: "First", due_date: "2026-08-01" });
    const second = task({ id: 2, text: "Second", due_date: "2026-08-10" });
    render(
      <TaskWorkspace
        initialData={{
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
          },
          project: null,
          items: [first, second],
        }}
      />,
    );

    await user.selectOptions(screen.getByLabelText("Sort tasks"), "due_date");

    fireEvent.dragStart(screen.getByText("First").closest("article")!);
    fireEvent.drop(screen.getByText("Second").closest("article")!);

    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("reveals a checkbox per row and a bulk bar when Select is toggled on", async () => {
    const user = userEvent.setup();
    render(
      <TaskWorkspace
        initialData={{
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
          },
          project: null,
          items: [task({ id: 1, text: "First" }), task({ id: 2, text: "Second" })],
        }}
      />,
    );

    expect(screen.queryByLabelText("Select First")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Select" }));

    expect(screen.getByLabelText("Select First")).toBeInTheDocument();
    expect(screen.getByLabelText("Select Second")).toBeInTheDocument();
    expect(screen.getByText("0 selected")).toBeInTheDocument();

    await user.click(screen.getByLabelText("Select First"));
    expect(screen.getByText("1 selected")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Clear" }));
    expect(screen.getByText("0 selected")).toBeInTheDocument();
  });

  it("bulk-completes selected tasks, replicating the archived/spawned branch for a recurring one", async () => {
    const user = userEvent.setup();
    const plain = task({ id: 1, url: "/api/items/1/", text: "Plain task" });
    const recurring = task({
      id: 2,
      url: "/api/items/2/",
      text: "Recurring task",
      recurrence: "weekly",
    });
    const plainCompleted = task({
      id: 1,
      url: "/api/items/1/",
      text: "Plain task",
      status: "completed",
      completed_at: "2026-07-24T12:30:00-04:00",
    });
    const recurringArchived = task({
      id: 2,
      url: "/api/items/2/",
      text: "Recurring task",
      recurrence: "weekly",
      status: "archived",
    });
    const spawned = task({
      id: 3,
      url: "/api/items/3/",
      text: "Recurring task",
      recurrence: "weekly",
      status: "active",
    });
    // Dispatched on the Request's path rather than on a url string:
    // openapi-fetch builds a Request and calls fetch(request), where the
    // hand-rolled client called fetch(url, init).
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const path = new URL((input as Request).url).pathname;
      if (path === "/api/v1/tasks/1") return taskWrite(plainCompleted);
      if (path === "/api/v1/tasks/2")
        return taskWrite(recurringArchived, { spawned });
      throw new Error(`unexpected fetch: ${path}`);
    });
    render(
      <TaskWorkspace
        initialData={{
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
          },
          project: null,
          items: [plain, recurring],
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Select" }));
    await user.click(screen.getByLabelText("Select Plain task"));
    await user.click(screen.getByLabelText("Select Recurring task"));
    await user.click(screen.getByRole("button", { name: "Mark complete" }));

    await waitFor(() => {
      const article = screen.getByText("Plain task").closest("article")!;
      expect(article.className).toMatch(/is-completed/);
    });
    expect(screen.getAllByText("Recurring task")).toHaveLength(1);
  });

  it("bulk-archives selected tasks as a plain status flip, no spawning", async () => {
    const user = userEvent.setup();
    const first = task({ id: 1, url: "/api/items/1/", text: "First" });
    const second = task({ id: 2, url: "/api/items/2/", text: "Second" });
    const firstArchived = task({
      id: 1,
      url: "/api/items/1/",
      text: "First",
      status: "archived",
    });
    const secondArchived = task({
      id: 2,
      url: "/api/items/2/",
      text: "Second",
      status: "archived",
    });
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const path = new URL((input as Request).url).pathname;
      if (path === "/api/v1/tasks/1") return taskWrite(firstArchived);
      if (path === "/api/v1/tasks/2") return taskWrite(secondArchived);
      throw new Error(`unexpected fetch: ${path}`);
    });
    render(
      <TaskWorkspace
        initialData={{
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
          },
          project: null,
          items: [first, second],
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Select" }));
    await user.click(screen.getByLabelText("Select First"));
    await user.click(screen.getByLabelText("Select Second"));
    await user.click(screen.getByRole("button", { name: "Archive" }));

    await waitFor(() =>
      expect(screen.queryByText("First")).not.toBeInTheDocument(),
    );
    expect(screen.queryByText("Second")).not.toBeInTheDocument();
  });

  it("removes a single tag by clicking its × without touching the others", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      taskWrite(task({ tags: ["home"] })),
    );
    render(
      <TaskWorkspace
        initialData={{
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
          },
          project: null,
          items: [task({ tags: ["groceries", "home"] })],
        }}
      />,
    );

    const article = screen.getByText("Write tests").closest("article")!;
    await user.click(within(article).getByRole("button", { name: "Remove tag groceries" }));

    await waitFor(async () =>
      expect(await sentRequests(fetch as never)).toContainEqual({
        path: "/api/v1/tasks/1",
        method: "PATCH",
        body: JSON.stringify({ tags: ["home"] }),
      }),
    );
    await waitFor(() => expect(within(article).getByText("home")).toBeInTheDocument());
    expect(within(article).queryByText("groceries")).not.toBeInTheDocument();
  });

  it("adds one or more tags via the + tag input without disturbing the existing set", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      taskWrite(task({ tags: ["home", "work", "urgent"] })),
    );
    render(
      <TaskWorkspace
        initialData={{
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
          },
          project: null,
          items: [task({ tags: ["home"] })],
        }}
      />,
    );

    const article = screen.getByText("Write tests").closest("article")!;
    const addInput = within(article).getByPlaceholderText("+ tag");
    await user.type(addInput, "work, urgent");
    fireEvent.blur(addInput);

    await waitFor(async () =>
      expect(await sentRequests(fetch as never)).toContainEqual({
        path: "/api/v1/tasks/1",
        method: "PATCH",
        body: JSON.stringify({ tags: ["home", "work", "urgent"] }),
      }),
    );
    await waitFor(() => expect(within(article).getByText("work")).toBeInTheDocument());
    expect(within(article).getByPlaceholderText("+ tag")).toHaveValue("");
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
      taskWrite(archived, { spawned }),
    );
    render(
      <TaskWorkspace
        initialData={{
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
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
      taskWrite(task({ tags: ["groceries", "home"] })),
    );
    render(
      <TaskWorkspace
        initialData={{
          area: {
            id: 1,
            title: "Programming",
            create_item_url: "/api/areas/1/items/",
          },
          project: null,
          items: [],
        }}
      />,
    );

    await user.type(screen.getByLabelText(/Add another item/), "Buy milk");
    await user.type(screen.getByLabelText(/Tags/), "groceries, home");
    await user.click(screen.getByRole("button", { name: "Add item" }));

    await waitFor(async () =>
      expect(await sentRequests(fetch as never)).toContainEqual({
        path: "/api/v1/areas/1/tasks",
        method: "POST",
        body: JSON.stringify({
            text: "Buy milk",
            due_date: null,
            tags: ["groceries", "home"],
            recurrence: "none",
          }),
      }),
    );
  });
});
