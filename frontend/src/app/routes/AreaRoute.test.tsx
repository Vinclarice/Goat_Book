import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { AreaRoute } from "./AreaRoute";
import { task } from "../../test/fixtures";

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

function listDetailData(overrides: Record<string, unknown> = {}) {
  return {
    area: {
      id: 7,
      title: "Programming",
      create_item_url: "/api/areas/7/items/",
      reorder_url: "/api/areas/7/items/reorder/",
    },
    items: [task({ text: "Write tests" })],
    archived_count: 0,
    archive_url: "/archive/",
    ...overrides,
  };
}

function renderAt(areaId: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/areas/${areaId}`]}>
        <Routes>
          <Route path="/areas/:areaId" element={<AreaRoute />} />
          <Route path="/agenda" element={<p>Agenda page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AreaRoute", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    document.cookie = "csrftoken=test-token";
  });

  it("renders the list's title and items once the query resolves", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(listDetailData()),
    );

    renderAt("7");

    expect(await screen.findByText("Write tests")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Programming")).toBeInTheDocument();
  });

  it("shows an error state when the request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({ detail: "nope" }, false),
    );

    renderAt("7");

    // B2.1: a 500 is the retryable kind of failure, so the person is
    // offered a retry rather than told their work is gone.
    expect(await screen.findByText(/Couldn't reach Clarice/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("deletes the list and returns to the agenda after confirming", async () => {
    const user = userEvent.setup();
    // openapi-fetch calls fetch(request) with a single Request object,
    // not fetch(url, init) -- the method lives on the request itself.
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "DELETE") {
        return jsonResponse({ deleted: 7 });
      }
      return jsonResponse(listDetailData());
    });

    renderAt("7");
    await screen.findByText("Write tests");

    await user.click(screen.getByRole("button", { name: "Delete area" }));
    await user.click(screen.getByRole("button", { name: "Delete area permanently" }));

    await waitFor(() => {
      expect(screen.getByText("Agenda page")).toBeInTheDocument();
    });
    const deleteCall = fetchMock.mock.calls.find(
      ([request]) => (request as Request).method === "DELETE",
    );
    expect(deleteCall?.[0]).toEqual(
      expect.objectContaining({ url: expect.stringContaining("/api/v1/areas/7") }),
    );
  });
});
