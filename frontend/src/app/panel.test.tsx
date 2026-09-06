import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";

import { Panel, PanelLink, backgroundFor } from "./panel";

/**
 * The panel mechanic — app-overhaul-plan.md increment 1.
 *
 * Rule 2 is that detail *opens* rather than navigates: it keeps a URL, a deep
 * link and the back button, and loses its nav entry. These tests hold the
 * three halves of that sentence separately, because each one is a different
 * way for the mechanic to be quietly wrong.
 */

function Probe() {
  const location = useLocation();
  return <div data-testid="pathname">{location.pathname}</div>;
}

describe("backgroundFor", () => {
  it("leaves an ordinary page alone", () => {
    // A path that is not a panel has no background, and the caller renders
    // one set of routes as it always did. Getting this wrong would render
    // every page twice.
    expect(backgroundFor({ pathname: "/day", state: null })).toBeNull();
  });

  it("renders a panel over the page it was opened from", () => {
    const background = backgroundFor({
      pathname: "/tasks/1",
      state: { background: { pathname: "/pool", search: "", hash: "" } },
    });

    expect(background?.pathname).toBe("/pool");
  });

  it("gives a deep-linked panel the day to sit on", () => {
    // Somebody's bookmark, or a link from an email. There is no page behind
    // it, so the mechanic supplies one -- and it is the day, because
    // increment 7 makes the day the only page there is. The alternative was a
    // second, full-page presentation of task detail, which is precisely
    // coherence-audit-2026-08-30.md's F3: what you can do to a task should
    // not depend on which page you met it on.
    expect(backgroundFor({ pathname: "/tasks/1", state: null })?.pathname).toBe(
      "/day",
    );
  });
});

describe("PanelLink", () => {
  it("remembers the page it was clicked from", async () => {
    render(
      <MemoryRouter initialEntries={["/pool"]}>
        <Probe />
        <Routes>
          <Route
            path="/pool"
            element={<PanelLink to="/tasks/1">Wash the car</PanelLink>}
          />
          <Route path="/tasks/:taskId" element={<p>the task</p>} />
        </Routes>
      </MemoryRouter>,
    );

    await userEvent.click(screen.getByRole("link", { name: "Wash the car" }));

    expect(screen.getByTestId("pathname")).toHaveTextContent("/tasks/1");
  });
});

describe("Panel", () => {
  function renderPanel(onClose = vi.fn()) {
    render(
      <MemoryRouter initialEntries={["/tasks/1"]}>
        <Panel title="Wash the car" onClose={onClose}>
          <button type="button">Complete</button>
        </Panel>
      </MemoryRouter>,
    );
    return onClose;
  }

  it("names itself to a screen reader", async () => {
    renderPanel();

    // Radix will warn and the panel is unusable without one. The title is the
    // task's own text rather than "Task", so somebody who opens three of these
    // in a row can tell them apart.
    expect(
      await screen.findByRole("dialog", { name: "Wash the car" }),
    ).toBeInTheDocument();
  });

  it("puts focus inside itself when it opens", async () => {
    renderPanel();

    // Not a nicety: a panel that opens without moving focus leaves a keyboard
    // user's cursor on the page behind it, tabbing through content they can no
    // longer see.
    await waitFor(() =>
      expect(
        screen.getByRole("dialog", { name: "Wash the car" }),
      ).toContainElement(document.activeElement as HTMLElement),
    );
  });

  it("closes on Escape", async () => {
    const onClose = renderPanel();

    await screen.findByRole("dialog");
    await userEvent.keyboard("{Escape}");

    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("offers a close control that says what it closes", async () => {
    const onClose = renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: /close/i }),
    );

    expect(onClose).toHaveBeenCalled();
  });

  it("keeps its content reachable", async () => {
    renderPanel();

    // The panel is a container, not a replacement. What was a page is still
    // the same markup inside it -- which is what lets TaskDetailRoute keep its
    // 930 lines of tests.
    expect(
      await screen.findByRole("button", { name: "Complete" }),
    ).toBeInTheDocument();
  });
});
