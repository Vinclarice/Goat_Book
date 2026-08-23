import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";

import { ProjectRoute } from "./ProjectRoute";

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

function projectDetailData(overrides: Record<string, unknown> = {}) {
  return {
    id: 3,
    title: "Website Relaunch",
    due_date: null,
    is_completed: false,
    completed_at: null,
    desired_outcome: "",
    abandon_if: "",
    learned: "",
    notes: "",
    paused_at: null,
    created_at: "2026-08-10T09:00:00-04:00",
    open_task_count: 0,
    areas: [],
    is_overdue: false,
    ...overrides,
  };
}

/* The retrospective -- S12.

   Unlike the brief it loads without being asked, and the difference is the
   Attention Policy rather than an inconsistency: the policy permits a queue
   inside a ritual somebody chose to open, and marking a project complete is
   that ritual. Having just declared the work over, being shown what it came
   to is the thing asked for. */
const RETRO = {
  weeks: [
    { week_start: "2026-03-02", met: 2, unfinished: 1, set_aside: 0 },
    { week_start: "2026-03-09", met: 0, unfinished: 0, set_aside: 0 },
    { week_start: "2026-03-16", met: 1, unfinished: 0, set_aside: 2 },
  ],
  met: 3,
  unfinished: 1,
  set_aside: 2,
  notes: [
    {
      id: "55555555-5555-5555-5555-555555555555",
      text: "The form needs a deposit field.",
      captured_at: "2026-03-03T09:00:00-04:00",
    },
  ],
  decisions: [
    {
      id: "66666666-6666-6666-6666-666666666666",
      question: "Deposit up front?",
      chose: "Yes, 20%",
      considered: "Invoice afterwards",
      decided_at: "2026-03-04T09:00:00-04:00",
    },
  ],
  learned: "",
  quiet_says: "Then 8 weeks with nothing pinned to a day for it, before you marked it done",
};


/* Everything the project page fetches that is *not* the project.
 *
 * **One place, because three separate hand-rolled mocks broke on one new
 * sub-component in a single day.** Each of these mocks ends with a catch-all
 * returning the project payload, so a request nobody anticipated does not fail
 * loudly — it succeeds with the wrong shape, and the component reading it takes
 * the whole route down. `ProjectRetrospective` reading `data.weeks.length` off a
 * project is what that looks like.
 *
 * Returns null when the URL is the project's own, which is the caller's to
 * answer because only the caller knows what state it is testing.
 */
function sideRequests(url: string) {
  if (url.includes("/api/v1/nav")) return jsonResponse(NAV);
  if (url.includes("/retrospective")) return jsonResponse(RETRO);
  return null;
}

const NAV = {
  areas: [],
  projects: [],
  archived_count: 0,
  settings_url: "/accounts/settings/",
};

/* ProjectRoute also fetches /api/v1/nav for its "add an area" picker. Every
   mock below has to answer that request too, or the picker throws
   mid-render and takes the whole route with it. */
function projectPageFetch(data: object = projectDetailData()) {
  return (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : (input as Request).url;
    const side = sideRequests(url);
    if (side) return side;
    return jsonResponse(data);
  };
}

function renderAt(projectId: string) {
  // Mirrors main.tsx: retry off, everything else at TanStack's defaults. The
  // default staleTime of 0 is what makes a background refetch possible at
  // all, so pinning it here would prove nothing about the real app.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    queryClient,
    ...render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/projects/${projectId}`]}>
        <Routes>
          <Route path="/projects/:projectId" element={<ProjectRoute />} />
          <Route path="/agenda" element={<p>Agenda page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
    ),
  };
}

describe("ProjectRoute", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    document.cookie = "csrftoken=test-token";
  });

  it("renders the project's title and open count", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(projectPageFetch());

    renderAt("3");

    expect(await screen.findByDisplayValue("Website Relaunch")).toBeInTheDocument();
    expect(screen.getByText(/0 open/)).toBeInTheDocument();
  });

  it("shows a due date as a plain calendar value, not a shifted instant", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      projectPageFetch(projectDetailData({ due_date: "2026-09-30" })),
    );

    renderAt("3");

    expect(await screen.findByLabelText("Due date")).toHaveValue("2026-09-30");
  });

  it("says so when no due date is set, and stops once one is", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(projectPageFetch());

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");
    expect(screen.getByText("No due date set")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Due date"), {
      target: { value: "2026-09-30" },
    });

    expect(screen.queryByText("No due date set")).not.toBeInTheDocument();
  });

  /* The purpose field -- planning-assistant-plan.md increment 3.
     Until this exists nothing can write a purpose except the API, and
     increment 4's brief anchors on exactly this text: a project carrying only
     a title gives its matcher nothing to work with. */
  it("shows a project's purpose", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      projectPageFetch(projectDetailData({ purpose: "Stop losing bookings to email." })),
    );

    renderAt("3");

    expect(await screen.findByLabelText("Purpose")).toHaveValue(
      "Stop losing bookings to email.",
    );
  });

  it("invites one when the project has none", async () => {
    /* An empty textarea reads the same whether nobody has written a purpose
       or somebody meant to and didn't -- the same gap the due-date hint
       fills, and it matters more here because the brief is silent without
       one and cannot say why. */
    vi.spyOn(globalThis, "fetch").mockImplementation(projectPageFetch());

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");

    expect(screen.getByText(/no purpose written/i)).toBeInTheDocument();
  });

  it("saves a purpose", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      const side = sideRequests(url);
      if (side) return side;
      if (request.method === "PATCH") {
        return jsonResponse(projectDetailData({ purpose: "Ship the booking form." }));
      }
      return jsonResponse(projectDetailData());
    });

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");

    await user.type(screen.getByLabelText("Purpose"), "Ship the booking form.");
    await user.click(screen.getByRole("button", { name: "Save purpose" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) => {
          const req = request as Request;
          return req.method === "PATCH" && req.url.includes("/api/v1/projects/3");
        }),
      ).toBe(true);
    });
  });

  /* The desired outcome and the pause -- planning-assistant-v2-plan.md
     increment 3. The outcome is a second anchor for the brief's retrieval; the
     pause is what lets a weekly check-in confirm what is active rather than
     ask. */
  it("shows a project's desired outcome", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      projectPageFetch(
        projectDetailData({ desired_outcome: "The booking form is live." }),
      ),
    );

    renderAt("3");

    expect(
      await screen.findByDisplayValue("The booking form is live."),
    ).toBeInTheDocument();
  });

  it("saves a desired outcome", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      const side = sideRequests(url);
      if (side) return side;
      if (request.method === "PATCH") {
        return jsonResponse(
          projectDetailData({ desired_outcome: "The booking form is live." }),
        );
      }
      return jsonResponse(projectDetailData());
    });

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");

    await user.type(
      screen.getByLabelText("What done looks like"),
      "The booking form is live.",
    );
    await user.click(screen.getByRole("button", { name: "Save outcome" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) => {
          const req = request as Request;
          return req.method === "PATCH" && req.url.includes("/api/v1/projects/3");
        }),
      ).toBe(true);
    });
  });

  /* What going wrong looks like -- S10, and D4 answered as *two fields*. Its
     own box and its own save, because a tripwire you cannot tell from an
     ambition can never be checked. */
  it("shows what would tell you a project went wrong", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      projectPageFetch(
        projectDetailData({ abandon_if: "Three months with no chapter." }),
      ),
    );

    renderAt("3");

    expect(
      await screen.findByDisplayValue("Three months with no chapter."),
    ).toBeInTheDocument();
  });

  it("keeps the abandonment condition apart from the outcome", async () => {
    /* The distinction the whole story is about. Two boxes with two values, so
       neither can be mistaken for the other. */
    vi.spyOn(globalThis, "fetch").mockImplementation(
      projectPageFetch(
        projectDetailData({
          desired_outcome: "A finished draft.",
          abandon_if: "Three months with no chapter.",
        }),
      ),
    );

    renderAt("3");

    expect(await screen.findByLabelText("What done looks like")).toHaveValue(
      "A finished draft.",
    );
    expect(
      screen.getByLabelText("What would tell you it went wrong"),
    ).toHaveValue("Three months with no chapter.");
  });

  it("saves an abandonment condition", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      const side = sideRequests(url);
      if (side) return side;
      if (request.method === "PATCH") {
        return jsonResponse(
          projectDetailData({ abandon_if: "Three months with no chapter." }),
        );
      }
      return jsonResponse(projectDetailData());
    });

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");

    await user.type(
      screen.getByLabelText("What would tell you it went wrong"),
      "Three months with no chapter.",
    );
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) => {
          const req = request as Request;
          return req.method === "PATCH" && req.url.includes("/api/v1/projects/3");
        }),
      ).toBe(true);
    });
  });

  it("parks a project without finishing it", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      const side = sideRequests(url);
      if (side) return side;
      if (request.method === "PATCH") {
        return jsonResponse(
          projectDetailData({ paused_at: "2026-08-19T09:00:00-04:00" }),
        );
      }
      return jsonResponse(projectDetailData());
    });

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");

    await user.click(screen.getByRole("button", { name: "Pause" }));

    await waitFor(() => {
      const patched = fetchMock.mock.calls
        .map(([request]) => request as Request)
        .filter((req) => req.method === "PATCH");
      expect(patched).toHaveLength(1);
    });
  });

  it("says a project is paused, and offers to pick it back up", async () => {
    /* Paused is not finished, and the page has to say which. A parked project
       that looked identical to an active one would make the state cosmetic. */
    vi.spyOn(globalThis, "fetch").mockImplementation(
      projectPageFetch(
        projectDetailData({ paused_at: "2026-08-19T09:00:00-04:00" }),
      ),
    );

    renderAt("3");

    expect(await screen.findByText("Paused")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resume" })).toBeInTheDocument();
  });

  it("will not save a purpose that has not changed", async () => {
    /* The same guard the name and date buttons carry. A PATCH that writes
       what is already there is a write nobody asked for, and on this field
       it would also be the thing that makes a brief look freshly considered
       when nothing was reconsidered. */
    vi.spyOn(globalThis, "fetch").mockImplementation(
      projectPageFetch(projectDetailData({ purpose: "Already written." })),
    );

    renderAt("3");
    await screen.findByLabelText("Purpose");

    expect(screen.getByRole("button", { name: "Save purpose" })).toBeDisabled();
  });

  /* The brief -- planning-assistant-plan.md increment 4.

     Asked for, never implied. That is not a performance preference dressed up:
     the Attention Policy permits a queue only inside a ritual the person chose
     to open, and a panel that retrieved on every render of a page that mostly
     wants a title would be the unsolicited one. */
  const BRIEF = {
    material: [
      {
        id: "11111111-1111-1111-1111-111111111111",
        text: "The booking form should collect the venue and the enquiries contact.",
        captured_at: "2026-08-01T09:00:00-04:00",
        reason: "3 of 5 shared terms appear in almost none of your other notes: booking, venue, enquiries",
        distinctive_terms: ["booking", "venue", "enquiries"],
      },
    ],
    questions: [
      {
        id: "22222222-2222-2222-2222-222222222222",
        text: "Which payment provider should we use?",
        captured_at: "2026-07-20T09:00:00-04:00",
        reason: "2 of 4 shared terms appear in almost none of your other notes: payment, provider",
        distinctive_terms: ["payment", "provider"],
      },
    ],
    commitments: [{ id: 7, text: "Draft the booking form copy", due_date: "2026-09-01" }],
    /* S16's other two nouns, unblocked on August 22 2026 when Source and
       Decision shipped hours apart. The story's done-means is "notes,
       decisions and sources"; this payload carried one of three until then. */
    sources: [
      {
        id: "33333333-3333-3333-3333-333333333333",
        title: "Booking systems for small venues",
        author: "R. Iyer",
        url: "",
        reason:
          "you read this, and 2 notes here came out of it, including: The booking form should collect…",
        note_count: 2,
      },
    ],
    decisions: [
      {
        id: "44444444-4444-4444-4444-444444444444",
        question: "How do we take bookings?",
        chose: "A form on the site",
        considered: "Keep the inbox and triage it",
        decided_at: "2026-07-02T09:00:00-04:00",
        superseded: false,
        reason:
          "you decided this while looking at: The booking form should collect the venue…",
      },
    ],
    learned_before: [
      {
        project_id: 9,
        project_title: "The old site",
        learned: "Start with the deposit rules, not the form layout.",
      },
    ],
    provenance_says: "",
    abandon_if: "Three months with no booking taken through it",
  };

  /* Every field the payload declares, because it declares them all. Written
     out rather than derived from BRIEF so that a new section added to one does
     not silently appear in the other -- the empty case is the one where a
     missing key would crash the panel rather than merely under-render it, which
     is exactly what happened when sources and decisions were added. */
  const EMPTY_BRIEF = {
    material: [],
    questions: [],
    commitments: [],
    sources: [],
    decisions: [],
    learned_before: [],
    provenance_says: "",
    abandon_if: "",
  };

  function briefPageFetch(brief: object = BRIEF, detail: object = projectDetailData()) {
    return (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      // Its own override first, then the shared ones: several tests below vary
      // the brief on purpose, and a shared answer would quietly win.
      if (url.includes("/brief")) return jsonResponse(brief);
      const side = sideRequests(url);
      if (side) return side;
      return jsonResponse(detail);
    };
  }

  it("does not fetch a brief until it is asked for", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(briefPageFetch());

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");

    expect(
      fetchMock.mock.calls.some(([request]) => {
        const url = typeof request === "string" ? request : (request as Request).url;
        return url.includes("/brief");
      }),
    ).toBe(false);
  });

  it("shows prior material, loose ends and dated work when asked", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(briefPageFetch());

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");
    await user.click(screen.getByRole("button", { name: /what bears on this/i }));

    /* `findAllByText` since August 22 2026, and the ambiguity is real rather
       than a test artefact: a source's reason cites one of the surfaced notes,
       so that note's opening words legitimately appear twice on the page --
       once as the note and once inside the citation naming it. Asserting a
       count would be worse, since it would break whenever a section is added.
       This asserts the note is present; the section tests below assert where. */
    expect(
      (await screen.findAllByText(/booking form should collect the venue/i)).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(/which payment provider/i)).toBeInTheDocument();
    expect(screen.getByText(/draft the booking form copy/i)).toBeInTheDocument();
  });

  it("shows the evidence that selected each item", async () => {
    /* The reason is the whole mechanic. Without it the panel can only say
       "related", which is the unfalsifiable label precision.md exists to
       avoid -- a person can check "these share three words appearing in none
       of your other notes" and cannot check a score. */
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(briefPageFetch());

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");
    await user.click(screen.getByRole("button", { name: /what bears on this/i }));

    // Both retrieved sections carry it, not just the first -- asserted as a
    // count because the singular form passed on one and would have gone on
    // passing if the other had quietly stopped showing its evidence.
    const reasons = await screen.findAllByText(
      /appear in almost none of your other notes/i,
    );
    expect(reasons).toHaveLength(2);
    expect(reasons[0]).toHaveTextContent("payment, provider");
  });

  it("offers the sources this project's material came out of", async () => {
    /* S16's second noun. Reached through `Node.came_from` -- a column somebody
       wrote -- rather than by matching the source's title against the purpose,
       which would be a similarity score wearing a causal word. */
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(briefPageFetch());

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");
    await user.click(screen.getByRole("button", { name: /what bears on this/i }));

    expect(
      await screen.findByText(/booking systems for small venues/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/2 notes here came out of it/i)).toBeInTheDocument();
  });

  it("offers the decisions taken while looking at it", async () => {
    /* S16's third noun, and the half a note cannot keep: `considered` is what
       you have forgotten eighteen months later. */
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(briefPageFetch());

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");
    await user.click(screen.getByRole("button", { name: /what bears on this/i }));

    expect(await screen.findByText(/how do we take bookings/i)).toBeInTheDocument();
    expect(screen.getByText(/keep the inbox and triage it/i)).toBeInTheDocument();
  });

  it("marks a decision that was later replaced", async () => {
    /* Superseded decisions come with the brief on purpose -- "what he learned
       last time" includes the answer he changed. Shown but marked, because a
       replaced decision presented as current is worse than omitting it. */
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      briefPageFetch({
        ...BRIEF,
        decisions: [{ ...BRIEF.decisions[0], superseded: true }],
      }),
    );

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");
    await user.click(screen.getByRole("button", { name: /what bears on this/i }));

    expect(await screen.findByText(/later replaced/i)).toBeInTheDocument();
  });

  it("says when nothing records where the material came from", async () => {
    /* D5's discipline, one axis over. An empty section cannot distinguish
       "nothing bears on this" from "nothing records its provenance", and today
       the second is the true one -- both columns got their first writing
       surface the day before this shipped. */
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      briefPageFetch({
        ...BRIEF,
        sources: [],
        decisions: [],
        provenance_says:
          "none of the notes here record where they came from or what you decided from them, so nothing can be reached that way yet",
      }),
    );

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");
    await user.click(screen.getByRole("button", { name: /what bears on this/i }));

    expect(
      await screen.findByText(/record where they came from/i),
    ).toBeInTheDocument();
  });

  it("keeps the abandonment condition in front of you while deciding", async () => {
    /* S10's second clause -- "still there when he is deciding whether to
       continue" -- which the brief payload dropped from the day the field was
       added until August 22 2026. The brief is the moment of deciding. */
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(briefPageFetch());

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");
    await user.click(screen.getByRole("button", { name: /what bears on this/i }));

    expect(
      await screen.findByText(/three months with no booking taken through it/i),
    ).toBeInTheDocument();
  });

  it("carries what earlier finished projects taught", async () => {
    /* S12's "kept for next time". A lesson stored where only its own finished
       project can show it has been filed, not kept -- and the moment it matters
       is the next project, which is the one whose brief this is. */
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(briefPageFetch());

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");
    await user.click(screen.getByRole("button", { name: /what bears on this/i }));

    expect(
      await screen.findByText(/start with the deposit rules/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/from the old site/i)).toBeInTheDocument();
  });

  function retroPageFetch(retro: object = RETRO) {
    const detail = projectDetailData({ is_completed: true });
    return (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      // Same rule: this one varies the retrospective.
      if (url.includes("/retrospective")) return jsonResponse(retro);
      if (url.includes("/brief")) return jsonResponse(BRIEF);
      const side = sideRequests(url);
      if (side) return side;
      return jsonResponse(detail);
    };
  }

  it("does not offer a retrospective while the project is running", async () => {
    /* "What did this come to" only has an answer once the answer has stopped
       changing. Before that it is a status report, which the brief already is. */
    vi.spyOn(globalThis, "fetch").mockImplementation(briefPageFetch());

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");

    expect(screen.queryByText(/what this came to/i)).not.toBeInTheDocument();
  });

  it("shows what the project came to once it is complete", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(retroPageFetch());

    renderAt("3");

    expect(await screen.findByText(/what this came to/i)).toBeInTheDocument();
    expect(
      screen.getByText(/finished 3 of the 4 things you pinned/i),
    ).toBeInTheDocument();
  });

  it("says set-aside separately, because it is not a shortfall", async () => {
    /* A pin dropped on purpose was a decision, and folding it into the
       denominator would report deliberate pruning as slippage. Same honest
       denominator the weekly review keeps. */
    vi.spyOn(globalThis, "fetch").mockImplementation(retroPageFetch());

    renderAt("3");

    expect(
      await screen.findByText(/set aside 2 more on purpose/i),
    ).toBeInTheDocument();
  });

  it("shows every week including the ones with nothing in them", async () => {
    /* A fortnight of silence in the middle of a quarter is the most legible
       thing a retrospective can show, and a list of only the busy weeks hides
       exactly that. */
    vi.spyOn(globalThis, "fetch").mockImplementation(retroPageFetch());

    renderAt("3");

    expect(await screen.findByText("2026-03-09")).toBeInTheDocument();
  });

  it("says a long silence before closing in one line, not twenty rows", async () => {
    /* Found in a browser: the first version rendered every week up to the
       close, which put twenty-two empty rows under a three-week project nobody
       had got round to marking done -- and made it read as a six-month one. */
    vi.spyOn(globalThis, "fetch").mockImplementation(retroPageFetch());

    renderAt("3");

    expect(
      await screen.findByText(/8 weeks with nothing pinned/i),
    ).toBeInTheDocument();
  });

  it("shows the decisions and the notes that became work", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(retroPageFetch());

    renderAt("3");

    expect(await screen.findByText(/deposit up front/i)).toBeInTheDocument();
    expect(screen.getByText(/needs a deposit field/i)).toBeInTheDocument();
  });

  it("lets him add what he would do differently", async () => {
    /* The one thing on the page no row can answer, which is why it is the only
       stored part of an otherwise entirely derived read.

       The body is captured in the mock rather than read off the call: every
       sibling test here asserts only method-and-URL, because openapi-fetch
       passes a single `Request` and its body is not on the arguments. Cloning
       it inside the mock is what makes this assert the sentence actually
       travelled rather than merely that a PATCH happened. */
    const user = userEvent.setup();
    const answered = retroPageFetch();
    const bodies: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const request = input as Request;
      if (request instanceof Request && request.method === "PATCH") {
        bodies.push(await request.clone().text());
      }
      return answered(input, init);
    });

    renderAt("3");
    const box = await screen.findByLabelText(/what would you do differently/i);
    await user.type(box, "Deposit rules first.");
    // Scoped to its own form: the abandonment-condition box also has a plain
    // "Save", and scoping is truer than renaming one of them to suit a query.
    await user.click(
      within(box.closest("form") as HTMLFormElement).getByRole("button", {
        name: "Save",
      }),
    );

    await waitFor(() => {
      expect(bodies.join(" ")).toContain("Deposit rules first.");
    });
  });

  it("says why a brief is empty when the project has no purpose", async () => {
    /* An empty brief and an unanchored one look identical and mean opposite
       things: "nothing of yours bears on this" versus "you have not told me
       what this is". */
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      briefPageFetch(EMPTY_BRIEF),
    );

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");
    await user.click(screen.getByRole("button", { name: /what bears on this/i }));

    expect(await screen.findByText(/needs a purpose/i)).toBeInTheDocument();
  });

  it("says nothing was found when the project does have a purpose", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      briefPageFetch(
        EMPTY_BRIEF,
        projectDetailData({ purpose: "Ship the booking form." }),
      ),
    );

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");
    await user.click(screen.getByRole("button", { name: /what bears on this/i }));

    expect(await screen.findByText(/nothing you have written/i)).toBeInTheDocument();
  });

  it("explains what the composition bar shows", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(projectPageFetch());

    renderAt("3");

    expect(
      await screen.findByText(/wider segment means more open work there/i),
    ).toBeInTheDocument();
  });

  it("shows an error state when the request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      jsonResponse({ detail: "nope" }, false),
    );

    renderAt("3");

    expect(await screen.findByText(/Couldn't reach Clarice/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("lists the project's own areas", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      projectPageFetch(
        projectDetailData({
          areas: [
            { id: 1, title: "Design", open_count: 2, overdue_count: 0, color_key: "sky" },
            { id: 2, title: "Dev", open_count: 5, overdue_count: 1, color_key: "sage" },
          ],
        }),
      ),
    );

    renderAt("3");

    expect(await screen.findByText("Design")).toBeInTheDocument();
    expect(screen.getByText("Dev")).toBeInTheDocument();
  });

  it("says so plainly when the project has no areas yet", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(projectPageFetch());

    renderAt("3");

    expect(
      await screen.findByText("No areas in this project yet."),
    ).toBeInTheDocument();
  });

  it("removes an area from the project", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      const side = sideRequests(url);
      if (side) return side;
      if (request.method === "PATCH" && url.includes("/project")) {
        return jsonResponse({ id: 1, title: "Design" });
      }
      return jsonResponse(
        projectDetailData({
          areas: [
            { id: 1, title: "Design", open_count: 0, overdue_count: 0, color_key: "sky" },
          ],
        }),
      );
    });

    renderAt("3");
    await screen.findByText("Design");

    await user.click(screen.getByRole("button", { name: "Remove" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) => {
          const req = request as Request;
          return req.method === "PATCH" && req.url.includes("/api/v1/areas/1/project");
        }),
      ).toBe(true);
    });
  });

  it("offers to add an area not already in this project", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      if (url.includes("/api/v1/nav")) {
        return jsonResponse({
          ...NAV,
          areas: [
            { id: 1, title: "Design", open_count: 0, overdue_count: 0, color_key: "sky" },
            { id: 5, title: "Marketing", open_count: 0, overdue_count: 0, color_key: "coral" },
          ],
        });
      }
      return jsonResponse(
        projectDetailData({
          areas: [
            { id: 1, title: "Design", open_count: 0, overdue_count: 0, color_key: "sky" },
          ],
        }),
      );
    });

    renderAt("3");
    await screen.findByText("Design");

    const picker = await screen.findByLabelText("Add an existing area");
    expect(screen.queryByRole("option", { name: "Design" })).not.toBeInTheDocument();
    expect(within(picker).getByRole("option", { name: "Marketing" })).toBeInTheDocument();
  });

  it("creates a brand new area directly in the project", async () => {
    // Vince's call: no first task required, unlike the Agenda sidebar's
    // own "+ New area" -- the predominant case for a project is areas
    // that don't exist yet.
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      const side = sideRequests(url);
      if (side) return side;
      if (request.method === "POST" && url.includes("/areas")) {
        return jsonResponse({ id: 9, title: "Legal" });
      }
      return jsonResponse(projectDetailData());
    });

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");

    await user.type(screen.getByLabelText("New area name"), "Legal");
    await user.click(screen.getByRole("button", { name: "Create area" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) => {
          const req = request as Request;
          return req.method === "POST" && req.url.includes("/api/v1/projects/3/areas");
        }),
      ).toBe(true);
    });
  });

  it("marks the project complete and reopens it", async () => {
    const user = userEvent.setup();
    let completed = false;
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      const side = sideRequests(url);
      if (side) return side;
      // Completing the project mounts the retrospective (S12), so this mock
      // has to answer that request too -- without it the panel receives a
      // project payload, and the route it lives on goes down with it.
      if (url.includes("/retrospective")) return jsonResponse(RETRO);
      if (request.method === "PATCH") completed = true;
      return jsonResponse(projectDetailData({ is_completed: completed }));
    });

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");

    await user.click(screen.getByRole("button", { name: "Mark complete" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Reopen" })).toBeInTheDocument();
    });
  });

  it("refreshes the sidebar when completion changes, since its Projects group only lists open ones", async () => {
    const user = userEvent.setup();
    let navFetches = 0;
    let completed = false;
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      if (url.includes("/api/v1/nav")) {
        navFetches += 1;
        return jsonResponse(NAV);
      }
      // Counting nav is this test's own business; everything else the page
      // fetches is not. Without this the catch-all below answers
      // `/retrospective` with a project and the route goes down.
      const side = sideRequests(url);
      if (side) return side;
      if (request.method === "PATCH") completed = true;
      return jsonResponse(projectDetailData({ is_completed: completed }));
    });

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");
    const fetchesBeforeClick = navFetches;

    await user.click(screen.getByRole("button", { name: "Mark complete" }));

    await waitFor(() => expect(navFetches).toBeGreaterThan(fetchesBeforeClick));
  });

  it("deletes the project and returns to the agenda after confirming", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      const side = sideRequests(url);
      if (side) return side;
      if (request.method === "DELETE") return jsonResponse({ deleted: 3 });
      return jsonResponse(projectDetailData());
    });

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");

    await user.click(screen.getByRole("button", { name: "Delete project" }));
    await user.click(screen.getByRole("button", { name: "Delete permanently" }));

    await waitFor(() => {
      expect(screen.getByText("Agenda page")).toBeInTheDocument();
    });
    const deleteCall = fetchMock.mock.calls.find(
      ([request]) => (request as Request).method === "DELETE",
    );
    expect(deleteCall?.[0]).toEqual(
      expect.objectContaining({ url: expect.stringContaining("/api/v1/projects/3") }),
    );
  });

  it("renames the project once the title actually changes", async () => {
    // The create form only ever set a title, and this page used to offer
    // no way to change it afterward -- unlike AreaRoute's own rename field,
    // which this mirrors: Save stays disabled until the text differs.
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      const side = sideRequests(url);
      if (side) return side;
      if (request.method === "PATCH") {
        return jsonResponse(projectDetailData({ title: "Website Relaunch v2" }));
      }
      return jsonResponse(projectDetailData());
    });

    renderAt("3");
    const titleField = await screen.findByDisplayValue("Website Relaunch");
    const saveName = screen.getByRole("button", { name: "Save name" });
    expect(saveName).toBeDisabled();

    await user.clear(titleField);
    await user.type(titleField, "Website Relaunch v2");
    expect(saveName).toBeEnabled();
    await user.click(saveName);

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) => {
          const req = request as Request;
          return req.method === "PATCH" && req.url.includes("/api/v1/projects/3");
        }),
      ).toBe(true);
    });
  });

  it("sets the project's due date once it actually changes", async () => {
    // Same gap on the other field: due_date was API-writable all along
    // (ProjectUpdateIn) but nothing on this page ever offered to write it.
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      const side = sideRequests(url);
      if (side) return side;
      if (request.method === "PATCH") {
        return jsonResponse(projectDetailData({ due_date: "2026-11-12" }));
      }
      return jsonResponse(projectDetailData());
    });

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");
    const dueField = screen.getByLabelText("Due date");
    const saveDate = screen.getByRole("button", { name: "Save date" });
    expect(saveDate).toBeDisabled();

    fireEvent.change(dueField, { target: { value: "2026-11-12" } });
    await user.click(saveDate);

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([request]) => {
          const req = request as Request;
          return req.method === "PATCH" && req.url.includes("/api/v1/projects/3");
        }),
      ).toBe(true);
    });
  });

  it("flags a past-due project as overdue", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      projectPageFetch(
        projectDetailData({ due_date: "2026-01-01", is_overdue: true }),
      ),
    );

    renderAt("3");

    expect(await screen.findByText("⚠ Overdue")).toBeInTheDocument();
  });

  it("keeps an unsaved project name and due date when the query refetches", async () => {
    // The queryFn seeded both fields, so every refetch re-ran the setters
    // and discarded whatever was being typed.
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(projectPageFetch());

    const { queryClient } = renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");

    await user.clear(screen.getByLabelText("Project name"));
    await user.type(screen.getByLabelText("Project name"), "Website Relaunch v2");
    await user.type(screen.getByLabelText("Due date"), "2026-09-30");
    // Wrapped in act so the refetch's state update is flushed before the
    // assertion -- without it the update is still pending and the test
    // passes over a value that is already lost.
    await act(async () => {
      await queryClient.refetchQueries({ queryKey: ["project", 3] });
    });

    expect(screen.getByLabelText("Project name")).toHaveValue("Website Relaunch v2");
    expect(screen.getByLabelText("Due date")).toHaveValue("2026-09-30");
  });

  it("keeps an unsaved project name while an area is added underneath it", async () => {
    // This page does not need an alt-tab to lose the edit. Four of its
    // mutations call refresh(), which invalidates this very query -- so
    // creating an area while the title was being retyped reseeded the field
    // from the server and the rename was gone, with the success message for
    // the area sitting right beside it.
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const request = input as Request;
      const url = typeof input === "string" ? input : request.url;
      const side = sideRequests(url);
      if (side) return side;
      if (request.method === "POST" && url.includes("/areas")) {
        return jsonResponse({ id: 9, title: "Legal" });
      }
      return jsonResponse(projectDetailData());
    });

    renderAt("3");
    await screen.findByDisplayValue("Website Relaunch");

    await user.clear(screen.getByLabelText("Project name"));
    await user.type(screen.getByLabelText("Project name"), "Website Relaunch v2");

    await user.type(screen.getByLabelText("New area name"), "Legal");
    await user.click(screen.getByRole("button", { name: "Create area" }));

    await waitFor(() =>
      expect(screen.getByLabelText("New area name")).toHaveValue(""),
    );
    expect(screen.getByLabelText("Project name")).toHaveValue("Website Relaunch v2");
  });
});
