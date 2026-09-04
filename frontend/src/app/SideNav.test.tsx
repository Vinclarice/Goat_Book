import { render, screen, waitFor, within } from "@testing-library/react";
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
  settings_url: "/accounts/settings/",
  mind_url: "/mind/",
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
            <Route path="/projects" element={<p>Projects index page</p>} />
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

  it("no longer lists Areas at all", async () => {
    // ~~"lists every list with its open and overdue counts"~~ --
    // **superlists-2.0-plan.md increment 8**: *Areas leave the navigation and
    // the composer.* Filing was the toll this redesign removes, and a rail
    // listing the places to file into is the strongest invitation to pay it.
    // Asserted as an absence, because a nav that quietly keeps a dead group is
    // how `/capture/` and the Inbox both outlived themselves here.
    renderNav();

    await screen.findByRole("navigation", { name: "Contents" });
    expect(screen.queryByText("Areas")).toBeNull();
    expect(screen.queryByText("Programming")).toBeNull();
    expect(screen.queryByLabelText("2 overdue")).toBeNull();
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

  it("routes the Projects heading to the index of every project", async () => {
    // Vince's call: a central landing page, reachable from the sidebar,
    // where a completed project stays visible -- the group below only
    // ever lists open ones.
    const user = userEvent.setup();
    renderNav();

    await user.click(await screen.findByRole("link", { name: "Projects" }));

    expect(await screen.findByText("Projects index page")).toBeInTheDocument();
  });

  it("says so when there are no open projects", async () => {
    renderNav();

    expect(await screen.findByText("No projects yet.")).toBeInTheDocument();
  });

  it("no longer offers the core's surfaces, because ViewNav does", async () => {
    // Today, Agenda, Review and Archive were a "Views" group in here, which is
    // what forced this rail to mean two things at once -- somewhere to switch
    // surface and a list of what the core holds. They are a sub-nav under the
    // app bar now, and ViewNav.test.tsx covers them there.
    renderNav();
    await screen.findByText("No projects yet.");

    // Scoped to the rail, because AppLayout renders ViewNav too and these
    // links are very much on the page -- the claim is about where they are,
    // not whether they exist. An unscoped query here would fail for the right
    // reason today and pass for the wrong one the moment ViewNav moved.
    const rail = within(screen.getByRole("navigation", { name: "Contents" }));

    expect(rail.queryByRole("link", { name: "Review" })).toBeNull();
    expect(rail.queryByRole("link", { name: /Archive/ })).toBeNull();
    expect(rail.queryByRole("link", { name: "Today" })).toBeNull();
  });

  it("carries no account controls, because the app bar does", async () => {
    // Preferences and Log out both moved to the server-rendered app bar, which
    // reaches the Django pages and /mind/ as well as this shell. Asserted as an
    // absence rather than deleted quietly: two logout controls with different
    // mechanics is the defect that forced the move, and a second one reappearing
    // here would be the same defect returning.
    renderNav();
    await screen.findByText("No projects yet.");

    expect(screen.queryByRole("link", { name: "Preferences" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Log out" })).toBeNull();
  });

  it("no longer offers the Inbox or Ideas at all", async () => {
    // Heron 4b deleted both, and this asserts their absence rather than simply
    // dropping the tests that covered them: a nav entry pointing at a route
    // that 404s is the kind of thing nobody notices until they click it.
    renderNav();
    await screen.findByText("No projects yet.");

    expect(screen.queryByRole("link", { name: /Inbox/ })).toBeNull();
    expect(screen.queryByRole("link", { name: "Ideas" })).toBeNull();
  });

  it("does not switch cores, because that is the app bar's job", async () => {
    // Second Mind stood in this group. It moved to the bar, which is
    // server-rendered and therefore present at /mind/ too -- so the crossing is
    // no longer one-way. The rule that travelled with it is asserted where it
    // now applies, in test_app_bar.py: that entry must never grow a count.
    renderNav();
    await screen.findByText("No projects yet.");

    expect(screen.queryByRole("link", { name: /Second Mind/ })).toBeNull();
  });

  it("renders the nav before its data arrives", () => {
    // A nav that appears a beat after the page makes every navigation look
    // like a layout shift, so the shell renders immediately.
    renderNav();

    // "Contents" rather than "Main": there is no single main navigation now,
    // which is the point of the split.
    expect(
      screen.getByRole("navigation", { name: "Contents" }),
    ).toBeInTheDocument();
    // ~~"Areas"~~ retired at increment 8; Projects is what the rail still
    // renders before its data arrives.
    expect(screen.getByText("Projects")).toBeInTheDocument();
  });

  it("closes the narrow-screen disclosure after navigating", async () => {
    const user = userEvent.setup();
    renderNav();
    const disclosure = document.querySelector("details") as HTMLDetailsElement;
    disclosure.open = true;

    await user.click(await screen.findByRole("link", { name: "Projects" }));

    await waitFor(() => expect(disclosure.open).toBe(false));
  });
});
