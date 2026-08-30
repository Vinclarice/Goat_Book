import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";

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
    closing_nudge: false,
    theme: "system",
    time_zone: "America/New_York",
    compass_purpose: "Build something worth maintaining.",
    compass_question: "What is the most I can do?",
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
  // Mirrors main.tsx exactly: retry off, everything else left at TanStack's
  // defaults. That matters here -- the default staleTime of 0 is what makes
  // a background refetch possible at all, so a test client that pinned
  // staleTime would prove nothing about the real app.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter><PreferencesRoute /></MemoryRouter>
      </QueryClientProvider>,
    ),
  };
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
    // Two switches now, so this names which. The digest is on and the
    // evening nudge is off, which is the difference the privacy policy
    // states in published text and a Django test holds against the model.
    const [digest, nudge] = screen.getAllByRole("switch");
    expect(digest).toBeChecked();
    expect(nudge).not.toBeChecked();
    expect(screen.getByRole("button", { name: "System" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("link", { name: "Change password" })).toHaveAttribute(
      "href",
      "/accounts/password/change/",
    );
  });

  // coherence-audit-2026-08-30.md F6. The enrolment page was linked from
  // exactly one place in the tree -- the challenge screen you only reach if
  // you already have a device -- so the only people who could find it were
  // the ones who did not need it. This is the front door.
  it("offers the second factor beside the other account links", async () => {
    mockApi();

    renderRoute();

    expect(
      await screen.findByRole("link", { name: "Two-factor authentication" }),
    ).toHaveAttribute("href", "/accounts/security/");
  });

  it("shows an error state when the request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({ detail: "nope" }, false),
    );

    renderRoute();

    // B2.1: a 500 is the retryable kind of failure, so the person is
    // offered a retry rather than told their work is gone.
    expect(await screen.findByText(/Couldn't reach Clarice/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
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

  it("keeps an unsaved edit when the query refetches underneath it", async () => {
    // The reported bug. staleTime defaults to 0 and refetchOnWindowFocus is
    // on, so switching tabs refetches -- and if the queryFn writes form
    // state, it silently restores the server's values over the edit. The
    // save that follows then reports "Saved." having written the old value
    // back, which is worse than failing.
    const user = userEvent.setup();
    mockApi();
    const { queryClient } = renderRoute();
    await screen.findByDisplayValue("vince");

    await user.selectOptions(
      screen.getByLabelText("Time zone"),
      "Asia/Makassar",
    );
    // Wrapped in act so the refetch's state update is flushed before the
    // assertion. Without it this test cannot see the bug at all: a bare
    // await leaves the update pending, the DOM still shows the edit, and
    // the test passes while the value is already lost -- which is exactly
    // how it behaved the first time I wrote it.
    await act(async () => {
      await queryClient.refetchQueries({ queryKey: ["preferences"] });
    });

    expect(screen.getByLabelText("Time zone")).toHaveValue("Asia/Makassar");
  });

  it("saves the edited value, not the one a refetch restored", async () => {
    const user = userEvent.setup();
    const fetchMock = mockApi(() =>
      preferencesData({ time_zone: "Asia/Makassar" }),
    );
    const { queryClient } = renderRoute();
    await screen.findByDisplayValue("vince");

    await user.selectOptions(
      screen.getByLabelText("Time zone"),
      "Asia/Makassar",
    );
    await queryClient.refetchQueries({ queryKey: ["preferences"] });
    await user.click(screen.getByRole("button", { name: "Save settings" }));

    await waitFor(() => expect(screen.getByText("Saved.")).toBeInTheDocument());
    expect(await patchBody(fetchMock)).toMatchObject({
      time_zone: "Asia/Makassar",
    });
  });

  it("stops claiming Saved once the form is edited again", async () => {
    // "Saved." lingering over an unsaved change is how someone concludes a
    // change was stored when it was not.
    const user = userEvent.setup();
    mockApi();
    renderRoute();
    await screen.findByDisplayValue("vince");

    await user.click(screen.getByRole("button", { name: "Save settings" }));
    await waitFor(() => expect(screen.getByText("Saved.")).toBeInTheDocument());

    await user.selectOptions(
      screen.getByLabelText("Time zone"),
      "Europe/London",
    );

    expect(screen.queryByText("Saved.")).not.toBeInTheDocument();
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

  it("keeps the compass when only the theme changes", async () => {
    // Same trap as the time zone above, and the compass is the newest field
    // it could have swallowed: clicking Dark must not blank a standing note.
    const user = userEvent.setup();
    const fetchMock = mockApi(() => preferencesData({ theme: "dark" }));

    renderRoute();
    await screen.findByDisplayValue("vince");

    await user.click(screen.getByRole("button", { name: "Dark" }));

    await waitFor(async () => {
      expect(await patchBody(fetchMock)).toMatchObject({
        compass_purpose: "Build something worth maintaining.",
        compass_question: "What is the most I can do?",
      });
    });
  });

  it("saves an edited compass", async () => {
    const user = userEvent.setup();
    const fetchMock = mockApi();

    renderRoute();
    const question = await screen.findByLabelText("Guiding question");
    await user.clear(question);
    await user.type(question, "What is worth finishing?");
    await user.click(screen.getByRole("button", { name: "Save settings" }));

    await waitFor(async () => {
      expect(await patchBody(fetchMock)).toMatchObject({
        compass_question: "What is worth finishing?",
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

/** Routes `/api/v1/nav` as well, which is where the purge date comes from. */
function mockLeaving(purgeAt: string | null, onDelete?: () => Response | object) {
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
    if (request.url.includes("/api/v1/me/delete")) {
      const answer = onDelete?.();
      return answer instanceof Promise ? answer : jsonResponse(answer ?? {});
    }
    if (request.url.includes("/api/v1/time-zones")) {
      return jsonResponse({ time_zones: TIME_ZONES });
    }
    return jsonResponse(preferencesData());
  });
}

describe("PreferencesRoute — leaving", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    document.cookie = "csrftoken=test-token";
  });

  it("offers the export before it offers the deletion", async () => {
    // Order on the page, not decoration. Deletion without export is a trap --
    // the only way out would be to destroy everything -- so the way to take
    // your data has to be visible from the same place, first.
    mockLeaving(null);
    renderRoute();
    await screen.findByDisplayValue("vince");

    const download = screen.getByRole("link", { name: "Download my data" });
    const remove = screen.getByRole("button", { name: "Delete my account…" });

    expect(download).toHaveAttribute("href", "/api/v1/me/export");
    expect(
      download.compareDocumentPosition(remove) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("asks for the password before it will schedule anything", async () => {
    const fetchMock = mockLeaving(null);
    const user = userEvent.setup();
    renderRoute();
    await screen.findByDisplayValue("vince");

    await user.click(screen.getByRole("button", { name: "Delete my account…" }));

    expect(screen.getByLabelText("Confirm your password")).toBeInTheDocument();
    // Nothing has been sent yet -- opening the form is not the request.
    expect(
      fetchMock.mock.calls.filter(([r]) =>
        (r as Request).url.includes("/me/delete"),
      ),
    ).toHaveLength(0);
  });

  it("says it is permanent and cannot be undone, before anything is clicked", async () => {
    // The words, asserted. It previously said only "erased after 30 days",
    // which implies permanence rather than stating it -- not enough for the one
    // control on the site that destroys data.
    mockLeaving(null);
    renderRoute();
    await screen.findByDisplayValue("vince");

    const section = screen
      .getByRole("heading", { name: "Delete my account" })
      .closest("div")!;
    expect(section).toHaveTextContent(/permanently deleted/i);
    expect(section).toHaveTextContent(/cannot be recovered/i);
  });

  it("needs both the acknowledgement and the password", async () => {
    // Two gates guarding different mistakes: the checkbox guards somebody who
    // thinks this pauses the account, the password guards somebody who is not
    // the account holder. Either alone leaves the other case uncovered.
    mockLeaving(null);
    const user = userEvent.setup();
    renderRoute();
    await screen.findByDisplayValue("vince");
    await user.click(screen.getByRole("button", { name: "Delete my account…" }));

    const submit = screen.getByRole("button", { name: "Schedule deletion" });
    expect(submit).toBeDisabled();

    await user.type(screen.getByLabelText("Confirm your password"), "hunter2");
    expect(submit).toBeDisabled();

    await user.click(screen.getByRole("checkbox"));
    expect(submit).toBeEnabled();
  });

  it("sends the password when both gates are satisfied", async () => {
    const fetchMock = mockLeaving(null);
    const user = userEvent.setup();
    renderRoute();
    await screen.findByDisplayValue("vince");
    await user.click(screen.getByRole("button", { name: "Delete my account…" }));

    await user.type(screen.getByLabelText("Confirm your password"), "hunter2");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Schedule deletion" }));

    await waitFor(async () => {
      const call = fetchMock.mock.calls.find(([r]) =>
        (r as Request).url.includes("/me/delete"),
      );
      expect(JSON.parse(await (call![0] as Request).text())).toEqual({
        password: "hunter2",
      });
    });
  });

  it("says when the data goes, that it is permanent, and offers to stop it", async () => {
    mockLeaving("2026-09-15T04:00:00Z");
    renderRoute();

    expect(
      await screen.findByRole("heading", {
        name: /scheduled for permanent deletion/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/cannot be recovered/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Keep my account" }),
    ).toBeInTheDocument();
    // And the delete control is gone -- there is nothing to schedule twice.
    expect(
      screen.queryByRole("button", { name: "Delete my account…" }),
    ).toBeNull();
  });

  it("still offers the export while the account is on its way out", async () => {
    // The last day before an erasure is the most likely moment somebody wants
    // their data, so this must not disappear along with the rest of the form.
    mockLeaving("2026-09-15T04:00:00Z");
    renderRoute();

    expect(
      await screen.findByRole("link", { name: "Download my data" }),
    ).toHaveAttribute("href", "/api/v1/me/export");
  });

  it("reports a refused password instead of looking like it worked", async () => {
    mockLeaving(null, () => jsonResponse({ detail: "no" }, false, 400));
    const user = userEvent.setup();
    renderRoute();
    await screen.findByDisplayValue("vince");
    await user.click(screen.getByRole("button", { name: "Delete my account…" }));

    await user.type(screen.getByLabelText("Confirm your password"), "wrong");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Schedule deletion" }));

    expect(
      await screen.findByText("That password did not match."),
    ).toBeInTheDocument();
  });

  it("tells them an email was sent, so an unexpected one is checkable", async () => {
    mockLeaving("2026-09-15T04:00:00Z");
    renderRoute();

    expect(await screen.findByText(/emailed you about this/i)).toBeInTheDocument();
    expect(screen.getByText(/change your password/i)).toBeInTheDocument();
  });
});
