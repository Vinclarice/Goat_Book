import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router";

import { AppRoutes } from "./AppRoutes";

/**
 * The route table itself, which is where B2.1's first defect lived: /app/
 * had no index route, so a direct visit matched nothing and rendered an
 * empty shell -- a blank page that looks exactly like a broken deploy.
 *
 * Asserting on the resolved pathname rather than on a page's content keeps
 * these honest about what they test. Whether the day renders is DayRoute's
 * business; whether "/" resolves to it is this table's.
 */
function PathnameProbe() {
  const location = useLocation();
  return <div data-testid="pathname">{location.pathname}</div>;
}

function renderAt(pathname: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[pathname]}>
        <PathnameProbe />
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AppRoutes", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // Every route under test fetches on mount. What it returns doesn't
    // matter here -- only that nothing escapes as an unhandled rejection.
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("not used"));
  });

  it("sends a bare /app/ visit to the day, without asking anything first", async () => {
    // B2.1's defect was a blank page, so the case that matters most is the one
    // where nothing answers: it must still land on a surface. fetch is
    // rejected by the beforeEach above, which is exactly that case -- and
    // since superlists-2.0-plan.md increment 8 there is nothing to ask,
    // because there is one surface to land on.
    renderAt("/");

    await waitFor(() =>
      expect(screen.getByTestId("pathname")).toHaveTextContent("/day"),
    );
  });

  it("sends a bookmarked Agenda to the day rather than to a 404", async () => {
    // ~~"sends a bare /app/ visit to the landing surface the server names"~~
    // and ~~"says something while it works out where to send you"~~ --
    // **superlists-2.0-plan.md increment 8 retired the Agenda into the day**,
    // so there is no preference to follow and no answer to wait for. Both
    // tests are replaced by this one, which holds the thing that still
    // matters: a path somebody bookmarked lands somewhere real.
    renderAt("/agenda");

    await waitFor(() =>
      expect(screen.getByTestId("pathname")).toHaveTextContent("/day"),
    );
  });

  it("gives an unknown path a real page rather than an empty shell", async () => {
    renderAt("/this-was-never-a-route");

    expect(await screen.findByText(/page doesn't exist/i)).toBeInTheDocument();
  });

  it("offers a way out of an unknown path", async () => {
    // A dead end is the defect, not the 404 itself. The exact name matters:
    // /agenda/i also matches SideNav's own link, which is itself the point
    // -- this page renders inside the layout, so the navigation is there
    // too and someone is never stranded.
    renderAt("/this-was-never-a-route");

    expect(
      await screen.findByRole("link", { name: "Go to Agenda" }),
    ).toHaveAttribute("href", "/agenda");
  });

  it("gives the weekly review both an undated and a dated path", async () => {
    // Two paths, one component, exactly as the day has: the undated one
    // lets the server say which week it is, and the dated one is what the
    // "week before" link points at. Without the dated path a review
    // written on a Monday could not reach the week it is about.
    renderAt("/review/2026-07-27");

    await waitFor(() =>
      expect(screen.getByTestId("pathname")).toHaveTextContent(
        "/review/2026-07-27",
      ),
    );
    expect(screen.queryByText(/page doesn't exist/i)).toBeNull();
  });

  it("does not redirect a path that really exists", async () => {
    renderAt("/archive");

    expect(await screen.findByTestId("pathname")).toHaveTextContent("/archive");
  });

  it("sends a pre-Release-D /lists/ bookmark to the area it names", async () => {
    // Slice 5 renamed a List to an Area in the route path too, which breaks
    // any URL someone saved. Redirecting rather than 404ing is the cheap
    // half of `principles.md`'s recoverable-failure rule.
    renderAt("/lists/7");

    await waitFor(() =>
      expect(screen.getByTestId("pathname")).toHaveTextContent("/areas/7"),
    );
  });
});
