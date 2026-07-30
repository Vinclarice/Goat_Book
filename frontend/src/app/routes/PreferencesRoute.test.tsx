import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { PreferencesRoute } from "./PreferencesRoute";

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

function preferencesData(overrides: Record<string, unknown> = {}) {
  return {
    username: "vince",
    email: "vince@example.com",
    daily_digest: true,
    theme: "system",
    ...overrides,
  };
}

function renderRoute() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <PreferencesRoute />
    </QueryClientProvider>,
  );
}

describe("PreferencesRoute", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    document.cookie = "csrftoken=test-token";
  });

  it("renders the current preferences once the query resolves", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(preferencesData()),
    );

    renderRoute();

    expect(await screen.findByDisplayValue("vince")).toBeInTheDocument();
    expect(screen.getByDisplayValue("vince@example.com")).toBeInTheDocument();
    expect(screen.getByRole("switch")).toBeChecked();
    expect(screen.getByRole("button", { name: "System" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("shows an error state when the request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({ detail: "nope" }, false),
    );

    renderRoute();

    expect(await screen.findByText("Something went wrong.")).toBeInTheDocument();
  });

  it("saves the account fields on submit", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "PATCH") {
        return jsonResponse(preferencesData({ username: "vince2" }));
      }
      return jsonResponse(preferencesData());
    });

    renderRoute();
    await screen.findByDisplayValue("vince");

    await user.clear(screen.getByLabelText("Username"));
    await user.type(screen.getByLabelText("Username"), "vince2");
    await user.click(screen.getByRole("button", { name: "Save settings" }));

    await waitFor(() => {
      expect(screen.getByText("Saved.")).toBeInTheDocument();
    });
    const patchCall = fetchMock.mock.calls.find(
      ([request]) => (request as Request).method === "PATCH",
    );
    expect(patchCall).toBeDefined();
  });

  it("applies and persists a theme change immediately", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "PATCH") {
        return jsonResponse(preferencesData({ theme: "dark" }));
      }
      return jsonResponse(preferencesData());
    });

    renderRoute();
    await screen.findByDisplayValue("vince");

    await user.click(screen.getByRole("button", { name: "Dark" }));

    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find(
        ([request]) => (request as Request).method === "PATCH",
      );
      expect(patchCall).toBeDefined();
    });
  });
});
