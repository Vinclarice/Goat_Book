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

/**
 * The agenda's rows, displayed rather than owned.
 *
 * Read-only on purpose. Slice 2's acceptance is that completing a task the
 * ordinary way shows up here on the next load; a Complete button would mean
 * reimplementing the agenda's mutation and undo beside it, and crane-plan
 * §5 is explicit that the Daily Page is new surface rather than a place to
 * restructure what it embeds.
 */
function ActionItems({ items, today }: { items: ActionItem[]; today: string }) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nothing due today. Anything you add with today&rsquo;s date shows up here.
      </p>
    );
  }
  return (
    <ul className="space-y-1">
      {items.map((item) => (
        <li
          key={item.id}
          className="flex items-baseline justify-between gap-3 rounded-lg border border-border px-3 py-2"
        >
          <span className="min-w-0">
            {/* The breadcrumb the agenda shows too, so a subtask row is not
                a floating fragment of a task nobody can place. */}
            {item.parent && (
              <span className="text-sm text-muted-foreground">
                {item.parent.text} /{" "}
              </span>
            )}
            <a href={`/app/tasks/${item.id}`} className="hover:underline">
              {item.text}
            </a>
          </span>
          {item.due_date && (
            <span className="shrink-0 text-sm text-muted-foreground">
              {/* agenda.ts's own label, not a second date format invented
                  here -- "3 days overdue" has to read the same on both
                  pages or one of them is lying. */}
              {dueLabel(item.due_date, today)}
            </span>
          )}
        </li>
      ))}
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

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-8">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-accent">
          {isToday ? "Today" : "Your day"}
        </p>
        <h1 className="text-2xl font-bold">{longDate(data.date)}</h1>
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-bold">Action items</h2>
        {data.shows_action_items ? (
          <ActionItems items={data.action_items} today={data.today} />
        ) : (
          // Said plainly rather than shown as an empty list: a task holds no
          // record of what it looked like on a past date, so this page can
          // show what was written and honestly nothing else.
          <p className="text-sm text-muted-foreground">
            Only today shows action items. What you wrote on this day is below.
          </p>
        )}
      </section>

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
