import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";

import { RouteFailure } from "./RouteFailure";

/**
 * Every route used to render the same "Something went wrong." for a deleted
 * list, an expired session, and a dropped connection alike. Those need
 * opposite responses from the person reading them -- log in again, go
 * somewhere else, or simply wait and retry -- so a single message is not
 * merely vague, it is misleading in two cases out of three.
 *
 * See design/bittern-plan.md, B2.1.
 */
function renderAt(pathname: string, element: React.ReactNode) {
  return render(
    <MemoryRouter initialEntries={[pathname]}>
      <Routes>
        <Route path="*" element={element} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RouteFailure", () => {
  it("sends an expired session to login, keeping where they were going", () => {
    // The whole point of preserving it: someone deep-linked to a task,
    // their session had expired, and after logging in they should land on
    // that task rather than being dumped at the Agenda to find it again.
    renderAt("/tasks/42", <RouteFailure status={401} />);

    expect(screen.getByRole("link", { name: /log in/i })).toHaveAttribute(
      "href",
      "/accounts/login/?next=%2Fapp%2Ftasks%2F42",
    );
  });

  it("explains a 403 without offering a way back in", () => {
    // Distinct from 401 on purpose. Logging in again does not help when
    // the answer is "this is not yours", and suggesting it would send
    // someone round a loop that cannot succeed.
    renderAt("/areas/7", <RouteFailure status={403} />);

    expect(screen.getByText(/no longer have access/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /log in/i })).not.toBeInTheDocument();
  });

  it("offers the Agenda when the thing is gone", () => {
    renderAt("/areas/7", <RouteFailure status={404} />);

    expect(screen.getByText(/no longer exists/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /agenda/i })).toHaveAttribute(
      "href",
      "/agenda",
    );
  });

  it("offers a retry when the server or the network failed", async () => {
    const retry = vi.fn();

    renderAt("/agenda", <RouteFailure status={503} onRetry={retry} />);
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));

    expect(retry).toHaveBeenCalledOnce();
  });

  it("treats an unknown status as retryable rather than permanent", () => {
    // A dropped connection has no status at all. Guessing "permanent"
    // would tell someone their task is gone when their wifi dropped --
    // the one wrong answer that loses trust rather than time.
    renderAt("/agenda", <RouteFailure status={undefined} onRetry={vi.fn()} />);

    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
    expect(screen.queryByText(/no longer exists/i)).not.toBeInTheDocument();
  });

  it("does not offer a retry button when there is nothing to retry", () => {
    renderAt("/agenda", <RouteFailure status={503} />);

    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });
});
