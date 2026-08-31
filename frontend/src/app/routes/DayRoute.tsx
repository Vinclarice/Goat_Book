import { FormEvent, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { Button } from "@/components/ui/button";

import { ageLabel, colorForKey, dueLabel, snoozePresets } from "../../agenda";
import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { updateTaskDueDate, updateTaskStatus } from "../../api";
import type { AreaColorKey } from "../../types";
import { FirstRun } from "./FirstRun";
import { JournalSuggestions } from "./JournalSuggestions";
import { RouteFailure } from "./RouteFailure";

const SECTIONS = [
  {
    field: "intentions",
    label: "Intentions",
    hint: "Outcomes or ways of showing up. Not always tasks.",
  },
  {
    field: "gratitude",
    label: "Grateful for",
    hint: "Short, and for you rather than for the record.",
  },
  {
    field: "happenings",
    label: "Happenings",
    hint: "What actually occurred. This is what a later review reads.",
  },
] as const;

type Field = (typeof SECTIONS)[number]["field"];
type Draft = Record<Field, string>;

const EMPTY: Draft = { intentions: "", gratitude: "", happenings: "" };

type AreaSummary = { id: number; title: string; url: string; color_key: AreaColorKey };
type ProjectSummary = { id: number; title: string; url: string };

type ActionItem = {
  id: number;
  text: string;
  due_date: string | null;
  age_in_days: number;
  // Null for a task standing on its own -- see Task.area_id in types.ts.
  area_id: number | null;
  project_id: number | null;
};

type Focus = {
  task_id: number | null;
  text: string;
  status: string | null;
  due_date: string | null;
  /** Where the task lives, so this page can act on it. Null for a pin whose
   * task was deleted -- the record of having planned it outlives the task. */
  url: string | null;
};

/**
 * The day's deliberate choices, above the broader agenda.
 *
 * Separate from Action Items rather than a filter over them, because they
 * answer different questions: the agenda says what is due, this says what
 * the person decided to do. Crane 3's finish rate divides one by the other,
 * so conflating them here would make the metric meaningless later.
 */
function FocusList({
  focus,
  today,
  onUnpin,
  onComplete,
  onDefer,
  busy,
}: {
  focus: Focus[];
  today: string;
  onUnpin: (taskId: number) => void;
  onComplete: (item: Focus) => void;
  onDefer: (item: Focus) => void;
  busy: boolean;
}) {
  if (focus.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nothing pinned yet. Choose from your action items below to plan the day.
      </p>
    );
  }
  return (
    <ul className="space-y-1">
      {focus.map((item) => (
        <li
          key={item.task_id ?? item.text}
          className="flex items-baseline justify-between gap-3 rounded-lg border border-accent px-3 py-2"
        >
          <span className="min-w-0">
            <span className={item.status === "completed" ? "line-through" : ""}>
              {item.text}
            </span>
          </span>
          <span className="flex shrink-0 items-baseline gap-3">
            {item.due_date && (
              <span className="text-sm text-muted-foreground">
                {dueLabel(item.due_date, today)}
              </span>
            )}
            {/* A deleted task leaves the record but nothing to address. */}
            {item.task_id !== null && item.status !== "completed" && (
              <Button
                type="button"
                variant="ghost"
                disabled={busy}
                aria-label={`Complete ${item.text}`}
                onClick={() => onComplete(item)}
              >
                Complete
              </Button>
            )}
            {item.task_id !== null && item.status !== "completed" && (
              <Button
                type="button"
                variant="ghost"
                disabled={busy}
                aria-label={`Move ${item.text} to tomorrow`}
                onClick={() => onDefer(item)}
              >
                Tomorrow
              </Button>
            )}
            {item.task_id !== null && (
              <Button
                type="button"
                variant="ghost"
                disabled={busy}
                onClick={() => onUnpin(item.task_id!)}
              >
                Unpin
              </Button>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

/**
 * The agenda's rows, displayed rather than owned.
 *
 * Read-only on purpose. Slice 2's acceptance is that completing a task the
 * ordinary way shows up here on the next load; a Complete button would mean
 * reimplementing the agenda's mutation and undo beside it, and crane-plan
 * §5 is explicit that the Daily Page is new surface rather than a place to
 * restructure what it embeds.
 */
function ActionItems({
  items,
  today,
  areas,
  projects,
  pinnedIds,
  onPin,
  onUnpin,
  busy,
}: {
  items: ActionItem[];
  today: string;
  areas: AreaSummary[];
  projects: ProjectSummary[];
  pinnedIds: Set<number>;
  onPin: (taskId: number) => void;
  onUnpin: (taskId: number) => void;
  busy: boolean;
}) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nothing due today. Anything you add with today&rsquo;s date shows up here.
      </p>
    );
  }
  // Same join the Agenda makes: an item only carries area_id/project_id,
  // and the title/url live once here rather than repeated on every item.
  const areaById = new Map(areas.map((each) => [each.id, each]));
  const projectById = new Map(projects.map((each) => [each.id, each]));
  return (
    <ul className="space-y-1">
      {items.map((item) => {
        const pinned = pinnedIds.has(item.id);
        const itemArea = item.area_id ? areaById.get(item.area_id) : undefined;
        const itemProject = item.project_id ? projectById.get(item.project_id) : undefined;
        return (
          <li
            key={item.id}
            className="flex items-baseline justify-between gap-3 rounded-lg border border-border px-3 py-2"
          >
            {/* **These links deliberately carry no `touch-target`.** The
                utility's own note says two controls closer than ~12px apart
                overlap on touch and the later one in the DOM wins -- and here
                the area and project chips sit at `gap-1.5` (6px) with the
                title 4px above them, so 44px boxes on all three would fight
                each other in both directions. The row would get worse, not
                more reachable.

                S2's thumb requirement is met by the controls its own story
                uses -- Complete, Tomorrow, Pin, Unpin -- which are `Button`s
                and inherit the floor from the primitive. Reaching a task's
                detail page is navigation, and the row is not where that has
                to be thumb-sized. Do not "finish the sweep" here without
                first widening the gaps. */}
            <span className="min-w-0 space-y-1">
              <span className="block">
                {/* A <Link>, not an <a href>: this reloaded the whole
                    shell to reach a route the client router already had --
                    coherence-audit-2026-08-30.md F4. */}
                <Link to={`/tasks/${item.id}`} className="hover:underline">
                  {item.text}
                </Link>
                {/* A pinned task stays in the agenda below -- the focus list is
                    above it, not carved out of it -- so the row says which it
                    is rather than leaving two identical-looking entries. */}
                {pinned && (
                  <span className="ml-2 text-sm text-accent">Pinned</span>
                )}
              </span>
              {/* ui-second-pass-plan.md F2: this row used to show neither --
                  less than the Agenda, even though the join was one field
                  away on each side. */}
              {(itemArea || itemProject) && (
                <span className="flex flex-wrap items-center gap-1.5">
                  {itemArea && (
                    <a
                      href={itemArea.url}
                      className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground"
                    >
                      <span
                        className="h-1.5 w-1.5 rounded-full"
                        aria-hidden="true"
                        style={{ background: colorForKey(itemArea.color_key) }}
                      />
                      {itemArea.title}
                    </a>
                  )}
                  {itemProject && (
                    <a
                      href={itemProject.url}
                      className="inline-flex items-center rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground"
                    >
                      {itemProject.title}
                    </a>
                  )}
                </span>
              )}
            </span>
            <span className="flex shrink-0 items-baseline gap-3">
              {/* Deliberately the same muted grey as the due label beside
                  it, and deliberately not destructive: the acceptance for
                  this is a tone test, and a red badge shouting about
                  lateness is the thing it fails. */}
              {ageLabel(item.age_in_days) && (
                <span className="text-sm text-muted-foreground">
                  {ageLabel(item.age_in_days)}
                </span>
              )}
              {item.due_date && (
                <span className="text-sm text-muted-foreground">
                  {/* agenda.ts's own label, not a second date format invented
                      here -- "3 days overdue" has to read the same on both
                      pages or one of them is lying. */}
                  {dueLabel(item.due_date, today)}
                </span>
              )}
              <Button
                type="button"
                variant="ghost"
                disabled={busy}
                onClick={() => (pinned ? onUnpin(item.id) : onPin(item.id))}
              >
                {pinned ? "Unpin" : "Pin to today"}
              </Button>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** "Saturday 3 August" -- the label a person recognises their own day by. */
function longDate(isoDate: string): string {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone: "UTC",
  }).format(new Date(`${isoDate}T00:00:00Z`));
}

type Standing = {
  routine_id: number;
  title: string;
  cadence: string;
  progress: number;
  target: number;
  unit: string;
  outcome: string;
  is_met: boolean;
};

/**
 * How far a routine has got, in words.
 *
 * crane-plan.md §3 left this to Crane 2 on purpose: a blank unit means the
 * target is a plain yes/no for the period rather than a count of anything,
 * and "how that difference should render (a toggle versus a running
 * number)" was named as a UI decision rather than a domain one. So a
 * one-of-one with no unit reads "Done" / "Not yet", and everything else
 * reads as a count -- "1 of 1" is a strange way to tell somebody they moved
 * today.
 */
function standingLabel(standing: Standing): string {
  if (standing.outcome === "skipped") return "Skipped";
  if (!standing.unit && standing.target === 1) {
    return standing.progress >= 1 ? "Done" : "Not yet";
  }
  const unit = standing.unit ? ` ${standing.unit}` : "";
  const count = `${standing.progress} of ${standing.target}${unit}`;
  // Says the count and then what was decided about it, rather than
  // replacing one with the other: "I did three and that was enough" is
  // both halves, and dropping the three would lose what actually happened.
  return standing.outcome === "partial" ? `${count} — enough` : count;
}

/**
 * Practice, on the day it belongs to.
 *
 * A routine is not a task and never appears in Action Items -- the agenda
 * is tasks, and the whole design rests on that staying true. It sits below
 * them because what is due today is a stronger claim on attention than what
 * you are practising, and above the day's writing because both are things
 * you do rather than record.
 */
function Routines({
  standings,
  loggable,
  onLog,
  onSkip,
  onEnough,
  onPause,
  busy,
}: {
  standings: Standing[];
  loggable: boolean;
  onLog: (routineId: number, amount: number) => void;
  onSkip: (routineId: number) => void;
  onEnough: (routineId: number) => void;
  onPause: (routineId: number) => void;
  busy: boolean;
}) {
  if (standings.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No routines yet. A routine is practice you repeat — five lessons a day,
        three sessions a week — rather than a task you finish once.
      </p>
    );
  }
  return (
    <ul className="space-y-1">
      {standings.map((standing) => (
        <li
          key={standing.routine_id}
          className="flex items-baseline justify-between gap-3 rounded-lg border border-border px-3 py-2"
        >
          <span className="min-w-0">
            <span className={standing.is_met ? "line-through" : ""}>
              {standing.title}
            </span>
            {standing.cadence === "weekly" && (
              <span className="ml-2 text-sm text-muted-foreground">weekly</span>
            )}
          </span>
          <span className="flex shrink-0 items-baseline gap-2">
            <span className="text-sm text-muted-foreground">
              {standingLabel(standing)}
            </span>
            {loggable && (
              <>
                {/* Minus first and only when there is something to take
                    back, so the common action is not the one you have to
                    aim past. */}
                {standing.progress > 0 && (
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={busy}
                    aria-label={`Undo one for ${standing.title}`}
                    onClick={() => onLog(standing.routine_id, -1)}
                  >
                    −1
                  </Button>
                )}
                <Button
                  type="button"
                  variant="ghost"
                  disabled={busy}
                  aria-label={`Log one for ${standing.title}`}
                  onClick={() => onLog(standing.routine_id, 1)}
                >
                  +1
                </Button>
                {/* "I did some of it, and that was enough." Offered only
                    where it is true: something done, and the target not
                    reached. With nothing done the honest statement is a
                    skip, which is the control beside it — and once the
                    target is met there is nothing left to be content
                    about. */}
                {standing.progress > 0 &&
                  !standing.is_met &&
                  standing.outcome !== "partial" && (
                    <Button
                      type="button"
                      variant="ghost"
                      disabled={busy}
                      aria-label={`Call it enough for ${standing.title}`}
                      onClick={() => onEnough(standing.routine_id)}
                    >
                      Enough
                    </Button>
                  )}
                {/* Says what was decided, not what happened -- a different
                    statement from logging, so a different control. */}
                {standing.outcome !== "skipped" && (
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={busy}
                    onClick={() => onSkip(standing.routine_id)}
                  >
                    Skip
                  </Button>
                )}
                {/* Skipping is about this period; pausing is about the
                    routine. Adjacent because they are both "not now", and
                    labelled apart because they are not the same not-now. */}
                <Button
                  type="button"
                  variant="ghost"
                  disabled={busy}
                  aria-label={`Pause ${standing.title}`}
                  onClick={() => onPause(standing.routine_id)}
                >
                  Pause
                </Button>
              </>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

/**
 * Rapid logging, on the page you are already looking at.
 *
 * Posts to the capture endpoint the Android client already uses, so the row
 * it writes is the same row -- no daily-shaped capture, no second definition
 * of what an empty capture is. See mind/tests/test_capture_paths_agree.py.
 *
 * Since Heron 4a that row is a knowledge-core `Node` rather than an Inbox
 * `Capture`: same URL, same request, different destination. This box is one
 * of the three surfaces that change under it, and the one nobody counted --
 * one-capture-surface-plan.md said there were two.
 *
 * Deliberately not part of the day's own form. What you capture is a thought
 * going somewhere to be thought about later; what you write below is this
 * day's record. Merging them into one save button is precisely the kind of
 * near-identical-controls-with-opposite-meanings confusion C2 found in the
 * task UI, and this page is new surface with no excuse for it.
 */
function CaptureBox() {
  const [text, setText] = useState("");
  const [captured, setCaptured] = useState(false);

  const mutation = useMutation({
    mutationFn: async (thought: string) => {
      const { error } = await apiV1.POST("/api/v1/capture", {
        // No tags UI here -- design/capture-tags-plan.md scoped tagging to
        // the Android compose screen and read-only display in the web
        // Inbox, not this quick-capture box.
        body: { text: thought, tags: [] },
      });
      if (error) throw new Error("Couldn't capture that. It's still here.");
    },
    onSuccess: () => {
      // Cleared only now. principles.md: capture is durable before it is
      // clever -- a thought must not be lost to a failed request, so the
      // box empties on success and never on the way there.
      setText("");
      setCaptured(true);
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setCaptured(false);
    if (!text.trim()) return;
    mutation.mutate(text);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      <label htmlFor="day-capture" className="text-sm font-bold">
        Capture a thought
      </label>
      <textarea
        id="day-capture"
        value={text}
        onChange={(event) => {
          setCaptured(false);
          setText(event.target.value);
        }}
        rows={2}
        placeholder="What's on your mind?"
        className="w-full rounded-lg border border-border bg-input px-3 py-2"
      />
      <div className="flex items-center gap-3">
        <Button type="submit" variant="secondary" disabled={mutation.isPending}>
          Capture
        </Button>
        {/* Says where it went, and has to keep being true. Without it the
            thought appears to vanish and the next one gets typed into
            Intentions instead -- but a confirmation naming the wrong place is
            worse than none, because somebody will go and look there. This read
            "Sent to your Inbox." until Heron 4a moved the destination. */}
        {captured && (
          <span className="text-sm text-muted-foreground">
            Kept. <a href="/mind/" className="touch-target underline">See it</a>
          </span>
        )}
        {mutation.isError && (
          <span className="text-sm text-destructive">
            {mutation.error.message}
          </span>
        )}
      </div>
      <p className="text-sm text-muted-foreground">
        Goes to the Inbox to sort out later — not into this day&rsquo;s notes.
      </p>
    </form>
  );
}

type PausedRoutine = {
  routine_id: number;
  title: string;
  cadence: string;
  target: number;
  unit: string;
};

/**
 * The ones put down, kept findable so they can be picked back up.
 *
 * Below the active list and quieter than it, because a paused routine is
 * not work for today -- but present, because one that appeared nowhere
 * would be one nobody could resume.
 */
function PausedRoutines({
  paused,
  onResume,
  busy,
}: {
  paused: PausedRoutine[];
  onResume: (routineId: number) => void;
  busy: boolean;
}) {
  if (paused.length === 0) return null;
  return (
    <div className="space-y-1">
      <p className="text-sm text-muted-foreground">Paused</p>
      <ul className="space-y-1">
        {paused.map((routine) => (
          <li
            key={routine.routine_id}
            className="flex items-baseline justify-between gap-3 rounded-lg border border-border px-3 py-2 opacity-70"
          >
            <span className="min-w-0">{routine.title}</span>
            <Button
              type="button"
              variant="ghost"
              disabled={busy}
              aria-label={`Resume ${routine.title}`}
              onClick={() => onResume(routine.routine_id)}
            >
              Resume
            </Button>
          </li>
        ))}
      </ul>
      {/* Says the thing people worry about before they have to ask. */}
      <p className="text-sm text-muted-foreground">
        Everything a paused routine already did is kept. Picking it back up
        starts from today rather than filling in the gap.
      </p>
    </div>
  );
}

/**
 * Keeping a new routine.
 *
 * On this page because the slice list never gave routine creation a
 * surface anywhere -- the same gap slice 6 found when the Daily Page
 * itself turned out to be reachable only by typing its URL. A routine is
 * content rather than a setting, so Preferences would have been the wrong
 * home for it even though that is where the compass went.
 *
 * Folded away by default: keeping a routine is a rare act next to logging
 * one, and four fields permanently open would make the day's page look
 * like a form.
 */
function AddRoutine({
  onCreate,
  busy,
}: {
  onCreate: (routine: {
    title: string;
    cadence: string;
    target_quantity: number;
    unit: string;
  }) => void;
  busy: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [cadence, setCadence] = useState("daily");
  const [target, setTarget] = useState("1");
  const [unit, setUnit] = useState("");

  if (!open) {
    return (
      <Button type="button" variant="ghost" onClick={() => setOpen(true)}>
        Keep a routine
      </Button>
    );
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;
    onCreate({
      title: title.trim(),
      cadence,
      target_quantity: Math.max(1, Number(target) || 1),
      unit: unit.trim(),
    });
    setTitle("");
    setUnit("");
    setTarget("1");
    setOpen(false);
  }

  return (
    <form onSubmit={submit} className="space-y-2 rounded-lg border border-border px-3 py-3">
      <div className="space-y-1">
        <label htmlFor="routine-title" className="text-sm font-bold">
          Routine
        </label>
        <input
          id="routine-title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Practice Spanish"
          className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <div className="space-y-1">
          <label htmlFor="routine-cadence" className="text-sm font-bold">
            How often
          </label>
          <select
            id="routine-cadence"
            value={cadence}
            onChange={(event) => setCadence(event.target.value)}
            className="rounded-lg border border-border bg-input px-3 py-1.5"
          >
            <option value="daily">Every day</option>
            <option value="weekly">Every week</option>
          </select>
        </div>
        <div className="space-y-1">
          <label htmlFor="routine-target" className="text-sm font-bold">
            How many
          </label>
          <input
            id="routine-target"
            type="number"
            min={1}
            value={target}
            onChange={(event) => setTarget(event.target.value)}
            className="w-20 rounded-lg border border-border bg-input px-3 py-1.5"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="routine-unit" className="text-sm font-bold">
            Of what
          </label>
          <input
            id="routine-unit"
            value={unit}
            onChange={(event) => setUnit(event.target.value)}
            placeholder="lessons"
            className="w-32 rounded-lg border border-border bg-input px-3 py-1.5"
          />
        </div>
      </div>
      {/* Says what leaving it blank means, rather than leaving somebody to
          find out by creating one. */}
      <p className="text-sm text-muted-foreground">
        Leave &ldquo;of what&rdquo; empty for a plain yes-or-no, like moving today.
      </p>
      <div className="flex items-center gap-3">
        <Button type="submit" variant="secondary" disabled={busy}>
          Keep it
        </Button>
        <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

export function DayRoute() {
  const { date } = useParams();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // The undated route asks the server what today is rather than reading the
  // browser clock: the day boundary is the owner's time zone, and that
  // lives on the server (see per-user-time-zones-plan.md). A phone in a
  // different zone from the account must still open the same page.
  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["day", date ?? "today"],
    queryFn: async () => {
      const { data, response } = date
        ? await apiV1.GET("/api/v1/day/{day}", { params: { path: { day: date } } })
        : await apiV1.GET("/api/v1/day");
      if (!response.ok || !data) throw new RequestFailed(response.status);
      return data;
    },
  });

  // Seeded once per day, not on every settle of the query.
  //
  // This query refetches when the tab regains focus, and writing the draft
  // from the fetch would mean an alt-tab silently restored the stored text
  // over whatever was being typed -- then "Saved." would confirm the
  // restored version. PreferencesRoute hit exactly this and the fix is the
  // same; the ref holds *which* day was seeded so that navigating from the
  // 3rd to the 4th still loads the 4th.
  const seededFor = useRef<string | null>(null);
  useEffect(() => {
    if (!data || seededFor.current === data.date) return;
    seededFor.current = data.date;
    setDraft({
      intentions: data.intentions,
      gratitude: data.gratitude,
      happenings: data.happenings,
    });
    setSaved(false);
  }, [data]);

  function edit(field: Field, value: string) {
    setSaved(false);
    setDraft((current) => ({ ...current, [field]: value }));
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      const day = data?.date;
      if (!day) throw new Error("Couldn't save this day.");
      const { data: updated, error } = await apiV1.PATCH("/api/v1/day/{day}", {
        params: { path: { day } },
        body: draft,
      });
      if (error) throw new Error("Couldn't save this day.");
      return updated;
    },
    onSuccess: (updated) => {
      setSaveError(null);
      setSaved(true);
      queryClient.setQueryData(["day", date ?? "today"], updated);
    },
    onError: (mutationError: Error) => {
      setSaved(false);
      setSaveError(mutationError.message);
    },
  });

  // Pin and unpin both answer with the whole day, so the focus list and the
  // action items can never disagree for a frame. Written straight into the
  // cache rather than invalidated: a refetch would settle the query again,
  // and the day's draft is deliberately seeded only once.
  const focusMutation = useMutation({
    mutationFn: async ({ taskId, pin }: { taskId: number; pin: boolean }) => {
      const day = data?.date;
      if (!day) throw new Error("Couldn't change what's pinned.");
      const { data: updated, error } = pin
        ? await apiV1.POST("/api/v1/day/{day}/focus", {
            params: { path: { day } },
            body: { task_id: taskId },
          })
        : await apiV1.DELETE("/api/v1/day/{day}/focus/{task_id}", {
            params: { path: { day, task_id: taskId } },
          });
      if (error) throw new Error("Couldn't change what's pinned.");
      return updated;
    },
    onSuccess: (updated) =>
      queryClient.setQueryData(["day", date ?? "today"], updated),
  });

  // Accepting the day's draft, in one act rather than one per task. That is
  // the whole point: the daily loop's manual cost was choosing five things by
  // hand every morning, while the weekly loop had fourteen increments of
  // assistant.
  //
  // **It sends the ids the draft displayed**, not a fresh read. The draft is
  // computed on read and stored nowhere, so between rendering and clicking a
  // task can be completed elsewhere or a recurrence can fire -- accepting what
  // was shown is the honest contract, and re-deriving would pin something
  // nobody saw.
  const acceptDraft = useMutation({
    mutationFn: async (taskIds: number[]) => {
      const day = data?.date;
      if (!day) throw new Error("Couldn't plan the day.");
      const { data: updated, error } = await apiV1.POST(
        "/api/v1/day/{day}/focus/draft",
        { params: { path: { day } }, body: { task_ids: taskIds } },
      );
      if (error) throw new Error("Couldn't plan the day.");
      return updated;
    },
    onSuccess: (updated) =>
      queryClient.setQueryData(["day", date ?? "today"], updated),
  });

  // Completing goes through the task's own endpoint rather than the day's,
  // because `updateTaskStatus` is the authority every other surface already
  // completes through -- `principles.md`'s *one rule, one authoritative
  // definition*. The read-only note that used to sit on the agenda rows here
  // was right that a second mutation would be wrong, and wrong that the only
  // alternative was doing without the verb.
  //
  // Invalidated rather than patched into the cache, unlike pin and unpin.
  // They answer with the whole day; this answers with a task, and a completed
  // *recurring* task also archives itself and spawns its successor -- so what
  // the day looks like afterwards is the server's answer, not one this page
  // can assemble. The draft survives a refetch by design; there is a test.
  const completeMutation = useMutation({
    mutationFn: async (item: Focus) => {
      // **`task_id`, not `url`.** The client addresses a task by id since
      // coherence-audit-2026-08-30.md F2, so a stand-in carrying only a url
      // produced a request with `{item_id}` still in the path. Both fields are
      // null in exactly the same case -- a pin whose task was deleted -- so
      // this is the same guard said directly.
      if (item.task_id === null) throw new Error("Couldn't complete that.");
      return updateTaskStatus(
        { id: item.task_id } as Parameters<typeof updateTaskStatus>[0],
        "completed",
      );
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["day", date ?? "today"] }),
  });

  // "Moves one task to tomorrow" -- S2's second verb, and the one that makes
  // the day a place to *decide* rather than only to look.
  //
  // **Not carry-forward.** daily-operating-system-vision.md forbids rewriting
  // a due date *automatically* -- "never automatically reschedule everything
  // left incomplete". One person, one item, one decision is the shape that
  // rule deliberately leaves open, and this is it.
  //
  // The date comes from `snoozePresets`, the authority the Agenda's own snooze
  // menu uses, rather than an inline today+1. That rule is already mirrored in
  // Python and TypeScript; a third copy here would be the exact drift
  // `mirrored-rules-brief.md` was written about. Serving the presets in the
  // payload -- the blueprint's highest-ROI adopt item -- would delete the
  // mirror properly, and is a bigger change than this one.
  const deferMutation = useMutation({
    mutationFn: async (item: Focus) => {
      const tomorrow = snoozePresets(data?.today ?? "").find(
        (preset) => preset.key === "tomorrow",
      );
      if (item.task_id === null || !tomorrow) throw new Error("Couldn't move that.");
      return updateTaskDueDate(
        { id: item.task_id } as Parameters<typeof updateTaskDueDate>[0],
        tomorrow.dueDate,
      );
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["day", date ?? "today"] }),
  });

  // Routine writes answer with today's standings rather than the whole day,
  // so the day in cache is patched with them instead of refetched. Same
  // reason as the focus mutations: a refetch would settle the query again,
  // and the day's draft is deliberately seeded only once.
  const routineMutation = useMutation({
    mutationFn: async (
      action:
        // One member per kind rather than a union of kinds on one member:
        // TypeScript narrows a discriminated union by literal, and a member
        // whose own discriminant is a union does not narrow away.
        | { kind: "log"; routineId: number; amount: number }
        | { kind: "skip"; routineId: number }
        | { kind: "enough"; routineId: number }
        | { kind: "pause"; routineId: number }
        | { kind: "resume"; routineId: number }
        | { kind: "create"; routine: Record<string, unknown> },
    ) => {
      if (action.kind === "pause" || action.kind === "resume") {
        const { data: updated, error } = await apiV1.POST(
          action.kind === "pause"
            ? "/api/v1/routines/{routine_id}/pause"
            : "/api/v1/routines/{routine_id}/resume",
          { params: { path: { routine_id: action.routineId } } },
        );
        if (error) throw new Error("Couldn't change that routine.");
        return updated;
      }
      if (action.kind === "create") {
        const { data: updated, error } = await apiV1.POST("/api/v1/routines", {
          body: action.routine as never,
        });
        if (error) throw new Error("Couldn't keep that routine.");
        return updated;
      }
      if (action.kind === "skip" || action.kind === "enough") {
        const { data: updated, error } = await apiV1.POST(
          action.kind === "skip"
            ? "/api/v1/routines/{routine_id}/skip"
            : "/api/v1/routines/{routine_id}/enough",
          { params: { path: { routine_id: action.routineId } } },
        );
        if (error) throw new Error("Couldn't skip that.");
        return updated;
      }
      const { data: updated, error } = await apiV1.POST(
        "/api/v1/routines/{routine_id}/log",
        {
          params: { path: { routine_id: action.routineId } },
          body: { amount: action.amount },
        },
      );
      if (error) throw new Error("Couldn't log that.");
      return updated;
    },
    onSuccess: (updated) =>
      queryClient.setQueryData(["day", date ?? "today"], (old: unknown) =>
        old
          ? {
              ...(old as object),
              routines: updated?.standings ?? [],
              paused_routines: updated?.paused ?? [],
            }
          : old,
      ),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaved(false);
    saveMutation.mutate();
  }

  if (isPending) return <p className="p-6">Loading…</p>;
  if (error || !data) {
    return <RouteFailure status={statusOf(error)} onRetry={() => refetch()} />;
  }

  const isToday = data.date === data.today;
  // Derived rather than stored: what is pinned is the focus list's answer,
  // and an action-item row asking "am I in it" must not be able to disagree.
  // Areas rather than emptiness: see the comment at the render below.
  const firstRun = data.areas.length === 0;
  const pinnedIds = new Set(
    data.focus
      .map((item) => item.task_id)
      .filter((id): id is number => id !== null),
  );

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-accent">
          {isToday ? "Today" : "Your day"}
        </p>
        <h1 className="text-2xl font-bold">{longDate(data.date)}</h1>
        {/* The only way into the calendar, and therefore into any date that
            is not this one. Without it the route is a surface nothing
            reaches -- the un-switched-on seam this project has found five
            times in a fortnight. */}
        <Link
          to={`/calendar/${data.date}`}
          className="touch-target inline-block text-sm text-muted-foreground hover:text-foreground"
        >
          Another day
        </Link>
      </div>

      {/* What the day's writing read as a commitment — increment 2 slice D.
          Below the compass and above the work, because it is about the
          writing rather than about the plan, and because nothing here happens
          until it is answered. */}
      <JournalSuggestions day={date ?? "today"} suggestions={data.suggestions} />

      {/* Above everything, and quiet. It is the thing you re-read rather
          than the thing you do -- and it is the same on every day's page,
          because it is stored on you and not on any of them. */}
      {(data.compass_purpose || data.compass_question) && (
        <section className="space-y-1 rounded-lg border border-border bg-input/40 px-4 py-3">
          {data.compass_purpose && (
            <p className="text-sm">{data.compass_purpose}</p>
          )}
          {data.compass_question && (
            <p className="text-sm font-bold">{data.compass_question}</p>
          )}
          <a
            href="/app/preferences"
            className="touch-target inline-block text-sm text-muted-foreground hover:text-foreground"
          >
            Edit your compass
          </a>
        </section>
      )}

      {/* What the week is for — product-stories.md S9, "on Wednesday the day
          knows". Beside the compass and for the compass's reason: context a
          day is meant to be read *in*, displayed and never owned here, with
          no copy that could drift from the week that holds it.

          Narrower than the compass and placed under it deliberately. The
          compass is stored on the person and is the same on every day's page;
          this changes every Monday, so the order is permanent, then weekly,
          then the day itself.

          Absent when blank rather than shown empty. Blank is a value — "I set
          none this week" is a real answer — and a heading over nothing is the
          empty frame that teaches you to scroll past the section on the weeks
          it does have something to say. */}
      {data.week_intention && (
        <section className="space-y-1 rounded-lg border border-border bg-input/40 px-4 py-3">
          <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
            This week
          </p>
          <p className="text-sm">{data.week_intention}</p>
        </section>
      )}

      {/* Nobody can have a task without an area, so no areas means nobody has
          started -- a fact about the account, not about the date being looked
          at, which is what keeps this away from an established person's quiet
          Tuesday. See FirstRun and product-stories.md S1: three empty states
          that cannot be acted on are the "six concepts" that story refuses. */}
      {firstRun ? (
        <FirstRun />
      ) : (
        <>
      <section className="space-y-2">
        <h2 className="text-sm font-bold">Focus</h2>
        {/* The awareness half of the brief — *what changed*, never what
            merely is. Everything here is deliberately something this page
            does not already show: overdue work is below, and the fact that he
            *chose* one of them yesterday is not.

            Three lists and never one ordering. A slipped commitment against a
            bill against a quiet project is `SearchRank` over two document
            sets again — a number that does not exist as relevance, failing
            silently.

            Absent entirely on a quiet day. A brief that filled three sections
            every morning would be skipped by the end of the week, so short is
            the correct output rather than a failure. */}
        {(data.brief.slipped.length > 0 ||
          data.brief.coming.length > 0 ||
          data.brief.gone_quiet.length > 0) && (
          <section className="space-y-2 rounded-lg border border-border px-3 py-2">
            <h2 className="text-sm font-bold">Since yesterday</h2>
            {data.brief.slipped.length > 0 && (
              <div>
                <p className="text-sm text-muted-foreground">
                  Chosen yesterday, still open:
                </p>
                <ul className="text-sm">
                  {data.brief.slipped.map((task) => (
                    <li key={`slipped-${task.id}-${task.text}`}>{task.text}</li>
                  ))}
                </ul>
              </div>
            )}
            {data.brief.coming.length > 0 && (
              <div>
                <p className="text-sm text-muted-foreground">Coming up:</p>
                <ul className="text-sm">
                  {data.brief.coming.map((task) => (
                    <li key={`coming-${task.id}`}>
                      {task.text}
                      {task.due_date && (
                        <span className="ml-2 text-muted-foreground">
                          {dueLabel(task.due_date, data.today)}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {data.brief.gone_quiet.length > 0 && (
              <div>
                <p className="text-sm text-muted-foreground">
                  Nothing has moved here:
                </p>
                <ul className="text-sm">
                  {data.brief.gone_quiet.map((project) => (
                    <li key={`quiet-${project.id}`}>
                      {project.title}
                      <span className="ml-2 text-muted-foreground">
                        {project.quiet_for_days} days
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}

        {/* Absent when there is no capacity to justify a number: null is not
            zero, and "no evidence yet" and "you have room" call for opposite
            responses. Says what it left out, because bounding the proposal is
            not hiding the work -- the full list is the action items below. */}
        {data.draft.proposed.length > 0 && (
          <div className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border border-accent px-3 py-2">
            <p className="text-sm text-muted-foreground">
              {data.draft.proposed.length} of {data.draft.available} have a
              claim on today. You finish {data.draft.typical} on a typical day.
            </p>
            <Button
              type="button"
              disabled={acceptDraft.isPending}
              onClick={() =>
                acceptDraft.mutate(data.draft.proposed.map((task) => task.id))
              }
            >
              Plan my day
            </Button>
          </div>
        )}

        {/* The other half of "no capacity, no proposal": with candidates and
            no figure, this rendered as blank space, which reads as broken
            rather than as honest. The count proves it is not; the second
            sentence says what unblocks it. **The floor is not restated here** —
            `TYPICAL_DAY_MINIMUM_SAMPLE` owns it, and a mirrored constant is one
            that disagrees later. Silent when there was nothing to propose
            either, and on a day already lived, where planning advice is a
            verdict. */}
        {data.draft.typical === null &&
          data.draft.available > 0 &&
          data.date >= data.today && (
            <p className="text-sm text-muted-foreground">
              {data.draft.available} could have a claim on today. Plan a few
              days by hand first, and this can start proposing a set.
            </p>
          )}
        <FocusList
          focus={data.focus}
          today={data.today}
          onUnpin={(taskId) => focusMutation.mutate({ taskId, pin: false })}
          onComplete={(item) => completeMutation.mutate(item)}
          onDefer={(item) => deferMutation.mutate(item)}
          busy={
            focusMutation.isPending ||
            completeMutation.isPending ||
            deferMutation.isPending
          }
        />
        {/* What the day actually holds — product-stories.md S3, whose
            done-means is "the day says so while he is still planning". The
            week-grain version of this sentence lives on the review's draft;
            D2's worked example was always a Tuesday, and this is that.

            **Stated, never graded.** "You have finished three on a typical
            day" is a fact about the days; "you only finish three" is a verdict
            about the person, and daily-operating-system-vision.md asks that
            history be useful without making missed work punishing — a planner
            being the surface most able to break it. A test asserts the second
            phrasing is *absent*, not merely that the first is present.

            Three conditions, each for its own reason. Absent below the
            evidence floor, because null is not zero and a zero would read as
            reassurance nobody earned. Absent before anything is pinned, since
            there is nothing to compare. And absent on a day already lived: the
            point is planning, the same distinction shows_action_items already
            makes at day == today, and on a past day this sentence is a verdict
            on something that cannot be changed. */}
        {isToday && data.typical_day !== null && data.focus.length > 0 && (
          <p className="text-sm text-muted-foreground">
            {data.focus.length} pinned for today. You have finished{" "}
            {data.typical_day} on a typical day.
            {data.focus.length > data.typical_day &&
              " That is more than the day usually holds."}
          </p>
        )}
        {focusMutation.isError && (
          <p className="text-sm text-destructive">
            {focusMutation.error.message}
          </p>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-bold">Action items</h2>
        {data.shows_action_items ? (
          <ActionItems
            items={data.action_items}
            today={data.today}
            areas={data.areas}
            projects={data.projects}
            pinnedIds={pinnedIds}
            onPin={(taskId) => focusMutation.mutate({ taskId, pin: true })}
            onUnpin={(taskId) => focusMutation.mutate({ taskId, pin: false })}
            busy={focusMutation.isPending}
          />
        ) : (
          // Said plainly rather than shown as an empty list: a task holds no
          // record of what it looked like on a past date, so this page can
          // show what was written and honestly nothing else.
          <p className="text-sm text-muted-foreground">
            Only today shows action items. What you wrote on this day is below.
          </p>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-bold">Routines</h2>
        <Routines
          standings={data.routines}
          loggable={data.routines_are_loggable}
          onLog={(routineId, amount) =>
            routineMutation.mutate({ kind: "log", routineId, amount })
          }
          onSkip={(routineId) =>
            routineMutation.mutate({ kind: "skip", routineId })
          }
          onEnough={(routineId) =>
            routineMutation.mutate({ kind: "enough", routineId })
          }
          onPause={(routineId) =>
            routineMutation.mutate({ kind: "pause", routineId })
          }
          busy={routineMutation.isPending}
        />
        {data.routines_are_loggable && (
          <PausedRoutines
            paused={data.paused_routines}
            onResume={(routineId) =>
              routineMutation.mutate({ kind: "resume", routineId })
            }
            busy={routineMutation.isPending}
          />
        )}
        {!data.routines_are_loggable && data.routines.length > 0 && (
          // Read-only rather than absent: an occurrence is a dated record,
          // so a past day can honestly say what happened -- it just cannot
          // be changed from here.
          <p className="text-sm text-muted-foreground">
            What this day&rsquo;s routines came to. Logging happens on today.
          </p>
        )}
        {data.routines_are_loggable && (
          <AddRoutine
            onCreate={(routine) =>
              routineMutation.mutate({ kind: "create", routine })
            }
            busy={routineMutation.isPending}
          />
        )}
        {routineMutation.isError && (
          <p className="text-sm text-destructive">
            {routineMutation.error.message}
          </p>
        )}
      </section>
        </>
      )}

      <CaptureBox />

      {/* S5's missing half: the record and the morning's choice were already
          good, and nothing ever asked for the first.

          Above the fields it is asking for, and only when the server says so
          -- the hour is read in the owner's own zone at the request boundary,
          so the client has no time of its own to reason about. Absent on a
          past day (a prompt there asks somebody to reconstruct one, and the
          record is worth reading because it was written while it was still
          true) and absent once the record exists. */}
      {data.closing !== null && (
        <section className="space-y-1 rounded-lg border border-accent px-3 py-2">
          <h2 className="text-sm font-bold">Close the day</h2>
          <p className="text-sm text-muted-foreground">
            {data.closing.chosen > 0 ? (
              <>
                You finished {data.closing.finished} of {data.closing.chosen}
                {data.closing.released > 0 && (
                  <>
                    {", and "}
                    {data.closing.released} you set aside
                  </>
                )}
                .{" "}
              </>
            ) : null}
            What happened today, while it is still true?
          </p>
        </section>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {SECTIONS.map(({ field, label, hint }) => (
          <div key={field} className="space-y-1">
            <label htmlFor={`day-${field}`} className="text-sm font-bold">
              {label}
            </label>
            <textarea
              id={`day-${field}`}
              value={draft[field]}
              onChange={(event) => edit(field, event.target.value)}
              rows={4}
              className="w-full rounded-lg border border-border bg-input px-3 py-2"
            />
            <p className="text-sm text-muted-foreground">{hint}</p>
          </div>
        ))}

        {saveError && <p className="text-sm text-destructive">{saveError}</p>}
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={saveMutation.isPending}>
            Save the day
          </Button>
          {saved && <span className="text-sm text-muted-foreground">Saved.</span>}
        </div>
      </form>
    </div>
  );
}
