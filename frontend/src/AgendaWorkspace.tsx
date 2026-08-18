import { FormEvent, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";

import {
  ageLabel,
  applyFilters,
  bucketFor,
  colorForKey,
  daysBetween,
  dueLabel,
  hasFilters,
  NO_FILTERS,
  snoozePresets,
  sortAgendaTasks,
  summaryCounts,
  tagSummaries,
  type AgendaFilters,
  type SnoozePreset,
} from "./agenda";
import {
  createTask,
  getCookie,
  updateTaskDueDate,
  updateTaskStatus,
} from "./api";
import { apiV1 } from "./api/client";
import type {
  AgendaBucketKey,
  AgendaWorkspaceData,
  Task,
} from "./types";

interface Props {
  initialData: AgendaWorkspaceData;
}

interface Toast {
  id: number;
  message: string;
  undo?: () => void;
}

const RECURRENCE_LABELS: Record<string, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
};

// Signature move (agenda-redesign-plan.md 2): the header's scope counts
// were boxy dashboard-KPI cards, the one place on this page not speaking
// the pill vocabulary every filter/tag/due-date chip already uses
// elsewhere -- including this same row's own chips a few lines down.
function scopePillClass(active: boolean): string {
  const base =
    "inline-flex min-h-11 items-center gap-2 rounded-full border px-4 py-2 text-left transition-colors";
  return active
    ? `${base} border-primary bg-primary/10 text-foreground`
    : `${base} border-border bg-card text-muted-foreground hover:border-foreground/25`;
}

function chipClass(active: boolean): string {
  const base =
    "inline-flex min-h-11 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs";
  return active
    ? `${base} border-primary bg-primary/10 text-foreground`
    : `${base} border-border bg-foreground/[0.03] text-muted-foreground hover:border-foreground/25`;
}

// Row-level tag pills stay dashed -- the same distinction site.css already
// drew between a chip that filters (solid) and one that just labels a row
// and can also be clicked to filter (dashed).
function tagPillClass(active: boolean): string {
  const base = "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs";
  return active
    ? `${base} border-primary text-primary`
    : `${base} border-dashed border-border text-muted-foreground`;
}

function dueDatePillClass(bucket: AgendaBucketKey): string {
  const base = "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs";
  if (bucket === "overdue") return `${base} border-destructive/40 bg-destructive/10 text-destructive`;
  if (bucket === "today") return `${base} border-primary/40 bg-primary/10 text-primary`;
  return `${base} border-border text-foreground`;
}

interface SnoozeMenuProps {
  taskText: string;
  presets: SnoozePreset[];
  disabled: boolean;
  onSelect: (preset: SnoozePreset) => void;
}

/**
 * The one control that sets a task's due date, replacing the old split
 * where a dated row offered "Tomorrow" and an undated one "Schedule".
 *
 * Hand-rolled rather than reaching for a portalled dropdown primitive: the
 * row only reveals its actions on hover/focus-within (see the row's own
 * `group` class below), so a menu portalled to <body> would take focus out
 * of the row and fade its own trigger out from underneath it.
 */
function SnoozeMenu({ taskText, presets, disabled, onSelect }: SnoozeMenuProps) {
  const [open, setOpen] = useState(false);

  return (
    <div
      className="relative"
      onKeyDown={(event) => event.key === "Escape" && setOpen(false)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <button
        className="inline-flex min-h-11 items-center rounded-md border border-border px-3 text-xs whitespace-nowrap text-muted-foreground hover:border-foreground/30 hover:text-foreground"
        type="button"
        disabled={disabled}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Schedule “${taskText}”`}
        onClick={() => setOpen((current) => !current)}
      >
        Schedule
      </button>

      {open && (
        <div
          role="menu"
          className="absolute top-full right-0 z-10 mt-1 flex min-w-36 flex-col rounded-xl bg-popover p-1 text-popover-foreground ring-1 ring-foreground/10"
        >
          {presets.map((preset) => (
            <button
              key={preset.key}
              role="menuitem"
              type="button"
              className="rounded-lg px-2.5 py-1.5 text-left text-sm hover:bg-foreground/5"
              disabled={disabled}
              onClick={() => {
                setOpen(false);
                onSelect(preset);
              }}
            >
              {preset.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function AgendaWorkspace({ initialData }: Props) {
  const { today, areas, projects, buckets } = initialData;

  const [tasks, setTasks] = useState(() =>
    sortAgendaTasks(initialData.items),
  );
  const [completedToday, setCompletedToday] = useState(
    initialData.completed_today,
  );
  const [filters, setFilters] = useState<AgendaFilters>(NO_FILTERS);
  const [collapsed, setCollapsed] = useState<Set<string>>(
    () => new Set(buckets.filter((b) => b.collapsed).map((b) => b.key)),
  );
  const [busyId, setBusyId] = useState<number | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [error, setError] = useState("");

  const [draftText, setDraftText] = useState("");
  const [draftArea, setDraftArea] = useState(() =>
    areas.length ? String(areas[0].id) : "",
  );
  const [draftDue, setDraftDue] = useState("");
  const [adding, setAdding] = useState(false);

  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [draftProject, setDraftProject] = useState("");
  const [projectError, setProjectError] = useState("");
  // project-workspace-plan.md: a Project is API-only (no Django-rendered
  // form to post to, unlike "New area" beside it), so this goes through a
  // mutation and the SPA router rather than a plain POST + reload.
  const createProject = useMutation({
    mutationFn: async (title: string) => {
      const { data, error } = await apiV1.POST("/api/v1/projects", {
        body: { title, due_date: null },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["nav"] });
      navigate(`/projects/${project.id}`);
    },
    onError: () => setProjectError("Couldn't create that project."),
  });

  function handleCreateProject(event: FormEvent) {
    event.preventDefault();
    const title = draftProject.trim();
    if (!title) return;
    setProjectError("");
    createProject.mutate(title);
  }

  const counts = useMemo(() => summaryCounts(tasks, today), [tasks, today]);
  const presets = useMemo(() => snoozePresets(today), [today]);
  const tags = useMemo(() => tagSummaries(tasks), [tasks]);
  const visible = useMemo(
    () => applyFilters(tasks, today, filters),
    [tasks, today, filters],
  );

  const grouped = useMemo(() => {
    const groups = new Map<AgendaBucketKey, Task[]>();
    for (const bucket of buckets) groups.set(bucket.key, []);
    for (const task of visible) {
      groups.get(bucketFor(task.due_date, today))?.push(task);
    }
    return groups;
  }, [visible, buckets, today]);

  const areaCounts = useMemo(() => {
    const open = new Map<number, number>();
    const overdue = new Map<number, number>();
    for (const task of tasks) {
      // An unfiled task counts toward no Area. Skipped rather than bucketed
      // under a placeholder id, so an Area's "3 open" keeps meaning three
      // tasks that are actually in it.
      if (task.area_id === null) continue;
      open.set(task.area_id, (open.get(task.area_id) ?? 0) + 1);
      if (bucketFor(task.due_date, today) === "overdue") {
        overdue.set(task.area_id, (overdue.get(task.area_id) ?? 0) + 1);
      }
    }
    return { open, overdue };
  }, [tasks, today]);

  // Tasks only carry an area_id -- title/url live once in `areas`, so
  // rendering a task's area pill looks them up here instead of the
  // server repeating them on every task.
  const areaById = useMemo(
    () => new Map(areas.map((each) => [each.id, each])),
    [areas],
  );

  // Same join as areaById, for the same reason: ui-second-pass-plan.md F2 --
  // a task only carries project_id, and the title/url live once here rather
  // than repeated on every task.
  const projectById = useMemo(
    () => new Map(projects.map((each) => [each.id, each])),
    [projects],
  );

  function notify(message: string, undo?: () => void) {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current, { id, message, undo }]);
    window.setTimeout(
      () => setToasts((current) => current.filter((t) => t.id !== id)),
      undo ? 8000 : 4000,
    );
  }

  function dismissToast(id: number) {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }

  function replaceTask(updated: Task) {
    setTasks((current) =>
      sortAgendaTasks(
        current.map((task) => (task.id === updated.id ? updated : task)),
      ),
    );
  }

  async function run<T>(
    taskId: number,
    action: () => Promise<T>,
  ): Promise<T | undefined> {
    setBusyId(taskId);
    setError("");
    try {
      return await action();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Something went wrong. Please try again.",
      );
      return undefined;
    } finally {
      setBusyId(null);
    }
  }

  async function complete(task: Task) {
    const result = await run(task.id, () =>
      updateTaskStatus(task, "completed"),
    );
    if (!result) return;

    setTasks((current) => {
      const remaining = current.filter((each) => each.id !== task.id);
      // A recurring task archives itself and returns its next occurrence in
      // the same response, which goes in before the re-bucket so it lands
      // in whichever bucket its own due date puts it.
      return sortAgendaTasks(
        result.spawned ? [...remaining, result.spawned] : remaining,
      );
    });

    // The task only rests here when it isn't recurring -- a recurring one
    // archived itself and left the day entirely.
    if (!result.spawned) {
      setCompletedToday((current) => [result.task, ...current]);
    }

    if (result.spawned) {
      const next = result.spawned;
      notify(
        next.due_date
          ? `Done. Next one due ${dueLabel(next.due_date, today)}.`
          : "Done. Next occurrence added.",
      );
      return;
    }

    notify(`Completed “${task.text}”`, () => reopen(result.task, true));
  }

  async function reopen(task: Task, silent = false) {
    const result = await run(task.id, () => updateTaskStatus(task, "active"));
    if (!result) return;
    setCompletedToday((current) =>
      current.filter((each) => each.id !== task.id),
    );
    setTasks((current) => sortAgendaTasks([...current, result.task]));
    if (!silent) notify(`Reopened “${task.text}”`);
  }

  async function reschedule(task: Task, dueDate: string | null, label: string) {
    const previous = task.due_date;
    const updated = await run(task.id, () => updateTaskDueDate(task, dueDate));
    if (!updated) return;
    replaceTask(updated);
    notify(label, () => {
      void run(task.id, () => updateTaskDueDate(updated, previous)).then(
        (reverted) => reverted && replaceTask(reverted),
      );
    });
  }

  function snooze(task: Task, preset: SnoozePreset) {
    void reschedule(
      task,
      preset.dueDate,
      preset.dueDate === null
        ? `Cleared the due date on “${task.text}”`
        : `Moved “${task.text}” to ${preset.label.toLowerCase()}`,
    );
  }

  async function submitQuickAdd(event: FormEvent) {
    event.preventDefault();
    const text = draftText.trim();
    const target = areas.find((each) => String(each.id) === draftArea);
    if (!text || !target) return;

    setAdding(true);
    setError("");
    try {
      const created = await createTask(
        target.create_item_url,
        text,
        draftDue || null,
      );
      setTasks((current) => sortAgendaTasks([...current, created]));
      setDraftText("");
      setDraftDue("");
      notify(`Added “${created.text}” to ${target.title}`);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to add that task.",
      );
    } finally {
      setAdding(false);
    }
  }

  function toggleBucket(key: string) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function toggleScope(scope: string) {
    setFilters((current) => ({
      ...current,
      scope: current.scope === scope ? null : scope,
    }));
  }

  function toggleArea(id: number) {
    setFilters((current) => ({
      ...current,
      area: current.area === id ? null : id,
    }));
  }

  function toggleTag(name: string) {
    setFilters((current) => ({
      ...current,
      tag: current.tag === name ? null : name,
    }));
  }

  function setQuery(query: string) {
    setFilters((current) => ({ ...current, query }));
  }

  function renderRow(task: Task, done = false) {
    const bucket = bucketFor(task.due_date, today);
    const taskArea = task.area_id ? areaById.get(task.area_id) : undefined;
    const taskProject = task.project_id ? projectById.get(task.project_id) : undefined;
    const age = !done ? ageLabel(daysBetween(task.created_at.slice(0, 10), today)) : null;

    return (
      <article
        key={task.id}
        className={[
          "group relative flex items-start gap-3 rounded-xl border border-l-4 border-border bg-card px-3 py-3",
          !done && bucket === "overdue" ? "border-l-destructive" : "border-l-transparent",
          busyId === task.id ? "opacity-60" : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        <button
          type="button"
          className="-ml-2 flex h-11 w-11 flex-none items-center justify-center rounded-lg"
          onClick={() => (done ? reopen(task) : complete(task))}
          disabled={busyId === task.id}
          aria-label={done ? `Reopen “${task.text}”` : `Complete “${task.text}”`}
        >
          <span
            aria-hidden="true"
            className={[
              "grid h-5 w-5 place-items-center rounded-md border text-xs font-bold",
              done
                ? "border-primary bg-primary text-primary-foreground"
                : "border-foreground/30 text-transparent",
            ].join(" ")}
          >
            ✓
          </span>
        </button>

        <div className="min-w-0 flex-1 pt-0.5">
          <span
            className={`block text-sm leading-snug break-words ${
              done ? "text-muted-foreground line-through decoration-primary" : "text-foreground"
            }`}
          >
            {task.text}
          </span>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            {taskArea && (
              <a
                className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-foreground"
                href={taskArea.url}
              >
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  aria-hidden="true"
                  style={{ background: colorForKey(taskArea.color_key) }}
                />
                {taskArea.title}
              </a>
            )}

            {taskProject && (
              <a
                className="rounded-full border border-border px-2.5 py-1 text-foreground"
                href={taskProject.url}
              >
                {taskProject.title}
              </a>
            )}

            {/* Client-side because it's a display rule rather than a
                domain one -- agenda.ts's own ageLabel doc comment says so.
                today is server-supplied (AgendaWorkspaceData.today), so
                this needs no browser-clock read of its own. */}
            {age && <span>{age}</span>}

            {task.due_date && (
              <span className={dueDatePillClass(bucket)}>{dueLabel(task.due_date, today)}</span>
            )}

            {task.recurrence !== "none" && (
              <span
                className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1"
                style={{ color: "var(--color-status-today)", borderColor: "color-mix(in oklch, var(--color-status-today) 35%, transparent)" }}
              >
                ⟳ {RECURRENCE_LABELS[task.recurrence] ?? task.recurrence}
              </span>
            )}

            {/* Deliberately a marker, not a preview: the row says notes
                exist and the detail view says what they are. */}
            {task.notes !== "" && (
              <span aria-label="Has notes" title="Has notes">
                ✎
              </span>
            )}

            {task.tags.map((tag) => (
              <button
                type="button"
                key={tag}
                className={tagPillClass(filters.tag === tag)}
                onClick={() => toggleTag(tag)}
                aria-pressed={filters.tag === tag}
              >
                #{tag}
              </button>
            ))}
          </div>
        </div>

        {!done && (
          <div className="flex flex-none items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 [@media(hover:none)]:opacity-100">
            {/* Clearing a date a task hasn't got would do nothing, so
                that one option comes and goes with the due date. */}
            <SnoozeMenu
              taskText={task.text}
              presets={presets.filter(
                (preset) => task.due_date || preset.dueDate !== null,
              )}
              disabled={busyId === task.id}
              onSelect={(preset) => snooze(task, preset)}
            />
            <a
              className="inline-flex min-h-11 items-center rounded-md border border-border px-3 text-xs whitespace-nowrap text-muted-foreground hover:border-foreground/30 hover:text-foreground"
              href={task.edit_url}
            >
              Edit
            </a>
          </div>
        )}
      </article>
    );
  }

  const filtering = hasFilters(filters);
  const activeArea = areas.find((each) => each.id === filters.area);

  return (
    <>
      <header className="mb-7">
        <p className="mb-2 text-xs font-extrabold tracking-[0.14em] text-primary uppercase">
          {new Intl.DateTimeFormat(undefined, {
            weekday: "long",
            day: "numeric",
            month: "long",
            timeZone: "UTC",
          }).format(new Date(`${today}T00:00:00Z`))}
        </p>
        <h1 className="mb-4 text-3xl font-bold tracking-tight sm:text-4xl">
          Hello, {initialData.username}.
        </h1>

        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by when a task is due">
          <button
            type="button"
            className={scopePillClass(filters.scope === "overdue")}
            aria-label="Show only overdue tasks"
            aria-pressed={filters.scope === "overdue"}
            onClick={() => toggleScope("overdue")}
          >
            <span className="text-lg font-extrabold tabular-nums text-destructive">
              {counts.overdue}
            </span>
            <span>Overdue</span>
          </button>
          <button
            type="button"
            className={scopePillClass(filters.scope === "today")}
            aria-label="Show only tasks due today"
            aria-pressed={filters.scope === "today"}
            onClick={() => toggleScope("today")}
          >
            <span className="text-lg font-extrabold tabular-nums text-primary">
              {counts.today}
            </span>
            <span>Today</span>
          </button>
          <button
            type="button"
            className={scopePillClass(filters.scope === "week")}
            aria-label="Show only tasks due this week"
            aria-pressed={filters.scope === "week"}
            onClick={() => toggleScope("week")}
          >
            <span className="text-lg font-extrabold tabular-nums text-foreground">
              {counts.week}
            </span>
            <span>This week</span>
          </button>
          <button
            type="button"
            className={scopePillClass(false)}
            aria-label="Show all open tasks"
            aria-pressed={false}
            onClick={() => setFilters(NO_FILTERS)}
          >
            <span className="text-lg font-extrabold tabular-nums text-foreground">
              {counts.open}
            </span>
            <span>Open</span>
          </button>
        </div>
      </header>

      <form
        className="mb-4 flex flex-wrap items-center gap-2 rounded-2xl border border-border bg-card px-3 py-2.5"
        onSubmit={submitQuickAdd}
      >
        <label className="sr-only" htmlFor="agenda-add-text">
          Task
        </label>
        <input
          id="agenda-add-text"
          className="min-w-40 flex-1 border-0 bg-transparent px-1 py-2 text-sm text-foreground outline-none placeholder:text-muted-foreground"
          type="text"
          placeholder="Add a task…"
          value={draftText}
          onChange={(event) => setDraftText(event.target.value)}
          autoComplete="off"
        />
        <label className="sr-only" htmlFor="agenda-add-area">
          Area
        </label>
        <span className="inline-flex h-11 items-center rounded-lg border border-border bg-foreground/[0.03] px-2.5 text-xs text-muted-foreground">
          <select
            id="agenda-add-area"
            className="border-0 bg-transparent text-inherit outline-none"
            value={draftArea}
            onChange={(event) => setDraftArea(event.target.value)}
          >
            {areas.map((each) => (
              <option key={each.id} value={each.id}>
                {each.title}
              </option>
            ))}
          </select>
        </span>
        <label className="sr-only" htmlFor="agenda-add-due">
          Due date
        </label>
        <span className="inline-flex h-11 items-center rounded-lg border border-border bg-foreground/[0.03] px-2.5 text-xs text-muted-foreground">
          <input
            id="agenda-add-due"
            type="date"
            className="border-0 bg-transparent text-inherit outline-none"
            value={draftDue}
            onChange={(event) => setDraftDue(event.target.value)}
          />
        </span>
        {/* Button's own size variants top out at h-9 (36px), short of the
            ~44px guideline this redesign otherwise enforces via plain
            Tailwind classes -- needs an explicit override. */}
        <Button
          type="submit"
          size="sm"
          className="h-11"
          disabled={adding || !draftText.trim() || areas.length === 0}
        >
          {adding ? "Adding…" : "Add"}
        </Button>
      </form>

      {/* Unified filter row -- agenda-redesign-plan.md 3. Area chips used
          to live here alone (the side nav now navigates instead of
          filtering, so the filter had to exist somewhere) while tags lived
          in a separate sidebar card: two surfaces, two shapes, for the same
          job of narrowing what's showing. Search sits beside it -- still
          "narrow what's showing," it just takes typed text instead of a
          click. */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {areas.length > 1 &&
            areas.map((each) => {
              const overdue = areaCounts.overdue.get(each.id) ?? 0;
              return (
                <button
                  key={each.id}
                  type="button"
                  className={chipClass(filters.area === each.id)}
                  aria-pressed={filters.area === each.id}
                  aria-label={`Show only ${each.title}`}
                  onClick={() => toggleArea(each.id)}
                >
                  <span
                    className="h-2 w-2 rounded-full"
                    aria-hidden="true"
                    style={{ background: colorForKey(each.color_key) }}
                  />
                  {each.title}
                  <span className={overdue ? "text-destructive" : "opacity-70"}>
                    {overdue ? `⚠ ${overdue} · ` : ""}
                    {areaCounts.open.get(each.id) ?? 0}
                  </span>
                </button>
              );
            })}
          {tags.map((tag) => (
            <button
              type="button"
              key={tag.name}
              className={chipClass(filters.tag === tag.name)}
              aria-pressed={filters.tag === tag.name}
              onClick={() => toggleTag(tag.name)}
            >
              #{tag.name} <span className="opacity-70">{tag.count}</span>
            </button>
          ))}
        </div>

        <label className="flex h-11 w-full max-w-[15rem] shrink-0 items-center gap-1.5 rounded-full border border-border px-3.5 text-sm text-muted-foreground focus-within:border-primary">
          <span className="sr-only">Search your agenda</span>
          <span aria-hidden="true">⌕</span>
          <input
            id="agenda-search"
            type="search"
            className="w-full border-0 bg-transparent text-foreground outline-none placeholder:text-muted-foreground"
            placeholder="Search your agenda…"
            value={filters.query}
            onChange={(event) => setQuery(event.target.value)}
            autoComplete="off"
          />
        </label>
      </div>

      <div aria-live="polite" className="min-h-6 text-sm">
        {error && <p className="text-destructive">{error}</p>}
      </div>

      {filtering && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-primary/30 bg-primary/[0.06] px-3.5 py-2 text-sm text-muted-foreground">
          <span>
            Showing{" "}
            {[
              filters.scope,
              activeArea?.title,
              filters.tag ? `#${filters.tag}` : null,
              filters.query.trim() ? `“${filters.query.trim()}”` : null,
            ]
              .filter(Boolean)
              .join(" · ")}{" "}
            — {visible.length} task{visible.length === 1 ? "" : "s"}
          </span>
          <button
            className="ml-auto inline-flex min-h-11 items-center rounded-md border border-border px-3 text-xs text-muted-foreground hover:border-foreground/30 hover:text-foreground"
            type="button"
            onClick={() => setFilters(NO_FILTERS)}
          >
            Clear
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-[minmax(0,1fr)_18.5rem]">
        <div>
          {visible.length === 0 && (
            <div className="rounded-lg border border-border bg-card px-6 py-10 text-center">
              {filtering ? (
                <>
                  <h3 className="text-base font-bold">Nothing matches that filter.</h3>
                  <p className="mt-2">
                    <button
                      className="inline-flex min-h-11 items-center rounded-md border border-border px-3 text-xs text-muted-foreground hover:border-foreground/30 hover:text-foreground"
                      type="button"
                      onClick={() => setFilters(NO_FILTERS)}
                    >
                      Show the whole agenda
                    </button>
                  </p>
                </>
              ) : areas.length === 0 ? (
                <>
                  <h3 className="text-base font-bold">Start your first area.</h3>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Create one on the right, then add tasks to it.
                  </p>
                </>
              ) : (
                <>
                  <h3 className="text-base font-bold">You're all caught up.</h3>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Add something above when it comes up.
                  </p>
                </>
              )}
            </div>
          )}

          {buckets.map((bucket) => {
            const items = grouped.get(bucket.key) ?? [];
            if (items.length === 0) return null;
            const isCollapsed = collapsed.has(bucket.key);
            return (
              <section className="mb-6" key={bucket.key}>
                <button
                  type="button"
                  className="mb-3 flex min-h-11 w-full items-center gap-2 border-b border-border py-2 text-left"
                  onClick={() => toggleBucket(bucket.key)}
                  aria-expanded={!isCollapsed}
                >
                  <h2
                    className={`text-xs font-extrabold tracking-[0.14em] uppercase ${
                      bucket.key === "overdue"
                        ? "text-destructive"
                        : bucket.key === "today"
                          ? "text-primary"
                          : "text-muted-foreground"
                    }`}
                  >
                    {bucket.label}
                  </h2>
                  <span className="text-xs tabular-nums text-muted-foreground">
                    {items.length}
                  </span>
                  <span
                    aria-hidden="true"
                    className={`ml-auto text-[0.65rem] text-muted-foreground transition-transform ${
                      isCollapsed ? "-rotate-90" : ""
                    }`}
                  >
                    ▼
                  </span>
                </button>
                <div className={`space-y-2 ${isCollapsed ? "hidden" : ""}`}>
                  {items.map((task) => renderRow(task))}
                </div>
              </section>
            );
          })}

          {completedToday.length > 0 && (
            <section className="mb-6">
              <button
                type="button"
                className="mb-3 flex min-h-11 w-full items-center gap-2 border-b border-border py-2 text-left"
                onClick={() => toggleBucket("completed")}
                aria-expanded={!collapsed.has("completed")}
              >
                <h2 className="text-xs font-extrabold tracking-[0.14em] text-muted-foreground uppercase">
                  Completed today
                </h2>
                <span className="text-xs tabular-nums text-muted-foreground">
                  {completedToday.length}
                </span>
                <span
                  aria-hidden="true"
                  className={`ml-auto text-[0.65rem] text-muted-foreground transition-transform ${
                    collapsed.has("completed") ? "-rotate-90" : ""
                  }`}
                >
                  ▼
                </span>
              </button>
              <div className={`space-y-2 ${collapsed.has("completed") ? "hidden" : ""}`}>
                {completedToday.map((task) => renderRow(task, true))}
              </div>
            </section>
          )}
        </div>

        <aside className="flex flex-col gap-4">
          <div className="rounded-xl border border-border bg-card p-4">
            {/* Areas moved to the persistent side nav, which navigates
                rather than filters (see design/side-nav-mockup.html). The
                "filter the agenda to one area" job it used to do is now a
                chip in the unified filter row, so this card keeps only
                what is neither navigation nor filtering. */}
            <h3 className="mb-3 text-xs font-extrabold tracking-[0.14em] text-muted-foreground uppercase">
              New area
            </h3>
            <details>
              <summary className="flex min-h-11 cursor-pointer items-center text-sm font-semibold text-primary">
                + New area
              </summary>
              {/* A plain Django POST: creating an area navigates to the new
                  area anyway, so there's nothing for the SPA layer to do. */}
              <form
                className="mt-2 grid gap-2"
                method="post"
                action={initialData.new_area_url}
              >
                <input
                  type="hidden"
                  name="csrfmiddlewaretoken"
                  value={getCookie("csrftoken")}
                />
                <label className="sr-only" htmlFor="agenda-new-title">
                  Area name
                </label>
                <input
                  id="agenda-new-title"
                  className="min-h-11 rounded-lg border border-border bg-input px-2.5 text-sm text-foreground outline-none"
                  name="title"
                  placeholder="Area name"
                  maxLength={100}
                />
                <label className="sr-only" htmlFor="agenda-new-text">
                  First task
                </label>
                <input
                  id="agenda-new-text"
                  className="min-h-11 rounded-lg border border-border bg-input px-2.5 text-sm text-foreground outline-none"
                  name="text"
                  placeholder="First task"
                  required
                />
                <Button type="submit" size="sm" className="h-11">
                  Create area
                </Button>
              </form>
            </details>
          </div>

          {/* project-workspace-plan.md: a Project's own creation entry
              point, the sibling of "New area" above -- a standalone
              workspace now rather than something built from inside an
              Area. */}
          <div className="rounded-xl border border-border bg-card p-4">
            <h3 className="mb-3 text-xs font-extrabold tracking-[0.14em] text-muted-foreground uppercase">
              New project
            </h3>
            <details>
              <summary className="flex min-h-11 cursor-pointer items-center text-sm font-semibold text-primary">
                + New project
              </summary>
              <form className="mt-2 grid gap-2" onSubmit={handleCreateProject}>
                <label className="sr-only" htmlFor="agenda-new-project">
                  Project name
                </label>
                <input
                  id="agenda-new-project"
                  className="min-h-11 rounded-lg border border-border bg-input px-2.5 text-sm text-foreground outline-none"
                  value={draftProject}
                  onChange={(event) => setDraftProject(event.target.value)}
                  placeholder="Project name"
                  maxLength={100}
                  required
                />
                <Button
                  type="submit"
                  size="sm"
                  className="h-11"
                  disabled={createProject.isPending}
                >
                  Create project
                </Button>
              </form>
              {projectError && <p className="text-sm text-destructive">{projectError}</p>}
            </details>
          </div>

          {/* A direct entry point from the main page itself, not just the
              persistent side nav, which could fail to render. The reason
              survived Heron; the destination did not.

              This used to link to /capture/ and /capture/ideas/. 4b deleted
              the Inbox and the Ideas shelf, and clarice/urls.py deliberately
              did not take the freed prefix -- so both were plain Django 404s,
              outside the SPA shell, with nothing but the browser button to get
              back. SideNav.tsx dropped the same two and this duplicate was
              missed, which nothing caught because no test looked at this block.

              A Django page, not an SPA route, so a plain anchor: React Router
              would try to handle /mind/ and 404 inside the shell. Hardcoded
              rather than read from the payload, unlike SideNav's -- AgendaOut
              carries no mind_url, and inventing one for a single link would be
              a schema change to avoid a constant that Heron step 5 made
              permanent. */}
          <div className="rounded-xl border border-border bg-card p-4">
            <h3 className="mb-3 text-xs font-extrabold tracking-[0.14em] text-muted-foreground uppercase">
              Capture
            </h3>
            <a
              className="flex min-h-11 items-center text-sm text-foreground hover:text-primary"
              href="/mind/"
            >
              Second Mind →
            </a>
          </div>

          <div className="rounded-xl border border-border bg-card p-4">
            <h3 className="mb-3 text-xs font-extrabold tracking-[0.14em] text-muted-foreground uppercase">
              Daily reminder
            </h3>
            <p className="mb-2 text-sm text-muted-foreground">
              {initialData.daily_digest
                ? "A summary of anything overdue or due today is emailed to you each morning."
                : "Daily reminder emails are switched off."}
            </p>
            <a
              className="flex min-h-11 items-center text-sm text-foreground hover:text-primary"
              href={initialData.settings_url}
            >
              Change this in settings →
            </a>
          </div>

          <div className="rounded-xl border border-border bg-card p-4">
            <a
              className="flex min-h-11 items-center gap-2 text-sm text-foreground hover:text-primary"
              href={initialData.archive_url}
            >
              <span>Archive</span>
              <span className="ml-auto text-xs text-muted-foreground">
                {initialData.archived_count} task
                {initialData.archived_count === 1 ? "" : "s"}
              </span>
            </a>
          </div>
        </aside>
      </div>

      <div
        className="fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 flex-col items-center gap-2"
        aria-live="polite"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="flex items-center gap-3 rounded-lg border border-border bg-popover px-4 py-2 text-sm text-popover-foreground shadow-lg"
          >
            <span>{toast.message}</span>
            {toast.undo && (
              <button
                className="inline-flex min-h-11 items-center rounded-md border border-border px-3 text-xs text-muted-foreground hover:border-foreground/30 hover:text-foreground"
                type="button"
                onClick={() => {
                  toast.undo?.();
                  dismissToast(toast.id);
                }}
              >
                Undo
              </button>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
