import { render, screen, waitFor } from "@testing-library/react";
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
          lists: [{ id: 1, title: "Programming", url: "/lists/1/" }],
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
              list_id: 2,
            }),
          ],
          lists: [
            { id: 1, title: "Programming", url: "/lists/1/" },
            { id: 2, title: "Home", url: "/lists/2/" },
          ],
        }}
      />,
    );

    await user.type(screen.getByRole("searchbox"), "home");

    expect(screen.getByText("Buy paint")).toBeInTheDocument();
    expect(screen.queryByText("Write tests")).not.toBeInTheDocument();
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
          lists: [{ id: 1, title: "Programming", url: "/lists/1/" }],
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
