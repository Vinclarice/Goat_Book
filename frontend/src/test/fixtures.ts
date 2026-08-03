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
    notes: "",
    area_id: 1,
    url: "/api/items/1/",
    edit_url: "/areas/items/1/edit",
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
    url: "/api/checklist-steps/1/",
    promote_url: "/api/checklist-steps/1/promote/",
    ...overrides,
  };
}

/** Fixed so bucket boundaries in tests don't move with the wall clock. */
export const TODAY = "2026-07-28";

export function agendaArea(
  overrides: Partial<AgendaWorkspaceData["areas"][number]> = {},
): AgendaWorkspaceData["areas"][number] {
  return {
    id: 1,
    title: "Programming",
    url: "/areas/1/",
    create_item_url: "/api/areas/1/items/",
    open_count: 0,
    overdue_count: 0,
    color_key: "sky",
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
    new_area_url: "/areas/new",
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
    ...overrides,
  };
}
