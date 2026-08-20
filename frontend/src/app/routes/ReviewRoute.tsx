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
  // Null for a task standing on its own — see CompletedTaskOut in
  // review/api_v1.py. Nothing on this page reads it yet; it is here because
  // this type mirrors the contract by hand.
  area_id: number | null;
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
  age_in_days: number;
  completed_on: string | null;
};

type Planned = {
  total: number;
  met: number;
  met_tasks: PlannedTask[];
  unfinished: PlannedTask[];
  set_aside: PlannedTask[];
  /** What his weeks actually hold -- median finished across up to eight
   *  prior weeks with a plan in them, strictly before this one. Null below
   *  the sample floor, never zero: "no evidence yet" and "you committed to
   *  more than you can hold" call for opposite responses. */
  typical: number | null;
  over_committed: boolean;
};

/** One commitment, with whatever context the week has about it. */
function PlannedRow({
  task,
  today,
  muted = false,
  onPinToToday,
  pinned = false,
  busy = false,
}: {
  task: PlannedTask;
  today: string;
  muted?: boolean;
  onPinToToday?: (taskId: number) => void;
  pinned?: boolean;
  busy?: boolean;
}) {
  const age = ageLabel(task.age_in_days);
  // Offered only where it means something: a task that still exists, and a
  // day that is not already today. A control that would be a no-op is a
  // control that teaches people the page does nothing.
  const canPin =
    onPinToToday !== undefined && task.task_id !== null && task.day !== today;
  return (
    <li
      className={`rounded-lg border border-border px-3 py-2${muted ? " opacity-70" : ""}`}
    >
      <span className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span>{task.text}</span>
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
        {/* One item, one decision, and nothing that acts on the rest.
            daily-operating-system-vision.md: never automatically
            reschedule everything left incomplete. */}
        {canPin &&
          (pinned ? (
            <span className="text-sm text-muted-foreground">
              On today&rsquo;s page.
            </span>
          ) : (
            <Button
              type="button"
              variant="ghost"
              disabled={busy}
              aria-label={`Put ${task.text} on today`}
              onClick={() => onPinToToday!(task.task_id!)}
            >
              Put on today
            </Button>
          ))}
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
  onPinToToday,
  pinnedIds,
  pinning,
}: {
  planned: Planned;
  today: string;
  review: ReviewRecord;
  onPinToToday: (taskId: number) => void;
  pinnedIds: Set<number>;
  pinning: boolean;
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

      {/* S3's last clause: "4 of 9" is honest as a rate and cannot on its own
          tell *over-committed* from *under-delivered*. This is the same
          comparison the draft below already makes for the week ahead, pointed
          at the week that just happened.

          Stated, never graded -- a fact about the weeks rather than a verdict
          about him, which is the draft's own refusal and the vision
          document's rule that history be useful without making missed work
          punishing. Absent entirely below the evidence floor: null is not
          zero, and a zero would read as a verdict nobody evidenced. */}
      {planned.typical !== null && (
        <p className="text-sm text-muted-foreground">
          You have finished {planned.typical} in a typical week.
          {planned.over_committed && " That is more than the week usually holds."}
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
                onPinToToday={onPinToToday}
                pinned={task.task_id !== null && pinnedIds.has(task.task_id)}
                busy={pinning}
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

type Thought = {
  public_id: string;
  text: string;
  captured_on: string;
};

type NameToConfirm = {
  label: string;
  mentions: number;
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

function Thoughts({ thoughts }: { thoughts: Thought[] }) {
  return (
    <ul className="space-y-1">
      {thoughts.map((thought) => (
        <li
          key={thought.public_id}
          className="flex items-baseline justify-between gap-3 rounded-lg border border-border px-3 py-2"
        >
          <span className="min-w-0">{thought.text}</span>
        </li>
      ))}
    </ul>
  );
}

/** Names that have recurred enough to be worth a question.
 *
 * Replaces the Inbox backlog, and is deliberately not the same thing. That was
 * everything untriaged, however old; this is the one queue the design permits,
 * finite by construction — three mentions spanning a day. The count is shown
 * because it is the reason the question is being asked at all, and a proposal
 * that will not show its evidence is asking for trust.
 */
function NamesToConfirm({ names }: { names: NameToConfirm[] }) {
  return (
    <ul className="space-y-1">
      {names.map((name) => (
        <li
          key={name.label}
          className="flex items-baseline justify-between gap-3 rounded-lg border border-border px-3 py-2"
        >
          <span className="min-w-0">{name.label}</span>
          <span className="shrink-0 text-sm text-muted-foreground">
            {name.mentions} mentions
          </span>
        </li>
      ))}
    </ul>
  );
}

type HabitPeriod = {
  period_start: string;
  outcome: string;
  progress: number;
  target: number;
};

type Habit = {
  routine_id: number;
  title: string;
  cadence: string;
  unit: string;
  met: number;
  expected: number;
  skipped: number;
  enough: number;
  paused_since: string | null;
  paused_days: number;
  periods: HabitPeriod[];
};

/**
 * What one period says about itself, in words rather than a verdict.
 *
 * A skip says what was decided; anything else says the count. There is no
 * "missed" here and there is not meant to be — crane-plan.md §3 is that
 * Crane 3 describes an elapsed-open period rather than relabelling it, and
 * a red "missed" is the relabelling.
 */
function periodLabel(period: HabitPeriod): string {
  if (period.outcome === "skipped") return "skipped";
  const count = `${period.progress} of ${period.target}`;
  // Both halves: what was done, and that it was called enough. Dropping
  // the count would lose what actually happened, and dropping the word
  // would make a contented day read as an unfinished one.
  return period.outcome === "partial" ? `${count} — enough` : count;
}

/** The mark a period wears. Filled when it was met, struck when it was
 *  deliberately skipped, and simply empty when it is still open. */
function periodMark(period: HabitPeriod): string {
  if (period.outcome === "completed") return "●";
  if (period.outcome === "skipped") return "–";
  // Half-filled: some of it was done, and that was the decision. Its own
  // mark rather than either of the others, because it is neither.
  if (period.outcome === "partial") return "◐";
  return "○";
}

function Habits({ habits }: { habits: Habit[] }) {
  return (
    <ul className="space-y-2">
      {habits.map((habit) => (
        <li
          key={habit.routine_id}
          className="space-y-1 rounded-lg border border-border px-3 py-2"
        >
          <span className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <span className="min-w-0">
              {habit.title}
              {habit.cadence === "weekly" && (
                <span className="ml-2 text-sm text-muted-foreground">
                  weekly
                </span>
              )}
            </span>
            <span className="flex shrink-0 items-baseline gap-2 text-sm text-muted-foreground">
              {habit.expected > 0 ? (
                <>
                  <span className="font-bold text-foreground">
                    {habit.met} of {habit.expected}
                  </span>
                  <span>met</span>
                </>
              ) : habit.paused_since ? (
                // Said, not left blank. Silence here reads the same as a
                // routine that did not exist yet, and a week somebody
                // deliberately put a routine down is a different fact from
                // a week it elapsed open — crane-plan.md §8.
                <span>Paused since {dayAndMonth(habit.paused_since)}</span>
              ) : (
                // Nothing was asked of it: a routine kept on Saturday is
                // not a routine that failed five days.
                <span>nothing expected yet</span>
              )}
              {/* A pause that started and finished inside the week leaves
                  no "since", so the days it took out are said here instead
                  — otherwise a denominator of four in a seven-day week
                  would look like an error. */}
              {!habit.paused_since && habit.paused_days > 0 && (
                <span>
                  · {habit.paused_days}{" "}
                  {habit.paused_days === 1 ? "day" : "days"} paused
                </span>
              )}
              {/* Beside the figure rather than inside it. A skip is out of
                  the denominator on purpose — the same call released pins
                  get — so the count that proves it stays visible. */}
              {habit.skipped > 0 && <span>· {habit.skipped} skipped</span>}
              {/* Beside the figure and apart from the skips, because "I did
                  some and stopped" and "I chose not to" are different facts
                  — which is the whole reason for a third outcome. */}
              {habit.enough > 0 && <span>· {habit.enough} called enough</span>}
            </span>
          </span>
          {habit.periods.length > 0 && (
            <span className="flex flex-wrap gap-1" aria-hidden={false}>
              {habit.periods.map((period) => (
                <span
                  key={period.period_start}
                  aria-label={`${weekday(period.period_start)}: ${periodLabel(period)}`}
                  title={`${weekday(period.period_start)}: ${periodLabel(period)}`}
                  className="text-sm text-muted-foreground"
                >
                  {periodMark(period)}
                </span>
              ))}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

type WeekSummary = {
  week_start: string;
  is_shown_week: boolean;
  planned_met: number | null;
  planned_total: number | null;
  habits_met: number | null;
  habits_expected: number | null;
};

/** A pair of figures, or the reason there is not one. */
function figure(met: number | null, total: number | null): string {
  if (met === null || total === null) return "—";
  if (total === 0) return "none";
  return `${met} of ${total}`;
}

/**
 * The shown week beside the four before it.
 *
 * One figure is a fact; five is a shape — two in three means something
 * different after three weeks of three in three than after three weeks of
 * one in five. Deliberately the same two numbers the page already shows
 * rather than a new kind of claim: the six analytical questions
 * architecture-trajectory.md §4 names have their home in release F.
 */
function RecentWeeks({ weeks }: { weeks: WeekSummary[] }) {
  return (
    <ul className="space-y-1">
      {weeks.map((week) => (
        <li
          key={week.week_start}
          aria-label={`Week of ${dayAndMonth(week.week_start)}`}
          className={`flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 rounded-lg border px-3 py-2 ${
            week.is_shown_week ? "border-accent" : "border-border"
          }`}
        >
          <span className="min-w-0">
            {dayAndMonth(week.week_start)}
            {week.is_shown_week && (
              <span className="ml-2 text-sm text-accent">this week</span>
            )}
          </span>
          {week.planned_total === null && week.habits_expected === null ? (
            // Never "0 of 0" for a week nobody was here for. That is the
            // least trustworthy number a page about trustworthy
            // denominators could print.
            <span className="shrink-0 text-sm text-muted-foreground">
              Nothing recorded yet
            </span>
          ) : (
            <span className="flex shrink-0 items-baseline gap-4 text-sm text-muted-foreground">
              <span>{figure(week.planned_met, week.planned_total)} planned</span>
              <span>{figure(week.habits_met, week.habits_expected)} habits</span>
            </span>
          )}
        </li>
      ))}
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
  const [weekIntention, setWeekIntention] = useState("");
  const [intentionError, setIntentionError] = useState<string | null>(null);
  const [intentionSaved, setIntentionSaved] = useState(false);
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
    // Seeded from the same effect and on the same key, so navigating to
    // another week reloads all three together. Separate state because it is a
    // separate record with a separate endpoint -- see the mutation below.
    setWeekIntention(data.draft.intention);
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

  // Scenario planning — v2 increment 8. A day is taken out and the same draft
  // is asked again; the answer replaces what is shown until the query settles
  // again. **Nothing is written**, which is why this is a GET and why the
  // scenario lives in component state rather than anywhere durable: a what-if
  // that persisted would be a plan somebody has to undo.
  const [unavailable, setUnavailable] = useState<string[]>([]);
  const scenario = useQuery({
    queryKey: ["week-draft", week ?? "current", unavailable.join(",")],
    enabled: unavailable.length > 0,
    queryFn: async () => {
      const day = data?.week_start;
      if (!day) throw new Error("Couldn't ask that.");
      const { data: drafted, error } = await apiV1.GET(
        "/api/v1/weeks/{day}/draft",
        {
          params: {
            path: { day },
            query: { unavailable: unavailable.join(",") },
          },
        },
      );
      if (error) throw new Error("Couldn't ask that.");
      return drafted;
    },
  });

  // The check-in — v2 increment 4. Two writes, because starting the ritual and
  // correcting what it believes are different statements: the first records
  // that somebody sat down, the second records what they changed.
  const startSession = useMutation({
    mutationFn: async () => {
      const day = data?.draft.week_start;
      if (!day) throw new Error("Couldn't start planning.");
      const { error } = await apiV1.POST("/api/v1/weeks/{day}/planning-session", {
        params: { path: { day } },
      });
      if (error) throw new Error("Couldn't start planning.");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  const correctSession = useMutation({
    mutationFn: async (unusual: string) => {
      const day = data?.draft.week_start;
      if (!day) throw new Error("Couldn't save that.");
      const { error } = await apiV1.PATCH("/api/v1/weeks/{day}/planning-session", {
        params: { path: { day } },
        body: { unusual },
      });
      if (error) throw new Error("Couldn't save that.");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  // Outcomes -- v2 increment 5. Three writes, because choosing, rewording and
  // dropping are three statements; the responses all carry the whole check-in
  // back, so the section re-renders from one source rather than reconciling.
  const chooseOutcome = useMutation({
    mutationFn: async (proposal: { project_id: number; suggested_text: string }) => {
      const day = data?.draft.week_start;
      if (!day) throw new Error("Couldn't add that outcome.");
      const { error } = await apiV1.POST("/api/v1/weeks/{day}/outcomes", {
        params: { path: { day } },
        // The project's own words, carried through unchanged. Nothing here
        // composes a sentence -- see the model on why that is D1's line.
        body: { text: proposal.suggested_text, project_id: proposal.project_id },
      });
      if (error) throw new Error("Couldn't add that outcome.");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
    onError: (caught: Error) => setSaveError(caught.message),
  });

  const dropOutcome = useMutation({
    mutationFn: async (outcomeId: number) => {
      const day = data?.draft.week_start;
      if (!day) throw new Error("Couldn't remove that outcome.");
      const { error } = await apiV1.DELETE(
        "/api/v1/weeks/{day}/outcomes/{outcome_id}",
        { params: { path: { day, outcome_id: outcomeId } } },
      );
      if (error) throw new Error("Couldn't remove that outcome.");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
    onError: (caught: Error) => setSaveError(caught.message),
  });

  // Answering a blocker in place -- v2 increment 6, and the end of "Decide them
  // in Second Mind". It posts to the knowledge core's own router on the shared
  // /api/v1/, which calls that core's services, so a question settled from here
  // records exactly what one settled from /mind/review/ does.
  //
  // Two verbs, not one. "I settled this" and "this was never a question" are
  // different facts, and the second is the only correction the question
  // heuristic will ever get -- collapsing them would spend that signal.
  const answerBlocker = useMutation({
    mutationFn: async ({
      publicId,
      disposition,
    }: {
      publicId: string;
      disposition: "answered" | "not-a-question";
    }) => {
      const { error } = await apiV1.POST(
        disposition === "answered"
          ? "/api/v1/questions/{public_id}/answered"
          : "/api/v1/questions/{public_id}/not-a-question",
        { params: { path: { public_id: publicId } } },
      );
      if (error) throw new Error("Couldn't record that.");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
    onError: (caught: Error) => setSaveError(caught.message),
  });

  // Parking a project from the check-in, through the task core's own endpoint.
  // The review proposes and the service that owns projects still decides --
  // the same shape pinning a task to today already takes, and the reason there
  // is no review-shaped write path for a bulk convenience to grow out of.
  const pauseProject = useMutation({
    mutationFn: async (projectId: number) => {
      const { error } = await apiV1.PATCH("/api/v1/projects/{project_id}", {
        params: { path: { project_id: projectId } },
        body: { is_paused: true },
      });
      if (error) throw new Error("Couldn't pause that project.");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  // What next week is for — product-stories.md S9. Its own mutation, its own
  // endpoint and its own control, for the reason the model is its own model:
  // an intention must not be able to invent a `WeeklyReview` row, because that
  // row's existence is the only evidence of whether reviewing is happening.
  // Folding this into the save above would put that risk one refactor away.
  //
  // It writes the week being *drafted*, not the week on screen. Both are on
  // the payload and confusing them would set an intention for a week that has
  // already happened.
  const intentionMutation = useMutation({
    mutationFn: async () => {
      const day = data?.draft.week_start;
      if (!day) throw new Error("Couldn't save what next week is for.");
      const { data: updated, error } = await apiV1.PUT(
        "/api/v1/weeks/{day}/intention",
        { params: { path: { day } }, body: { text: weekIntention } },
      );
      if (error) throw new Error("Couldn't save what next week is for.");
      return updated;
    },
    onSuccess: (updated) => {
      setIntentionError(null);
      setIntentionSaved(true);
      // Patched into the cached week rather than invalidated. The response is
      // the intention and not the week, and a refetch would cost the whole
      // review to carry one string back.
      // `typeof data` rather than a named type: the payload's shape comes
      // from the generated contract, and naming a local copy would be a
      // second definition to keep in step with it.
      queryClient.setQueryData(queryKey, (cached: typeof data) =>
        cached
          ? { ...cached, draft: { ...cached.draft, intention: updated.text } }
          : cached,
      );
    },
    onError: (caught: Error) => {
      setIntentionSaved(false);
      setIntentionError(caught.message);
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

  // Through the day's own endpoint, not one of the review's. The review
  // proposes; the service that owns pinning still decides — and there is
  // deliberately no review-shaped write path for a bulk convenience to
  // grow out of later.
  const [pinnedIds, setPinnedIds] = useState<Set<number>>(new Set());
  const pinMutation = useMutation({
    mutationFn: async (taskId: number) => {
      const day = data?.today;
      if (!day) throw new Error("Couldn't put that on today.");
      const { error } = await apiV1.POST("/api/v1/day/{day}/focus", {
        params: { path: { day } },
        body: { task_id: taskId },
      });
      if (error) throw new Error("Couldn't put that on today.");
      return taskId;
    },
    onSuccess: (taskId) => {
      // Said on the row rather than left to the payload. Pinning to today
      // changes nothing about a past week, so without this the click would
      // look like it had done nothing at all.
      setPinnedIds((current) => new Set(current).add(taskId));
      queryClient.invalidateQueries({ queryKey: ["day"] });
      queryClient.invalidateQueries({ queryKey: ["nav"] });
    },
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

  // `weekDraft`, because `draft` above is the review's own unsaved text. Two
  // different drafts on one page, and the collision was a build error rather
  // than a subtle bug only because they share a scope.
  const { loose_ends: looseEnds, upcoming, check_in: checkIn } = data;
  // The scenario's answer stands in for the draft while one is being asked.
  // Same shape, same renderer -- a what-if is the same week seen under a
  // different assumption, not a different kind of thing.
  const weekDraft = scenario.data ?? data.draft;

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
          onPinToToday={(taskId) => pinMutation.mutate(taskId)}
          pinnedIds={pinnedIds}
          pinning={pinMutation.isPending}
        />
        {pinMutation.isError && (
          <p className="text-sm text-destructive">
            {pinMutation.error.message}
          </p>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-bold">Finished</h2>
        <Finished completed={data.completed} />
      </section>

      {/* Absent when no routine existed in the week: a habit nobody kept
          is not a habit that went badly. */}
      {data.habits.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-bold">Habits</h2>
          <Habits habits={data.habits} />
        </section>
      )}

      {/* Absent when every week behind this one is empty: a trend with
          no history in it is five rows saying nothing. */}
      {data.recent_weeks.some(
        (week) => week.planned_total !== null || week.habits_expected !== null,
      ) && (
        <section className="space-y-2">
          <h2 className="text-sm font-bold">Recent weeks</h2>
          <RecentWeeks weeks={data.recent_weeks} />
        </section>
      )}

      <section className="space-y-2">
        <h2 className="text-sm font-bold">In your own words</h2>
        <Written written={data.written} />
      </section>

      {/* Absent rather than empty, unlike the writing above: an idea nobody
          had is not a fact about the week worth a heading. */}
      {data.thoughts.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-bold">Thoughts you captured</h2>
          <Thoughts thoughts={data.thoughts} />
        </section>
      )}

      {/* Loose ends and upcoming constraints -- planning-assistant-plan.md
          increment 5. Rendered only when they have something in them: an
          empty section reads the same as "you have none", and a review that
          shows five empty headings teaches you to scroll past all five.

          Extractive, and nothing here proposes. Every item already exists and
          already belongs to the person, so there is no confirm gate — the
          same reason the project brief has none. */}
      {(looseEnds.unanswered.length > 0 ||
        looseEnds.unanswered_commitments.length > 0 ||
        looseEnds.overdue.length > 0) && (
        <section className="space-y-2">
          <h2 className="text-sm font-bold">Still open</h2>

          {looseEnds.unanswered.length > 0 && (
            <div>
              <h3 className="text-sm text-muted-foreground">Unanswered questions</h3>
              <ul className="mt-1 space-y-1">
                {looseEnds.unanswered.map((question) => (
                  <li key={question.public_id} className="text-sm">
                    {question.text}{" "}
                    {/* The date is the evidence: "you asked this" is a fact,
                        and when is what makes it a loose end. */}
                    <span className="text-muted-foreground">
                      — asked {question.asked_on}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {looseEnds.unanswered_commitments.length > 0 && (
            <div>
              <h3 className="text-sm text-muted-foreground">
                Commitments you never answered
              </h3>
              <ul className="mt-1 space-y-1">
                {looseEnds.unanswered_commitments.map((commitment) => (
                  <li key={commitment.id} className="text-sm">
                    {commitment.text}{" "}
                    <span className="text-muted-foreground">
                      — proposed {commitment.proposed_on}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-1 text-sm text-muted-foreground">
                Read out of something you captured, and never accepted or
                dismissed.{" "}
                <a href="/mind/" className="underline hover:text-foreground">
                  Decide them in Second Mind
                </a>
                .
              </p>
            </div>
          )}

          {looseEnds.overdue.length > 0 && (
            <div>
              <h3 className="text-sm text-muted-foreground">Overdue</h3>
              <ul className="mt-1 space-y-1">
                {looseEnds.overdue.map((task) => (
                  <li key={task.id} className="text-sm">
                    {task.text}{" "}
                    <span className="text-muted-foreground">— due {task.due_date}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {(upcoming.tasks.length > 0 || upcoming.projects.length > 0) && (
        <section className="space-y-2">
          <h2 className="text-sm font-bold">Before the next review</h2>
          <ul className="space-y-1">
            {upcoming.projects.map((project) => (
              <li key={`project-${project.id}`} className="text-sm">
                {project.title}{" "}
                <span className="text-muted-foreground">
                  — project due {project.due_date}
                </span>
              </li>
            ))}
            {upcoming.tasks.map((task) => (
              <li key={`task-${task.id}`} className="text-sm">
                {task.text}{" "}
                <span className="text-muted-foreground">— due {task.due_date}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Next week, drafted -- planning-assistant-plan.md increment 6, and the
          last of the six. Rendered only when there is something to propose:
          an empty planner is indistinguishable from one that failed, and a
          heading over nothing teaches people to stop reading this far.

          **Nothing here is committed.** No confirm button, because there is
          nothing to confirm -- these tasks already exist and already carry
          their dates. Acting on one happens through the task itself, and
          ignoring the whole thing costs nothing, which is what keeps it a
          proposal rather than a plan somebody has to undo. */}
      {/* The section is no longer gated on there being proposals, and the
          guard moved down to the list instead -- see below. The comment above
          argues an empty planner reads as one that failed, which is true of a
          *proposal* and not of a writing prompt: an empty box asking what next
          week is for is an invitation, the same as the review's own two
          textareas, and a week with nothing scheduled in it is exactly when
          saying what it is for is worth most. */}
      <section className="space-y-2">
          <h2 className="text-sm font-bold">Next week</h2>

          {/* The check-in -- v2 increment 4. It opens with what the system
              believes and takes corrections; it does not ask for what is
              already recorded. A session that began "which projects are
              active?" would be asking somebody to supply an answer the
              database already holds.

              Behind a button, because reading the review must not count as
              planning: `review.reads` is query-only and a session recorded on
              page load would make every refresh a planning session, which
              would destroy the one number the record exists to produce. */}
          {!checkIn.started ? (
            <Button
              size="sm"
              variant="secondary"
              disabled={startSession.isPending}
              onClick={() => startSession.mutate()}
            >
              Plan next week
            </Button>
          ) : (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <label htmlFor="week-unusual" className="text-sm text-muted-foreground">
                  How is next week looking?
                </label>
                {/* A direction and never a number. The typical-week figure
                    below stays the authority on what a week holds; this says
                    only that next week is not a typical one, and nothing
                    multiplies the two together -- a declared figure beside a
                    derived one would be two authorities for one rule. */}
                <select
                  id="week-unusual"
                  value={checkIn.unusual}
                  onChange={(event) => correctSession.mutate(event.target.value)}
                  className="rounded-lg border border-border bg-input px-2 py-1 text-sm"
                >
                  <option value="usual">About usual</option>
                  <option value="less_time">Less time than usual</option>
                  <option value="more_time">More time than usual</option>
                </select>
              </div>

              {/* What the week is already committed to -- v2 increment 5.
                  Two or three things that will be true by Friday, each chosen
                  separately. Listed before the proposals, because the question
                  "is this enough?" is easier to answer looking at what is
                  already there. */}
              {checkIn.outcomes.length > 0 && (
                <ul className="space-y-1">
                  {checkIn.outcomes.map((outcome) => (
                    <li
                      key={outcome.id}
                      className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border border-accent px-3 py-2 text-sm"
                    >
                      <span>
                        {outcome.text}
                        {/* The snapshot, not the project's current name. A
                            rename does not rewrite what was committed to. */}
                        {outcome.project_title && (
                          <span className="text-muted-foreground">
                            {" "}
                            — {outcome.project_title}
                          </span>
                        )}
                      </span>
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-label="Drop this outcome"
                        disabled={dropOutcome.isPending}
                        onClick={() => dropOutcome.mutate(outcome.id)}
                      >
                        Drop
                      </Button>
                    </li>
                  ))}
                </ul>
              )}

              {/* What is worth choosing, and why. `because` is stated facts a
                  reader can check -- a deadline, work already dated into the
                  week -- rather than a score, and the sentence offered is the
                  project's own `desired_outcome`. Capped at five in the read:
                  a ritual opening with nine choices is the pile this step
                  exists to replace. */}
              {checkIn.proposals.length > 0 && (
                <ul className="space-y-1">
                  {checkIn.proposals.map((proposal) => (
                    <li
                      key={proposal.project_id}
                      className="flex flex-wrap items-baseline justify-between gap-2 text-sm"
                    >
                      <span>
                        {proposal.project_title}{" "}
                        <span className="text-muted-foreground">
                          — {proposal.because.join(" · ")}
                        </span>
                      </span>
                      <Button
                        size="sm"
                        variant="secondary"
                        aria-label={`Use ${proposal.project_title}`}
                        disabled={chooseOutcome.isPending}
                        onClick={() => chooseOutcome.mutate(proposal)}
                      >
                        Use
                      </Button>
                    </li>
                  ))}
                </ul>
              )}

              {/* What stands in the way of what was just chosen -- increment
                  6. Defined against the outcomes rather than being every open
                  question, which is what increment 5 bought by putting the
                  choosing first.

                  Each row carries its own evidence: what it blocks, how long
                  it has been open, and whether later notes came back to it.
                  A question that keeps returning is a different kind of
                  blocker from one asked once and forgotten. */}
              {checkIn.blockers.length > 0 && (
                <ul className="space-y-1">
                  {checkIn.blockers.map((blocker) => (
                    <li
                      key={blocker.public_id}
                      className="space-y-1 rounded-lg border border-border px-3 py-2 text-sm"
                    >
                      <p>{blocker.text}</p>
                      <p className="text-muted-foreground">
                        Blocks “{blocker.outcome_text}” — open{" "}
                        {blocker.days_open} days
                        {blocker.came_back === 1 && ", came back once"}
                        {blocker.came_back > 1 &&
                          `, came back ${blocker.came_back === 2 ? "twice" : `${blocker.came_back} times`}`}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={answerBlocker.isPending}
                          onClick={() =>
                            answerBlocker.mutate({
                              publicId: blocker.public_id,
                              disposition: "answered",
                            })
                          }
                        >
                          Settled
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={answerBlocker.isPending}
                          onClick={() =>
                            answerBlocker.mutate({
                              publicId: blocker.public_id,
                              disposition: "not-a-question",
                            })
                          }
                        >
                          Not a question
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}

              {/* Overdue work, the ones serving a chosen outcome first.
                  Ordered and never filtered: a leftover connected to nothing
                  is exactly the row worth deciding about, and hiding it would
                  make this a backlog rather than triage. */}
              {checkIn.carryover.length > 0 && (
                <ul className="space-y-1">
                  {checkIn.carryover.map((task) => (
                    <li key={task.id} className="text-sm">
                      {task.text}{" "}
                      <span className="text-muted-foreground">
                        {task.serves_an_outcome
                          ? "— serves an outcome"
                          : task.due_date && `— due ${task.due_date}`}
                      </span>
                    </li>
                  ))}
                </ul>
              )}

              {checkIn.projects.length > 0 && (
                <ul className="space-y-1">
                  {checkIn.projects.map((project) => (
                    <li
                      key={project.id}
                      className="flex flex-wrap items-baseline justify-between gap-2 text-sm"
                    >
                      <span>
                        {project.title}{" "}
                        <span className="text-muted-foreground">
                          {project.looks_active
                            ? "— active"
                            : `— nothing for ${project.quiet_for_days} days`}
                        </span>
                      </span>
                      {/* Only the quiet ones get the control. Offering to park
                          a project somebody worked on yesterday is a question
                          nobody needed asked. */}
                      {!project.looks_active && (
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={pauseProject.isPending}
                          onClick={() => pauseProject.mutate(project.id)}
                        >
                          {`Pause ${project.title}`}
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* product-stories.md S9 -- "on Sunday she decides what the week is
              about". Written here because this is the moment somebody is
              already looking forwards, and read on the Day page, which is
              where "on Wednesday the day knows" is answered.

              Its own control rather than a field on "Save the review": two
              records, two endpoints, and one button that meant both would be
              the near-identical-controls problem C2 found in the task UI. */}
          <div className="space-y-1">
            <label htmlFor="week-intention" className="text-sm text-muted-foreground">
              What is next week for?
            </label>
            <textarea
              id="week-intention"
              rows={2}
              value={weekIntention}
              onChange={(event) => {
                setWeekIntention(event.target.value);
                setIntentionSaved(false);
              }}
              className="w-full rounded-lg border border-border bg-input/40 px-3 py-2 text-sm"
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => intentionMutation.mutate()}
                disabled={intentionMutation.isPending}
              >
                Save
              </Button>
              {/* Not the bare "Saved." the review's own save uses, and the
                  difference is deliberate. Two controls on one page
                  confirming with the same string is how `test_pages.py`'s
                  `_table()` came to measure the wrong table: a query that
                  matches two things silently picks one. Distinct text keeps
                  "which save worked?" answerable by reading the page. */}
              {intentionSaved && (
                <span className="text-sm text-muted-foreground">
                  Saved what next week is for.
                </span>
              )}
              {intentionError && (
                <span className="text-sm text-destructive">{intentionError}</span>
              )}
            </div>
          </div>

          {/* Capacity, stated. Never "you only finish four" -- that is a
              verdict about the person where this is a fact about the weeks,
              and the vision document asks history to be useful without making
              missed work punishing. Absent entirely when there is too little
              history: null is not zero, and a zero would read as reassurance
              nobody earned. */}
          {weekDraft.typical_week !== null && (
            <p className="text-sm text-muted-foreground">
              {weekDraft.proposed.length} dated for next week. You have finished{" "}
              {weekDraft.typical_week} in a typical week.
              {weekDraft.over_committed && " That is more than the week usually holds."}
            </p>
          )}

          {/* The week laid out by day -- v2 increment 7. Only work already
              dated into the week appears here; overdue work stays in the flat
              list below and lands on no day, because placing a late task onto
              a weekday would be re-dating it and nothing here re-dates.

              Every day is shown, empty ones included: an empty day is where
              anything being moved would go.

              **Stated, never scolded.** "More than a typical day" is a fact
              about the days; "too much" is a verdict about the person, and a
              test asserts the second phrasing is absent. */}
          {/* Taking a day out -- v2 increment 8. One control per day, and the
              answer is the same draft asked again. Nothing moves: work due on
              a day that is gone is reported below as displaced, and where it
              actually goes stays the person's decision, made through the task.

              The buttons are named for the day so a screen reader hears which
              one, and so the test can ask for Thursday by name. */}
          {weekDraft.days.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted-foreground">What if:</span>
              {weekDraft.days.map((day) => {
                const weekdayName = new Intl.DateTimeFormat(undefined, {
                  weekday: "long",
                  timeZone: "UTC",
                }).format(new Date(`${day.date}T00:00:00Z`));
                const out = unavailable.includes(day.date);
                return (
                  <Button
                    key={`what-if-${day.date}`}
                    size="sm"
                    variant={out ? "secondary" : "ghost"}
                    aria-label={
                      out ? `Put back ${weekdayName}` : `Take out ${weekdayName}`
                    }
                    onClick={() =>
                      setUnavailable((current) =>
                        current.includes(day.date)
                          ? current.filter((each) => each !== day.date)
                          : [...current, day.date],
                      )
                    }
                  >
                    {out ? `${weekdayName} is out` : weekdayName}
                  </Button>
                );
              })}
              {unavailable.length > 0 && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setUnavailable([])}
                >
                  Put the week back
                </Button>
              )}
            </div>
          )}

          {/* What the scenario costs, stated rather than resolved. These have
              not moved and nothing has been re-dated -- this is the list of
              decisions the answer hands back to the person. */}
          {weekDraft.displaced.length > 0 && (
            <p className="text-sm text-muted-foreground">
              {weekDraft.displaced.length} dated on a day you have taken out:{" "}
              {weekDraft.displaced.map((each) => each.text).join(", ")}.
            </p>
          )}

          {weekDraft.days.some((day) => day.tasks.length > 0) && (
            <ul className="space-y-1">
              {weekDraft.days.map((day) => (
                <li key={day.date} className="text-sm">
                  <span className="text-muted-foreground">
                    {new Intl.DateTimeFormat(undefined, {
                      weekday: "long",
                      timeZone: "UTC",
                    }).format(new Date(`${day.date}T00:00:00Z`))}
                  </span>
                  {day.tasks.length === 0 ? (
                    <span className="text-muted-foreground"> — free</span>
                  ) : (
                    <ul className="mt-1 space-y-1 pl-4">
                      {day.tasks.map((task) => (
                        <li key={task.id}>
                          {task.text}
                          {/* Marked rather than filtered: work connected to
                              nothing chosen is exactly what somebody should
                              see before deciding about it. */}
                          {task.serves_an_outcome && (
                            <span className="text-muted-foreground">
                              {" "}
                              — serves an outcome
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                  {day.over_committed && (
                    <p className="text-sm text-muted-foreground">
                      {day.tasks.length} here, which is more than a typical day
                      of yours holds.
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}

          {weekDraft.proposed.length > 0 && (
            <ul className="space-y-1">
              {weekDraft.proposed.map((task) => (
                <li key={task.id} className="text-sm">
                  {task.text}
                  {task.due_date && (
                    <span className="text-muted-foreground"> — due {task.due_date}</span>
                  )}
                </li>
              ))}
            </ul>
          )}

          {weekDraft.routines.length > 0 && (
            <div>
              {/* Named apart from the tasks, because they are a different life
                  cycle -- a routine is measured toward a quantity over a
                  period and never spawns a task. */}
              <h3 className="text-sm text-muted-foreground">Also running</h3>
              <ul className="mt-1 space-y-1">
                {weekDraft.routines.map((routine) => (
                  <li key={routine.id} className="text-sm">
                    {routine.title}{" "}
                    <span className="text-muted-foreground">— {routine.cadence}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
      </section>

      {data.names_to_confirm.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-bold">Names worth confirming</h2>
          <NamesToConfirm names={data.names_to_confirm} />
          {/* Says why these are here and where they are answered. Like the
              Inbox list it replaces, this is not week-scoped -- a name that
              recurred over a month is exactly the one worth naming, and
              filtering to seven days would hide it. */}
          <p className="text-sm text-muted-foreground">
            Things you keep mentioning, whenever they came up.{" "}
            <a href="/mind/concepts/" className="underline hover:text-foreground">
              Name them in Second Mind
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
