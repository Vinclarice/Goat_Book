import { render, screen } from "@testing-library/react";
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
    completed_at: null,
    created_at: "2026-08-10T09:00:00-04:00",
    open_task_count: 0,
    areas: [],
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
});
