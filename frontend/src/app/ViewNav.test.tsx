import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ViewNav } from "./ViewNav";

/** The task core's sub-nav.
 *
 * These four were a "Views" group inside the side rail until the rail became
 * contents. The tests came with them: a surface nobody can reach has shipped
 * twice in this project's history, and the active marker was silently lost
 * once already when a token rename left the CSS unresolvable.
 */

function jsonResponse(data: object) {
  const body = JSON.stringify(data);
  return Promise.resolve({
    ok: true,
    status: 200,
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

const NAV = { areas: [], projects: [], archived_count: 4, mind_url: "/mind/" };

function renderNav(at = "/day") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[at]}>
        <ViewNav />
        <Routes>
          <Route path="/day" element={<p>Day page</p>} />
          <Route path="/pool" element={<p>Pool page</p>} />
          <Route path="/review" element={<p>Review page</p>} />
          <Route path="/archive" element={<p>Archive page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ViewNav", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse(NAV));
  });

  it("offers every surface of the task core", async () => {
    renderNav();

    const nav = screen.getByRole("navigation", { name: "Views" });
    // The list is the point, not an example. Calendar and Bills shipped
    // behind a single link each on the Day page and were not findable at
    // all; this test is what should have been consulted about whether they
    // were surfaces, and adding one here is what makes that true.
    //
    // **Bills became Money on August 27, 2026**, when the surface widened
    // past bills -- income next. The entry is renamed here rather than added,
    // because it is the same surface under a word that survives a salary line.
    for (const name of [
      "Today",
      // ~~"Agenda"~~ -- retired into the day at increment 8. The list below is
      // the point of this test, so removing an entry belongs here and not only
      // in the component: a surface that stops existing has to stop being
      // asserted, deliberately.
      "Pool",
      "Review",
      "Calendar",
      "Money",
      /Archive/,
    ]) {
      expect(
        nav.querySelector("a") && screen.getByRole("link", { name }),
      ).toBeInTheDocument();
    }
  });

  it("marks the surface you are on", async () => {
    renderNav("/archive");

    const archive = screen.getByRole("link", { name: /Archive/ });
    // The class carries the marker, so this asserts the token-backed class is
    // applied rather than that it renders a particular colour -- jsdom applies
    // no stylesheet and could not see the colour either way.
    expect(archive.className).toMatch(/border-accent/);
  });

  it("does not mark a surface you are not on", () => {
    renderNav("/archive");

    expect(screen.getByRole("link", { name: "Today" }).className).toMatch(
      /border-transparent/,
    );
  });

  it("offers the weekly review from every surface", async () => {
    // In its own test because the Daily Page spent five slices reachable only
    // by typing its URL, and routine creation had no surface at all until
    // Crane 2 slice 3. A review nobody can open would be the same gap again.
    const user = userEvent.setup();
    renderNav();

    await user.click(screen.getByRole("link", { name: "Review" }));

    expect(await screen.findByText("Review page")).toBeInTheDocument();
  });

  it("shows how much is in the archive, once the count arrives", async () => {
    renderNav();

    expect(
      await screen.findByRole("link", { name: /Archive\s*4/ }),
    ).toBeInTheDocument();
  });

  it("renders before its data does", () => {
    // A nav that appears a beat after the page makes every navigation look
    // like a layout shift.
    renderNav();

    expect(screen.getByRole("navigation", { name: "Views" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Today" })).toBeInTheDocument();
  });

  it("no longer offers the Agenda, which retired into the day", async () => {
    // superlists-2.0-plan.md increment 8. Asserted as an absence, because a
    // nav that quietly keeps a dead surface is how `/capture/` and the Inbox
    // both outlived themselves in this codebase.
    renderNav();

    expect(screen.queryByRole("link", { name: "Agenda" })).toBeNull();
  });
});
