import type {
  ArchiveWorkspaceData,
  AgendaWorkspaceData,
  ChecklistStep,
  Task,
} from "../types";

export function task(overrides: Partial<Task> = {}): Task {
  return {
    id: 1,
    text: "Write tests",
    status: "active",
    created_at: "2026-07-24T12:00:00-04:00",
    updated_at: "2026-07-24T12:00:00-04:00",
    completed_at: null,
    archived_at: null,
    due_date: null,
    position: 0,
    tags: [],
    recurrence: "none",
  priority: "none",
  lead_days: 0,
    notes: "",
    area_id: 1,
    project_id: null,
    url: "/api/items/1/",
    ...overrides,
  };
}

export function checklistStep(overrides: Partial<ChecklistStep> = {}): ChecklistStep {
  return {
    id: 1,
    text: "Refill medication",
    position: 0,
    is_done: false,
    completed_at: null,
    carries_forward: true,
    task_id: 1,
    ...overrides,
  };
}

/** Fixed so bucket boundaries in tests don't move with the wall clock. */
export const TODAY = "2026-07-28";

export function agendaArea(
  overrides: Partial<AgendaWorkspaceData["areas"][number]> = {},
): AgendaWorkspaceData["areas"][number] {
  // **Derived from the id, since August 30, 2026.** These three were hardcoded
  // to area 1 whatever id was passed, so every area in every test claimed area
  // 1's urls -- and "adds a task to the selected list" asserted the *unselected*
  // area's create url and passed. Nothing was wrong in production, where the
  // server reverses each one with its own id; the fixture simply could not tell
  // the two apart, so neither could the test.
  const id = overrides.id ?? 1;
  return {
    id,
    title: "Programming",
    url: `/areas/${id}/`,
    create_item_url: `/api/areas/${id}/items/`,
    open_count: 0,
    overdue_count: 0,
    color_key: "sky",
    ...overrides,
  };
}

export function agendaProject(
  overrides: Partial<AgendaWorkspaceData["projects"][number]> = {},
): AgendaWorkspaceData["projects"][number] {
  return {
    id: 1,
    title: "Kitchen remodel",
    url: "/areas/1/",
    ...overrides,
  };
}

export function agendaData(
  overrides: Partial<AgendaWorkspaceData> = {},
): AgendaWorkspaceData {
  return {
    today: TODAY,
    username: "vince",
    archive_url: "/archive/",
    archived_count: 0,
    settings_url: "/accounts/settings/",
    daily_digest: true,
    buckets: [
      { key: "overdue", label: "Overdue", collapsed: false },
      { key: "today", label: "Today", collapsed: false },
      { key: "week", label: "This week", collapsed: false },
      { key: "later", label: "Later", collapsed: true },
      { key: "someday", label: "No due date", collapsed: true },
    ],
    items: [],
    completed_today: [],
    areas: [agendaArea()],
    projects: [],
    ...overrides,
  };
}

export function archiveArea(
  overrides: Partial<ArchiveWorkspaceData["areas"][number]> = {},
) {
  return {
    id: 1,
    title: "Programming",
    url: "/areas/1/",
    ...overrides,
  };
}

export function archiveData(
  overrides: Partial<ArchiveWorkspaceData> = {},
): ArchiveWorkspaceData {
  return {
    items: [],
    areas: [archiveArea(), archiveArea({ id: 2, title: "Home", url: "/areas/2/" })],
    projects: [],
    ...overrides,
  };
}

/**
 * A `fetch` response openapi-fetch will accept.
 *
 * **Added August 30, 2026** — coherence-audit-2026-08-30.md F2. Task and
 * checklist writes go through `apiV1` now, and openapi-fetch builds a real
 * `Request` and reads `headers`, `text()` and `clone()` off the response. The
 * per-file `jsonResponse` helpers these replace returned `{ok, status, json}`
 * and nothing else, which was enough for the hand-rolled client and is not
 * enough for this one.
 */
export function apiResponse(body: unknown, ok = true, status = ok ? 200 : 400) {
  const text = JSON.stringify(body);
  return Promise.resolve({
    ok,
    status,
    headers: new Headers({
      "content-type": "application/json",
      "content-length": String(text.length),
    }),
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(text),
    clone() {
      return this;
    },
  } as unknown as Response);
}

/**
 * One mock body that answers both task-write shapes.
 *
 * `POST /areas/{id}/tasks` returns the task itself; `PATCH /tasks/{id}`
 * returns `TaskUpdateOut` — `{task, spawned, spawned_checklist_steps}`. Most
 * tests stub `fetch` once for the whole render and touch both, so this carries
 * the task's own fields *and* the named result. A server never sends both at
 * once; a double that has to satisfy two callers is allowed to, and saying so
 * here is cheaper than splitting thirty stubs by method.
 */
export function taskWrite(
  written: Task,
  extra: Record<string, unknown> = {},
) {
  return apiResponse({
    ...written,
    task: written,
    spawned: null,
    spawned_checklist_steps: [],
    ...extra,
  });
}

/** The path openapi-fetch actually requested, for asserting on a call.
 *
 * It passes a single `Request` to `fetch`, where the hand-rolled client passed
 * `(url, init)` — so `toHaveBeenCalledWith(url, ...)` no longer describes
 * anything real.
 */
export function requestedPaths(mock: { mock: { calls: unknown[][] } }): string[] {
  return mock.mock.calls.map((call) => {
    const first = call[0];
    return first instanceof Request ? new URL(first.url).pathname : String(first);
  });
}

/** Every request openapi-fetch actually sent, as path/method/body.
 *
 * The hand-rolled client called `fetch(url, init)`, so a test could assert
 * `toHaveBeenCalledWith(url, objectContaining({method, body}))`. openapi-fetch
 * calls `fetch(request)` with one `Request`, whose body is only readable
 * asynchronously — hence the await, and hence `waitFor(async () => ...)` at
 * the call sites.
 */
export async function sentRequests(mock: {
  mock: { calls: unknown[][] };
}): Promise<{ path: string; method: string; body: string }[]> {
  return Promise.all(
    mock.mock.calls.map(async (call) => {
      const request = call[0] as Request;
      return {
        path: new URL(request.url).pathname,
        method: request.method,
        body: request.body ? await request.clone().text() : "",
      };
    }),
  );
}

/** Turns a `fetch` mock into a handler over path/method/body.
 *
 * **Why the test files needed this on August 30, 2026.** They dispatched on
 * `typeof input !== "string"` — a Request meant the typed client, a string
 * meant the hand-rolled one. coherence-audit-2026-08-30.md F2 put task and
 * checklist writes on the typed client too, so every call is a Request now and
 * that test would have matched everything.
 */
export function routeRequests(
  handler: (request: {
    path: string;
    method: string;
    body: Record<string, unknown>;
  }) => Promise<Response> | Response,
) {
  return async (input: unknown): Promise<Response> => {
    const request = input as Request;
    return handler({
      path: new URL(request.url).pathname,
      method: request.method,
      body: request.body
        ? (JSON.parse(await request.clone().text()) as Record<string, unknown>)
        : {},
    });
  };
}
