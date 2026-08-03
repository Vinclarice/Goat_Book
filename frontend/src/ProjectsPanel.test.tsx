import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ProjectsPanel } from "./ProjectsPanel";

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

function project(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    title: "Website Relaunch",
    area_id: 7,
    due_date: null,
    is_completed: false,
    completed_at: null,
    created_at: "2026-08-03T09:00:00-04:00",
    open_task_count: 0,
    ...overrides,
  };
}

/* openapi-fetch calls fetch(request) with a single Request object rather
   than (url, init), so every assertion below reads the Request instead of a
   separate init argument. Written the other way first and corrected against
   what the mock actually received. */
type FetchCall = [Request];

function callsWithMethod(
  fetchMock: { mock: { calls: unknown[][] } },
  method: string,
): Request[] {
  return (fetchMock.mock.calls as FetchCall[])
    .map(([request]) => request)
    .filter((request) => request.method === method);
}

async function bodyOf(request: Request): Promise<unknown> {
  return JSON.parse(await request.clone().text());
}

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ProjectsPanel areaId={7} />
    </QueryClientProvider>,
  );
}

describe("ProjectsPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    document.cookie = "csrftoken=test-token";
  });

  it("asks only for this area's projects", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => jsonResponse([]));

    renderPanel();

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect((fetchMock.mock.calls[0][0] as Request).url).toContain("area_id=7");
  });

  it("shows each project with how much is still open in it", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse([project({ open_task_count: 3 })]),
    );

    renderPanel();

    expect(await screen.findByText("Website Relaunch")).toBeInTheDocument();
    expect(screen.getByText("3 open")).toBeInTheDocument();
  });

  it("says so plainly when an area has no projects yet", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse([]));

    renderPanel();

    expect(
      await screen.findByText(/no projects in this area/i),
    ).toBeInTheDocument();
  });

  it("shows a due date when the project has one", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse([project({ due_date: "2026-09-30" })]),
    );

    renderPanel();

    // Asserted on the parts rather than one formatted string: the component
    // uses Intl with the runtime's locale, and pinning "Sep 30, 2026" would
    // make this fail on a machine that formats dates differently rather than
    // on a real regression.
    const line = await screen.findByText(/due .*2026/);
    expect(line.textContent).toMatch(/Sep|09|9/);
    expect(line.textContent).toContain("30");
  });

  it("creates a project in this area", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        if ((input as Request).method === "POST") {
          return jsonResponse(project({ title: "Website Relaunch" }));
        }
        return jsonResponse([]);
      });

    renderPanel();
    await screen.findByText(/no projects in this area/i);

    await user.type(
      screen.getByLabelText("New project"), "Website Relaunch",
    );
    await user.click(screen.getByRole("button", { name: "Add project" }));

    await waitFor(() => expect(callsWithMethod(fetchMock, "POST")).toHaveLength(1));
    expect(await bodyOf(callsWithMethod(fetchMock, "POST")[0])).toEqual({
      area_id: 7,
      title: "Website Relaunch",
      due_date: null,
    });
  });

  it("does not post an empty project name", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => jsonResponse([]));

    renderPanel();
    await screen.findByText(/no projects in this area/i);

    await user.click(screen.getByRole("button", { name: "Add project" }));

    expect(callsWithMethod(fetchMock, "POST")).toHaveLength(0);
  });

  it("marks a project complete and says its tasks were left alone", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        if ((input as Request).method === "PATCH") {
          return jsonResponse(
            project({ is_completed: true, completed_at: "2026-08-03T10:00:00-04:00" }),
          );
        }
        return jsonResponse([project({ open_task_count: 2 })]);
      });

    renderPanel();
    await screen.findByText("Website Relaunch");

    await user.click(screen.getByRole("button", { name: /mark complete/i }));

    await waitFor(() => expect(callsWithMethod(fetchMock, "PATCH")).toHaveLength(1));
    expect(await bodyOf(callsWithMethod(fetchMock, "PATCH")[0])).toEqual({
      is_completed: true,
    });
  });

  it("warns before completing a project that still has open tasks", async () => {
    /* principles.md: automations propose, people decide. Completing the
       grouping deliberately does not touch the tasks, so the one thing the
       interface owes someone is saying that out loud rather than letting
       them assume it tidied up. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse([project({ open_task_count: 2 })]),
    );

    renderPanel();
    await screen.findByText("Website Relaunch");

    expect(
      screen.getByText(/2 open .*stay open/i),
    ).toBeInTheDocument();
  });

  it("reopens a completed project", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        if ((input as Request).method === "PATCH") {
          return jsonResponse(project());
        }
        return jsonResponse([
          project({ is_completed: true, completed_at: "2026-08-03T10:00:00-04:00" }),
        ]);
      });

    renderPanel();
    await screen.findByText("Website Relaunch");

    await user.click(screen.getByRole("button", { name: /reopen/i }));

    await waitFor(() => expect(callsWithMethod(fetchMock, "PATCH")).toHaveLength(1));
    expect(await bodyOf(callsWithMethod(fetchMock, "PATCH")[0])).toEqual({
      is_completed: false,
    });
  });

  it("deletes a project and says the tasks survive", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        if ((input as Request).method === "DELETE") {
          return jsonResponse({ deleted: 1 });
        }
        return jsonResponse([project()]);
      });

    renderPanel();
    await screen.findByText("Website Relaunch");

    await user.click(screen.getByRole("button", { name: /delete project/i }));
    // The confirmation says what actually happens: the grouping goes, the
    // work does not.
    expect(await screen.findByText(/tasks will stay/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /delete permanently/i }));

    await waitFor(() =>
      expect(callsWithMethod(fetchMock, "DELETE")).toHaveLength(1),
    );
  });

  it("keeps the failure visible rather than silently doing nothing", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      if ((input as Request).method === "POST") {
        return jsonResponse({ detail: "Give the project a name" }, false, 409);
      }
      return jsonResponse([]);
    });

    renderPanel();
    await screen.findByText(/no projects in this area/i);

    await user.type(screen.getByLabelText("New project"), "x");
    await user.click(screen.getByRole("button", { name: "Add project" }));

    expect(
      await screen.findByText("Give the project a name"),
    ).toBeInTheDocument();
  });
});
