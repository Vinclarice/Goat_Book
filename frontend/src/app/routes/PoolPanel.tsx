import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";

import { ageSentence, dueLabel } from "../../agenda";
import { apiV1 } from "../../api/client";
import { RequestFailed } from "../../api/failure";
import { whenItIs } from "./Appointments";
import { PickButtons } from "./PoolRoute";

/**
 * The head of the pool, beside the day.
 *
 * `design/superlists-2.0-plan.md`: *the pool is a panel **and** a page.* Vince:
 * *"I like the panel but also I'd perhaps like a second page with the entire
 * list."* Both read `/api/v1/pool`, so neither is a copy of the other — this
 * one passes `head`, and the server decides what the head of a pool is.
 *
 * **This is what lets the Agenda retire.** The Agenda answered *what is open*,
 * and until now the day page could not: it showed what was due and what was
 * chosen, and the rest lived on another screen. `superlists-2.0-plan.md`'s
 * whole shape is one page with the pool beside it.
 *
 * **A column, not a second page.** No search box here — the whole-pool page has
 * one, and a panel that could be filtered would be a place to *work* rather
 * than a place to glance. What it offers is the two picks, which is the one
 * verb a line needs from beside a day.
 */
export function PoolPanel() {
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ["pool", "head"],
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/pool", {
        params: { query: { head: true } },
      });
      if (!data) throw new RequestFailed(response.status);
      return data;
    },
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pool"] });
      queryClient.invalidateQueries({ queryKey: ["day"] });
    },
  });

  // Rendered as nothing until it arrives rather than as a spinner: the panel
  // is beside the day and not the day itself, and a loading state in a column
  // reads as the page being broken.
  if (!data) return null;

  const rows = [...data.fixed, ...data.floating];

  return (
    <section className="space-y-2" aria-labelledby="pool-panel">
      <h2 id="pool-panel" className="text-sm font-bold">
        The pool{" "}
        <span className="font-mono text-xs font-normal tabular-nums text-muted-foreground">
          {data.open_count} open
        </span>
      </h2>
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nothing open.</p>
      ) : (
        <ul className="flex flex-col">
          {data.fixed.map((row) => (
            <li
              key={`${row.kind}-${row.task?.id ?? row.bill?.id ?? row.appointment?.public_id}`}
              className="flex min-h-11 items-center gap-3 border-t border-border text-sm"
            >
              <span className="min-w-0 flex-1 truncate">
                {row.task?.text ?? row.bill?.payee ?? row.appointment?.text}
              </span>
              <span className="whitespace-nowrap text-xs text-muted-foreground">
                {row.kind === "bill" && "bill · "}
                {row.appointment
                  ? whenItIs(row.appointment)
                  : dueLabel(row.due_date, data.today)}
              </span>
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
          {data.floating.map((row) => (
            <li
              key={row.task.id}
              className="flex min-h-11 items-center gap-3 border-t border-border text-sm"
            >
              <span className="min-w-0 flex-1 truncate">{row.task.text}</span>
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
      )}
      {/* The count is the whole pool and this is the head of it, so the link
          says how many are really there — otherwise a panel showing six would
          read as a pool of six. */}
      <Link to="/pool" className="touch-target text-sm text-accent hover:underline">
        The whole pool ({data.open_count}) →
      </Link>
    </section>
  );
}
