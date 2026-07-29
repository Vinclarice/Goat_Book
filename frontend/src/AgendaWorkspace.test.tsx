import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AgendaWorkspace } from "./AgendaWorkspace";
import { agendaData, agendaList, task, TODAY } from "./test/fixtures";

function jsonResponse(data: object, ok = true) {
  return Promise.resolve({
    ok,
    status: ok ? 200 : 400,
    json: () => Promise.resolve(data),
  } as Response);
}

const home = { id: 2, title: "Home", url: "/lists/2/" };

function sampleItems() {
  return [
    task({ id: 1, text: "Renew insurance", due_date: "2026-07-22" }),
    task({ id: 2, text: "Ship the fix", due_date: TODAY }),
    task({
      id: 3,
      text: "Buy milk",
      due_date: "2026-07-30",
      list: home,
      tags: ["errand"],
    }),
    task({ id: 4, text: "Renew domain", due_date: "2026-09-01" }),
    task({ id: 5, text: "Refactor services", due_date: null }),
  ];
}

function renderAgenda(overrides = {}) {
  return render(
    <AgendaWorkspace
      initialData={agendaData({
        items: sampleItems(),
        lists: [agendaList(), agendaList({ id: 2, title: "Home" })],
        ...overrides,
      })}
    />,
  );
}

function section(name: RegExp) {
  return screen.getByRole("heading", { name }).closest<HTMLElement>("section")!;
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
    render(
      <AgendaWorkspace
        initialData={agendaData({
          items: [task({ id: 1, text: "Ship the fix", due_date: TODAY })],
        })}
      />,
    );

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

  it("snoozes a dated task to tomorrow", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() =>
        jsonResponse({
          data: task({ id: 2, text: "Ship the fix", due_date: "2026-07-29" }),
        }),
      );
    renderAgenda();

    const row = screen.getByText("Ship the fix").closest<HTMLElement>(".agenda-row")!;
    await user.click(within(row).getByRole("button", { name: "Tomorrow" }));

    await waitFor(() =>
      expect(screen.getByText(/Moved “Ship the fix” to tomorrow/)).toBeInTheDocument(),
    );
    const [, options] = fetchMock.mock.calls[0];
    expect(JSON.parse(String(options?.body))).toEqual({
      due_date: "2026-07-29",
    });
  });

  it("schedules an undated task for today", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() =>
        jsonResponse({
          data: task({ id: 5, text: "Refactor services", due_date: TODAY }),
        }),
      );
    const user2 = user;
    renderAgenda();

    await user2.click(screen.getByRole("button", { name: /No due date/ }));
    const row = screen.getByText("Refactor services").closest<HTMLElement>(".agenda-row")!;
    await user2.click(within(row).getByRole("button", { name: "Schedule" }));

    await waitFor(() =>
      expect(screen.getByText(/Scheduled “Refactor services” for today/)).toBeInTheDocument(),
    );
    const [, options] = fetchMock.mock.calls[0];
    expect(JSON.parse(String(options?.body))).toEqual({ due_date: TODAY });
  });

  it("adds a task to the selected list", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        { data: task({ id: 6, text: "Water the plants", list: home }) },
        true,
      ),
    );
    renderAgenda();

    await user.type(screen.getByLabelText("Task"), "Water the plants");
    await user.selectOptions(screen.getByLabelText("List"), "2");
    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() =>
      expect(screen.getByText(/Added “Water the plants” to Home/)).toBeInTheDocument(),
    );
    expect(fetchMock.mock.calls[0][0]).toBe("/api/lists/1/items/");
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

  it("invites a first list when the account is empty", () => {
    render(
      <AgendaWorkspace initialData={agendaData({ items: [], lists: [] })} />,
    );

    expect(screen.getByText("Start your first list.")).toBeInTheDocument();
  });

  it("says so when everything is done", () => {
    renderAgenda({ items: [] });

    expect(screen.getByText("You're all caught up.")).toBeInTheDocument();
  });

  it("links to the archive with its count", () => {
    renderAgenda({ archived_count: 23 });

    expect(screen.getByText("23 tasks")).toBeInTheDocument();
  });
});
