import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ArchiveManager as BareArchiveManager } from "./ArchiveManager";
import { apiResponse, sentRequests, task, taskWrite } from "./test/fixtures";

const NAV_SEED = {
  areas: [],
  projects: [],
  archived_count: 1,
  settings_url: "/accounts/settings/",
};

/** As in TaskWorkspace.test: restoring or deleting moves the archive badge and
 *  an area's open count, so these render through a provider. Shadowing the
 *  import leaves the existing render calls alone. */
function ArchiveManager(props: React.ComponentProps<typeof BareArchiveManager>) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>
      <BareArchiveManager {...props} />
    </QueryClientProvider>
  );
}

describe("ArchiveManager", () => {
  beforeEach(() => {
    document.cookie = "csrftoken=test-token";
    vi.restoreAllMocks();
  });

  it("tells the side nav the archive badge has moved", async () => {
    // Restoring drops archived_count and raises an area's open_count, and the
    // badge is rendered by a SideNav that never remounts.
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      taskWrite(task({ status: "completed", archived_at: null })),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    queryClient.setQueryData(["nav"], NAV_SEED);

    render(
      <QueryClientProvider client={queryClient}>
        <BareArchiveManager
          initialData={{
            items: [
              task({
                status: "archived",
                completed_at: "2026-07-24T12:20:00-04:00",
                archived_at: "2026-07-24T12:30:00-04:00",
              }),
            ],
            areas: [{ id: 1, title: "Programming", url: "/areas/1/" }],
            projects: [],
          }}
        />
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Restore" }));

    await waitFor(() =>
      expect(queryClient.getQueryState(["nav"])?.isInvalidated).toBe(true),
    );
  });

  it("restores an archived task after server confirmation", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      taskWrite(task({ status: "completed", archived_at: null })),
    );
    render(
      <ArchiveManager
        initialData={{
          items: [
            task({
              status: "archived",
              completed_at: "2026-07-24T12:20:00-04:00",
              archived_at: "2026-07-24T12:30:00-04:00",
            }),
          ],
          areas: [{ id: 1, title: "Programming", url: "/areas/1/" }],
          projects: [],
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Restore" }));

    await waitFor(() =>
      expect(screen.queryByText("Write tests")).not.toBeInTheDocument(),
    );
    expect(screen.getByText(/restored to Programming/)).toBeInTheDocument();
  });

  it("shows when a task was archived, not when it was created", () => {
    render(
      <ArchiveManager
        initialData={{
          items: [
            task({
              status: "archived",
              created_at: "2026-01-01T00:00:00-04:00",
              completed_at: null,
              archived_at: "2026-07-24T12:30:00-04:00",
            }),
          ],
          areas: [{ id: 1, title: "Programming", url: "/areas/1/" }],
          projects: [],
        }}
      />,
    );

    const row = screen.getByText("Write tests").closest("article")!;
    expect(row.textContent).toContain("Archived");
    expect(row.textContent).toContain("Jul 24, 2026");
    expect(row.textContent).not.toContain("Created");
  });

  it("searches archived task text and list names", async () => {
    const user = userEvent.setup();
    render(
      <ArchiveManager
        initialData={{
          items: [
            task({ status: "archived", archived_at: "2026-07-24T12:30:00-04:00" }),
            task({
              id: 2,
              text: "Buy paint",
              status: "archived",
              archived_at: "2026-07-24T12:30:00-04:00",
              area_id: 2,
            }),
          ],
          areas: [
            { id: 1, title: "Programming", url: "/areas/1/" },
            { id: 2, title: "Home", url: "/areas/2/" },
          ],
          projects: [],
        }}
      />,
    );

    await user.type(screen.getByRole("searchbox"), "home");

    expect(screen.getByText("Buy paint")).toBeInTheDocument();
    expect(screen.queryByText("Write tests")).not.toBeInTheDocument();
  });

  it("shows an archived task's project, the same way it shows its area", () => {
    render(
      <ArchiveManager
        initialData={{
          items: [
            task({
              id: 1,
              text: "Order cabinets",
              status: "archived",
              archived_at: "2026-07-24T12:30:00-04:00",
              project_id: 7,
            }),
            task({
              id: 2,
              text: "Pay rent",
              status: "archived",
              archived_at: "2026-07-24T12:30:00-04:00",
            }),
          ],
          areas: [{ id: 1, title: "Programming", url: "/areas/1/" }],
          projects: [{ id: 7, title: "Kitchen remodel", url: "/areas/1/" }],
        }}
      />,
    );

    const withProject = screen.getByText("Order cabinets").closest("article")!;
    const withoutProject = screen.getByText("Pay rent").closest("article")!;
    expect(
      within(withProject).getByRole("link", { name: "Kitchen remodel" }),
    ).toHaveAttribute("href", "/areas/1/");
    expect(
      within(withoutProject).queryByText("Kitchen remodel"),
    ).not.toBeInTheDocument();
  });

  it("requires confirmation before permanent deletion", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      apiResponse({ deleted: 1 }),
    );
    render(
      <ArchiveManager
        initialData={{
          items: [
            task({
              status: "archived",
              completed_at: "2026-07-24T12:20:00-04:00",
              archived_at: "2026-07-24T12:30:00-04:00",
            }),
          ],
          areas: [{ id: 1, title: "Programming", url: "/areas/1/" }],
          projects: [],
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("This cannot be undone");
    expect(fetch).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Delete permanently" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(await sentRequests(fetch as never)).toContainEqual({
      path: "/api/v1/tasks/1",
      method: "DELETE",
      body: "",
    });
  });
});
