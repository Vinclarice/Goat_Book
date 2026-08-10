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
