import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { RouteFailure } from "./RouteFailure";

/**
 * What is due this month, and what it comes to.
 *
 * A bill is a task with a sidecar — `architecture-trajectory.md` §4 said no
 * to a primitive, and the vision document's own canonical recurring task is
 * "pay rent every month" — so this page is a read over rows that already
 * exist rather than a second kind of thing.
 */
function monthLabel(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
}

function dayLabel(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
  });
}

export function BillsRoute() {
  const { month } = useParams();
  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["bills", month ?? "today"],
    queryFn: async () => {
      const day = month ?? new Date().toISOString().slice(0, 10);
      const { data, response } = await apiV1.GET("/api/v1/bills/{day}", {
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

  const due = Object.entries(data.due_totals);
  const paid = Object.entries(data.paid_totals);

  return (
    <div className="max-w-2xl mx-auto space-y-4 px-4 py-8">
      <nav className="flex items-baseline justify-between gap-3">
        <Link
          to={`/bills/${data.previous_month}`}
          className="touch-target text-sm text-muted-foreground hover:text-foreground"
        >
          ← {monthLabel(data.previous_month)}
        </Link>
        <h1 className="font-sans text-xl font-bold">
          {monthLabel(data.month_start)}
        </h1>
        <Link
          to={`/bills/${data.next_month}`}
          className="touch-target text-sm text-muted-foreground hover:text-foreground"
        >
          {monthLabel(data.next_month)} →
        </Link>
      </nav>

      {data.bills.length === 0 ? (
        // "Nothing is due" rather than "0.00 is due" — different facts, and
        // only one of them deserves a total.
        <p className="text-sm text-muted-foreground">
          No bills due this month.
        </p>
      ) : (
        <>
          <ul className="space-y-1">
            {data.bills.map((bill) => (
              <li
                key={bill.task_id}
                className="flex flex-wrap items-baseline justify-between gap-3 rounded-lg border border-border px-3 py-2"
              >
                <span className="min-w-0">
                  <Link
                    to={`/tasks/${bill.task_id}`}
                    className={
                      bill.paid ? "text-muted-foreground hover:underline" : "hover:underline"
                    }
                  >
                    {bill.text}
                  </Link>
                  {/* A word, not a strikethrough: paid is a good outcome and
                      the month's record of it should not read as cancelled. */}
                  {bill.paid && (
                    <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                      paid
                    </span>
                  )}
                  {bill.payee && (
                    <span className="ml-2 text-sm text-muted-foreground">
                      {bill.payee}
                    </span>
                  )}
                </span>
                <span className="flex shrink-0 items-baseline gap-3">
                  <span className="text-sm text-muted-foreground">
                    {dayLabel(bill.due_date)}
                  </span>
                  <span className="text-sm">
                    {bill.amount === null ? (
                      // Not "0.00", which would read as free.
                      <span className="text-muted-foreground">no amount</span>
                    ) : (
                      `${bill.amount} ${bill.currency}`
                    )}
                  </span>
                </span>
              </li>
            ))}
          </ul>

          {/* One line per currency, never one number: adding 500 USD to 40 GBP
              produces 540 of nothing.

              And two figures rather than one. A single "total" held what was
              outstanding, so a month that cost 1264.99 reported 64.99 -- see
              bills-page-plan.md. What you owe and what the month cost are
              different questions and the page now answers both out loud. */}
          <div className="space-y-1 border-t border-border pt-2">
            {due.map(([code, total]) => (
              <p key={`due-${code}`} className="text-sm">
                <span className="font-bold">
                  {total} {code}
                </span>{" "}
                still to pay
              </p>
            ))}
            {paid.map(([code, total]) => (
              <p key={`paid-${code}`} className="text-sm text-muted-foreground">
                <span className="font-bold">
                  {total} {code}
                </span>{" "}
                already paid
              </p>
            ))}
            {due.length === 0 && paid.length > 0 && (
              <p className="text-sm">Everything this month is paid.</p>
            )}
            {data.unpriced > 0 && (
              <p className="text-sm text-muted-foreground">
                {data.unpriced === 1
                  ? "One bill has no amount, so it is not counted above."
                  : `${data.unpriced} bills have no amount, so they are not counted above.`}
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
