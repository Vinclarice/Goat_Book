import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { ageLabel, dueLabel } from "../../agenda";
import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { RouteFailure } from "./RouteFailure";

type CompletedTask = {
  task_id: number;
  text: string;
  completed_on: string;
  list_id: number;
  parent: { id: number; text: string } | null;
};

/** "27 July" — the half of a date a week's title needs. */
function dayAndMonth(isoDate: string): string {
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "long",
    timeZone: "UTC",
  }).format(new Date(`${isoDate}T00:00:00Z`));
}

/** "Wednesday" — how a person places a day inside a week they lived. */
function weekday(isoDate: string): string {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    timeZone: "UTC",
  }).format(new Date(`${isoDate}T00:00:00Z`));
}

/**
 * The window this page is reporting on, said in full.
 *
 * Named rather than left to "this week", because the default is the week in
 * progress and not the one before it — and a figure whose window the reader
 * has to infer is the kind of number crane-plan.md §8 was written to avoid.
 * The year appears only when the week straddles one, where it is the
 * difference between a label and a puzzle.
 */
function weekTitle(start: string, end: string): string {
  const sameYear = start.slice(0, 4) === end.slice(0, 4);
  const suffix = sameYear ? "" : ` ${end.slice(0, 4)}`;
  return `${dayAndMonth(start)}${sameYear ? "" : ` ${start.slice(0, 4)}`} – ${dayAndMonth(end)}${suffix}`;
}

/** Tasks grouped under the day they were finished, in the week's order. */
function byDay(completed: CompletedTask[]) {
  const days: { day: string; tasks: CompletedTask[] }[] = [];
  for (const task of completed) {
    const last = days[days.length - 1];
    if (last && last.day === task.completed_on) last.tasks.push(task);
    else days.push({ day: task.completed_on, tasks: [task] });
  }
  return days;
}

type PlannedTask = {
  task_id: number | null;
  text: string;
  day: string;
  due_date: string | null;
  parent: { id: number; text: string } | null;
  age_in_days: number;
  completed_on: string | null;
};

type Planned = {
  total: number;
  met: number;
  met_tasks: PlannedTask[];
  unfinished: PlannedTask[];
  set_aside: PlannedTask[];
};

/** One commitment, with whatever context the week has about it. */
function PlannedRow({
  task,
  today,
  muted = false,
}: {
  task: PlannedTask;
  today: string;
  muted?: boolean;
}) {
  const age = ageLabel(task.age_in_days);
  return (
    <li
      className={`rounded-lg border border-border px-3 py-2${muted ? " opacity-70" : ""}`}
    >
      <span className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span>
          {task.parent && (
            <span className="mr-2 text-sm text-muted-foreground">
              {task.parent.text} ›
            </span>
          )}
          {task.text}
        </span>
        {task.due_date && (
          <span className="text-sm text-muted-foreground">
            {dueLabel(task.due_date, today)}
          </span>
        )}
        {/* A fact, in the same grey as everything else. The vision
            document's test is that history be useful without making missed
            work feel like punishment, and this page is the one most able
            to fail it. */}
        {age && <span className="text-sm text-muted-foreground">{age}</span>}
      </span>
    </li>
  );
}

/**
 * What was planned, and what came of it.
 *
 * The rate is met over total, and total counts only the pins that were
 * still standing when the week ended. That is the definition
 * daily-operating-system-vision.md insists on — completed planned
 * commitments over planned commitments — and it is the reason unpinning
 * releases a record rather than deleting one.
 */
function PlannedWork({ planned, today }: { planned: Planned; today: string }) {
  if (planned.total === 0 && planned.set_aside.length === 0) {
    // No rate at all rather than "0 of 0": a week nobody planned is not a
    // week that failed a plan, and a fraction with nothing behind it
    // invites a conclusion from nothing.
    return (
      <p className="text-sm text-muted-foreground">
        Nothing was pinned to a day this week.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      {planned.total > 0 && (
        <p className="text-sm text-muted-foreground">
          <span className="text-base font-bold text-foreground">
            {planned.met} of {planned.total}
          </span>{" "}
          {planned.total === 1 ? "commitment" : "commitments"} finished
        </p>
      )}

      {planned.met_tasks.length > 0 && (
        <ul className="space-y-1">
          {planned.met_tasks.map((task) => (
            <PlannedRow
              key={`${task.task_id}-${task.day}`}
              task={task}
              today={today}
            />
          ))}
        </ul>
      )}

      {planned.unfinished.length > 0 && (
        <div className="space-y-1">
          <h3 className="text-sm text-muted-foreground">Still open</h3>
          <ul className="space-y-1">
            {planned.unfinished.map((task) => (
              <PlannedRow
                key={`${task.task_id}-${task.day}`}
                task={task}
                today={today}
              />
            ))}
          </ul>
        </div>
      )}

      {planned.set_aside.length > 0 && (
        <div className="space-y-1">
          <h3 className="text-sm text-muted-foreground">
            Set aside on purpose
          </h3>
          <ul className="space-y-1">
            {planned.set_aside.map((task) => (
              <PlannedRow
                key={`${task.task_id}-${task.day}`}
                task={task}
                today={today}
                muted
              />
            ))}
          </ul>
          {/* Says why they are not in the count, before anybody wonders
              whether the number is hiding them. */}
          <p className="text-sm text-muted-foreground">
            Taken off a day deliberately, so they are not counted against the
            week.
          </p>
        </div>
      )}
    </div>
  );
}

function Finished({ completed }: { completed: CompletedTask[] }) {
  if (completed.length === 0) {
    // Said plainly rather than left blank. An empty area reads as a page
    // that failed to load, and this one is reporting a fact.
    return (
      <p className="text-sm text-muted-foreground">
        Nothing was marked finished in this week.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      {byDay(completed).map(({ day, tasks }) => (
        <div key={day} className="space-y-1">
          <h3 className="text-sm text-muted-foreground">{weekday(day)}</h3>
          <ul className="space-y-1">
            {tasks.map((task) => (
              <li
                key={task.task_id}
                className="rounded-lg border border-border px-3 py-2"
              >
                {/* The breadcrumb, so a subtask row is not a fragment
                    nobody can place — the same reason the agenda carries
                    one. */}
                {task.parent && (
                  <span className="mr-2 text-sm text-muted-foreground">
                    {task.parent.text} ›
                  </span>
                )}
                <span>{task.text}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

/**
 * The weekly review — for now, the week and what got finished in it.
 *
 * Two paths, one component, exactly as the day has: the undated one asks
 * the server which week it is rather than trusting the browser's clock,
 * because a week boundary belongs to the account's time zone. Any date in
 * the dated form addresses the week containing it, and the server snaps it
 * to the Monday the routines domain uses — so a link cannot name a week
 * that domain would disagree about.
 */
export function ReviewRoute() {
  const { week } = useParams();

  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["review", week ?? "current"],
    queryFn: async () => {
      const { data, response } = week
        ? await apiV1.GET("/api/v1/review/{day}", {
            params: { path: { day: week } },
          })
        : await apiV1.GET("/api/v1/review");
      if (!response.ok || !data) throw new RequestFailed(response.status);
      return data;
    },
  });

  if (isPending) return <p className="p-6">Loading…</p>;
  if (error || !data) {
    return <RouteFailure status={statusOf(error)} onRetry={() => refetch()} />;
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-accent">
          {data.is_current_week ? "This week" : "Week in review"}
        </p>
        <h1 className="text-2xl font-bold">
          {weekTitle(data.week_start, data.week_end)}
        </h1>
      </div>

      <nav className="flex items-center gap-4 text-sm" aria-label="Weeks">
        <Link
          to={`/review/${data.previous_week}`}
          className="text-muted-foreground hover:text-foreground"
        >
          ← The week before
        </Link>
        {/* Absent on the week in progress rather than disabled: there is
            nothing to review in a week that has not happened, and a control
            leading somewhere empty reads as a page that is broken. */}
        {!data.is_current_week && (
          <Link
            to={`/review/${data.next_week}`}
            className="text-muted-foreground hover:text-foreground"
          >
            The week after →
          </Link>
        )}
      </nav>

      {/* Above what merely got finished, because it is the deliberate half
          of the week -- the same reason Focus sits above Action Items on
          the day. */}
      <section className="space-y-2">
        <h2 className="text-sm font-bold">What you planned</h2>
        <PlannedWork planned={data.planned} today={data.today} />
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-bold">Finished</h2>
        <Finished completed={data.completed} />
      </section>
    </div>
  );
}
