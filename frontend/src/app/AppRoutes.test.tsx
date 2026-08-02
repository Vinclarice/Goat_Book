import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router";

import { AppRoutes } from "./AppRoutes";

/**
 * The route table itself, which is where B2.1's first defect lived: /app/
 * had no index route, so a direct visit matched nothing and rendered an
 * empty shell -- a blank page that looks exactly like a broken deploy.
 *
 * Asserting on the resolved pathname rather than on Agenda's content keeps
 * these honest about what they test. Whether the Agenda renders is
 * AgendaRoute's business; whether "/" resolves to it is this table's.
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

  it("sends a bare /app/ visit to the Agenda instead of rendering nothing", async () => {
    renderAt("/");

    expect(await screen.findByTestId("pathname")).toHaveTextContent("/agenda");
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

  it("does not redirect a path that really exists", async () => {
    renderAt("/archive");

    expect(await screen.findByTestId("pathname")).toHaveTextContent("/archive");
  });
});
