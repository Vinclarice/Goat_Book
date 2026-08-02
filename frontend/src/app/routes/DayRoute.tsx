import { FormEvent, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router";

import { Button } from "@/components/ui/button";

import { dueLabel } from "../../agenda";
import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
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

type ActionItem = {
  id: number;
  text: string;
  due_date: string | null;
  parent: { id: number; text: string } | null;
};

type Focus = {
  task_id: number | null;
  text: string;
  status: string | null;
  due_date: string | null;
  parent: { id: number; text: string } | null;
};

/** A task's breadcrumb, so a subtask row is not a fragment nobody can place. */
function Breadcrumb({ parent }: { parent: { text: string } | null }) {
  if (!parent) return null;
  return (
    <span className="text-sm text-muted-foreground">{parent.text} / </span>
  );
}

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
  busy,
}: {
  focus: Focus[];
  today: string;
  onUnpin: (taskId: number) => void;
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
            <Breadcrumb parent={item.parent} />
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
            {/* A deleted task leaves the record but nothing to unpin. */}
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
  pinnedIds,
  onPin,
  onUnpin,
  busy,
}: {
  items: ActionItem[];
  today: string;
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
  return (
    <ul className="space-y-1">
      {items.map((item) => {
        const pinned = pinnedIds.has(item.id);
        return (
          <li
            key={item.id}
            className="flex items-baseline justify-between gap-3 rounded-lg border border-border px-3 py-2"
          >
            <span className="min-w-0">
              {/* The breadcrumb the agenda shows too, so a subtask row is not
                  a floating fragment of a task nobody can place. */}
              <Breadcrumb parent={item.parent} />
              <a href={`/app/tasks/${item.id}`} className="hover:underline">
                {item.text}
              </a>
              {/* A pinned task stays in the agenda below -- the focus list is
                  above it, not carved out of it -- so the row says which it
                  is rather than leaving two identical-looking entries. */}
              {pinned && (
                <span className="ml-2 text-sm text-accent">Pinned</span>
              )}
            </span>
            <span className="flex shrink-0 items-baseline gap-3">
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

/**
 * Rapid logging, on the page you are already looking at.
 *
 * Posts to the capture endpoint the Inbox and the Android client already
 * use, so the row it writes is the same row -- no daily-shaped capture, no
 * second definition of what an empty capture is. See
 * capture/tests/test_capture_paths_agree.py.
 *
 * Deliberately not part of the day's own form. What you capture is a
 * thought going to the Inbox to be triaged later; what you write below is
 * this day's record. Merging them into one save button is precisely the
 * kind of near-identical-controls-with-opposite-meanings confusion C2
 * found in the task UI, and this page is new surface with no excuse for it.
 */
function CaptureBox() {
  const [text, setText] = useState("");
  const [captured, setCaptured] = useState(false);

  const mutation = useMutation({
    mutationFn: async (thought: string) => {
      const { error } = await apiV1.POST("/api/v1/capture", {
        body: { text: thought },
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
        {/* Says where it went. Without this the thought appears to vanish,
            and the next one gets typed into Intentions instead. */}
        {captured && (
          <span className="text-sm text-muted-foreground">
            Sent to your Inbox.
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
      </div>

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
            className="inline-block text-sm text-muted-foreground hover:text-foreground"
          >
            Edit your compass
          </a>
        </section>
      )}

      <section className="space-y-2">
        <h2 className="text-sm font-bold">Focus</h2>
        <FocusList
          focus={data.focus}
          today={data.today}
          onUnpin={(taskId) => focusMutation.mutate({ taskId, pin: false })}
          busy={focusMutation.isPending}
        />
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

      <CaptureBox />

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
