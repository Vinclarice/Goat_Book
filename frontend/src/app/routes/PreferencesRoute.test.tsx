import { render, screen, waitFor, within } from "@testing-library/react";
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
    time_zone: "America/New_York",
    ...overrides,
  };
}

const TIME_ZONES = ["America/New_York", "Asia/Makassar", "Europe/London"];

/** Routes by URL, since the route now reads two endpoints. */
function mockApi(onPatch: () => object = () => preferencesData()) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const request = input as Request;
    if (request.url.includes("/api/v1/time-zones")) {
      return jsonResponse({ time_zones: TIME_ZONES });
    }
    if (request.method === "PATCH") {
      return jsonResponse(onPatch());
    }
    return jsonResponse(preferencesData());
  });
}

async function patchBody(fetchMock: ReturnType<typeof mockApi>) {
  const call = fetchMock.mock.calls.find(
    ([request]) => (request as Request).method === "PATCH",
  );
  return JSON.parse(await (call![0] as Request).text());
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
    mockApi();

    renderRoute();

    expect(await screen.findByDisplayValue("vince")).toBeInTheDocument();
    expect(screen.getByDisplayValue("vince@example.com")).toBeInTheDocument();
    expect(screen.getByRole("switch")).toBeChecked();
    expect(screen.getByRole("button", { name: "System" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("link", { name: "Change password" })).toHaveAttribute(
      "href",
      "/accounts/password/change/",
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
    const fetchMock = mockApi(() => preferencesData({ username: "vince2" }));

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

  it("shows the account's current time zone", async () => {
    mockApi();

    renderRoute();

    expect(await screen.findByLabelText("Time zone")).toHaveValue(
      "America/New_York",
    );
  });

  it("offers the zones the server will accept", async () => {
    // Not the browser's own Intl list: the two can disagree, and the
    // disagreement would be a validation error on an offered option.
    mockApi();

    renderRoute();

    const picker = await screen.findByLabelText("Time zone");
    expect(
      within(picker).getByRole("option", { name: "Asia/Makassar" }),
    ).toBeInTheDocument();
  });

  it("saves a changed time zone", async () => {
    const user = userEvent.setup();
    const fetchMock = mockApi(() =>
      preferencesData({ time_zone: "Asia/Makassar" }),
    );

    renderRoute();
    await screen.findByDisplayValue("vince");

    await user.selectOptions(
      screen.getByLabelText("Time zone"),
      "Asia/Makassar",
    );
    await user.click(screen.getByRole("button", { name: "Save settings" }));

    await waitFor(() => {
      expect(screen.getByText("Saved.")).toBeInTheDocument();
    });
    expect(await patchBody(fetchMock)).toMatchObject({
      time_zone: "Asia/Makassar",
    });
  });

  it("keeps the time zone when only the theme changes", async () => {
    // The theme mutation sends the whole preferences object, so a missing
    // time_zone here would silently reset the user's day boundaries.
    const user = userEvent.setup();
    const fetchMock = mockApi(() => preferencesData({ theme: "dark" }));

    renderRoute();
    await screen.findByDisplayValue("vince");

    await user.click(screen.getByRole("button", { name: "Dark" }));

    await waitFor(async () => {
      expect(await patchBody(fetchMock)).toMatchObject({
        time_zone: "America/New_York",
      });
    });
  });

  it("applies and persists a theme change immediately", async () => {
    const user = userEvent.setup();
    const fetchMock = mockApi(() => preferencesData({ theme: "dark" }));

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
