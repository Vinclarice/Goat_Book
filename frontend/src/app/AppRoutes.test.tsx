import { render, screen, waitFor } from "@testing-library/react";
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

  it("sends a bare /app/ visit somewhere real even if the preference is unreachable", async () => {
    // B2.1's defect was a blank page, so the case that matters most is the
    // one where the answer never arrives: it must still land on a surface
    // rather than render nothing. fetch is rejected by the beforeEach
    // above, which is exactly that case.
    renderAt("/");

    // waitFor rather than findBy: the probe is on screen from the first
    // render, so findBy would resolve at "/" before the redirect happens.
    // The redirect is asynchronous now that the destination is the
    // server's answer.
    await waitFor(() =>
      expect(screen.getByTestId("pathname")).toHaveTextContent("/day"),
    );
  });

  it("sends a bare /app/ visit to the landing surface the server names", async () => {
    // Crane 1 slice 6 turned this from a fixed /agenda into a preference.
    // The answer is the server's; this table only follows it.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: () => Promise.resolve({ landing_surface: "agenda", lists: [] }),
        text: () =>
          Promise.resolve(JSON.stringify({ landing_surface: "agenda", lists: [] })),
        clone() {
          return this;
        },
      } as unknown as Response),
    );

    renderAt("/");

    await waitFor(() =>
      expect(screen.getByTestId("pathname")).toHaveTextContent("/agenda"),
    );
  });

  it("says something while it works out where to send you", async () => {
    // Never a blank /app/, which is the exact shape of B2.1's defect.
    renderAt("/");

    expect(screen.getByText("Loading…")).toBeInTheDocument();
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
