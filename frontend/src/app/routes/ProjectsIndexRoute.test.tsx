import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { ProjectsIndexRoute } from "./ProjectsIndexRoute";

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
    due_date: null,
    is_completed: false,
    paused_at: null,
    completed_at: null,
    created_at: "2026-08-10T09:00:00-04:00",
    open_task_count: 0,
    areas: [],
    is_overdue: false,
    ...overrides,
  };
}

function render_() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/projects"]}>
        <Routes>
          <Route path="/projects" element={<ProjectsIndexRoute />} />
          <Route path="/projects/:projectId" element={<p>Project page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ProjectsIndexRoute", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("lists every project, open and completed alike", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse([
        project({ id: 1, title: "Website Relaunch" }),
        project({ id: 2, title: "Shipped last month", is_completed: true }),
      ]),
    );

    render_();

    expect(await screen.findByText("Website Relaunch")).toBeInTheDocument();
    expect(screen.getByText("Shipped last month")).toBeInTheDocument();
  });

  it("says so plainly when there are no projects yet", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse([]));

    render_();

    expect(await screen.findByText(/No projects yet/)).toBeInTheDocument();
  });

  it("routes to a project's own page", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse([project({ id: 5, title: "Website Relaunch" })]),
    );

    render_();
    await user.click(await screen.findByText("Website Relaunch"));

    expect(await screen.findByText("Project page")).toBeInTheDocument();
  });

  it("shows an error state when the request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({ detail: "nope" }, false),
    );

    render_();

    expect(await screen.findByText(/Couldn't reach Clarice/i)).toBeInTheDocument();
  });

  it("creates a project from the index page and lands on its own page", async () => {
    // Vince's own gap: creating a project used to live only in the Agenda
    // sidebar, a step removed from the page actually about projects.
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      if (request.method === "POST" && url.includes("/api/v1/projects")) {
        return jsonResponse(project({ id: 9, title: "Launch the business" }));
      }
      return jsonResponse([]);
    });

    render_();
    await user.type(await screen.findByLabelText("Project name"), "Launch the business");
    await user.click(screen.getByRole("button", { name: "Create project" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) => {
          const req = request as Request;
          return req.method === "POST" && req.url.includes("/api/v1/projects");
        }),
      ).toBe(true);
    });
    expect(await screen.findByText("Project page")).toBeInTheDocument();
  });

  it("shows an overdue project with a warning", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse([project({ due_date: "2026-01-01", is_overdue: true })]),
    );

    render_();

    expect(await screen.findByText(/overdue/i)).toBeInTheDocument();
  });

  it("explains what the composition bar shows once there's a project to show it on", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse([project()]));

    render_();

    expect(
      await screen.findByText(/colored strip shows how its open work is split/i),
    ).toBeInTheDocument();
  });

  it("files a paused project apart from the active ones", async () => {
    /* The index is where a person scans "what am I actually working on", so a
       parked project sitting silently among the open ones would make the
       pause cosmetic exactly where it matters most --
       planning-assistant-v2-plan.md increment 3. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse([
        project({ id: 1, title: "Website launch" }),
        project({
          id: 2,
          title: "Newsletter",
          paused_at: "2026-08-19T09:00:00-04:00",
        }),
      ]),
    );

    render_();

    expect(await screen.findByText("Paused")).toBeInTheDocument();
    const paused = screen.getByRole("heading", { name: "Paused" }).parentElement;
    expect(paused).not.toBeNull();
    expect(within(paused as HTMLElement).getByText("Newsletter")).toBeInTheDocument();
    expect(
      within(paused as HTMLElement).queryByText("Website launch"),
    ).toBeNull();
  });
});
