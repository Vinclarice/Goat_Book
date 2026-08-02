import type { AgendaBucketKey, ListColorKey, Task } from "./types";

/** Mirrors lists.agenda.WEEK_HORIZON_DAYS. */
export const WEEK_HORIZON_DAYS = 7;

/**
 * The server assigns each list a semantic color_key (see the List-Color
 * Contract) -- this just maps that key to the CSS token holding its
 * actual value, so light/dark theming and future color changes are
 * handled entirely by tailwind.css, not here.
 */
export function colorForKey(key: ListColorKey): string {
  return `var(--list-color-${key})`;
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

// Python's date.weekday() counts from Monday, JS's getUTCDay() from
// Sunday -- these are the JS numbers for lists.agenda.MONDAY/SATURDAY.
const MONDAY = 1;
const SATURDAY = 6;

function weekdayOf(isoDate: string): number {
  return new Date(`${isoDate}T00:00:00Z`).getUTCDay();
}

/** Mirrors lists.agenda.next_weekday. */
function nextWeekday(isoDate: string, weekday: number): string {
  const ahead = (weekday - weekdayOf(isoDate) + 7) % 7;
  return addDays(isoDate, ahead || 7);
}

export type SnoozeKey = "tomorrow" | "weekend" | "next_week" | "clear";

export interface SnoozePreset {
  key: SnoozeKey;
  label: string;
  dueDate: string | null;
}

/** Mirrors lists.agenda.snooze_presets -- see there for the edge cases. */
export function snoozePresets(today: string): SnoozePreset[] {
  const weekend =
    weekdayOf(today) === SATURDAY
      ? addDays(today, 1)
      : nextWeekday(today, SATURDAY);
  return [
    { key: "tomorrow", label: "Tomorrow", dueDate: addDays(today, 1) },
    { key: "weekend", label: "This weekend", dueDate: weekend },
    {
      key: "next_week",
      label: "Next week",
      dueDate: nextWeekday(today, MONDAY),
    },
    { key: "clear", label: "Clear", dueDate: null },
  ];
}

/**
 * Which buckets each filter scope includes.
 *
 * Client-only, and deliberately so: the API delivers every open task and
 * the filtering happens here, so no server code has ever needed this. It
 * used to claim it mirrored `lists.agenda.SCOPES`, which does not exist and
 * never did -- a comment naming an absent authority reads as a guarantee,
 * which is worse than saying nothing.
 *
 * The rule underneath it *is* mirrored: the bucket a task falls into comes
 * from bucketFor, which does have a Python authority. This only groups
 * those keys. If the server ever filters by scope -- a digest that reports
 * "this week", say -- the definition moves there and this becomes a real
 * mirror with a real test.
 */
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
    if (filters.list !== null && task.list_id !== filters.list) return false;
    if (filters.tag && !task.tags.includes(filters.tag)) return false;
    return true;
  });
}

/**
 * The header counts, derived from the tasks already on the client.
 *
 * Client-only for the same reason as SCOPES, and it carried the same false
 * claim about a `lists.agenda.summary_counts`. The server does compute
 * per-list open/overdue counts in `list_summaries`, which is a different
 * thing -- those are per list and come down in the payload; these are
 * across the whole agenda and are pure derivation over bucketFor.
 *
 * Note `week` is cumulative on purpose: overdue and today are inside "this
 * week", so the number answers "what does this week hold" rather than
 * "what falls strictly in the week bucket".
 */
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
