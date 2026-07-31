import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { AppLayout } from "./AppLayout";

function jsonResponse(data: object, ok = true) {
  const body = JSON.stringify(data);
  return Promise.resolve({
    ok,
    status: ok ? 200 : 500,
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

const NAV = {
  lists: [
    {
      id: 1,
      title: "Programming",
      open_count: 5,
      overdue_count: 2,
      color_key: "sky",
    },
    {
      id: 2,
      title: "Home",
      open_count: 1,
      overdue_count: 0,
      color_key: "sage",
    },
  ],
  archived_count: 4,
  inbox_count: 3,
  settings_url: "/accounts/settings/",
  inbox_url: "/capture/",
};

function renderNav(initialPath = "/agenda") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/agenda" element={<p>Agenda page</p>} />
            <Route path="/lists/:listId" element={<p>List page</p>} />
            <Route path="/archive" element={<p>Archive page</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SideNav", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse(NAV));
  });

  it("lists every list with its open and overdue counts", async () => {
    renderNav();

    expect(await screen.findByText("Programming")).toBeInTheDocument();
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByLabelText("2 overdue")).toBeInTheDocument();
  });

  it("navigates to a list rather than filtering the agenda", async () => {
    const user = userEvent.setup();
    renderNav();

    await user.click(await screen.findByText("Programming"));

    // The whole point of the split: the nav means the same thing on every
    // page, so it navigates and the header chips filter.
    expect(await screen.findByText("List page")).toBeInTheDocument();
  });

  it("marks the current view as active", async () => {
    renderNav("/archive");

    const archive = await screen.findByRole("link", { name: /Archive/ });
    expect(archive.className).toMatch(/active/);
  });

  it("links the inbox out of the SPA and shows what's waiting", async () => {
    renderNav();
    // Wait for the payload before asserting: the loading shell renders an
    // Inbox link too, with the same fallback href, so asserting on the
    // first match would pass without the data ever arriving.
    await screen.findByText("Programming");

    const inbox = screen.getByRole("link", { name: /Inbox/ });
    // A Django page, so a real href rather than a router link.
    expect(inbox).toHaveAttribute("href", "/capture/");
    expect(inbox).toHaveTextContent("3");
  });

  it("renders the nav before its data arrives", () => {
    // A nav that appears a beat after the page makes every navigation look
    // like a layout shift, so the shell renders immediately.
    renderNav();

    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(screen.getByText("Agenda")).toBeInTheDocument();
  });

  it("closes the narrow-screen disclosure after navigating", async () => {
    const user = userEvent.setup();
    renderNav();
    const disclosure = document.querySelector("details") as HTMLDetailsElement;
    disclosure.open = true;

    await user.click(await screen.findByText("Programming"));

    await waitFor(() => expect(disclosure.open).toBe(false));
  });
});
