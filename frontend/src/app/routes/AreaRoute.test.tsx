import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { AreaRoute } from "./AreaRoute";
import { task } from "../../test/fixtures";

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

function listDetailData(overrides: Record<string, unknown> = {}) {
  return {
    area: {
      id: 7,
      title: "Programming",
      create_item_url: "/api/areas/7/items/",
      reorder_url: "/api/areas/7/items/reorder/",
    },
    items: [task({ text: "Write tests" })],
    project: null,
    archived_count: 0,
    archive_url: "/archive/",
    ...overrides,
  };
}

/* The Area page fetches the caller's projects for its "add to a project"
   picker whenever the area has none of its own yet -- project-workspace-plan.md.
   Every mock below has to answer that request with an array or the picker
   throws mid-render and takes the whole route with it. */
function areaPageFetch(data: object = listDetailData()) {
  return (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    if (url.includes("/api/v1/projects")) return jsonResponse([]);
    return jsonResponse(data);
  };
}

function renderAt(areaId: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/areas/${areaId}`]}>
        <Routes>
          <Route path="/areas/:areaId" element={<AreaRoute />} />
          <Route path="/agenda" element={<p>Agenda page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AreaRoute", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    document.cookie = "csrftoken=test-token";
  });

  it("renders the list's title and items once the query resolves", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(areaPageFetch());

    renderAt("7");

    expect(await screen.findByText("Write tests")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Programming")).toBeInTheDocument();
  });

  it("shows an error state when the request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({ detail: "nope" }, false),
    );

    renderAt("7");

    // B2.1: a 500 is the retryable kind of failure, so the person is
    // offered a retry rather than told their work is gone.
    expect(await screen.findByText(/Couldn't reach Clarice/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("only offers to save the area name once it's actually changed", async () => {
    // ui-second-pass-plan.md F5: "a rename that looks like an edit field
    // until you notice the button." A disabled Save says there is nothing
    // to save yet, rather than looking like a live field with an inert
    // button sitting beside it.
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(areaPageFetch());

    renderAt("7");
    await screen.findByText("Write tests");

    const save = screen.getByRole("button", { name: "Save name" });
    expect(save).toBeDisabled();

    await user.clear(screen.getByLabelText("Area name"));
    await user.type(screen.getByLabelText("Area name"), "Home projects");

    expect(save).toBeEnabled();
  });

  it("shows which project the area belongs to", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      areaPageFetch(
        listDetailData({
          project: { id: 3, title: "Website Relaunch", url: "/app/projects/3" },
        }),
      ),
    );

    renderAt("7");

    expect(await screen.findByText("Website Relaunch")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Remove from project" }),
    ).toBeInTheDocument();
  });

  it("offers to add the area to a project when it has none", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "PATCH" && request.url.includes("/project")) {
        return jsonResponse({ id: 7, title: "Programming" });
      }
      if (request.url.includes("/api/v1/projects")) {
        return jsonResponse([
          { id: 3, title: "Website Relaunch", areas: [], open_task_count: 0 },
        ]);
      }
      return jsonResponse(listDetailData());
    });

    renderAt("7");
    await screen.findByText("Write tests");

    await user.selectOptions(screen.getByLabelText("Add to a project"), "3");
    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) =>
          (request as Request).url.includes("/api/v1/areas/7/project"),
        ),
      ).toBe(true);
    });
  });

  it("keeps the area-destroying action away from the project-scoped ones", async () => {
    // ui-second-pass-plan.md F5: "two destructive actions with different
    // scopes on one screen." Deleting the area takes every task with it;
    // deleting a project leaves its tasks in place. Asserting DOM order
    // rather than a screenshot: Delete area should read after the task
    // list, not sit beside Projects' own per-row Delete project buttons.
    vi.spyOn(globalThis, "fetch").mockImplementation(areaPageFetch());

    renderAt("7");
    await screen.findByText("Write tests");

    const tasksHeading = screen.getByRole("heading", { name: "Tasks" });
    const deleteArea = screen.getByRole("button", { name: "Delete area" });
    expect(
      tasksHeading.compareDocumentPosition(deleteArea) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("deletes the list and returns to the agenda after confirming", async () => {
    const user = userEvent.setup();
    // openapi-fetch calls fetch(request) with a single Request object,
    // not fetch(url, init) -- the method lives on the request itself.
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "DELETE") {
        return jsonResponse({ deleted: 7 });
      }
      if (request.url.includes("/api/v1/projects")) return jsonResponse([]);
      return jsonResponse(listDetailData());
    });

    renderAt("7");
    await screen.findByText("Write tests");

    await user.click(screen.getByRole("button", { name: "Delete area" }));
    await user.click(screen.getByRole("button", { name: "Delete area permanently" }));

    await waitFor(() => {
      expect(screen.getByText("Agenda page")).toBeInTheDocument();
    });
    const deleteCall = fetchMock.mock.calls.find(
      ([request]) => (request as Request).method === "DELETE",
    );
    expect(deleteCall?.[0]).toEqual(
      expect.objectContaining({ url: expect.stringContaining("/api/v1/areas/7") }),
    );
  });
});
