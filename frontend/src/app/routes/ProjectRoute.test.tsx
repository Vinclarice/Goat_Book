import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { ProjectRoute } from "./ProjectRoute";

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

function projectDetailData(overrides: Record<string, unknown> = {}) {
  return {
    id: 3,
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

const NAV = {
  areas: [],
  projects: [],
  archived_count: 0,
  inbox_count: 0,
  settings_url: "/accounts/settings/",
  inbox_url: "/capture/",
  ideas_url: "/capture/ideas/",
};

/* ProjectRoute also fetches /api/v1/nav for its "add an area" picker. Every
   mock below has to answer that request too, or the picker throws
   mid-render and takes the whole route with it. */
function projectPageFetch(data: object = projectDetailData()) {
  return (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.includes("/api/v1/nav")) return jsonResponse(NAV);
    return jsonResponse(data);
  };
}

function renderAt(projectId: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/projects/${projectId}`]}>
        <Routes>
          <Route path="/projects/:projectId" element={<ProjectRoute />} />
          <Route path="/agenda" element={<p>Agenda page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ProjectRoute", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    document.cookie = "csrftoken=test-token";
  });

  it("renders the project's title and open count", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(projectPageFetch());

    renderAt("3");

    expect(await screen.findByText("Website Relaunch")).toBeInTheDocument();
    expect(screen.getByText(/0 open/)).toBeInTheDocument();
  });

  it("shows an error state when the request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({ detail: "nope" }, false),
    );

    renderAt("3");

    expect(await screen.findByText(/Couldn't reach Clarice/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("lists the project's own areas", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      projectPageFetch(
        projectDetailData({
          areas: [
            { id: 1, title: "Design", open_count: 2, overdue_count: 0, color_key: "sky" },
            { id: 2, title: "Dev", open_count: 5, overdue_count: 1, color_key: "sage" },
          ],
        }),
      ),
    );

    renderAt("3");

    expect(await screen.findByText("Design")).toBeInTheDocument();
    expect(screen.getByText("Dev")).toBeInTheDocument();
  });

  it("says so plainly when the project has no areas yet", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(projectPageFetch());

    renderAt("3");

    expect(
      await screen.findByText("No areas in this project yet."),
    ).toBeInTheDocument();
  });

  it("removes an area from the project", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      if (url.includes("/api/v1/nav")) return jsonResponse(NAV);
      if (request.method === "PATCH" && url.includes("/project")) {
        return jsonResponse({ id: 1, title: "Design" });
      }
      return jsonResponse(
        projectDetailData({
          areas: [
            { id: 1, title: "Design", open_count: 0, overdue_count: 0, color_key: "sky" },
          ],
        }),
      );
    });

    renderAt("3");
    await screen.findByText("Design");

    await user.click(screen.getByRole("button", { name: "Remove" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) => {
          const req = request as Request;
          return req.method === "PATCH" && req.url.includes("/api/v1/areas/1/project");
        }),
      ).toBe(true);
    });
  });

  it("offers to add an area not already in this project", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.includes("/api/v1/nav")) {
        return jsonResponse({
          ...NAV,
          areas: [
            { id: 1, title: "Design", open_count: 0, overdue_count: 0, color_key: "sky" },
            { id: 5, title: "Marketing", open_count: 0, overdue_count: 0, color_key: "coral" },
          ],
        });
      }
      return jsonResponse(
        projectDetailData({
          areas: [
            { id: 1, title: "Design", open_count: 0, overdue_count: 0, color_key: "sky" },
          ],
        }),
      );
    });

    renderAt("3");
    await screen.findByText("Design");

    const picker = await screen.findByLabelText("Add an area");
    expect(screen.queryByRole("option", { name: "Design" })).not.toBeInTheDocument();
    expect(within(picker).getByRole("option", { name: "Marketing" })).toBeInTheDocument();
  });

  it("marks the project complete and reopens it", async () => {
    const user = userEvent.setup();
    let completed = false;
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      if (url.includes("/api/v1/nav")) return jsonResponse(NAV);
      if (request.method === "PATCH") completed = true;
      return jsonResponse(projectDetailData({ is_completed: completed }));
    });

    renderAt("3");
    await screen.findByText("Website Relaunch");

    await user.click(screen.getByRole("button", { name: "Mark complete" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Reopen" })).toBeInTheDocument();
    });
  });

  it("deletes the project and returns to the agenda after confirming", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      if (url.includes("/api/v1/nav")) return jsonResponse(NAV);
      if (request.method === "DELETE") return jsonResponse({ deleted: 3 });
      return jsonResponse(projectDetailData());
    });

    renderAt("3");
    await screen.findByText("Website Relaunch");

    await user.click(screen.getByRole("button", { name: "Delete project" }));
    await user.click(screen.getByRole("button", { name: "Delete permanently" }));

    await waitFor(() => {
      expect(screen.getByText("Agenda page")).toBeInTheDocument();
    });
    const deleteCall = fetchMock.mock.calls.find(
      ([request]) => (request as Request).method === "DELETE",
    );
    expect(deleteCall?.[0]).toEqual(
      expect.objectContaining({ url: expect.stringContaining("/api/v1/projects/3") }),
    );
  });
});
