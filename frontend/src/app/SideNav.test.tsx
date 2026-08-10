import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { AppLayout } from "./AppLayout";

function jsonResponse(data: object, ok = true) {
  const body = JSON.stringify(data);
  return Promise.resolve({
    ok,
    status: ok ? 200 : 500,
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

const NAV = {
  areas: [
    {
      id: 1,
      title: "Programming",
      open_count: 5,
      overdue_count: 2,
      color_key: "sky",
    },
    {
      id: 2,
      title: "Home",
      open_count: 1,
      overdue_count: 0,
      color_key: "sage",
    },
  ],
  projects: [],
  archived_count: 4,
  inbox_count: 3,
  settings_url: "/accounts/settings/",
  inbox_url: "/capture/",
  ideas_url: "/capture/ideas/",
};

function renderNav(initialPath = "/agenda") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/agenda" element={<p>Agenda page</p>} />
            <Route path="/review" element={<p>Review page</p>} />
            <Route path="/areas/:areaId" element={<p>Area page</p>} />
            <Route path="/projects/:projectId" element={<p>Project page</p>} />
            <Route path="/archive" element={<p>Archive page</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SideNav", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse(NAV));
  });

  it("lists every list with its open and overdue counts", async () => {
    renderNav();

    expect(await screen.findByText("Programming")).toBeInTheDocument();
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByLabelText("2 overdue")).toBeInTheDocument();
  });

  it("lists open projects in their own group, flat across areas", async () => {
    // ui-second-pass-plan.md F3, Vince's call: a top-level Projects group,
    // not nested under Areas.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({
        ...NAV,
        projects: [
          { id: 9, title: "Kitchen remodel", open_task_count: 3 },
        ],
      }),
    );
    renderNav();

    expect(await screen.findByText("Kitchen remodel")).toBeInTheDocument();
    const heading = screen.getByRole("heading", { name: "Projects" });
    expect(
      heading.closest("div")?.textContent,
    ).toContain("Kitchen remodel");
  });

  it("routes a project through the SPA router, to its own page", async () => {
    // project-workspace-plan.md: a project has its own page now, closing
    // the gap that used to send every click back to a parent Area instead.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({
        ...NAV,
        projects: [
          { id: 9, title: "Kitchen remodel", open_task_count: 3 },
        ],
      }),
    );
    const user = userEvent.setup();
    renderNav();

    await user.click(await screen.findByText("Kitchen remodel"));

    expect(await screen.findByText("Project page")).toBeInTheDocument();
  });

  it("says so when there are no open projects", async () => {
    renderNav();

    expect(await screen.findByText("No projects yet.")).toBeInTheDocument();
  });

  it("navigates to a list rather than filtering the agenda", async () => {
    const user = userEvent.setup();
    renderNav();

    await user.click(await screen.findByText("Programming"));

    // The whole point of the split: the nav means the same thing on every
    // page, so it navigates and the header chips filter.
    expect(await screen.findByText("Area page")).toBeInTheDocument();
  });

  it("offers the weekly review from every page", async () => {
    // In this slice rather than a later one. The Daily Page spent five
    // slices reachable only by typing its URL and routine creation had no
    // surface at all until Crane 2 slice 3; a review nobody can open is
    // the same gap a third time.
    const user = userEvent.setup();
    renderNav();

    await user.click(await screen.findByRole("link", { name: "Review" }));

    expect(await screen.findByText("Review page")).toBeInTheDocument();
  });

  it("marks the current view as active", async () => {
    renderNav("/archive");

    const archive = await screen.findByRole("link", { name: /Archive/ });
    expect(archive.className).toMatch(/active/);
  });

  it("links the inbox out of the SPA and shows what's waiting", async () => {
    renderNav();
    // Wait for the payload before asserting: the loading shell renders an
    // Inbox link too, with the same fallback href, so asserting on the
    // first match would pass without the data ever arriving.
    await screen.findByText("Programming");

    const inbox = screen.getByRole("link", { name: /Inbox/ });
    // A Django page, so a real href rather than a router link.
    expect(inbox).toHaveAttribute("href", "/capture/");
    expect(inbox).toHaveTextContent("3");
  });

  it("links out to the ideas page, without a count", async () => {
    renderNav();
    await screen.findByText("Programming");

    const ideas = screen.getByRole("link", { name: "Ideas" });

    expect(ideas).toHaveAttribute("href", "/capture/ideas/");
    // Deliberately bare: a pile of ideas isn't a backlog to work down, and
    // a number beside it would read as pressure to empty it.
    expect(ideas).toHaveTextContent(/^Ideas$/);
  });

  it("renders the nav before its data arrives", () => {
    // A nav that appears a beat after the page makes every navigation look
    // like a layout shift, so the shell renders immediately.
    renderNav();

    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(screen.getByText("Agenda")).toBeInTheDocument();
  });

  it("offers a way out of the session", async () => {
    // Before B2 the only logout lived in a Django template the SPA never
    // renders, so every /app route was a place you could not leave.
    renderNav();

    expect(
      await screen.findByRole("button", { name: "Log out" }),
    ).toBeInTheDocument();
  });

  it("posts to the logout endpoint and then leaves the app", async () => {
    const user = userEvent.setup();
    const assign = vi.fn();
    vi.spyOn(window, "location", "get").mockReturnValue({
      ...window.location,
      assign,
    } as unknown as Location);
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const request = input as Request;
        if (request.url.includes("/me/logout")) {
          return Promise.resolve({
            ok: true,
            status: 204,
            headers: new Headers(),
            text: () => Promise.resolve(""),
            json: () => Promise.resolve(null),
            clone() {
              return this;
            },
          } as unknown as Response);
        }
        return jsonResponse(NAV);
      });
    renderNav();

    await user.click(await screen.findByRole("button", { name: "Log out" }));

    await waitFor(() => expect(assign).toHaveBeenCalledWith("/"));
    const logoutCalls = fetchMock.mock.calls.filter(([request]) =>
      (request as Request).url.includes("/me/logout"),
    );
    // Exactly once: a double-submit would race two session invalidations.
    expect(logoutCalls).toHaveLength(1);
    expect((logoutCalls[0][0] as Request).method).toBe("POST");
  });

  it("keeps you where you are when logging out fails", async () => {
    // A failed logout means the session is still alive. Navigating anyway
    // would look like it worked and leave the session open behind you.
    const user = userEvent.setup();
    const assign = vi.fn();
    vi.spyOn(window, "location", "get").mockReturnValue({
      ...window.location,
      assign,
    } as unknown as Location);
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.url.includes("/me/logout")) {
        return jsonResponse({ detail: "nope" }, false);
      }
      return jsonResponse(NAV);
    });
    renderNav();

    await user.click(await screen.findByRole("button", { name: "Log out" }));

    expect(await screen.findByText(/Couldn't log out/)).toBeInTheDocument();
    expect(assign).not.toHaveBeenCalled();
  });

  it("closes the narrow-screen disclosure after navigating", async () => {
    const user = userEvent.setup();
    renderNav();
    const disclosure = document.querySelector("details") as HTMLDetailsElement;
    disclosure.open = true;

    await user.click(await screen.findByText("Programming"));

    await waitFor(() => expect(disclosure.open).toBe(false));
  });
});
