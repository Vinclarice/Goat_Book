export function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

/** A plain date (YYYY-MM-DD), not an instant -- formatDate would turn
 * 2026-09-30 into an evening in the browser's zone. Parsed into parts
 * instead so a date the server calls the 30th never displays as the 29th.
 */
export function formatDateOnly(value: string): string {
  const [year, month, day] = value.split("-").map(Number);
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(year, month - 1, day));
}

/** An instant (a real ISO timestamp with its own offset, like
 * completed_at/archived_at), shown as just its date -- no time of day, the
 * minute it happened is not the point once it's history. Shared rather
 * than repeated: TaskWorkspace's own "Completed <date>" line and the
 * Archive page's "Archived <date>" line both want exactly this. */
export function formatShortDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(
    new Date(value),
  );
}
