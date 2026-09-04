import { useState } from "react";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Link } from "react-router";

import { Button } from "@/components/ui/button";

import { ageSentence, dueLabel } from "../../agenda";
import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { RouteFailure } from "./RouteFailure";

/**
 * The whole pool — every open line the owner has, in one list.
 *
 * `design/superlists-2.0-plan.md` increment 1, and its rule 1. This is the
 * page half of *"I like the panel but also I'd perhaps like a second page with
 * the entire list"*; the panel beside the day arrives with increment 2 and
 * reads the same endpoint, so neither is a copy of the other.
 *
 * **No Area anywhere on it.** That is the point rather than an omission: the
 * pool is what the Agenda becomes once there is nothing to file into, and a
 * line that needs a *why* will mention a project the way the knowledge core
 * mentions a person.
 *
 * **One write, and it is the pick** -- increment 2. A line can be chosen for
 * today or for tomorrow, which is the plan's rule 2: the list is written *for*
 * a day and never *on* it, so making tomorrow's set this evening is the
 * ordinary case rather than the clever one. Choosing *today* after the day's
 * work has begun lands the line below the line, and the server decides that by
 * comparing two timestamps -- nothing here has to know where the line is. The
 * stale prompt is increment 6.
 */
export function PoolRoute() {
  const [query, setQuery] = useState("");
  const queryClient = useQueryClient();
  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["pool", query],
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/pool", {
        params: { query: { q: query } },
      });
      if (!data) throw new RequestFailed(response.status);
      return data;
    },
    // Typing re-asks the server, and without this every keystroke empties the
    // list to a loading state and back — which reads as the page flickering
    // rather than as a search narrowing.
    placeholderData: keepPreviousData,
  });

  const pick = useMutation({
    mutationFn: async ({ taskId, day }: { taskId: number; day: string }) => {
      const { data, response } = await apiV1.POST("/api/v1/day/{day}/focus", {
        params: { path: { day } },
        body: { task_id: taskId },
      });
      if (!data) throw new RequestFailed(response.status);
      return data;
    },
    // Both surfaces, because one act changed both: the pool row now says
    // "picked", and the day it was picked for has a new line on it. Leaving
    // the day stale would mean a pick that only appears after a reload.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pool"] });
      queryClient.invalidateQueries({ queryKey: ["day"] });
    },
  });

  if (isPending) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (error) {
    return <RouteFailure status={statusOf(error)} onRetry={() => refetch()} />;
  }

  const empty = data.fixed.length === 0 && data.floating.length === 0;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="font-sans text-xl font-bold">The pool</h1>
        {/* A count and not a verdict — rule 12. How much is open is a fact
            about a list, and nothing on this page draws a conclusion from it. */}
        <span className="font-mono text-sm tabular-nums text-muted-foreground">
          {data.open_count} open
        </span>
      </div>

      <label className="flex h-11 w-full max-w-xs items-center gap-2 rounded-full border border-border px-3.5 text-sm text-muted-foreground focus-within:border-primary">
        <span className="sr-only">Find a line</span>
        <span aria-hidden="true">⌕</span>
        <input
          className="w-full border-0 bg-transparent text-foreground outline-none placeholder:text-muted-foreground"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Find a line"
        />
      </label>

      {empty && (
        <div className="rounded-lg border border-dashed border-border px-5 py-6 text-sm text-muted-foreground">
          <p>
            {query
              ? `Nothing open matches “${query}”.`
              : "Nothing open. An empty pool is a fact about today, not a failure."}
          </p>
        </div>
      )}

      {data.fixed.length > 0 && (
        <section aria-labelledby="pool-fixed">
          <h2
            id="pool-fixed"
            className="mb-1 font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground"
          >
            Fixed
          </h2>
          <ul className="flex flex-col">
            {data.fixed.map((row) => (
              <li
                key={`${row.kind}-${row.task?.id ?? row.bill?.id}`}
                className="flex min-h-11 items-center gap-3 border-t border-border text-sm"
              >
                {row.task ? (
                  <Link
                    to={`/tasks/${row.task.id}`}
                    className="min-w-0 flex-1 truncate hover:text-accent"
                  >
                    {row.task.text}
                  </Link>
                ) : (
                  /* A bill leaves for Money rather than opening a task page.
                     It stopped being an `Item` on September 1, 2026, and it is
                     in this list because paying is a real thing to do on a
                     day — bill-as-a-model-plan.md decision 4 — not because it
                     is a line you can pick. */
                  <Link
                    to={`/money/bills/${row.bill?.id}`}
                    className="min-w-0 flex-1 truncate hover:text-accent"
                  >
                    {row.bill?.payee}
                  </Link>
                )}
                <span className="whitespace-nowrap text-xs text-muted-foreground">
                  {row.kind === "bill" && "bill · "}
                  {dueLabel(row.due_date, data.today)}
                </span>
                {/* Only a task. A bill has no pick, because `DailyFocus` has
                    nothing to point at once a bill stopped being an `Item`. */}
                {row.task && (
                  <PickButtons
                    taskId={row.task.id}
                    text={row.task.text}
                    today={data.today}
                    pickedFor={row.picked_for}
                    onPick={(taskId, day) => pick.mutate({ taskId, day })}
                    busy={pick.isPending}
                  />
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.floating.length > 0 && (
        <section aria-labelledby="pool-floating">
          <h2
            id="pool-floating"
            className="mb-1 font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground"
          >
            {/* Named in the heading because the order is the information. */}
            Floating · oldest first
          </h2>
          <ul className="flex flex-col">
            {data.floating.map((row) => (
              <li
                key={row.task.id}
                className="flex min-h-11 items-center gap-3 border-t border-border text-sm"
              >
                <Link
                  to={`/tasks/${row.task.id}`}
                  className="min-w-0 flex-1 truncate hover:text-accent"
                >
                  {row.task.text}
                </Link>
                {/* Muted, like everything else on the row. A floating line has
                    no due date, so nothing was promised and there is nothing
                    here to be late for — rule 1. */}
                <span className="whitespace-nowrap text-xs text-muted-foreground">
                  {ageSentence(row.age_in_days)}
                </span>
                <PickButtons
                  taskId={row.task.id}
                  text={row.task.text}
                  today={data.today}
                  pickedFor={row.picked_for}
                  onPick={(taskId, day) => pick.mutate({ taskId, day })}
                  busy={pick.isPending}
                />
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

/** Tomorrow's date, from the server's today rather than the browser's clock.
 *
 * The day boundary belongs to the account's time zone, so a browser in another
 * one would offer the wrong date — the same reason the pool's ages and due
 * labels are all measured against `data.today`.
 */
function dayAfter(today: string) {
  const date = new Date(`${today}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString().slice(0, 10);
}

/**
 * Choose this line for today or for tomorrow.
 *
 * **Two days and no date picker.** Rule 11 makes a past day read-only and rule
 * 2 says the list is written for a day, so the useful range is exactly *the
 * day I am in* and *the one I am planning*. A picker would offer a hundred
 * days nobody wants and a wrong one that the server would then refuse.
 *
 * **A picked line says so instead of offering the button again.** Repinning is
 * idempotent on the server, so without this the second click would look
 * identical to the first and report nothing.
 */
function PickButtons({
  taskId,
  text,
  today,
  pickedFor,
  onPick,
  busy,
}: {
  taskId: number;
  text: string;
  today: string;
  pickedFor: string[];
  onPick: (taskId: number, day: string) => void;
  busy: boolean;
}) {
  const tomorrow = dayAfter(today);
  const days = [
    { day: today, label: "Today", picked: "Picked for today" },
    { day: tomorrow, label: "Tomorrow", picked: "Picked for tomorrow" },
  ];
  return (
    <span className="flex shrink-0 items-center gap-1">
      {days.map((each) =>
        pickedFor.includes(each.day) ? (
          <span key={each.day} className="text-xs text-accent">
            {each.picked}
          </span>
        ) : (
          <Button
            key={each.day}
            type="button"
            variant="ghost"
            disabled={busy}
            /* The visible word is "Today"; the accessible name says which
               line it belongs to, because a list of twenty identical "Today"
               buttons tells a screen reader nothing. */
            aria-label={`Pick ${text} for ${each.label.toLowerCase()}`}
            onClick={() => onPick(taskId, each.day)}
          >
            {each.label}
          </Button>
        ),
      )}
    </span>
  );
}

