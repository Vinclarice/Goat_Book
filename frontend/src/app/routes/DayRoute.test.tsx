import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { DayRoute } from "./DayRoute";

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

function dayData(overrides: Record<string, unknown> = {}) {
  return {
    date: "2026-08-03",
    intentions: "",
    gratitude: "",
    happenings: "",
    today: "2026-08-03",
    ...overrides,
  };
}

function renderAt(path: string, stored = dayData()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/day" element={<DayRoute />} />
          <Route path="/day/:date" element={<DayRoute />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("DayRoute", () => {
  it("shows what was already written for the day", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ intentions: "Finish the slice", gratitude: "Rain" })),
    );

    renderAt("/day/2026-08-03");

    expect(await screen.findByLabelText("Intentions")).toHaveValue(
      "Finish the slice",
    );
    expect(screen.getByLabelText("Grateful for")).toHaveValue("Rain");
  });

  it("sends only the day's own text when saving", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const request = input as Request;
        if (request.method === "PATCH") {
          return jsonResponse(dayData({ intentions: "Ship it" }));
        }
        return jsonResponse(dayData());
      });

    renderAt("/day/2026-08-03");
    const intentions = await screen.findByLabelText("Intentions");
    await userEvent.type(intentions, "Ship it");
    await userEvent.click(screen.getByRole("button", { name: "Save the day" }));

    await waitFor(() => expect(screen.getByText("Saved.")).toBeInTheDocument());
    const patch = fetchSpy.mock.calls
      .map(([input]) => input as Request)
      .find((request) => request.method === "PATCH");
    expect(patch?.url).toContain("/api/v1/day/2026-08-03");
  });

  it("labels the day as Today only when the server says it is", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ date: "2026-08-01", today: "2026-08-03" })),
    );

    renderAt("/day/2026-08-01");

    expect(await screen.findByText("Your day")).toBeInTheDocument();
    expect(screen.queryByText("Today")).not.toBeInTheDocument();
  });

  it("asks the server which day it is when the route carries no date", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => jsonResponse(dayData()));

    renderAt("/day");

    await screen.findByLabelText("Intentions");
    const url = (fetchSpy.mock.calls[0][0] as Request).url;
    expect(url).toMatch(/\/api\/v1\/day$/);
  });

  it("does not overwrite what is being typed when the query refetches", async () => {
    // The bug PreferencesRoute already had: an alt-tab refetch that seeds
    // the form again silently restores the stored text over an edit in
    // progress, and the save that follows reports success for the wrong
    // value.
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(dayData({ intentions: "Stored text" })),
    );

    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/day/2026-08-03"]}>
          <Routes>
            <Route path="/day/:date" element={<DayRoute />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const intentions = await screen.findByLabelText("Intentions");
    await userEvent.clear(intentions);
    await userEvent.type(intentions, "Half a thought");
    await client.refetchQueries({ queryKey: ["day", "2026-08-03"] });

    await waitFor(() => expect(intentions).toHaveValue("Half a thought"));
  });

  it("offers a way out when the day cannot be loaded", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({ detail: "nope" }, false, 500),
    );

    renderAt("/day/2026-08-03");

    expect(
      await screen.findByRole("button", { name: /try again/i }),
    ).toBeInTheDocument();
  });
});
