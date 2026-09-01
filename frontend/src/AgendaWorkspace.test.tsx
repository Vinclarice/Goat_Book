import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";

import { AgendaWorkspace } from "./AgendaWorkspace";
import {
  agendaData,
  agendaArea,
  agendaProject,
  apiResponse,
  requestedPaths,
  sentRequests,
  task,
  taskWrite,
  TODAY,
} from "./test/fixtures";

const home = { id: 2, title: "Home", url: "/areas/2/" };

function sampleItems() {
  return [
    task({ id: 1, text: "Renew insurance", due_date: "2026-07-22" }),
    task({ id: 2, text: "Ship the fix", due_date: TODAY }),
    task({
      id: 3,
      text: "Buy milk",
      due_date: "2026-07-30",
      area_id: home.id,
      tags: ["errand"],
    }),
    task({ id: 4, text: "Renew domain", due_date: "2026-09-01" }),
    task({ id: 5, text: "Refactor services", due_date: null }),
  ];
}

function renderAgenda(overrides = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AgendaWorkspace
          initialData={agendaData({
            items: sampleItems(),
            areas: [agendaArea(), agendaArea({ id: 2, title: "Home" })],
            ...overrides,
          })}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function section(name: RegExp) {
  return screen.getByRole("heading", { name }).closest<HTMLElement>("section")!;
}

async function openSnoozeMenu(
  user: ReturnType<typeof userEvent.setup>,
  text: string,
) {
  const row = screen.getByText(text).closest<HTMLElement>("article")!;
  await user.click(within(row).getByRole("button", { name: `Schedule “${text}”` }));
}

describe("AgendaWorkspace", () => {
  beforeEach(() => {
    document.cookie = "csrftoken=test-token";
    vi.restoreAllMocks();
  });

  it("groups tasks from every list by how soon they are due", () => {
    renderAgenda();

    expect(within(section(/Overdue/)).getByText("Renew insurance")).toBeInTheDocument();
    expect(within(section(/^Today/)).getByText("Ship the fix")).toBeInTheDocument();
    expect(within(section(/This week/)).getByText("Buy milk")).toBeInTheDocument();
    expect(within(section(/Later/)).getByText("Renew domain")).toBeInTheDocument();
    expect(within(section(/No due date/)).getByText("Refactor services")).toBeInTheDocument();
  });

  it("shows headline counts with overdue folded into this week", () => {
    renderAgenda();

    const overdue = screen.getByRole("button", { name: "Show only overdue tasks" });
    const week = screen.getByRole("button", { name: "Show only tasks due this week" });
    expect(within(overdue).getByText("1")).toBeInTheDocument();
    expect(within(week).getByText("3")).toBeInTheDocument();
  });

  it("says how overdue a task is", () => {
    renderAgenda();

    expect(screen.getByText("6 days overdue")).toBeInTheDocument();
  });

  it("shows a task's project, the same way it shows its area", () => {
    renderAgenda({
      items: [
        task({ id: 1, text: "Order cabinets", due_date: TODAY, project_id: 1 }),
        task({ id: 2, text: "Ship the fix", due_date: TODAY }),
      ],
      projects: [agendaProject({ id: 1, title: "Kitchen remodel", url: "/areas/1/" })],
    });

    const withProject = screen.getByText("Order cabinets").closest<HTMLElement>("article")!;
    const withoutProject = screen.getByText("Ship the fix").closest<HTMLElement>("article")!;
    const projectPill = within(withProject).getByRole("link", { name: "Kitchen remodel" });
    expect(projectPill).toHaveAttribute("href", "/areas/1/");
    expect(within(withoutProject).queryByText("Kitchen remodel")).not.toBeInTheDocument();
  });

  it("marks rows that have notes, and only those", () => {
    renderAgenda({
      items: [
        task({ id: 1, text: "Renew insurance", due_date: TODAY, notes: "Policy 4471" }),
        task({ id: 2, text: "Ship the fix", due_date: TODAY }),
      ],
    });

    expect(screen.getAllByLabelText("Has notes")).toHaveLength(1);
  });

  it("says how long a task has been waiting, but only once it's worth mentioning", () => {
    renderAgenda({
      items: [
        task({
          id: 1,
          text: "Look into a standing desk",
          due_date: null,
          created_at: "2026-07-10T12:00:00-04:00",
        }),
        task({ id: 2, text: "Ship the fix", due_date: TODAY }),
      ],
    });

    expect(screen.getByText("Added 18 days ago")).toBeInTheDocument();
    const recent = screen.getByText("Ship the fix").closest<HTMLElement>("article")!;
    expect(within(recent).queryByText(/Added/)).not.toBeInTheDocument();
  });

  it("starts the far-off buckets collapsed", () => {
    renderAgenda();

    expect(
      screen.getByRole("button", { name: /Later/ }),
    ).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.getByRole("button", { name: /Overdue 1/ }),
    ).toHaveAttribute("aria-expanded", "true");
  });

  it("expands a bucket when its heading is clicked", async () => {
    const user = userEvent.setup();
    renderAgenda();

    await user.click(screen.getByRole("button", { name: /Later/ }));

    expect(
      screen.getByRole("button", { name: /Later/ }),
    ).toHaveAttribute("aria-expanded", "true");
  });

  it("filters to one scope when a headline number is clicked", async () => {
    const user = userEvent.setup();
    renderAgenda();

    await user.click(screen.getByRole("button", { name: "Show only overdue tasks" }));

    expect(screen.getByText("Renew insurance")).toBeInTheDocument();
    expect(screen.queryByText("Ship the fix")).not.toBeInTheDocument();
    expect(screen.getByText(/1 task/)).toBeInTheDocument();
  });

  it("clears a scope filter when the same number is clicked again", async () => {
    const user = userEvent.setup();
    renderAgenda();

    await user.click(screen.getByRole("button", { name: "Show only overdue tasks" }));
    await user.click(screen.getByRole("button", { name: "Show only overdue tasks" }));

    expect(screen.getByText("Ship the fix")).toBeInTheDocument();
  });

  it("filters by tag when a tag pill is clicked", async () => {
    const user = userEvent.setup();
    renderAgenda();

    await user.click(screen.getAllByRole("button", { name: "#errand" })[0]);

    expect(screen.getByText("Buy milk")).toBeInTheDocument();
    expect(screen.queryByText("Ship the fix")).not.toBeInTheDocument();
  });

  it("searches task text and updates the filter banner", async () => {
    const user = userEvent.setup();
    renderAgenda();

    await user.type(screen.getByRole("searchbox"), "milk");

    expect(screen.getByText("Buy milk")).toBeInTheDocument();
    expect(screen.queryByText("Ship the fix")).not.toBeInTheDocument();
    expect(screen.getByText(/“milk”/)).toBeInTheDocument();
  });

  it("clears the search box along with every other filter", async () => {
    const user = userEvent.setup();
    renderAgenda();

    await user.type(screen.getByRole("searchbox"), "milk");
    await user.click(screen.getByRole("button", { name: "Clear" }));

    expect(screen.getByRole("searchbox")).toHaveValue("");
    expect(screen.getByText("Ship the fix")).toBeInTheDocument();
  });

  it("filters by list from the sidebar", async () => {
    const user = userEvent.setup();
    renderAgenda();

    await user.click(screen.getByRole("button", { name: /Home/ }));

    expect(screen.getByText("Buy milk")).toBeInTheDocument();
    expect(screen.queryByText("Renew insurance")).not.toBeInTheDocument();
  });

  it("keeps headline counts unfiltered while rows narrow", async () => {
    const user = userEvent.setup();
    renderAgenda();

    await user.click(screen.getByRole("button", { name: /Home/ }));

    const open = screen.getByRole("button", { name: "Show all open tasks" });
    expect(within(open).getByText("5")).toBeInTheDocument();
  });

  it("explains when a filter matches nothing", async () => {
    const user = userEvent.setup();
    renderAgenda({
      items: [task({ id: 1, text: "Ship the fix", due_date: TODAY })],
    });

    await user.click(screen.getByRole("button", { name: "Show only overdue tasks" }));

    expect(screen.getByText("Nothing matches that filter.")).toBeInTheDocument();
  });

  it("moves a completed task into completed today and offers undo", async () => {
    const user = userEvent.setup();
    const completed = {
      ...task({ id: 2, text: "Ship the fix", due_date: TODAY }),
      status: "completed" as const,
    };
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      taskWrite(completed),
    );
    renderAgenda();

    await user.click(
      screen.getByRole("button", { name: /Complete “Ship the fix”/ }),
    );

    await waitFor(() =>
      expect(screen.getByText(/Completed “Ship the fix”/)).toBeInTheDocument(),
    );
    expect(
      within(section(/Completed today/)).getByText("Ship the fix"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Undo" })).toBeInTheDocument();
  });

  it("adds the next occurrence when a recurring task is completed", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      taskWrite({ ...task({ id: 2 }), status: "archived" }, {
        spawned: task({
          id: 99,
          text: "Ship the fix",
          due_date: "2026-08-04",
          recurrence: "weekly",
        }),
      }),
    );
    renderAgenda();

    await user.click(
      screen.getByRole("button", { name: /Complete “Ship the fix”/ }),
    );

    await waitFor(() =>
      expect(screen.getByText(/Next one due/)).toBeInTheDocument(),
    );
    expect(screen.queryByText("Completed today")).not.toBeInTheDocument();
  });

  it("snoozes a dated task to tomorrow from the menu", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() =>
        taskWrite(task({ id: 2, text: "Ship the fix", due_date: "2026-07-29" })),
      );
    renderAgenda();

    await openSnoozeMenu(user, "Ship the fix");
    await user.click(screen.getByRole("menuitem", { name: "Tomorrow" }));

    await waitFor(() =>
      expect(screen.getByText(/Moved “Ship the fix” to tomorrow/)).toBeInTheDocument(),
    );
    const [sent] = await sentRequests(fetchMock);
    expect(JSON.parse(sent.body)).toEqual({
      due_date: "2026-07-29",
    });
  });

  it("offers the same menu to an undated task", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() =>
        taskWrite(
          task({ id: 5, text: "Refactor services", due_date: "2026-08-03" }),
        ),
      );
    renderAgenda();

    await user.click(screen.getByRole("button", { name: /No due date/ }));
    await openSnoozeMenu(user, "Refactor services");
    await user.click(screen.getByRole("menuitem", { name: "Next week" }));

    await waitFor(() =>
      expect(
        screen.getByText(/Moved “Refactor services” to next week/),
      ).toBeInTheDocument(),
    );
    const [sent] = await sentRequests(fetchMock);
    expect(JSON.parse(sent.body)).toEqual({
      due_date: "2026-08-03",
    });
  });

  it("clears the due date of a dated task", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() =>
        taskWrite(task({ id: 2, text: "Ship the fix", due_date: null })),
      );
    renderAgenda();

    await openSnoozeMenu(user, "Ship the fix");
    await user.click(screen.getByRole("menuitem", { name: "Clear" }));

    await waitFor(() =>
      expect(
        screen.getByText(/Cleared the due date on “Ship the fix”/),
      ).toBeInTheDocument(),
    );
    const [sent] = await sentRequests(fetchMock);
    expect(JSON.parse(sent.body)).toEqual({ due_date: null });
  });

  it("leaves clear out of the menu when there is no date to clear", async () => {
    const user = userEvent.setup();
    renderAgenda();

    await user.click(screen.getByRole("button", { name: /No due date/ }));
    await openSnoozeMenu(user, "Refactor services");

    expect(
      screen.getAllByRole("menuitem").map((item) => item.textContent),
    ).toEqual(["Tomorrow", "This weekend", "Next week"]);
  });

  it("closes the menu again when escape is pressed", async () => {
    const user = userEvent.setup();
    renderAgenda();

    await openSnoozeMenu(user, "Ship the fix");
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("menuitem")).not.toBeInTheDocument();
  });

  it("adds a task to the selected list", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      taskWrite(task({ id: 6, text: "Water the plants", area_id: home.id })),
    );
    renderAgenda();

    await user.type(screen.getByLabelText("Task"), "Water the plants");
    await user.selectOptions(screen.getByLabelText("Area"), "2");
    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() =>
      expect(screen.getByText(/Added “Water the plants” to Home/)).toBeInTheDocument(),
    );
    // Area 2, which is the one the test selects. This asserted area 1 and
    // passed, because agendaArea() gave every area area 1's create url --
    // see that fixture. Addressing the endpoint by id is what exposed it.
    expect(requestedPaths(fetchMock)).toContain("/api/v1/areas/2/tasks");
  });

  it("surfaces a server error instead of losing the task", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      apiResponse({ detail: "You've already got this in your list" }, false),
    );
    renderAgenda();

    await user.type(screen.getByLabelText("Task"), "Ship the fix");
    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() =>
      expect(
        screen.getByText("You've already got this in your list"),
      ).toBeInTheDocument(),
    );
  });

  it("invites a first area when the account is empty", () => {
    renderAgenda({ items: [], areas: [] });

    expect(screen.getByText("Start your first area.")).toBeInTheDocument();
  });

  it("says so when everything is done", () => {
    renderAgenda({ items: [] });

    expect(screen.getByText("You're all caught up.")).toBeInTheDocument();
  });

  it("opens a task's own page without leaving the app", async () => {
    // coherence-audit-2026-08-30.md F4. This was an <a href> to `edit_url`,
    // a Django view whose entire body was a redirect back into this SPA --
    // two round trips to reach a route the client router already had.
    renderAgenda();

    const card = screen.getByText("Ship the fix").closest<HTMLElement>("article")!;
    const open = within(card).getByRole("link", { name: "Open" });
    expect(open).toHaveAttribute("href", "/tasks/2");
  });

  it("shows a bill in the bucket its date puts it in", async () => {
    /* Decision 4: bills stay on this screen because paying is a real thing to
       do on a day. They used to arrive in `items` because a bill was an Item;
       they arrive in `bills` because soon it will not be, and `bucketFor` is
       shared so a bill and a task due the same day land together. */
    renderAgenda({
      bills: [
        {
          task_id: 9,
          payee: "Landlord",
          due_date: TODAY,
          amount: "1200.00",
          currency: "USD",
          direction: "out",
          repeats: true,
        },
      ],
    });

    const card = screen.getByText("Landlord").closest<HTMLElement>("article")!;
    expect(within(card).getByText("bill")).toBeInTheDocument();
    expect(within(card).getByText("1200.00 USD")).toBeInTheDocument();
    expect(
      within(card).getByRole("link", { name: "Landlord" }),
    ).toHaveAttribute("href", "/money/bills/9");
  });

  it("pays a bill from the agenda", async () => {
    // The verb decision 4 exists for: the day is where paying gets noticed.
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      apiResponse({}),
    );
    renderAgenda({
      bills: [
        {
          task_id: 9,
          payee: "Landlord",
          due_date: TODAY,
          amount: "1200.00",
          currency: "USD",
          direction: "out",
          repeats: true,
        },
      ],
    });

    await user.click(screen.getByRole("button", { name: "Mark paid" }));

    await waitFor(() =>
      expect(
        requestedPaths(fetchMock).some((path) =>
          path.includes("/api/v1/money/bills/entry/9/pay"),
        ),
      ).toBe(true),
    );
  });

  it("says received rather than paid for money coming in", () => {
    renderAgenda({
      bills: [
        {
          task_id: 4,
          payee: "Work",
          due_date: TODAY,
          amount: "3000.00",
          currency: "USD",
          direction: "in",
          repeats: true,
        },
      ],
    });

    expect(
      screen.getByRole("button", { name: "Mark received" }),
    ).toBeInTheDocument();
  });

  it("links to the archive with its count", () => {
    renderAgenda({ archived_count: 23 });

    expect(screen.getByText("23 tasks")).toBeInTheDocument();
  });

  it("creates a project and navigates to its own page", async () => {
    // project-workspace-plan.md: a Project is API-only, so creating one goes
    // through a mutation and the SPA router rather than a plain form POST.
    // Its sibling card does the same since coherence-audit-2026-08-30.md F1.
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST" && request.url.includes("/api/v1/projects")) {
        return apiResponse({ id: 9, title: "Website Relaunch" });
      }
      return apiResponse({});
    });
    renderAgenda();

    await user.click(screen.getByText("+ New project"));
    await user.type(screen.getByLabelText("Project name"), "Website Relaunch");
    await user.click(screen.getByRole("button", { name: "Create project" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) => {
          const req = request as Request;
          return req.method === "POST" && req.url.includes("/api/v1/projects");
        }),
      ).toBe(true);
    });
  });

  it("creates an area through the API, like the project card beside it", async () => {
    // coherence-audit-2026-08-30.md F1. This card was a plain Django form
    // POST that reloaded the page, sitting next to a typed mutation doing
    // the same job -- the clearest instance of the seam the audit is about.
    // No first task any more either: the sibling does not ask for one.
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST" && request.url.includes("/api/v1/areas")) {
        return apiResponse({
          id: 12,
          title: "Home",
          create_item_url: "/api/areas/12/items/",
        });
      }
      return apiResponse({});
    });
    renderAgenda();

    await user.click(screen.getByText("+ New area"));
    await user.type(screen.getByLabelText("Area name"), "Home");
    await user.click(screen.getByRole("button", { name: "Create area" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) => {
          const req = request as Request;
          return req.method === "POST" && req.url.includes("/api/v1/areas");
        }),
      ).toBe(true);
    });
  });

  it("does not offer routes that no longer exist", async () => {
    // Heron 4b deleted the Inbox and the Ideas shelf and freed /capture/,
    // which clarice/urls.py deliberately did not take -- so both hrefs here
    // were plain Django 404s, outside the SPA shell, with no way back but the
    // browser button. SideNav.tsx removed the same two links and this
    // duplicate was missed; nothing failed because no test asserted on the
    // block at all.
    renderAgenda();
    await screen.findByText("Renew insurance");

    const dead = document.querySelectorAll('a[href^="/capture/"]');
    expect(dead).toHaveLength(0);
  });

  it("still offers a way into the knowledge core from the page itself", async () => {
    // The block's reason survives its links: a direct entry point from the
    // main page, not only through a nav element that could fail to render.
    // Only the destination changed, and there is one of them now.
    renderAgenda();
    await screen.findByText("Renew insurance");

    expect(document.querySelector('a[href="/mind/"]')).not.toBeNull();
  });
});
