import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { AppLayout } from "./AppLayout";

/** The bug these exist for.
 *
 * The nav lives inside a <details> that nothing ever opened, while the CSS
 * hid its <summary> above the breakpoint -- so at desktop width the nav was
 * sealed inside a closed disclosure with no handle to open it. Browsers that
 * skip rendering a closed disclosure's contents (Firefox) collapsed it to
 * zero height and left an empty 210px gutter; Chromium happened to paint it
 * anyway, which is why it shipped.
 *
 * jsdom has no paint model, so these cannot assert visibility. They assert
 * the invariant that was actually violated: above the breakpoint the
 * disclosure is open, and it stays open. Proving what a person sees needs
 * the browser-level coverage of Bittern B2.2.
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

const NAV = {
  areas: [
    { id: 1, title: "Programming", open_count: 5, overdue_count: 2, color_key: "sky" },
  ],
  archived_count: 4,
  settings_url: "/accounts/settings/",
};

/** Pretend the viewport is wide (or not) for the layout's own query.
 *
 * `matches` is a getter over shared state rather than a fixed value, so
 * resizeTo() changes the answer on the very object the component is already
 * holding -- swapping in a fresh matchMedia would leave it reading a stale
 * one.
 */
function setViewport({ wide }: { wide: boolean }) {
  const listeners = new Set<() => void>();
  const state = { wide };
  window.matchMedia = ((query: string) =>
    ({
      // Only the layout's min-width query flips; anything else (the theme's
      // prefers-color-scheme, say) keeps the suite's default.
      get matches() {
        return query.includes("min-width") ? state.wide : false;
      },
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: (_: string, fn: () => void) => listeners.add(fn),
      removeEventListener: (_: string, fn: () => void) => listeners.delete(fn),
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList) as typeof window.matchMedia;
  return {
    resizeTo(next: boolean) {
      state.wide = next;
      listeners.forEach((fn) => fn());
    },
  };
}

function renderLayout(initialPath = "/agenda") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/agenda" element={<p>Agenda page</p>} />
            <Route path="/areas/:areaId" element={<p>Area page</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function disclosure() {
  return document.querySelector("details") as HTMLDetailsElement;
}

describe("AppLayout disclosure", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse(NAV));
  });

  it("opens the disclosure above the breakpoint", () => {
    // The whole defect in one assertion: the summary is hidden by CSS up
    // here, so a closed disclosure is one nothing can ever reopen.
    setViewport({ wide: true });

    renderLayout();

    expect(disclosure().open).toBe(true);
  });

  it("leaves it closed below the breakpoint", () => {
    setViewport({ wide: false });

    renderLayout();

    expect(disclosure().open).toBe(false);
  });

  it("keeps it open across navigation above the breakpoint", async () => {
    // The close-on-navigate behaviour is for phones. Applied at desktop
    // width it re-seals the nav on the first click.
    const user = userEvent.setup();
    setViewport({ wide: true });
    renderLayout();

    await user.click(await screen.findByText("Programming"));

    expect(await screen.findByText("Area page")).toBeInTheDocument();
    expect(disclosure().open).toBe(true);
  });

  it("still closes after navigating below the breakpoint", async () => {
    const user = userEvent.setup();
    setViewport({ wide: false });
    renderLayout();
    disclosure().open = true;

    await user.click(await screen.findByText("Programming"));

    expect(await screen.findByText("Area page")).toBeInTheDocument();
    expect(disclosure().open).toBe(false);
  });

  it("opens the disclosure when the window grows past the breakpoint", () => {
    const viewport = setViewport({ wide: false });
    renderLayout();
    expect(disclosure().open).toBe(false);

    // Resizing a narrow window wide would otherwise leave the nav sealed,
    // since the summary disappears at the same moment.
    viewport.resizeTo(true);

    expect(disclosure().open).toBe(true);
  });
});
