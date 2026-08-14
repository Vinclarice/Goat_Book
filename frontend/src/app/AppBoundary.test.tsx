import { render, screen } from "@testing-library/react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

import { AppBoundary } from "./AppBoundary";

/** Defect 5 of commercial-blueprint.md: any render exception is a white screen.
 *
 * The only error boundary in the codebase was `MountBoundary` in
 * `src/main.tsx` -- the island entry point, which no template references any
 * more. `src/app/main.tsx` is what actually ships, and it mounted the router
 * bare. So a single thrown exception anywhere in a route replaced the whole
 * application with a blank page: no message, no way back, and nothing to
 * distinguish it from a failure to load at all.
 *
 * These assert the two things a boundary is for. It has to *catch* -- proven
 * by rendering a component that throws, which React would otherwise let
 * unmount the entire tree -- and it has to leave the person somewhere they can
 * act, rather than somewhere they can only reload and hope.
 */

function Boom(): never {
  throw new Error("the agenda exploded");
}

describe("AppBoundary", () => {
  beforeEach(() => {
    // React logs caught errors to console.error by design. Silenced so a
    // passing run is quiet, and restored after, so a *real* unexpected error
    // in another test is still loud.
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders its children when nothing is wrong", () => {
    render(
      <AppBoundary>
        <p>the agenda</p>
      </AppBoundary>,
    );

    expect(screen.getByText("the agenda")).toBeInTheDocument();
  });

  it("shows a message instead of a blank page when a child throws", () => {
    render(
      <AppBoundary>
        <Boom />
      </AppBoundary>,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("offers a way back rather than only a reload", () => {
    render(
      <AppBoundary>
        <Boom />
      </AppBoundary>,
    );

    expect(screen.getByRole("link", { name: /agenda/i })).toHaveAttribute(
      "href",
      "/app",
    );
  });

  it("does not put the error text on screen", () => {
    /* The message is for the console and for Sentry, not for a person who
     * cannot act on it. "the agenda exploded" tells them nothing and reads as
     * the application blaming itself at them. */
    render(
      <AppBoundary>
        <Boom />
      </AppBoundary>,
    );

    expect(screen.queryByText(/exploded/)).not.toBeInTheDocument();
  });

  it("still reports the error where it can be found", () => {
    render(
      <AppBoundary>
        <Boom />
      </AppBoundary>,
    );

    expect(console.error).toHaveBeenCalled();
  });
});
