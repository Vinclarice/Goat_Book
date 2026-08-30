import { act, render, screen, waitFor } from "@testing-library/react";
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
      <MemoryRouter initialEntries={[`/areas/${areaId}`]}>
        <Routes>
          <Route path="/areas/:areaId" element={<AreaRoute />} />
          <Route path="/agenda" element={<p>Agenda page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
    ),
  };
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

  it("counts what deleting the area would destroy, by state", async () => {
    // The dialog said "all of its tasks" and nothing about how many, so the
    // one number that decides whether this is a tidy-up or a loss was the one
    // it withheld. Item.list is CASCADE with no status filter and delete_list
    // has no archive step, so completed and archived work goes too.
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      areaPageFetch(
        listDetailData({
          items: [
            task({ id: 1, text: "Write tests" }),
            task({ id: 2, text: "Read the docs" }),
            task({ id: 3, text: "Ship it", status: "completed" }),
          ],
          archived_count: 4,
        }),
      ),
    );

    renderAt("7");
    await screen.findByText("Write tests");

    await user.click(screen.getByRole("button", { name: "Delete area" }));

    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("7 tasks");
    expect(dialog).toHaveTextContent("2 active");
    expect(dialog).toHaveTextContent("1 completed");
    expect(dialog).toHaveTextContent("4 archived");
  });

  it("says that past weeks change, and that finished reviews do not", async () => {
    // The other half of what was withheld. completed_in_week queries live
    // with no snapshot, so a hard-deleted task leaves a past week's completed
    // list retroactively -- but recent_weeks prefers the stamped
    // recorded_planned_met/_total for a week whose review was completed, so a
    // finished week's headline holds. Both halves are true and saying only
    // the alarming one would be its own kind of wrong.
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      areaPageFetch(
        listDetailData({
          items: [task({ id: 3, text: "Ship it", status: "completed" })],
        }),
      ),
    );

    renderAt("7");
    await screen.findByText("Ship it");

    await user.click(screen.getByRole("button", { name: "Delete area" }));

    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent(/past weeks|weeks you never reviewed/i);
    expect(dialog).toHaveTextContent(/already finished|stamped/i);
  });

  it("does not talk about history when there is none to lose", async () => {
    // An area of purely active work is the ordinary case, and a paragraph
    // about weekly reviews there is noise that trains people to skip the
    // dialog -- which is what makes the warning worthless on the day it
    // matters.
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      areaPageFetch(
        listDetailData({
          items: [task({ id: 1, text: "Write tests" })],
          archived_count: 0,
        }),
      ),
    );

    renderAt("7");
    await screen.findByText("Write tests");

    await user.click(screen.getByRole("button", { name: "Delete area" }));

    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("1 task");
    expect(dialog).not.toHaveTextContent(/review/i);
    // And no breakdown of zeroes, which is the other half of the same point.
    expect(dialog).not.toHaveTextContent(/0 completed/);
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

  it("keeps an unsaved area name when the query refetches underneath it", async () => {
    // Same bug PreferencesRoute already fixed, in a route that never got the
    // guard: the queryFn seeded `title`, so it re-ran on every refetch.
    // Joining a project calls refetch() directly, so this does not even need
    // an alt-tab -- renaming an area and then adding it to a project
    // silently reverted the rename.
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(areaPageFetch());

    const { queryClient } = renderAt("7");
    await screen.findByDisplayValue("Programming");

    await user.clear(screen.getByLabelText("Area name"));
    await user.type(screen.getByLabelText("Area name"), "Deep work");
    // Wrapped in act so the refetch's state update is flushed before the
    // assertion -- without it the update is still pending and the test
    // passes over a value that is already lost.
    await act(async () => {
      await queryClient.refetchQueries({ queryKey: ["area", 7] });
    });

    expect(screen.getByLabelText("Area name")).toHaveValue("Deep work");
  });
});
