import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ArchiveManager } from "./ArchiveManager";
import { task } from "./test/fixtures";

function jsonResponse(data: object) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve(data),
  } as Response);
}

describe("ArchiveManager", () => {
  beforeEach(() => {
    document.cookie = "csrftoken=test-token";
    vi.restoreAllMocks();
  });

  it("restores an archived task after server confirmation", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      jsonResponse({
        data: task({ status: "completed", archived_at: null }),
      }),
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
      jsonResponse({ data: { deleted: 1 } }),
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
    expect(fetch).toHaveBeenCalledWith(
      "/api/items/1/",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
