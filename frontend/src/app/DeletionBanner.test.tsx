import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";

import { DeletionBanner } from "./DeletionBanner";

function jsonResponse(data: object, ok = true, status = ok ? 200 : 500) {
  const body = JSON.stringify(data);
  return Promise.resolve({
    ok,
    status,
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

function mockNav(purgeAt: string | null) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const request = input as Request;
    if (request.url.includes("/api/v1/nav")) {
      return jsonResponse({
        areas: [],
        projects: [],
        archived_count: 0,
        settings_url: "/accounts/settings/",
        mind_url: "/mind/",
        landing_surface: "day",
        deletion_purge_at: purgeAt,
      });
    }
    return jsonResponse({});
  });
}

function renderBanner() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DeletionBanner />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DeletionBanner", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    document.cookie = "csrftoken=test-token";
  });

  it("renders nothing at all when nobody is leaving", async () => {
    // The common case, and the one that must cost nothing: every route mounts
    // this, so an empty state that still drew a box would put a gap at the top
    // of the whole application.
    mockNav(null);
    const { container } = renderBanner();

    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("says it is permanent and names the date", async () => {
    mockNav("2026-09-15T04:00:00Z");
    renderBanner();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/permanent deletion/i);
    expect(alert).toHaveTextContent(/cannot be recovered/i);
    expect(alert).toHaveTextContent(new Date("2026-09-15T04:00:00Z").toLocaleDateString());
  });

  it("carries the stop button itself", async () => {
    // Undoing a destructive thing must not be harder than starting it, and
    // "go and find the page where you did it" is harder.
    const fetchMock = mockNav("2026-09-15T04:00:00Z");
    const user = userEvent.setup();
    renderBanner();

    await user.click(await screen.findByRole("button", { name: "Keep my account" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.find(([r]) =>
          (r as Request).url.includes("/me/delete/cancel"),
        ),
      ).toBeDefined();
    });
  });

  it("is an alert, so it is announced rather than only seen", async () => {
    mockNav("2026-09-15T04:00:00Z");
    renderBanner();

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
