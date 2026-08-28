import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { CategoriesRoute } from "./CategoriesRoute";

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

const CATEGORIES = [
  { id: 1, name: "Housing", line_count: 3 },
  { id: 2, name: "Subscriptions", line_count: 0 },
];

function renderCategories() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/money/categories"]}>
        <Routes>
          <Route path="/money/categories" element={<CategoriesRoute />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CategoriesRoute", () => {
  afterEach(() => vi.restoreAllMocks());

  it("lists the categories and how many bills each holds", async () => {
    /* The count is shown because deleting is safe and people assume it is
       not -- "3 bills will become uncategorised" should be a fact you see. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(CATEGORIES),
    );

    renderCategories();

    expect(await screen.findByText("Housing")).toBeInTheDocument();
    expect(screen.getByText("3 bills")).toBeInTheDocument();
  });

  it("says that deleting one leaves its bills alone", async () => {
    /* A category is a label, not a container, and that is not obvious. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(CATEGORIES),
    );

    renderCategories();

    expect(
      await screen.findByText(/Deleting one leaves its bills alone/),
    ).toBeInTheDocument();
  });

  it("adds one", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const request = input as Request;
        if (request.method === "POST") return jsonResponse({}, true, 201);
        return jsonResponse(CATEGORIES);
      });

    renderCategories();

    await userEvent.type(await screen.findByLabelText("Add a category"), "Boat");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    const posted = fetchSpy.mock.calls
      .map(([request]) => request as Request)
      .filter((request) => request.method === "POST");
    await waitFor(() => expect(posted).toHaveLength(1));
  });

  it("renames one in place", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const request = input as Request;
        if (request.method === "PATCH") return jsonResponse({});
        return jsonResponse(CATEGORIES);
      });

    renderCategories();

    await userEvent.click(
      await screen.findByRole("button", { name: "Rename Housing" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    const patched = fetchSpy.mock.calls
      .map(([request]) => request as Request)
      .filter((request) => request.method === "PATCH");
    await waitFor(() => expect(patched).toHaveLength(1));
  });

  it("shows the server's own words when a name collides", async () => {
    /* Every 409 on this router is written for a person, and the page has to
       let it through rather than substituting an apology. */
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") {
        return jsonResponse(
          { detail: "There is already a category called Housing." },
          false,
          409,
        );
      }
      return jsonResponse(CATEGORIES);
    });

    renderCategories();

    await userEvent.type(await screen.findByLabelText("Add a category"), "Housing");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    expect(
      await screen.findByText(/already a category called Housing/),
    ).toBeInTheDocument();
  });

  it("reports a failure rather than an empty list", async () => {
    /* No categories and a broken request look identical, and only one means
       there is nothing to show. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({}, false, 500),
    );

    renderCategories();

    expect(
      await screen.findByRole("button", { name: /Try again/i }),
    ).toBeInTheDocument();
  });
});
