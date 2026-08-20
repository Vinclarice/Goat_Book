import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { ReviewRoute } from "./ReviewRoute";

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

function weekData(overrides: Record<string, unknown> = {}) {
  return {
    week_start: "2026-07-27",
    week_end: "2026-08-02",
    today: "2026-08-02",
    is_current_week: true,
    previous_week: "2026-07-20",
    next_week: "2026-08-03",
    completed: [],
    planned: { total: 0, met: 0, met_tasks: [], unfinished: [], set_aside: [] },
    written: [],
    thoughts: [],
    names_to_confirm: [],
    loose_ends: { unanswered: [], unanswered_commitments: [], overdue: [] },
    upcoming: { tasks: [], projects: [] },
    draft: {
      week_start: "2026-08-03",
      intention: "",
      proposed: [],
      routines: [],
      typical_week: null,
      over_committed: false,
    },
    check_in: {
      started: false,
      unusual: "usual",
      projects: [],
      outcomes: [],
      proposals: [],
            blockers: [],
            carryover: [],
    },
    habits: [],
    recent_weeks: [],
    review: {
      reflections: "",
      plan: "",
      completed_at: null,
      recorded_total: null,
      recorded_met: null,
    },
    ...overrides,
  };
}

function plannedTask(overrides: Record<string, unknown> = {}) {
  return {
    task_id: 1,
    text: "Pay rent",
    day: "2026-07-27",
    due_date: null,
    age_in_days: 0,
    completed_on: null,
    ...overrides,
  };
}

function completedTask(overrides: Record<string, unknown> = {}) {
  return {
    task_id: 1,
    text: "Pay rent",
    completed_on: "2026-07-29",
    area_id: 3,
    ...overrides,
  };
}

function habitPeriod(overrides: Record<string, unknown> = {}) {
  return {
    period_start: "2026-07-27",
    outcome: "open",
    progress: 0,
    target: 5,
    ...overrides,
  };
}

function weekSummary(overrides: Record<string, unknown> = {}) {
  return {
    week_start: "2026-07-20",
    is_shown_week: false,
    planned_met: null,
    planned_total: null,
    habits_met: null,
    habits_expected: null,
    ...overrides,
  };
}

function renderAt(path: string, stored = weekData()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/review" element={<ReviewRoute />} />
          <Route path="/review/:week" element={<ReviewRoute />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("ReviewRoute", () => {
  it("names the week it is showing", async () => {
    // The default is the week you are in rather than the one before, so the
    // page has to say which one that is -- a number with an unnamed window
    // behind it is the kind of figure this release exists to avoid.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(weekData()),
    );

    renderAt("/review");

    // Order left to the reader's locale, like every other date in the app
    // — the assertion is that both ends of the window are named, not which
    // way round a month and a day go.
    const heading = await screen.findByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent(/(27 July|July 27)/);
    expect(heading).toHaveTextContent(/(2 August|August 2)/);
  });

  it("lists what was finished, with the day it was finished on", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          completed: [
            completedTask(),
            completedTask({ task_id: 2, text: "Book the dentist", completed_on: "2026-07-31" }),
          ],
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("Pay rent")).toBeInTheDocument();
    expect(screen.getByText("Book the dentist")).toBeInTheDocument();
    expect(screen.getByText("Wednesday")).toBeInTheDocument();
    expect(screen.getByText("Friday")).toBeInTheDocument();
  });

  it("says so plainly when nothing was finished", async () => {
    // Not an empty list: a week with nothing in it is a fact, and a blank
    // area reads as a page that failed to load.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(weekData()),
    );

    renderAt("/review");

    expect(
      await screen.findByText(/Nothing was marked finished/),
    ).toBeInTheDocument();
  });

  it("reports the finish rate over what was planned, not over the backlog", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          planned: {
            total: 3,
            met: 2,
            met_tasks: [
              plannedTask({ completed_on: "2026-07-29" }),
              plannedTask({ task_id: 2, text: "Book the dentist", completed_on: "2026-07-31" }),
            ],
            unfinished: [plannedTask({ task_id: 3, text: "Call the bank" })],
            set_aside: [],
          },
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("2 of 3")).toBeInTheDocument();
  });

  it("keeps what was deliberately set aside out of the count and on the page", async () => {
    // released_at's whole purpose: a decommitment is not a failure to
    // finish, and a denominator that counted both would report a number
    // that looks authoritative and is not.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          planned: {
            total: 1,
            met: 1,
            met_tasks: [plannedTask({ completed_on: "2026-07-29" })],
            unfinished: [],
            set_aside: [
              plannedTask({ task_id: 9, text: "Reorganise the shed" }),
            ],
          },
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("1 of 1")).toBeInTheDocument();
    expect(screen.getByText("Reorganise the shed")).toBeInTheDocument();
    expect(screen.getByText(/Set aside/)).toBeInTheDocument();
  });

  it("says how long an unfinished commitment has been waiting", async () => {
    // The Daily Page's wording, from the Daily Page's rule: a fact with no
    // conclusion drawn from it. A red "12 days late!" fails the vision
    // document's test that history be useful without being punishing.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          planned: {
            total: 1,
            met: 0,
            met_tasks: [],
            unfinished: [plannedTask({ age_in_days: 12 })],
            set_aside: [],
          },
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("Added 12 days ago")).toBeInTheDocument();
  });

  it("does not report a rate for a week nobody planned", async () => {
    // A week with no plan is not a week that failed one, and "0 of 0" is
    // the shape of number that invites a conclusion from nothing.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(weekData()),
    );

    renderAt("/review");
    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByText("0 of 0")).toBeNull();
    expect(screen.getByText(/Nothing was pinned/)).toBeInTheDocument();
  });

  it("shows a day's own words under the day they were written for", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          written: [
            {
              date: "2026-07-28",
              intentions: "",
              gratitude: "The rain",
              happenings: "",
            },
          ],
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("Tuesday")).toBeInTheDocument();
    expect(screen.getByText("The rain")).toBeInTheDocument();
    // Only the section that was written: three empty headings under every
    // day would bury the one line that says something.
    expect(screen.queryByText("Intentions")).toBeNull();
  });

  it("lists names worth confirming, with the evidence for asking", async () => {
    // Replaces the Inbox backlog this used to show, and is deliberately not
    // the same thing: that was everything untriaged however old, this is the
    // one queue the design permits — finite, because a name has to recur to
    // reach it. The count is why the question is being asked.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          names_to_confirm: [{ label: "Marguerite", mentions: 4 }],
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("Marguerite")).toBeInTheDocument();
    expect(screen.getByText("4 mentions")).toBeInTheDocument();
  });

  it("lists the thoughts the week captured", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          thoughts: [
            {
              public_id: "3f1b0c9e-1111-4a2b-8c3d-000000000001",
              text: "the boiler is making that noise",
              captured_on: "2026-07-28",
            },
          ],
        }),
      ),
    );

    renderAt("/review");

    expect(
      await screen.findByText("the boiler is making that noise"),
    ).toBeInTheDocument();
  });

  it("leaves out the sections a week has nothing for", async () => {
    // A heading over an empty area reads as something that failed to load.
    // The week's own words are the exception: a week nobody wrote in is
    // worth saying out loud, because writing is the habit under review.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(weekData()),
    );

    renderAt("/review");
    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByText("Ideas you added")).toBeNull();
    expect(screen.queryByText("Still in your inbox")).toBeNull();
    expect(screen.getByText(/Nothing written/)).toBeInTheDocument();
  });

  it("keeps a plan for the coming week", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input) => {
        const request = input as Request;
        if (request.method === "PATCH") {
          return jsonResponse(
            weekData({
              review: {
                reflections: "",
                plan: "Two mornings on the review",
                completed_at: null,
                recorded_total: null,
                recorded_met: null,
              },
            }),
          );
        }
        return jsonResponse(weekData());
      });

    renderAt("/review");
    await userEvent.type(
      await screen.findByLabelText("Next week"),
      "Two mornings",
    );
    await userEvent.click(screen.getByRole("button", { name: "Save the review" }));

    await waitFor(() => expect(screen.getByText("Saved.")).toBeInTheDocument());
    const patched = fetchSpy.mock.calls
      .map(([request]) => request as Request)
      .filter((request) => request.method === "PATCH");
    expect(patched).toHaveLength(1);
  });

  /* The check-in -- planning-assistant-v2-plan.md increment 4. The forward
     half of the ritual opens with what the system believes and takes
     corrections, rather than asking for what it already knows. */
  it("offers to start planning, and records that somebody did", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") {
        return jsonResponse({ started: true, unusual: "usual", projects: [] });
      }
      return jsonResponse(weekData());
    });

    renderAt("/review");
    await userEvent.click(
      await screen.findByRole("button", { name: "Plan next week" }),
    );

    await waitFor(() => {
      const posted = fetchSpy.mock.calls
        .map(([request]) => request as Request)
        .filter((req) => req.url.includes("planning-session"));
      expect(posted).toHaveLength(1);
    });
  });

  it("says which project has not moved, and for how long", async () => {
    /* The plan's own example: "Newsletter has not moved in five weeks --
       still going?" An opinion to correct, not a question to answer. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          check_in: {
            started: true,
            unusual: "usual",
            projects: [
              {
                id: 7,
                title: "Newsletter",
                quiet_for_days: 40,
                looks_active: false,
              },
              {
                id: 8,
                title: "Website launch",
                quiet_for_days: 2,
                looks_active: true,
              },
            ],
            outcomes: [],
            proposals: [],
            blockers: [],
            carryover: [],
          },
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("Newsletter")).toBeInTheDocument();
    expect(screen.getByText(/nothing for 40 days/)).toBeInTheDocument();
    /* The active one is stated too, so the list reads as "here is what I
       believe" rather than as a pile of problems. */
    expect(screen.getByText("Website launch")).toBeInTheDocument();
  });

  it("parks a project from the check-in", async () => {
    /* Correcting the belief in place. Sending somebody to the project page to
       do it would make the check-in a report rather than a ritual. */
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "PATCH") return jsonResponse({ id: 7 });
      return jsonResponse(
        weekData({
          check_in: {
            started: true,
            unusual: "usual",
            projects: [
              {
                id: 7,
                title: "Newsletter",
                quiet_for_days: 40,
                looks_active: false,
              },
            ],
            outcomes: [],
            proposals: [],
            blockers: [],
            carryover: [],
          },
        }),
      );
    });

    renderAt("/review");
    await userEvent.click(
      await screen.findByRole("button", { name: "Pause Newsletter" }),
    );

    await waitFor(() => {
      const patched = fetchSpy.mock.calls
        .map(([request]) => request as Request)
        .filter((req) => req.url.includes("/api/v1/projects/7"));
      expect(patched).toHaveLength(1);
    });
  });

  it("takes a correction about how unusual the week is", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "PATCH") {
        return jsonResponse({ started: true, unusual: "less_time", projects: [] });
      }
      return jsonResponse(
        weekData({
          check_in: { started: true, unusual: "usual", projects: [],
            outcomes: [],
            proposals: [],
            blockers: [],
            carryover: [],
          },
        }),
      );
    });

    renderAt("/review");
    await userEvent.selectOptions(
      await screen.findByLabelText("How is next week looking?"),
      "less_time",
    );

    await waitFor(() => {
      const patched = fetchSpy.mock.calls
        .map(([request]) => request as Request)
        .filter((req) => req.url.includes("planning-session"));
      expect(patched).toHaveLength(1);
    });
  });

  /* Outcomes -- planning-assistant-v2-plan.md increment 5, and D3 answered:
     an intention is one sentence about what a week is for, an outcome is one
     of two or three things that will be true by Friday. */
  it("offers a project the week has a reason to be about, with the reason", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          check_in: {
            started: true,
            unusual: "usual",
            projects: [],
            outcomes: [],
            proposals: [
              {
                project_id: 7,
                project_title: "Website launch",
                suggested_text: "The booking form is live.",
                because: ["Due 2026-08-28", "4 tasks already dated for it"],
              },
            ],
            blockers: [],
            carryover: [],
          },
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("Website launch")).toBeInTheDocument();
    expect(screen.getByText(/Due 2026-08-28/)).toBeInTheDocument();
    expect(screen.getByText(/4 tasks already dated for it/)).toBeInTheDocument();
  });

  it("chooses an outcome using the project's own words", async () => {
    /* Never a composed sentence: what is offered is the project's own
       `desired_outcome`, which is what increment 3 added it for. */
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") {
        return jsonResponse({
          started: true,
          unusual: "usual",
          projects: [],
          outcomes: [
            {
              id: 1,
              text: "The booking form is live.",
              project_title: "Website launch",
              project_id: 7,
            },
          ],
          proposals: [],
            blockers: [],
            carryover: [],
        });
      }
      return jsonResponse(
        weekData({
          check_in: {
            started: true,
            unusual: "usual",
            projects: [],
            outcomes: [],
            proposals: [
              {
                project_id: 7,
                project_title: "Website launch",
                suggested_text: "The booking form is live.",
                because: ["Due 2026-08-28"],
              },
            ],
            blockers: [],
            carryover: [],
          },
        }),
      );
    });

    renderAt("/review");
    await userEvent.click(
      await screen.findByRole("button", { name: "Use Website launch" }),
    );

    await waitFor(() => {
      const posted = fetchSpy.mock.calls
        .map(([request]) => request as Request)
        .filter((req) => req.url.includes("/outcomes"));
      expect(posted).toHaveLength(1);
    });
  });

  it("lists what the week is already committed to", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          check_in: {
            started: true,
            unusual: "usual",
            projects: [],
            outcomes: [
              {
                id: 1,
                text: "The booking form is live.",
                project_title: "Website launch",
                project_id: 7,
              },
            ],
            proposals: [],
            blockers: [],
            carryover: [],
          },
        }),
      ),
    );

    renderAt("/review");

    expect(
      await screen.findByText("The booking form is live."),
    ).toBeInTheDocument();
  });

  it("takes an outcome back off the week", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "DELETE") {
        return jsonResponse({
          started: true,
          unusual: "usual",
          projects: [],
          outcomes: [],
          proposals: [],
            blockers: [],
            carryover: [],
        });
      }
      return jsonResponse(
        weekData({
          check_in: {
            started: true,
            unusual: "usual",
            projects: [],
            outcomes: [
              {
                id: 1,
                text: "The booking form is live.",
                project_title: "Website launch",
                project_id: 7,
              },
            ],
            proposals: [],
            blockers: [],
            carryover: [],
          },
        }),
      );
    });

    renderAt("/review");
    await userEvent.click(
      await screen.findByRole("button", { name: "Drop this outcome" }),
    );

    await waitFor(() => {
      const deleted = fetchSpy.mock.calls
        .map(([request]) => request as Request)
        .filter((req) => req.method === "DELETE");
      expect(deleted).toHaveLength(1);
    });
  });

  /* Blockers and carryover, triaged against the outcomes -- increment 6. */
  it("names the question standing in the way, and what it blocks", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          check_in: {
            started: true,
            unusual: "usual",
            projects: [],
            outcomes: [],
            proposals: [],
            blockers: [
              {
                public_id: "11111111-1111-1111-1111-111111111111",
                text: "Which analytics provider should we use?",
                days_open: 12,
                came_back: 2,
                outcome_text: "The booking form is live.",
              },
            ],
            carryover: [],
          },
        }),
      ),
    );

    renderAt("/review");

    expect(
      await screen.findByText("Which analytics provider should we use?"),
    ).toBeInTheDocument();
    /* The evidence for the word "blocker": what it blocks, how long it has
       been open, and that it came back. */
    expect(screen.getByText(/The booking form is live\./)).toBeInTheDocument();
    expect(screen.getByText(/open 12 days/)).toBeInTheDocument();
    expect(screen.getByText(/came back twice/)).toBeInTheDocument();
  });

  it("answers a blocker in place rather than pointing at another surface", async () => {
    /* v1's review could only link out: "Decide them in Second Mind". This is
       the whole point of increment 6, and it goes through the knowledge
       core's own service so both surfaces record the same decision. */
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "POST") return jsonResponse({ public_id: "x" });
      return jsonResponse(
        weekData({
          check_in: {
            started: true,
            unusual: "usual",
            projects: [],
            outcomes: [],
            proposals: [],
            blockers: [
              {
                public_id: "11111111-1111-1111-1111-111111111111",
                text: "Which analytics provider should we use?",
                days_open: 12,
                came_back: 0,
                outcome_text: "The booking form is live.",
              },
            ],
            carryover: [],
          },
        }),
      );
    });

    renderAt("/review");
    await userEvent.click(
      await screen.findByRole("button", { name: "Settled" }),
    );

    await waitFor(() => {
      const posted = fetchSpy.mock.calls
        .map(([request]) => request as Request)
        .filter((req) => req.url.includes("/answered"));
      expect(posted).toHaveLength(1);
    });
  });

  it("marks the leftover work that serves what the week is for", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          check_in: {
            started: true,
            unusual: "usual",
            projects: [],
            outcomes: [],
            proposals: [],
            blockers: [],
            carryover: [
              {
                id: 1,
                text: "Write the copy",
                due_date: "2026-07-30",
                serves_an_outcome: true,
              },
              {
                id: 2,
                text: "Fix the gate",
                due_date: "2026-07-29",
                serves_an_outcome: false,
              },
            ],
          },
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("Write the copy")).toBeInTheDocument();
    /* Nothing is hidden: the unconnected leftover is the row most worth
       deciding about. */
    expect(screen.getByText("Fix the gate")).toBeInTheDocument();
    expect(screen.getByText(/serves an outcome/)).toBeInTheDocument();
  });

  it("lets a person say what next week is for", async () => {
    // product-stories.md S9's missing half. `WeeklyIntention` has had a model,
    // a service, a read and a Day payload since 8b02c1b, and no way in --
    // `set_intention` had no caller outside its own tests.
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      if (request.method === "PUT") {
        return jsonResponse({ week_start: "2026-08-03", text: "Ship the booking form" });
      }
      return jsonResponse(weekData());
    });

    renderAt("/review");
    await userEvent.type(
      await screen.findByLabelText("What is next week for?"),
      "Ship the booking form",
    );
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(screen.getByText("Saved what next week is for.")).toBeInTheDocument(),
    );
    // Deliberately not the bare "Saved." the review's own save shows: two
    // controls confirming with one string makes a passing query ambiguous.
    const written = fetchSpy.mock.calls
      .map(([request]) => request as Request)
      .filter((request) => request.method === "PUT");
    expect(written).toHaveLength(1);
    // Addressed to the week being drafted, which is the week *after* the one
    // on screen -- drafting the reviewed week would plan a week that has
    // already happened.
    expect(written[0].url).toContain("/api/v1/weeks/2026-08-03/intention");
  });

  it("offers the intention even when nothing is dated into next week", async () => {
    // The proposal list is hidden when empty, because an empty planner reads
    // as one that failed. A writing prompt is not an empty state, and a week
    // with nothing scheduled is exactly when saying what it is for matters.
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse(weekData()));

    renderAt("/review");

    expect(
      await screen.findByLabelText("What is next week for?"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Also running")).toBeNull();
  });

  it("seeds the field with what the week already says", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          draft: {
            week_start: "2026-08-03",
            intention: "Get the launch review done",
            proposed: [],
            routines: [],
            typical_week: null,
            over_committed: false,
          },
        }),
      ),
    );

    renderAt("/review");

    await waitFor(() =>
      expect(screen.getByLabelText("What is next week for?")).toHaveValue(
        "Get the launch review done",
      ),
    );
  });

  it("shows the figure the review recorded rather than a live recount", async () => {
    // The whole reason for stamping: a task deleted from the archive
    // afterwards moves the live number, and a conclusion drawn on a Sunday
    // should not be edited by a tidy-up on a Tuesday.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          planned: {
            total: 1,
            met: 0,
            met_tasks: [],
            unfinished: [plannedTask()],
            set_aside: [],
          },
          review: {
            reflections: "",
            plan: "",
            completed_at: "2026-08-02T18:00:00+00:00",
            recorded_total: 1,
            recorded_met: 1,
          },
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("1 of 1")).toBeInTheDocument();
    expect(screen.getByText(/as you recorded it/i)).toBeInTheDocument();
  });

  it("offers a way back out of a completed review", async () => {
    // A one-way door on a mis-tap is not a recoverable failure.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          review: {
            reflections: "",
            plan: "",
            completed_at: "2026-08-02T18:00:00+00:00",
            recorded_total: 0,
            recorded_met: 0,
          },
        }),
      ),
    );

    renderAt("/review");

    expect(
      await screen.findByRole("button", { name: "Reopen this review" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Mark this week reviewed" }),
    ).toBeNull();
  });

  it("puts one unfinished commitment on today, and only that one", async () => {
    // Through the day's own pin endpoint rather than a review-shaped write
    // path: the service that owns pinning still owns it.
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() =>
        jsonResponse(
          weekData({
            planned: {
              total: 2,
              met: 0,
              met_tasks: [],
              unfinished: [
                plannedTask({ task_id: 3, text: "Call the bank" }),
                plannedTask({ task_id: 4, text: "Fix the gate" }),
              ],
              set_aside: [],
            },
          }),
        ),
      );

    renderAt("/review");
    await userEvent.click(
      await screen.findByRole("button", { name: "Put Call the bank on today" }),
    );

    const pins = fetchSpy.mock.calls
      .map(([request]) => request as Request)
      .filter((request) => request.url.includes("/focus"));
    expect(pins).toHaveLength(1);
    expect(pins[0].url).toContain("/api/v1/day/2026-08-02/focus");
    // Typographic apostrophe, as the rest of the app renders one.
    expect(await screen.findByText(/On today.s page/)).toBeInTheDocument();
  });

  it("offers nothing that acts on more than one commitment", async () => {
    // The forbidden convenience. daily-operating-system-vision.md: never
    // automatically reschedule everything left incomplete.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          planned: {
            total: 2,
            met: 0,
            met_tasks: [],
            unfinished: [
              plannedTask({ task_id: 3, text: "Call the bank" }),
              plannedTask({ task_id: 4, text: "Fix the gate" }),
            ],
            set_aside: [],
          },
        }),
      ),
    );

    renderAt("/review");
    await screen.findByRole("button", { name: "Put Call the bank on today" });

    expect(
      screen.getAllByRole("button", { name: /Put .* on today/ }),
    ).toHaveLength(2);
    // Word-anchored: an unanchored /all/ matches "Call the bank", which is
    // how this assertion first failed against a page that was correct.
    expect(
      screen.queryByRole("button", {
        name: /\b(all|everything|forward)\b/i,
      }),
    ).toBeNull();
  });

  it("does not offer to move something that is already on today", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          planned: {
            total: 1,
            met: 0,
            met_tasks: [],
            unfinished: [plannedTask({ task_id: 3, day: "2026-08-02" })],
            set_aside: [],
          },
        }),
      ),
    );

    renderAt("/review");
    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByRole("button", { name: /on today/ })).toBeNull();
  });

  it("reads a habit as met over the periods the week expected", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          habits: [
            {
              routine_id: 1,
              title: "Practice Spanish",
              cadence: "daily",
              unit: "lessons",
              met: 5,
              expected: 7,
              skipped: 0,
              periods: [
                habitPeriod({ period_start: "2026-07-27", outcome: "completed", progress: 5 }),
                habitPeriod({ period_start: "2026-07-28", outcome: "open", progress: 2 }),
              ],
            },
          ],
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("Practice Spanish")).toBeInTheDocument();
    expect(screen.getByText("5 of 7")).toBeInTheDocument();
  });

  it("says what became of each period without calling any of it missed", async () => {
    // crane-plan.md §3: an elapsed-open period gets described here, not
    // relabelled. "Missed" is the verdict the product does not assert.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          habits: [
            {
              routine_id: 1,
              title: "Practice Spanish",
              cadence: "daily",
              unit: "lessons",
              met: 1,
              expected: 2,
              skipped: 1,
              periods: [
                habitPeriod({ period_start: "2026-07-27", outcome: "completed", progress: 5 }),
                habitPeriod({ period_start: "2026-07-28", outcome: "skipped" }),
                habitPeriod({ period_start: "2026-07-29", outcome: "open", progress: 2 }),
              ],
            },
          ],
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByLabelText(/Monday: 5 of 5/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Tuesday: skipped/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Wednesday: 2 of 5/)).toBeInTheDocument();
    expect(screen.queryByText(/missed/i)).toBeNull();
  });

  it("says how many periods were skipped rather than hiding them in the figure", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          habits: [
            {
              routine_id: 1,
              title: "Practice Spanish",
              cadence: "daily",
              unit: "lessons",
              met: 5,
              expected: 6,
              skipped: 1,
              periods: [habitPeriod({ outcome: "skipped" })],
            },
          ],
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("5 of 6")).toBeInTheDocument();
    expect(screen.getByText(/1 skipped/)).toBeInTheDocument();
  });

  it("says a routine was paused rather than showing it as a row of nothing", async () => {
    // §8's answer to the first question §3 left open. Silence reads the
    // same as a routine that did not exist yet.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          habits: [
            {
              routine_id: 1,
              title: "Practice Spanish",
              cadence: "daily",
              unit: "lessons",
              met: 0,
              expected: 0,
              skipped: 0,
              enough: 0,
              paused_since: "2026-07-20",
              paused_days: 7,
              periods: [],
            },
          ],
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText(/Paused since 20 July|Paused since July 20/)).toBeInTheDocument();
    expect(screen.queryByText(/0 of 0/)).toBeNull();
  });

  it("counts the days a mid-week pause took out, without claiming it is still down", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          habits: [
            {
              routine_id: 1,
              title: "Practice Spanish",
              cadence: "daily",
              unit: "lessons",
              met: 3,
              expected: 4,
              skipped: 0,
              enough: 0,
              paused_since: null,
              paused_days: 3,
              periods: [habitPeriod({ outcome: "completed", progress: 5 })],
            },
          ],
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("3 of 4")).toBeInTheDocument();
    expect(screen.getByText(/3 days paused/)).toBeInTheDocument();
    expect(screen.queryByText(/Paused since/)).toBeNull();
  });

  it("reports a period called enough as neither met nor skipped", async () => {
    // Crane 3 slice 8. Three states, three readings: a skip says the thing
    // was not done, this says some of it was and that was right.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          habits: [
            {
              routine_id: 1,
              title: "Practice Spanish",
              cadence: "daily",
              unit: "lessons",
              met: 4,
              expected: 6,
              skipped: 0,
              enough: 1,
              paused_since: null,
              paused_days: 0,
              periods: [
                habitPeriod({
                  period_start: "2026-07-27",
                  outcome: "partial",
                  progress: 3,
                }),
              ],
            },
          ],
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByLabelText(/Monday: 3 of 5 — enough/)).toBeInTheDocument();
    expect(screen.getByText(/1 called enough/)).toBeInTheDocument();
    expect(screen.queryByText(/skipped/)).toBeNull();
  });

  it("leaves the habits section out when no routine existed", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(weekData()),
    );

    renderAt("/review");
    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByText("Habits")).toBeNull();
  });

  it("puts the week beside the four before it", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          recent_weeks: [
            weekSummary({ week_start: "2026-06-29", planned_met: 1, planned_total: 4 }),
            weekSummary({ week_start: "2026-07-06", planned_met: 2, planned_total: 4 }),
            weekSummary({ week_start: "2026-07-13", planned_met: 3, planned_total: 4 }),
            weekSummary({ week_start: "2026-07-20", planned_met: 4, planned_total: 4 }),
            weekSummary({
              week_start: "2026-07-27",
              is_shown_week: true,
              planned_met: 2,
              planned_total: 3,
            }),
          ],
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("Recent weeks")).toBeInTheDocument();
    const rows = screen.getAllByRole("listitem", { name: /week of/i });
    expect(rows).toHaveLength(5);
    // The one being read is marked, so a row cannot be mistaken for
    // another week's.
    expect(screen.getByText("this week")).toBeInTheDocument();
  });

  it("says a week has no data rather than printing nought of nought", async () => {
    // The distinction the whole release is about. A week before somebody
    // was here is not a week in which they planned nothing.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          recent_weeks: [
            weekSummary({ week_start: "2026-06-29" }),
            weekSummary({
              week_start: "2026-07-27",
              is_shown_week: true,
              planned_met: 0,
              planned_total: 0,
              habits_met: 0,
              habits_expected: 0,
            }),
          ],
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("Nothing recorded yet")).toBeInTheDocument();
  });

  it("leaves the trend out entirely when there is no history behind it", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          recent_weeks: [
            weekSummary({ week_start: "2026-07-20" }),
            weekSummary({ week_start: "2026-07-27", is_shown_week: true }),
          ],
        }),
      ),
    );

    renderAt("/review");
    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByText("Recent weeks")).toBeNull();
  });

  it("reaches the week before without editing the URL", async () => {
    // The missing surface this sequence has now shipped twice. A review is
    // written on a Monday about the week that just ended, so the week
    // before has to be one click from the default.
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => jsonResponse(weekData()));

    renderAt("/review");
    await screen.findByRole("heading", { level: 1 });
    await userEvent.click(screen.getByRole("link", { name: /week before/i }));

    expect(
      fetchSpy.mock.calls.some((call) =>
        String((call[0] as Request).url).includes("/api/v1/review/2026-07-20"),
      ),
    ).toBe(true);
  });

  it("offers no way forward from the week in progress", async () => {
    // There is nothing to review in a week that has not started, and a
    // control that leads somewhere empty invites the conclusion that the
    // page is broken.
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(weekData({ is_current_week: true })),
    );

    renderAt("/review");
    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByRole("link", { name: /week after/i })).toBeNull();
  });

  it("offers the week after once you are looking at a past one", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(weekData({ is_current_week: false })),
    );

    renderAt("/review/2026-07-27");

    expect(
      await screen.findByRole("link", { name: /week after/i }),
    ).toBeInTheDocument();
  });

  /* Loose ends and upcoming constraints -- planning-assistant-plan.md
     increment 5. Extractive: every item already belongs to the person, so
     these sections show and never propose. */
  it("shows a question nothing has answered, with when it was asked", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          loose_ends: {
            unanswered: [
              {
                public_id: "11111111-1111-1111-1111-111111111111",
                text: "Which payment provider should we use?",
                asked_on: "2026-07-21",
              },
            ],
            unanswered_commitments: [],
            overdue: [],
          },
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText(/which payment provider/i)).toBeInTheDocument();
    // The date is the evidence: "you asked this" is a fact, "on the 21st" is
    // what makes it a loose end rather than a note.
    expect(screen.getByText(/2026-07-21/)).toBeInTheDocument();
  });

  it("shows a commitment nobody accepted or dismissed", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          loose_ends: {
            unanswered: [],
            unanswered_commitments: [
              {
                id: 12,
                text: "I must ring the venue on Thursday.",
                source: "journal",
                proposed_on: "2026-07-25",
              },
            ],
            overdue: [],
          },
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText(/ring the venue/i)).toBeInTheDocument();
  });

  it("shows overdue work as a loose end", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          loose_ends: {
            unanswered: [],
            unanswered_commitments: [],
            overdue: [{ id: 4, text: "Chase the invoice", due_date: "2026-07-20" }],
          },
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText(/chase the invoice/i)).toBeInTheDocument();
  });

  it("shows what arrives before the next review", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          upcoming: {
            tasks: [{ id: 9, text: "Send the deposit", due_date: "2026-08-05" }],
            projects: [{ id: 2, title: "Website launch", due_date: "2026-08-07" }],
          },
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText(/send the deposit/i)).toBeInTheDocument();
    expect(screen.getByText(/website launch/i)).toBeInTheDocument();
  });

  it("stays quiet when there is nothing hanging and nothing coming", async () => {
    /* An empty section is worse than no section here: "you have no loose
       ends" and "this week had none worth showing" read the same, and a
       review that renders five empty headings teaches you to scroll past all
       five. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse(weekData()));

    renderAt("/review");
    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByText(/still unanswered/i)).toBeNull();
    expect(screen.queryByText(/before the next review/i)).toBeNull();
  });

  /* Next week, drafted -- planning-assistant-plan.md increment 6, the last of
     the six. A proposal: nothing is pinned and ignoring it costs nothing. */
  it("proposes next week's dated work", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          draft: {
            week_start: "2026-08-03",
            intention: "Ship the booking form.",
            proposed: [{ id: 3, text: "Chase the invoice", due_date: "2026-07-30" }],
            routines: [],
            typical_week: 4,
            over_committed: false,
          },
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText("Ship the booking form.")).toBeInTheDocument();
    expect(screen.getByText("Chase the invoice")).toBeInTheDocument();
  });

  it("says the week holds less than this, without saying you failed", async () => {
    /* The vision document asks that history be useful without making missed
       work feel like punishment, and a planner is the surface most able to
       break that. The wording states capacity; it does not grade anybody. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          draft: {
            week_start: "2026-08-03",
            intention: "",
            proposed: [
              { id: 1, text: "One", due_date: "2026-08-04" },
              { id: 2, text: "Two", due_date: "2026-08-05" },
            ],
            routines: [],
            typical_week: 1,
            over_committed: true,
          },
        }),
      ),
    );

    renderAt("/review");

    expect(await screen.findByText(/finished 1 in a typical week/i)).toBeInTheDocument();
    expect(screen.queryByText(/only finish/i)).toBeNull();
  });

  it("offers no capacity when there is not enough history", async () => {
    /* Null, never zero. "No evidence yet" and "you have room" call for
       opposite responses, and a page rendering 0 would show the second. */
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse(
        weekData({
          draft: {
            week_start: "2026-08-03",
            intention: "",
            proposed: [{ id: 1, text: "One", due_date: "2026-08-04" }],
            routines: [],
            typical_week: null,
            over_committed: false,
          },
        }),
      ),
    );

    renderAt("/review");
    await screen.findByText("One");

    expect(screen.queryByText(/typical week/i)).toBeNull();
  });

  it("stays quiet when there is nothing to propose", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse(weekData()));

    renderAt("/review");
    await screen.findByRole("heading", { level: 1 });

    // **Narrowed rather than deleted when S9's field arrived.** This asserted
    // that the whole "Next week" heading was absent, on the argument that an
    // empty planner reads as one that failed. The section now always carries
    // a box asking what next week is for, so the heading is no longer over
    // nothing and that assertion was wrong about the new contract -- but what
    // it was protecting is unchanged, and is what this now checks: nothing
    // *proposed* is shown when there is nothing to propose.
    expect(screen.queryByText(/dated for next week/)).toBeNull();
    expect(screen.queryByText("Also running")).toBeNull();
    // Scoped to this section's heading. The review already carries a "Plan
    // for next week" field of the person's own words, which is a different
    // thing living happily beside the proposal and must not be asserted away.
    expect(screen.getByRole("heading", { name: "Next week" })).toBeInTheDocument();
  });
});