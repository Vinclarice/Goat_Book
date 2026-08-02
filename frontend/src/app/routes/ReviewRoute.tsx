import { FormEvent, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { Button } from "@/components/ui/button";

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

type ReviewRecord = {
  reflections: string;
  plan: string;
  completed_at: string | null;
  recorded_total: number | null;
  recorded_met: number | null;
};

/** "2 August" — a timestamp said the way a person would say it. */
function shortDate(isoInstant: string): string {
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "long",
  }).format(new Date(isoInstant));
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
function PlannedWork({
  planned,
  today,
  review,
}: {
  planned: Planned;
  today: string;
  review: ReviewRecord;
}) {
  // A completed review shows the figure it recorded, not a fresh count.
  // Permanently deleting an archived task afterwards moves the live number
  // — DailyFocus.task is SET_NULL and there is nothing left to ask — and a
  // conclusion drawn on a Sunday should not be edited by a tidy-up on a
  // Tuesday.
  const recorded =
    review.completed_at !== null &&
    review.recorded_total !== null &&
    review.recorded_met !== null;
  const total = recorded ? review.recorded_total! : planned.total;
  const met = recorded ? review.recorded_met! : planned.met;

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
      {total > 0 && (
        <p className="text-sm text-muted-foreground">
          <span className="text-base font-bold text-foreground">
            {met} of {total}
          </span>{" "}
          {total === 1 ? "commitment" : "commitments"} finished
          {recorded && (
            <>
              {" — "}
              <span>as you recorded it on {shortDate(review.completed_at!)}</span>
            </>
          )}
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

type WrittenDay = {
  date: string;
  intentions: string;
  gratitude: string;
  happenings: string;
};

type IdeaAdded = {
  idea_id: number;
  text: string;
  status: string;
  added_on: string;
};

type WaitingCapture = {
  capture_id: number;
  text: string;
  age_in_days: number;
};

/** The same three labels the day itself uses, so nothing is renamed on the
 *  way into a review. */
const WRITTEN_SECTIONS = [
  { field: "intentions", label: "Intentions" },
  { field: "gratitude", label: "Grateful for" },
  { field: "happenings", label: "Happenings" },
] as const;

/**
 * What the week was written in, day by day.
 *
 * Read-only, with a link back to the day that owns each entry: a review
 * reads writing, and editing it belongs on the page it was written on
 * rather than in a second form that could disagree with the first.
 *
 * Only the sections that have something in them are rendered. Three empty
 * headings under every day would bury the one line that says anything.
 */
function Written({ written }: { written: WrittenDay[] }) {
  if (written.length === 0) {
    // Said out loud, unlike the other sections below, which simply do not
    // appear. Writing is the habit under review, so a week with none of it
    // is a fact about the week rather than an absent feature.
    return (
      <p className="text-sm text-muted-foreground">
        Nothing written on any day this week.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      {written.map((day) => (
        <div key={day.date} className="space-y-1">
          <h3 className="text-sm text-muted-foreground">
            <a href={`/app/day/${day.date}`} className="hover:text-foreground">
              {weekday(day.date)}
            </a>
          </h3>
          {WRITTEN_SECTIONS.filter((section) => day[section.field]).map(
            (section) => (
              <div key={section.field} className="rounded-lg border border-border px-3 py-2">
                <p className="text-sm font-bold">{section.label}</p>
                {/* Plain text, preserved as typed -- the same decision the
                    day's own fields make, and no Markdown renderer between
                    somebody's words and the page. */}
                <p className="whitespace-pre-wrap">{day[section.field]}</p>
              </div>
            ),
          )}
        </div>
      ))}
    </div>
  );
}

function Ideas({ ideas }: { ideas: IdeaAdded[] }) {
  return (
    <ul className="space-y-1">
      {ideas.map((idea) => (
        <li
          key={idea.idea_id}
          className="flex items-baseline justify-between gap-3 rounded-lg border border-border px-3 py-2"
        >
          <span className="min-w-0">{idea.text}</span>
          {/* Only when it is not the ordinary case: a chip reading
              "exploring" beside every row would be noise. */}
          {idea.status !== "exploring" && (
            <span className="shrink-0 text-sm text-muted-foreground">
              {idea.status}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

function Waiting({ captures }: { captures: WaitingCapture[] }) {
  return (
    <ul className="space-y-1">
      {captures.map((capture) => {
        const age = ageLabel(capture.age_in_days);
        return (
          <li
            key={capture.capture_id}
            className="flex items-baseline justify-between gap-3 rounded-lg border border-border px-3 py-2"
          >
            <span className="min-w-0">{capture.text}</span>
            {age && (
              <span className="shrink-0 text-sm text-muted-foreground">
                {age}
              </span>
            )}
          </li>
        );
      })}
    </ul>
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
  const queryClient = useQueryClient();
  const queryKey = ["review", week ?? "current"];
  const [draft, setDraft] = useState({ reflections: "", plan: "" });
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const { data, error, isPending, refetch } = useQuery({
    queryKey,
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

  // Seeded once per week rather than on every settle of the query, for the
  // reason the Daily Page learned: this query refetches when the tab
  // regains focus, and writing the draft from the fetch would mean an
  // alt-tab silently restored the stored text over whatever was being
  // typed — then "Saved." would confirm the restored version.
  const seededFor = useRef<string | null>(null);
  useEffect(() => {
    if (!data || seededFor.current === data.week_start) return;
    seededFor.current = data.week_start;
    setDraft({
      reflections: data.review.reflections,
      plan: data.review.plan,
    });
    setSaved(false);
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const day = data?.week_start;
      if (!day) throw new Error("Couldn't save this review.");
      const { data: updated, error } = await apiV1.PATCH(
        "/api/v1/review/{day}",
        { params: { path: { day } }, body: draft },
      );
      if (error) throw new Error("Couldn't save this review.");
      return updated;
    },
    onSuccess: (updated) => {
      setSaveError(null);
      setSaved(true);
      // Written straight into the cache rather than invalidated: a refetch
      // would settle the query again, and the draft is seeded only once.
      queryClient.setQueryData(queryKey, updated);
    },
    onError: (caught: Error) => {
      setSaved(false);
      setSaveError(caught.message);
    },
  });

  // Completing and reopening are separate statements, so separate routes —
  // and neither is a field on the save above, which would make one control
  // mean two things.
  const decideMutation = useMutation({
    mutationFn: async (decision: "complete" | "reopen") => {
      const day = data?.week_start;
      if (!day) throw new Error("Couldn't change this review.");
      const { data: updated, error } = await apiV1.POST(
        decision === "complete"
          ? "/api/v1/review/{day}/complete"
          : "/api/v1/review/{day}/reopen",
        { params: { path: { day } } },
      );
      if (error) throw new Error("Couldn't change this review.");
      return updated;
    },
    onSuccess: (updated) => queryClient.setQueryData(queryKey, updated),
  });

  function edit(field: "reflections" | "plan", value: string) {
    setSaved(false);
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaved(false);
    saveMutation.mutate();
  }

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
        <PlannedWork
          planned={data.planned}
          today={data.today}
          review={data.review}
        />
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-bold">Finished</h2>
        <Finished completed={data.completed} />
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-bold">In your own words</h2>
        <Written written={data.written} />
      </section>

      {/* Absent rather than empty, unlike the writing above: an idea nobody
          had is not a fact about the week worth a heading. */}
      {data.ideas.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-bold">Ideas you added</h2>
          <Ideas ideas={data.ideas} />
        </section>
      )}

      {data.unresolved_captures.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-bold">Still in your inbox</h2>
          <Waiting captures={data.unresolved_captures} />
          {/* Says why old ones are here, and where they get dealt with.
              This list is not week-scoped and would otherwise look like a
              mistake on a review of one week. */}
          <p className="text-sm text-muted-foreground">
            Everything still waiting, whenever it arrived.{" "}
            <a href="/capture/" className="underline hover:text-foreground">
              Sort them out in the Inbox
            </a>
            .
          </p>
        </section>
      )}

      {/* Last, because it is the part written after reading everything
          above it. Two fields and nothing that touches a task: the vision
          document asks for "a short planning area", and anything that
          scheduled work from here would be the automatic rescheduling it
          forbids. */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="review-reflections" className="text-sm font-bold">
            Reflections
          </label>
          <p className="text-sm text-muted-foreground">
            What this week was actually like.
          </p>
          <textarea
            id="review-reflections"
            value={draft.reflections}
            onChange={(event) => edit("reflections", event.target.value)}
            rows={4}
            className="w-full rounded-lg border border-border bg-input px-3 py-2"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="review-plan" className="text-sm font-bold">
            Next week
          </label>
          <p className="text-sm text-muted-foreground">
            What the coming week is for. Nothing here schedules anything —
            pinning work to a day is still yours to do.
          </p>
          <textarea
            id="review-plan"
            value={draft.plan}
            onChange={(event) => edit("plan", event.target.value)}
            rows={4}
            className="w-full rounded-lg border border-border bg-input px-3 py-2"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={saveMutation.isPending}>
            Save the review
          </Button>
          {data.review.completed_at ? (
            <Button
              type="button"
              variant="ghost"
              disabled={decideMutation.isPending}
              onClick={() => decideMutation.mutate("reopen")}
            >
              Reopen this review
            </Button>
          ) : (
            <Button
              type="button"
              variant="secondary"
              disabled={decideMutation.isPending}
              onClick={() => decideMutation.mutate("complete")}
            >
              Mark this week reviewed
            </Button>
          )}
          {saved && <span className="text-sm text-muted-foreground">Saved.</span>}
          {saveError && (
            <span className="text-sm text-destructive">{saveError}</span>
          )}
          {decideMutation.isError && (
            <span className="text-sm text-destructive">
              {decideMutation.error.message}
            </span>
          )}
        </div>
        {!data.review.completed_at && (
          // Says what the button does before it is pressed, because it
          // records a number that then stops moving.
          <p className="text-sm text-muted-foreground">
            Marking it reviewed keeps the count above as it stands now, so a
            later tidy-up cannot change what you concluded.
          </p>
        )}
      </form>
    </div>
  );
}
