import type { AgendaBucketKey, Task } from "./types";

/** Mirrors lists.agenda.WEEK_HORIZON_DAYS. */
export const WEEK_HORIZON_DAYS = 7;

/** Mirrors lists.agenda.LIST_COLORS, indexed the same way. */
export const LIST_COLORS = [
  "#8fc7d6", "#a8dba8", "#f4c98a", "#c9a8dc",
  "#f4a3a3", "#9ab6e0", "#e5a8c4", "#f1e394",
];

export function colorForList(listId: number): string {
  return LIST_COLORS[listId % LIST_COLORS.length];
}

/**
 * Shifts a YYYY-MM-DD date string by whole days.
 *
 * Anchored at UTC midnight rather than local time so a machine in a
 * negative offset doesn't roll the date backwards on parse.
 */
export function addDays(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function daysBetween(from: string, to: string): number {
  const start = Date.parse(`${from}T00:00:00Z`);
  const end = Date.parse(`${to}T00:00:00Z`);
  return Math.round((end - start) / 86_400_000);
}

/** Mirrors lists.agenda.bucket_for. */
export function bucketFor(
  dueDate: string | null,
  today: string,
): AgendaBucketKey {
  if (dueDate === null) return "someday";
  if (dueDate < today) return "overdue";
  if (dueDate === today) return "today";
  if (dueDate <= addDays(today, WEEK_HORIZON_DAYS)) return "week";
  return "later";
}

/** Mirrors lists.agenda.SCOPES. */
export const SCOPES: Record<string, AgendaBucketKey[]> = {
  overdue: ["overdue"],
  today: ["today"],
  week: ["overdue", "today", "week"],
};

export interface AgendaFilters {
  scope: string | null;
  list: number | null;
  tag: string | null;
}

export const NO_FILTERS: AgendaFilters = {
  scope: null,
  list: null,
  tag: null,
};

export function hasFilters(filters: AgendaFilters): boolean {
  return Boolean(filters.scope || filters.list !== null || filters.tag);
}

export function applyFilters(
  tasks: Task[],
  today: string,
  filters: AgendaFilters,
): Task[] {
  return tasks.filter((task) => {
    if (filters.scope && SCOPES[filters.scope]) {
      if (!SCOPES[filters.scope].includes(bucketFor(task.due_date, today))) {
        return false;
      }
    }
    if (filters.list !== null && task.list.id !== filters.list) return false;
    if (filters.tag && !task.tags.includes(filters.tag)) return false;
    return true;
  });
}

/** Mirrors lists.agenda.summary_counts. */
export function summaryCounts(tasks: Task[], today: string) {
  let overdue = 0;
  let dueToday = 0;
  let week = 0;
  for (const task of tasks) {
    const bucket = bucketFor(task.due_date, today);
    if (bucket === "overdue") overdue += 1;
    else if (bucket === "today") dueToday += 1;
    else if (bucket === "week") week += 1;
  }
  return {
    overdue,
    today: dueToday,
    week: overdue + dueToday + week,
    open: tasks.length,
  };
}

export function tagSummaries(tasks: Task[]) {
  const counts = new Map<string, number>();
  for (const task of tasks) {
    for (const tag of task.tags) {
      counts.set(tag, (counts.get(tag) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

/** The short due-date label shown on a task row. */
export function dueLabel(dueDate: string, today: string): string {
  const bucket = bucketFor(dueDate, today);
  if (bucket === "overdue") {
    const days = daysBetween(dueDate, today);
    return days === 1 ? "Yesterday" : `${days} days overdue`;
  }
  if (bucket === "today") return "Today";
  if (daysBetween(today, dueDate) === 1) return "Tomorrow";
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(new Date(`${dueDate}T00:00:00Z`));
}

/** Keeps a list in the same order the server would return it in. */
export function sortAgendaTasks(tasks: Task[]): Task[] {
  return [...tasks].sort((a, b) => {
    if (a.due_date !== b.due_date) {
      if (a.due_date === null) return 1;
      if (b.due_date === null) return -1;
      return a.due_date < b.due_date ? -1 : 1;
    }
    if (a.position !== b.position) return a.position - b.position;
    return a.id - b.id;
  });
}
