import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { RouteFailure } from "./RouteFailure";

/**
 * A month you can look at, and land on a day from — S13's second require.
 *
 * `/app/day/:date` has had no UI entry point at all: reaching a day twelve
 * weeks back meant clicking "the week before" twelve times, which
 * `commercial-blueprint.md` Part 2 names by that description. Search results
 * for a day already link to their own date; what has never existed is a way
 * to reach a date you have not searched for.
 *
 * **A view over what is already there.** Open tasks by due date and days that
 * were written in. The calendar that carries *events* is
 * `clarice-v3-plan.md`'s later work and needs a model this does not.
 */
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function monthLabel(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
}

/** Monday-first, matching the week the review and the draft already use. */
function blanksBefore(iso: string) {
  return (new Date(`${iso}T00:00:00`).getDay() + 6) % 7;
}

export function CalendarRoute() {
  const { month } = useParams();
  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["calendar", month ?? "today"],
    queryFn: async () => {
      const day = month ?? new Date().toISOString().slice(0, 10);
      const { data, response } = await apiV1.GET("/api/v1/calendar/{day}", {
        params: { path: { day } },
      });
      if (!data) throw new RequestFailed(response.status);
      return data;
    },
  });

  if (isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (error) {
    return <RouteFailure status={statusOf(error)} onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-4">
      <nav className="flex items-baseline justify-between gap-3">
        <Link
          to={`/calendar/${data.previous_month}`}
          className="touch-target text-sm text-muted-foreground hover:text-foreground"
        >
          ← {monthLabel(data.previous_month)}
        </Link>
        <h1 className="font-sans text-xl font-bold">
          {monthLabel(data.month_start)}
        </h1>
        <Link
          to={`/calendar/${data.next_month}`}
          className="touch-target text-sm text-muted-foreground hover:text-foreground"
        >
          {monthLabel(data.next_month)} →
        </Link>
      </nav>

      {/* The only way into the bills month. An unreachable route is the
          un-switched-on seam under a nicer name, and this is the other
          month-shaped surface. */}
      <Link
        to={`/bills/${data.month_start}`}
        className="touch-target inline-block text-sm text-muted-foreground hover:text-foreground"
      >
        Bills this month
      </Link>

      <div className="grid grid-cols-7 gap-1">
        {WEEKDAYS.map((name) => (
          <div key={name} className="text-center text-xs text-muted-foreground">
            {name}
          </div>
        ))}
        {Array.from({ length: blanksBefore(data.month_start) }).map((_, index) => (
          <div key={`blank-${index}`} aria-hidden="true" />
        ))}
        {data.days.map((day) => (
          <Link
            key={day.date}
            to={`/day/${day.date}`}
            aria-label={`${day.date}${day.due > 0 ? `, ${day.due} due` : ""}${
              day.appointments > 0 ? `, ${day.appointments} in the diary` : ""
            }${day.written ? ", written" : ""}`}
            className={`flex min-h-16 flex-col rounded-lg border px-2 py-1 hover:border-accent ${
              day.date === data.today ? "border-accent" : "border-border"
            }`}
          >
            <span className="text-sm">
              {Number(day.date.slice(8, 10))}
            </span>
            {/* Counts and a mark, not the rows. A month is for choosing a day
                to open; showing every task on every date would be the Day
                page thirty-one times over. */}
            {day.due > 0 && (
              <span className="text-xs text-muted-foreground">
                {day.due} due
              </span>
            )}
            {/* Counted apart from `due`, because a day with a deadline and a
                day with a two o'clock are different days -- one number could
                not say which. */}
            {day.appointments > 0 && (
              <span className="text-xs text-muted-foreground">
                {day.appointments} on
              </span>
            )}
            {day.written && (
              <span className="text-xs text-accent" aria-hidden="true">
                 written
              </span>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
