import { FormEvent, useMemo, useState } from "react";

import {
  applyFilters,
  bucketFor,
  colorForKey,
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
 * Hand-rolled rather than reaching for a portalled dropdown primitive:
 * site.css only reveals .agenda-actions on .agenda-row:hover or
 * :focus-within, so a menu portalled to <body> would take focus out of
 * the row and fade its own trigger out from underneath it.
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
        className="btn btn-outline-light btn-sm"
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

  function renderRow(task: Task, done = false) {
    const bucket = bucketFor(task.due_date, today);
    const taskArea = areaById.get(task.area_id);
    const taskProject = task.project_id ? projectById.get(task.project_id) : undefined;
    const rowClass = [
      "agenda-row",
      done ? "is-done" : bucket === "overdue" ? "is-overdue" : "",
      !done && bucket === "today" ? "is-today" : "",
      busyId === task.id ? "is-busy" : "",
    ]
      .filter(Boolean)
      .join(" ");

    return (
      <div className={rowClass} key={task.id}>
        <button
          type="button"
          className={`agenda-checkbox${done ? " is-checked" : ""}`}
          onClick={() => (done ? reopen(task) : complete(task))}
          disabled={busyId === task.id}
          aria-label={
            done ? `Reopen “${task.text}”` : `Complete “${task.text}”`
          }
        >
          <span aria-hidden="true">✓</span>
        </button>

        <div className="agenda-body">
          <span className="agenda-text">{task.text}</span>
          <div className="agenda-meta">
            {taskArea && (
              <a className="pill pill-list" href={taskArea.url}>
                <span
                  className="dot"
                  aria-hidden="true"
                  style={{ background: colorForKey(taskArea.color_key) }}
                />
                {taskArea.title}
              </a>
            )}

            {taskProject && (
              <a className="pill pill-project" href={taskProject.url}>
                {taskProject.title}
              </a>
            )}

            {task.due_date && (
              <span
                className={`pill pill-due${
                  bucket === "overdue"
                    ? " overdue"
                    : bucket === "today"
                      ? " today"
                      : ""
                }`}
              >
                {dueLabel(task.due_date, today)}
              </span>
            )}

            {task.recurrence !== "none" && (
              <span className="pill pill-recur">
                ⟳ {RECURRENCE_LABELS[task.recurrence] ?? task.recurrence}
              </span>
            )}

            {/* Deliberately a marker, not a preview: the row says notes
                exist and the detail view says what they are. */}
            {task.notes !== "" && (
              <span className="pill" title="Has notes" aria-label="Has notes">
                ✎
              </span>
            )}

            {task.tags.map((tag) => (
              <button
                type="button"
                key={tag}
                className={`pill pill-tag${
                  filters.tag === tag ? " is-active" : ""
                }`}
                onClick={() => toggleTag(tag)}
                aria-pressed={filters.tag === tag}
              >
                #{tag}
              </button>
            ))}
          </div>
        </div>

        {!done && (
          <div className="agenda-actions">
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
            <a className="btn btn-outline-light btn-sm" href={task.edit_url}>
              Edit
            </a>
          </div>
        )}
      </div>
    );
  }

  const filtering = hasFilters(filters);
  const activeArea = areas.find((each) => each.id === filters.area);

  return (
    <>
      <header className="agenda-header">
        <div>
          <p className="eyebrow">
            {new Intl.DateTimeFormat(undefined, {
              weekday: "long",
              day: "numeric",
              month: "long",
              timeZone: "UTC",
            }).format(new Date(`${today}T00:00:00Z`))}
          </p>
          <h1>Hello, {initialData.username}.</h1>
        </div>

        <div className="header-stats">
          <button
            type="button"
            className="stat is-danger"
            aria-label="Show only overdue tasks"
            aria-pressed={filters.scope === "overdue"}
            onClick={() => toggleScope("overdue")}
          >
            <span className="stat-num">{counts.overdue}</span>
            <span className="stat-label">Overdue</span>
          </button>
          <button
            type="button"
            className="stat is-accent"
            aria-label="Show only tasks due today"
            aria-pressed={filters.scope === "today"}
            onClick={() => toggleScope("today")}
          >
            <span className="stat-num">{counts.today}</span>
            <span className="stat-label">Today</span>
          </button>
          <button
            type="button"
            className="stat"
            aria-label="Show only tasks due this week"
            aria-pressed={filters.scope === "week"}
            onClick={() => toggleScope("week")}
          >
            <span className="stat-num">{counts.week}</span>
            <span className="stat-label">This week</span>
          </button>
          <button
            type="button"
            className="stat"
            aria-label="Show all open tasks"
            aria-pressed={false}
            onClick={() => setFilters(NO_FILTERS)}
          >
            <span className="stat-num">{counts.open}</span>
            <span className="stat-label">Open</span>
          </button>
        </div>
      </header>

      {/* Area filtering used to live in the sidebar, where clicking an area
          filtered rather than navigated. The side nav now navigates, so the
          filter has to exist somewhere -- as chips, here, alongside the
          scope filters it belongs with. */}
      {areas.length > 1 && (
        <div className="agenda-list-chips">
          {areas.map((each) => {
            const overdue = areaCounts.overdue.get(each.id) ?? 0;
            return (
              <button
                key={each.id}
                type="button"
                className={`tag-chip${filters.area === each.id ? " is-active" : ""}`}
                aria-pressed={filters.area === each.id}
                aria-label={`Show only ${each.title}`}
                onClick={() => toggleArea(each.id)}
              >
                <span
                  className="dot"
                  aria-hidden="true"
                  style={{ background: colorForKey(each.color_key) }}
                />
                {each.title}
                <span className={overdue ? "n warn" : "n"}>
                  {areaCounts.open.get(each.id) ?? 0}
                </span>
              </button>
            );
          })}
        </div>
      )}

      <form className="quick-add" onSubmit={submitQuickAdd}>
        <label className="visually-hidden" htmlFor="agenda-add-text">
          Task
        </label>
        <input
          id="agenda-add-text"
          className="quick-add-text"
          type="text"
          placeholder="Add a task…"
          value={draftText}
          onChange={(event) => setDraftText(event.target.value)}
          autoComplete="off"
        />
        <label className="visually-hidden" htmlFor="agenda-add-area">
          Area
        </label>
        <select
          id="agenda-add-area"
          className="quick-add-select"
          value={draftArea}
          onChange={(event) => setDraftArea(event.target.value)}
        >
          {areas.map((each) => (
            <option key={each.id} value={each.id}>
              {each.title}
            </option>
          ))}
        </select>
        <label className="visually-hidden" htmlFor="agenda-add-due">
          Due date
        </label>
        <input
          id="agenda-add-due"
          className="quick-add-date"
          type="date"
          value={draftDue}
          onChange={(event) => setDraftDue(event.target.value)}
        />
        <button
          className="btn btn-primary"
          type="submit"
          disabled={adding || !draftText.trim() || areas.length === 0}
        >
          {adding ? "Adding…" : "Add"}
        </button>
      </form>

      <div aria-live="polite">
        {error && <p className="agenda-form-error">{error}</p>}
      </div>

      {filtering && (
        <div className="filter-banner">
          <span>
            Showing{" "}
            {[
              filters.scope,
              activeArea?.title,
              filters.tag ? `#${filters.tag}` : null,
            ]
              .filter(Boolean)
              .join(" · ")}{" "}
            — {visible.length} task{visible.length === 1 ? "" : "s"}
          </span>
          <button
            className="btn btn-outline-light btn-sm"
            type="button"
            onClick={() => setFilters(NO_FILTERS)}
          >
            Clear
          </button>
        </div>
      )}

      <div className="agenda-grid">
        <div>
          {visible.length === 0 && (
            <div className="all-clear">
              {filtering ? (
                <>
                  <h3>Nothing matches that filter.</h3>
                  <p>
                    <button
                      className="btn btn-outline-light btn-sm"
                      type="button"
                      onClick={() => setFilters(NO_FILTERS)}
                    >
                      Show the whole agenda
                    </button>
                  </p>
                </>
              ) : areas.length === 0 ? (
                <>
                  <h3>Start your first area.</h3>
                  <p>Create one on the right, then add tasks to it.</p>
                </>
              ) : (
                <>
                  <h3>You're all caught up.</h3>
                  <p>Add something above when it comes up.</p>
                </>
              )}
            </div>
          )}

          {buckets.map((bucket) => {
            const items = grouped.get(bucket.key) ?? [];
            if (items.length === 0) return null;
            const isCollapsed = collapsed.has(bucket.key);
            return (
              <section
                className={`agenda-section ${bucket.key}${
                  isCollapsed ? " is-collapsed" : ""
                }`}
                key={bucket.key}
              >
                <button
                  type="button"
                  className="section-head"
                  onClick={() => toggleBucket(bucket.key)}
                  aria-expanded={!isCollapsed}
                >
                  <h2>{bucket.label}</h2>
                  <span className="count">{items.length}</span>
                  <span className="chev" aria-hidden="true">
                    ▼
                  </span>
                </button>
                <div className="section-body">
                  {items.map((task) => renderRow(task))}
                </div>
              </section>
            );
          })}

          {completedToday.length > 0 && (
            <section
              className={`agenda-section completed${
                collapsed.has("completed") ? " is-collapsed" : ""
              }`}
            >
              <button
                type="button"
                className="section-head"
                onClick={() => toggleBucket("completed")}
                aria-expanded={!collapsed.has("completed")}
              >
                <h2>Completed today</h2>
                <span className="count">{completedToday.length}</span>
                <span className="chev" aria-hidden="true">
                  ▼
                </span>
              </button>
              <div className="section-body">
                {completedToday.map((task) => renderRow(task, true))}
              </div>
            </section>
          )}
        </div>

        <aside className="agenda-sidebar">
          <div className="side-card">
            {/* Areas moved to the persistent side nav, which navigates
                rather than filters (see design/side-nav-mockup.html). The
                "filter the agenda to one area" job it used to do is now a
                chip in the header, so this card keeps only what is neither
                navigation nor filtering. */}
            <h3>New area</h3>
            <details className="new-list-details">
              <summary>+ New area</summary>
              {/* A plain Django POST: creating an area navigates to the new
                  area anyway, so there's nothing for the SPA layer to do. */}
              <form
                className="new-list-form"
                method="post"
                action={initialData.new_area_url}
              >
                <input
                  type="hidden"
                  name="csrfmiddlewaretoken"
                  value={getCookie("csrftoken")}
                />
                <label className="visually-hidden" htmlFor="agenda-new-title">
                  Area name
                </label>
                <input
                  id="agenda-new-title"
                  className="form-control"
                  name="title"
                  placeholder="Area name"
                  maxLength={100}
                />
                <label className="visually-hidden" htmlFor="agenda-new-text">
                  First task
                </label>
                <input
                  id="agenda-new-text"
                  className="form-control"
                  name="text"
                  placeholder="First task"
                  required
                />
                <button className="btn btn-primary btn-sm" type="submit">
                  Create area
                </button>
              </form>
            </details>
          </div>

          {/* A direct entry point to Capture from the main page itself,
              not just the persistent side nav -- the inbox is where
              anything gets in, and Ideas is the "second brain" shelf, so
              neither should be reachable only through a nav element that
              could fail to render. Plain hrefs, same fallback pattern
              SideNav.tsx already uses, since AgendaOut doesn't carry
              these URLs today. */}
          <div className="side-card">
            <h3>Capture</h3>
            {/* .side-link is inline-block in site.css, meant for one link
                per card (see "Daily reminder" below) -- forced block here
                so two links stack instead of running together. */}
            <a className="side-link" style={{ display: "block" }} href="/capture/">
              Inbox →
            </a>
            <a className="side-link" style={{ display: "block" }} href="/capture/ideas/">
              Ideas →
            </a>
          </div>

          {tags.length > 0 && (
            <div className="side-card">
              <h3>Tags</h3>
              <div className="tag-cloud">
                {tags.map((tag) => (
                  <button
                    type="button"
                    key={tag.name}
                    className={`tag-chip${
                      filters.tag === tag.name ? " is-active" : ""
                    }`}
                    aria-pressed={filters.tag === tag.name}
                    onClick={() => toggleTag(tag.name)}
                  >
                    #{tag.name} <span className="n">{tag.count}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="side-card">
            <h3>Daily reminder</h3>
            <p className="side-note">
              {initialData.daily_digest
                ? "A summary of anything overdue or due today is emailed to you each morning."
                : "Daily reminder emails are switched off."}
            </p>
            <a className="side-link" href={initialData.settings_url}>
              Change this in settings →
            </a>
          </div>

          <div className="side-card">
            <a className="archive-link" href={initialData.archive_url}>
              <span>Archive</span>
              <span className="n">
                {initialData.archived_count} task
                {initialData.archived_count === 1 ? "" : "s"}
              </span>
            </a>
          </div>
        </aside>
      </div>

      <div className="agenda-toasts" aria-live="polite">
        {toasts.map((toast) => (
          <div className="agenda-toast" key={toast.id}>
            <span>{toast.message}</span>
            {toast.undo && (
              <button
                className="btn btn-outline-light btn-sm"
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
