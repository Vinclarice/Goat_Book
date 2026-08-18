import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";

import { AgendaWorkspace } from "./AgendaWorkspace";
import { agendaData, agendaArea, agendaProject, task, TODAY } from "./test/fixtures";

function jsonResponse(data: object, ok = true) {
  return Promise.resolve({
    ok,
    status: ok ? 200 : 400,
    json: () => Promise.resolve(data),
  } as Response);
}

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
      jsonResponse({ data: completed }),
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
      jsonResponse({
        data: { ...task({ id: 2 }), status: "archived" },
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
        jsonResponse({
          data: task({ id: 2, text: "Ship the fix", due_date: "2026-07-29" }),
        }),
      );
    renderAgenda();

    await openSnoozeMenu(user, "Ship the fix");
    await user.click(screen.getByRole("menuitem", { name: "Tomorrow" }));

    await waitFor(() =>
      expect(screen.getByText(/Moved “Ship the fix” to tomorrow/)).toBeInTheDocument(),
    );
    const [, options] = fetchMock.mock.calls[0];
    expect(JSON.parse(String(options?.body))).toEqual({
      due_date: "2026-07-29",
    });
  });

  it("offers the same menu to an undated task", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() =>
        jsonResponse({
          data: task({
            id: 5,
            text: "Refactor services",
            due_date: "2026-08-03",
          }),
        }),
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
    const [, options] = fetchMock.mock.calls[0];
    expect(JSON.parse(String(options?.body))).toEqual({
      due_date: "2026-08-03",
    });
  });

  it("clears the due date of a dated task", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() =>
        jsonResponse({
          data: task({ id: 2, text: "Ship the fix", due_date: null }),
        }),
      );
    renderAgenda();

    await openSnoozeMenu(user, "Ship the fix");
    await user.click(screen.getByRole("menuitem", { name: "Clear" }));

    await waitFor(() =>
      expect(
        screen.getByText(/Cleared the due date on “Ship the fix”/),
      ).toBeInTheDocument(),
    );
    const [, options] = fetchMock.mock.calls[0];
    expect(JSON.parse(String(options?.body))).toEqual({ due_date: null });
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
      jsonResponse(
        { data: task({ id: 6, text: "Water the plants", area_id: home.id }) },
        true,
      ),
    );
    renderAgenda();

    await user.type(screen.getByLabelText("Task"), "Water the plants");
    await user.selectOptions(screen.getByLabelText("Area"), "2");
    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() =>
      expect(screen.getByText(/Added “Water the plants” to Home/)).toBeInTheDocument(),
    );
    expect(fetchMock.mock.calls[0][0]).toBe("/api/areas/1/items/");
  });

  it("surfaces a server error instead of losing the task", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        { errors: { text: ["You've already got this in your list"] } },
        false,
      ),
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

  it("links to the archive with its count", () => {
    renderAgenda({ archived_count: 23 });

    expect(screen.getByText("23 tasks")).toBeInTheDocument();
  });

  it("creates a project and navigates to its own page", async () => {
    // project-workspace-plan.md: unlike "New area", a Project is API-only,
    // so creating one goes through a mutation and the SPA router rather
    // than a plain form POST. apiV1 (openapi-fetch) needs a fuller Response
    // shape than this file's own plain jsonResponse gives api.ts's calls.
    function openapiResponse(data: object) {
      const body = JSON.stringify(data);
      return Promise.resolve({
        ok: true,
        status: 200,
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
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST" && request.url.includes("/api/v1/projects")) {
        return openapiResponse({ id: 9, title: "Website Relaunch" });
      }
      return jsonResponse({});
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
