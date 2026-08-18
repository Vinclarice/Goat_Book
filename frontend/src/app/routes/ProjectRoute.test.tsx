import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
    is_overdue: false,
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
  // Mirrors main.tsx: retry off, everything else at TanStack's defaults. The
  // default staleTime of 0 is what makes a background refetch possible at
  // all, so pinning it here would prove nothing about the real app.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    queryClient,
    ...render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/projects/${projectId}`]}>
        <Routes>
          <Route path="/projects/:projectId" element={<ProjectRoute />} />
          <Route path="/agenda" element={<p>Agenda page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
    ),
  };
}

describe("ProjectRoute", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    document.cookie = "csrftoken=test-token";
  });

  it("renders the project's title and open count", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(projectPageFetch());

    renderAt("3");

    expect(await screen.findByDisplayValue("Website Relaunch")).toBeInTheDocument();
    expect(screen.getByText(/0 open/)).toBeInTheDocument();
  });

  it("shows a due date as a plain calendar value, not a shifted instant", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      projectPageFetch(projectDetailData({ due_date: "2026-09-30" })),
    );

    renderAt("3");

    expect(await screen.findByLabelText("Due date")).toHaveValue("2026-09-30");
  });

  it("says so when no due date is set, and stops once one is", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(projectPageFetch());

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");
    expect(screen.getByText("No due date set")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Due date"), {
      target: { value: "2026-09-30" },
    });

    expect(screen.queryByText("No due date set")).not.toBeInTheDocument();
  });

  it("explains what the composition bar shows", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(projectPageFetch());

    renderAt("3");

    expect(
      await screen.findByText(/wider segment means more open work there/i),
    ).toBeInTheDocument();
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

    const picker = await screen.findByLabelText("Add an existing area");
    expect(screen.queryByRole("option", { name: "Design" })).not.toBeInTheDocument();
    expect(within(picker).getByRole("option", { name: "Marketing" })).toBeInTheDocument();
  });

  it("creates a brand new area directly in the project", async () => {
    // Vince's call: no first task required, unlike the Agenda sidebar's
    // own "+ New area" -- the predominant case for a project is areas
    // that don't exist yet.
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      if (url.includes("/api/v1/nav")) return jsonResponse(NAV);
      if (request.method === "POST" && url.includes("/areas")) {
        return jsonResponse({ id: 9, title: "Legal" });
      }
      return jsonResponse(projectDetailData());
    });

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");

    await user.type(screen.getByLabelText("New area name"), "Legal");
    await user.click(screen.getByRole("button", { name: "Create area" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) => {
          const req = request as Request;
          return req.method === "POST" && req.url.includes("/api/v1/projects/3/areas");
        }),
      ).toBe(true);
    });
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
    await screen.findByDisplayValue("Website Relaunch");

    await user.click(screen.getByRole("button", { name: "Mark complete" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Reopen" })).toBeInTheDocument();
    });
  });

  it("refreshes the sidebar when completion changes, since its Projects group only lists open ones", async () => {
    const user = userEvent.setup();
    let navFetches = 0;
    let completed = false;
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      if (url.includes("/api/v1/nav")) {
        navFetches += 1;
        return jsonResponse(NAV);
      }
      if (request.method === "PATCH") completed = true;
      return jsonResponse(projectDetailData({ is_completed: completed }));
    });

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");
    const fetchesBeforeClick = navFetches;

    await user.click(screen.getByRole("button", { name: "Mark complete" }));

    await waitFor(() => expect(navFetches).toBeGreaterThan(fetchesBeforeClick));
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
    await screen.findByDisplayValue("Website Relaunch");

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

  it("renames the project once the title actually changes", async () => {
    // The create form only ever set a title, and this page used to offer
    // no way to change it afterward -- unlike AreaRoute's own rename field,
    // which this mirrors: Save stays disabled until the text differs.
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      if (url.includes("/api/v1/nav")) return jsonResponse(NAV);
      if (request.method === "PATCH") {
        return jsonResponse(projectDetailData({ title: "Website Relaunch v2" }));
      }
      return jsonResponse(projectDetailData());
    });

    renderAt("3");
    const titleField = await screen.findByDisplayValue("Website Relaunch");
    const saveName = screen.getByRole("button", { name: "Save name" });
    expect(saveName).toBeDisabled();

    await user.clear(titleField);
    await user.type(titleField, "Website Relaunch v2");
    expect(saveName).toBeEnabled();
    await user.click(saveName);

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) => {
          const req = request as Request;
          return req.method === "PATCH" && req.url.includes("/api/v1/projects/3");
        }),
      ).toBe(true);
    });
  });

  it("sets the project's due date once it actually changes", async () => {
    // Same gap on the other field: due_date was API-writable all along
    // (ProjectUpdateIn) but nothing on this page ever offered to write it.
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      if (url.includes("/api/v1/nav")) return jsonResponse(NAV);
      if (request.method === "PATCH") {
        return jsonResponse(projectDetailData({ due_date: "2026-11-12" }));
      }
      return jsonResponse(projectDetailData());
    });

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");
    const dueField = screen.getByLabelText("Due date");
    const saveDate = screen.getByRole("button", { name: "Save date" });
    expect(saveDate).toBeDisabled();

    fireEvent.change(dueField, { target: { value: "2026-11-12" } });
    await user.click(saveDate);

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) => {
          const req = request as Request;
          return req.method === "PATCH" && req.url.includes("/api/v1/projects/3");
        }),
      ).toBe(true);
    });
  });

  it("flags a past-due project as overdue", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      projectPageFetch(
        projectDetailData({ due_date: "2026-01-01", is_overdue: true }),
      ),
    );

    renderAt("3");

    expect(await screen.findByText("⚠ Overdue")).toBeInTheDocument();
  });

  it("keeps an unsaved project name and due date when the query refetches", async () => {
    // The queryFn seeded both fields, so every refetch re-ran the setters
    // and discarded whatever was being typed.
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(projectPageFetch());

    const { queryClient } = renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");

    await user.clear(screen.getByLabelText("Project name"));
    await user.type(screen.getByLabelText("Project name"), "Website Relaunch v2");
    await user.type(screen.getByLabelText("Due date"), "2026-09-30");
    // Wrapped in act so the refetch's state update is flushed before the
    // assertion -- without it the update is still pending and the test
    // passes over a value that is already lost.
    await act(async () => {
      await queryClient.refetchQueries({ queryKey: ["project", 3] });
    });

    expect(screen.getByLabelText("Project name")).toHaveValue("Website Relaunch v2");
    expect(screen.getByLabelText("Due date")).toHaveValue("2026-09-30");
  });

  it("keeps an unsaved project name while an area is added underneath it", async () => {
    // This page does not need an alt-tab to lose the edit. Four of its
    // mutations call refresh(), which invalidates this very query -- so
    // creating an area while the title was being retyped reseeded the field
    // from the server and the rename was gone, with the success message for
    // the area sitting right beside it.
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      if (url.includes("/api/v1/nav")) return jsonResponse(NAV);
      if (request.method === "POST" && url.includes("/areas")) {
        return jsonResponse({ id: 9, title: "Legal" });
      }
      return jsonResponse(projectDetailData());
    });

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");

    await user.clear(screen.getByLabelText("Project name"));
    await user.type(screen.getByLabelText("Project name"), "Website Relaunch v2");

    await user.type(screen.getByLabelText("New area name"), "Legal");
    await user.click(screen.getByRole("button", { name: "Create area" }));

    await waitFor(() =>
      expect(screen.getByLabelText("New area name")).toHaveValue(""),
    );
    expect(screen.getByLabelText("Project name")).toHaveValue("Website Relaunch v2");
  });
});
