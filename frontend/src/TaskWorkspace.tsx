import { FormEvent, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";

import { Button } from "@/components/ui/button";

import {
  createTask,
  updateTaskDueDate,
  updateTaskRecurrence,
  updateTaskStatus,
  updateTaskTags,
  updateTaskText,
} from "./api";
import { ageLabel, daysBetween } from "./agenda";
import { formatShortDate } from "./format";
import type { Task, TaskRecurrence, TaskStatus, TaskWorkspaceData } from "./types";

// A second copy of TaskDetailRoute's, and the one `lists/models.py`'s comment
// warns about when it says adding a value means something else has to change.
// It stays a copy rather than being lifted somewhere shared, because
// `Record<TaskRecurrence, string>` is what makes it safe: adding a cadence
// fails the build here until this is updated, which is how this one was found
// at all. A shared constant would be tidier and would lose that.
const RECURRENCE_LABELS: Record<TaskRecurrence, string> = {
  none: "Doesn't repeat",
  daily: "Daily",
  weekly: "Weekly",
  fortnightly: "Every two weeks",
  monthly: "Monthly",
  quarterly: "Quarterly",
  annual: "Annually",
};

function todayIsoDate(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset();
  return new Date(now.getTime() - offset * 60000).toISOString().slice(0, 10);
}

function isOverdue(task: Task): boolean {
  return (
    task.status === "active" &&
    task.due_date !== null &&
    task.due_date < todayIsoDate()
  );
}

function formatDueDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
  }).format(new Date(`${value}T00:00:00`));
}

// TaskWorkspaceData carries no server "today" (unlike AgendaWorkspaceData) --
// reuses the same browser-clock read todayIsoDate() already does, and
// agenda.ts's own ageLabel so this reads exactly like the Agenda and the
// weekly review rather than inventing a second phrasing for the same fact.
function createdAgeLabel(task: Task): string | null {
  return ageLabel(daysBetween(task.created_at.slice(0, 10), todayIsoDate()));
}

const TAG_COLORS = [
  "#f4a3a3", "#f4c98a", "#f1e394", "#a8dba8",
  "#8fc7d6", "#9ab6e0", "#c9a8dc", "#e5a8c4",
];

function tagColor(name: string): string {
  let hash = 0;
  for (let index = 0; index < name.length; index += 1) {
    hash = (hash * 31 + name.charCodeAt(index)) >>> 0;
  }
  return TAG_COLORS[hash % TAG_COLORS.length];
}

function filterPillClass(active: boolean): string {
  const base =
    "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs whitespace-nowrap";
  return active
    ? `${base} border-primary bg-primary text-primary-foreground font-medium`
    : `${base} border-border text-muted-foreground hover:text-foreground`;
}

// The due-date pill IS the real <input type="date">, styled down to pill
// size, rather than a second block of text duplicating what it says --
// task-list-redesign-plan.md 2.
function dueDatePillClass(item: Task): string {
  const base =
    "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs cursor-pointer";
  if (isOverdue(item)) return `${base} border-destructive/40 bg-destructive/10 text-destructive`;
  if (item.due_date) return `${base} border-border text-foreground`;
  return `${base} border-dashed border-border text-muted-foreground`;
}

// Quiet until the row is hovered or focused -- most tasks never repeat --
// except an already-active recurrence, which stays visible without a
// hover so it isn't hidden state.
function recurrencePillClass(item: Task): string {
  const base =
    "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs transition-opacity";
  if (item.recurrence !== "none") return `${base} border-transparent`;
  return (
    `${base} border-border text-muted-foreground opacity-0 ` +
    "group-hover:opacity-100 group-focus-within:opacity-100 [@media(hover:none)]:opacity-100"
  );
}

function parseTagInput(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(",")
        .map((tag) => tag.trim())
        .filter((tag) => tag.length > 0),
    ),
  );
}

type Filter = "all" | "active" | "completed";
//: ~~"manual"~~ -- **retired September 4, 2026**, superlists-2.0-plan.md
//: increment 8: *manual ordering leaves the interface.* Dragging a backlog
//: into an order is planning without deciding, and the morning pick is what
//: replaces it. `Item.position` and `POST /areas/{id}/tasks/reorder` both
//: stay -- the column holds an order somebody made, and removing a write path
//: is D3's kind of decision rather than this one's.
type Sort = "due_date" | "added";

interface Props {
  initialData: TaskWorkspaceData;
}

export function TaskWorkspace({ initialData }: Props) {
  // SideNav is mounted once in AppLayout, outside the <Outlet/>, so it does not
  // remount when a route changes and its query is the only thing that refreshes
  // it. Every write below moves at least one number it shows -- an area's
  // open_count or overdue_count, a project's open_task_count, the archive badge.
  //
  // Invalidated after *every* write rather than only the ones whose counts
  // obviously move. Picking is how this happened: seven other files got it
  // right and these three were missed, and a rule that has to be re-derived per
  // handler will be missed again the next time one is added. The nav payload is
  // small and this is one extra request after a write somebody just waited for.
  const queryClient = useQueryClient();
  const refreshNav = () =>
    queryClient.invalidateQueries({ queryKey: ["nav"] });


  const [items, setItems] = useState(initialData.items);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [newText, setNewText] = useState("");
  const [newDueDate, setNewDueDate] = useState("");
  const [newTags, setNewTags] = useState("");
  const [newRecurrence, setNewRecurrence] = useState<TaskRecurrence>("none");
  const [sort, setSort] = useState<Sort>("added");
  const [tagFilter, setTagFilter] = useState<string | null>(null);
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [tagDrafts, setTagDrafts] = useState<Record<number, string>>({});
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingText, setEditingText] = useState("");
  const [busyId, setBusyId] = useState<number | "new" | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const counts = useMemo(
    () => ({
      all: items.length,
      active: items.filter((item) => item.status === "active").length,
      completed: items.filter((item) => item.status === "completed").length,
    }),
    [items],
  );

  const visibleItems = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    const filtered = items.filter((item) => {
      const matchesFilter = filter === "all" || item.status === filter;
      const matchesQuery =
        !normalizedQuery || item.text.toLocaleLowerCase().includes(normalizedQuery);
      const matchesTag = !tagFilter || item.tags.includes(tagFilter);
      return matchesFilter && matchesQuery && matchesTag;
    });
    if (sort !== "due_date") return filtered;
    // Ascending, no-due-date last -- the same rule bucketFor's own bucket
    // order already implies (dated buckets before "someday").
    return [...filtered].sort((a, b) => {
      if (a.due_date === b.due_date) return 0;
      if (a.due_date === null) return 1;
      if (b.due_date === null) return -1;
      return a.due_date < b.due_date ? -1 : 1;
    });
  }, [filter, items, query, sort, tagFilter]);

  const allTags = useMemo(() => {
    const names = new Set<string>();
    items.forEach((item) => item.tags.forEach((tag) => names.add(tag)));
    return Array.from(names).sort();
  }, [items]);

  function replaceItem(updated: Task) {
    setItems((current) =>
      current.map((item) => (item.id === updated.id ? updated : item)),
    );
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusyId("new");
    try {
      const created = await createTask(
        initialData.area.id,
        newText,
        newDueDate || null,
        parseTagInput(newTags),
        newRecurrence,
      );
      setItems((current) => [...current, created]);
      setNewText("");
      setNewDueDate("");
      setNewTags("");
      setNewRecurrence("none");
      setNotice("Task added.");
      refreshNav();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to add task.");
    } finally {
      setBusyId(null);
    }
  }

  // Shared by the single-task and bulk paths so a recurring task's
  // complete-and-spawn behaves identically either way.
  function applyStatusResult(updated: Task, spawned: Task | undefined) {
    if (updated.status === "archived") {
      setItems((current) => {
        const withoutArchived = current.filter((item) => item.id !== updated.id);
        return spawned ? [...withoutArchived, spawned] : withoutArchived;
      });
    } else {
      setItems((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
    }
  }

  async function changeStatus(task: Task, status: TaskStatus) {
    setError("");
    setNotice("");
    setBusyId(task.id);
    try {
      const { task: updated, spawned } = await updateTaskStatus(task, status);
      applyStatusResult(updated, spawned);
      if (updated.status === "archived") {
        setNotice(
          spawned
            ? "Task completed — next occurrence added."
            : "Task moved to Done & archived.",
        );
      } else {
        setNotice(status === "active" ? "Task reopened." : "Task completed.");
      }
      refreshNav();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update task.");
    } finally {
      setBusyId(null);
    }
  }

  function toggleSelectMode() {
    setSelectMode((current) => !current);
    setSelectedIds([]);
  }

  function toggleSelected(id: number) {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((each) => each !== id) : [...current, id],
    );
  }

  // Mark complete / Archive bulk because they're already single, safe
  // per-task calls (updateTaskStatus) run in a loop -- editing due date,
  // tags, or repeat stays per-task since "set every selected task's due
  // date to the same day" isn't a real request anyone's made.
  async function bulkChangeStatus(status: "completed" | "archived") {
    const targets = items.filter((item) => selectedIds.includes(item.id));
    if (targets.length === 0) return;
    setError("");
    setNotice("");
    setBulkBusy(true);
    try {
      const results = await Promise.all(
        targets.map((target) => updateTaskStatus(target, status)),
      );
      results.forEach(({ task: updated, spawned }) => applyStatusResult(updated, spawned));
      setNotice(
        status === "completed"
          ? `${targets.length} task${targets.length === 1 ? "" : "s"} completed.`
          : `${targets.length} task${targets.length === 1 ? "" : "s"} archived.`,
      );
      setSelectedIds([]);
      refreshNav();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update tasks.");
    } finally {
      setBulkBusy(false);
    }
  }

  async function changeRecurrence(task: Task, recurrence: TaskRecurrence) {
    setError("");
    setNotice("");
    setBusyId(task.id);
    try {
      const updated = await updateTaskRecurrence(task, recurrence);
      replaceItem(updated);
      setNotice("Recurrence updated.");
      refreshNav();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update recurrence.");
    } finally {
      setBusyId(null);
    }
  }

  async function changeDueDate(task: Task, dueDate: string | null) {
    setError("");
    setNotice("");
    setBusyId(task.id);
    try {
      const updated = await updateTaskDueDate(task, dueDate);
      replaceItem(updated);
      setNotice(dueDate ? "Due date updated." : "Due date cleared.");
      refreshNav();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update due date.");
    } finally {
      setBusyId(null);
    }
  }

  async function saveTags(task: Task, tags: string[]) {
    setError("");
    setNotice("");
    setBusyId(task.id);
    try {
      const updated = await updateTaskTags(task, tags);
      replaceItem(updated);
      setNotice("Tags updated.");
      if (tagFilter && !updated.tags.includes(tagFilter)) {
        setTagFilter(null);
      }
      refreshNav();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update tags.");
    } finally {
      setBusyId(null);
    }
  }

  function removeTag(task: Task, tag: string) {
    saveTags(task, task.tags.filter((each) => each !== tag));
  }

  async function addTags(task: Task, rawValue: string) {
    const additions = parseTagInput(rawValue);
    if (additions.length === 0) return;
    setTagDrafts((current) => {
      const next = { ...current };
      delete next[task.id];
      return next;
    });
    await saveTags(task, Array.from(new Set([...task.tags, ...additions])));
  }

  function startEditing(task: Task) {
    setEditingId(task.id);
    setEditingText(task.text);
    setError("");
  }

  async function saveEdit(event: FormEvent, task: Task) {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusyId(task.id);
    try {
      const updated = await updateTaskText(task, editingText);
      replaceItem(updated);
      setEditingId(null);
      setNotice("Task updated.");
      refreshNav();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to edit task.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section aria-labelledby="task-workspace-heading">
      <h2 id="task-workspace-heading" className="sr-only">
        Tasks
      </h2>

      <form
        className="mb-6 flex flex-wrap items-center gap-2 rounded-2xl border border-border bg-card px-3 py-2.5"
        onSubmit={handleCreate}
      >
        <label htmlFor="react-new-task" className="sr-only">
          Add another item
        </label>
        <input
          id="react-new-task"
          className="min-w-[10rem] flex-1 border-0 bg-transparent px-1 py-1.5 text-sm text-foreground outline-none placeholder:text-muted-foreground"
          value={newText}
          onChange={(event) => {
            setNewText(event.target.value);
            setError("");
          }}
          onFocus={() => setError("")}
          placeholder="What's next?"
          required
          disabled={busyId === "new"}
        />
        <span className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-foreground/[0.03] px-2.5 py-1.5 text-xs text-muted-foreground">
          <input
            id="react-new-task-due"
            type="date"
            aria-label="Due date (optional)"
            className="w-[6.5rem] border-0 bg-transparent text-inherit outline-none"
            value={newDueDate}
            onChange={(event) => setNewDueDate(event.target.value)}
            disabled={busyId === "new"}
          />
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-foreground/[0.03] px-2.5 py-1.5 text-xs text-muted-foreground">
          <span aria-hidden="true">🏷</span>
          <input
            id="react-new-task-tags"
            type="text"
            aria-label="Tags (optional, comma separated)"
            className="w-24 border-0 bg-transparent text-foreground outline-none placeholder:text-muted-foreground"
            value={newTags}
            onChange={(event) => setNewTags(event.target.value)}
            placeholder="Tags"
            disabled={busyId === "new"}
          />
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-foreground/[0.03] px-2.5 py-1.5 text-xs text-muted-foreground">
          <span aria-hidden="true">↻</span>
          <select
            id="react-new-task-recurrence"
            aria-label="Repeats"
            className="border-0 bg-transparent text-inherit outline-none"
            value={newRecurrence}
            onChange={(event) => setNewRecurrence(event.target.value as TaskRecurrence)}
            disabled={busyId === "new"}
          >
            {(Object.keys(RECURRENCE_LABELS) as TaskRecurrence[]).map((value) => (
              <option key={value} value={value}>
                {RECURRENCE_LABELS[value]}
              </option>
            ))}
          </select>
        </span>
        {/* Button's own size variants top out at h-9 (36px), short of the
            ~44px guideline this redesign otherwise enforces via plain
            Tailwind classes -- needs an explicit override. */}
        <Button type="submit" size="sm" className="h-11" disabled={busyId === "new"}>
          {busyId === "new" ? "Adding…" : "Add item"}
        </Button>
      </form>

      <div className="mb-3.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5" aria-label="Filter tasks">
          {(["all", "active", "completed"] as Filter[]).map((value) => (
            <button
              key={value}
              type="button"
              className={filterPillClass(filter === value)}
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
            >
              {value === "active" ? "Open" : value[0].toUpperCase() + value.slice(1)}
              <span className="text-[0.7rem] tabular-nums">{counts[value]}</span>
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="inline-flex items-center rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground">
            <span className="sr-only">Sort tasks</span>
            <select
              className="border-0 bg-transparent text-inherit outline-none"
              value={sort}
              onChange={(event) => setSort(event.target.value as Sort)}
            >
              <option value="added">Added</option>
              <option value="due_date">Due date</option>
            </select>
          </label>
          <button
            type="button"
            className={filterPillClass(selectMode)}
            aria-pressed={selectMode}
            onClick={toggleSelectMode}
          >
            Select
          </button>
          <label className="inline-flex w-full items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground sm:w-56">
            <span className="sr-only">Search tasks</span>
            <span aria-hidden="true">⌕</span>
            <input
              className="w-full border-0 bg-transparent text-foreground outline-none placeholder:text-muted-foreground"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search this area"
            />
          </label>
        </div>
      </div>

      {allTags.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-1.5" aria-label="Filter by tag">
          {allTags.map((tag) => (
            <button
              key={tag}
              type="button"
              className="rounded-full border border-dashed px-2.5 py-0.5 text-xs"
              style={{
                backgroundColor: tagFilter === tag ? tagColor(tag) : "transparent",
                borderColor: tagColor(tag),
                borderStyle: tagFilter === tag ? "solid" : "dashed",
                color: tagFilter === tag ? "#14181f" : tagColor(tag),
              }}
              aria-pressed={tagFilter === tag}
              onClick={() => setTagFilter((current) => (current === tag ? null : tag))}
            >
              {tag}
            </button>
          ))}
        </div>
      )}

      {selectMode && (
        <div className="mb-3 flex flex-wrap items-center gap-2.5 rounded-lg border border-primary/30 bg-primary/[0.08] px-3.5 py-2 text-sm">
          <span className="font-bold">{selectedIds.length} selected</span>
          <button
            type="button"
            className="rounded-md border border-border px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-40"
            disabled={bulkBusy || selectedIds.length === 0}
            onClick={() => bulkChangeStatus("completed")}
          >
            Mark complete
          </button>
          <button
            type="button"
            className="rounded-md border border-border px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-40"
            disabled={bulkBusy || selectedIds.length === 0}
            onClick={() => bulkChangeStatus("archived")}
          >
            Archive
          </button>
          <button
            type="button"
            className="ml-auto rounded-md border border-border px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-40"
            disabled={selectedIds.length === 0}
            onClick={() => setSelectedIds([])}
          >
            Clear
          </button>
        </div>
      )}

      <div className="min-h-6 text-sm" aria-live="polite">
        {error && <p className="text-destructive">{error}</p>}
        {!error && notice && <p className="text-muted-foreground">{notice}</p>}
      </div>

      <div className="border-t border-border">
        {visibleItems.map((item, index) => {
          // project-workspace-plan.md 2: every task on this page shares the
          // same Area, so it either carries this Area's one project or none
          // -- no per-task join left to make, unlike Agenda/Archive.
          const itemProject = item.project_id !== null ? initialData.project : undefined;
          const age = createdAgeLabel(item);
          return (
          <article
            key={item.id}
            className={[
              "group relative flex items-start gap-3 border-b border-l-4 border-border py-3 pr-1 pl-3",
              item.status === "completed" ? "is-completed" : "",
              isOverdue(item) ? "is-overdue border-l-destructive" : "border-l-transparent",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            <span className="flex flex-none items-center gap-2 pt-0.5">
              {selectMode ? (
                <input
                  type="checkbox"
                  aria-label={`Select ${item.text}`}
                  checked={selectedIds.includes(item.id)}
                  onChange={() => toggleSelected(item.id)}
                  disabled={bulkBusy}
                />
              ) : (
                <span className="text-xs tabular-nums text-muted-foreground">
                  {String(index + 1).padStart(2, "0")}
                </span>
              )}
            </span>
            <div className="min-w-0 flex-1">
              {editingId === item.id ? (
                <form className="grid gap-2" onSubmit={(event) => saveEdit(event, item)}>
                  <label className="sr-only" htmlFor={`edit-task-${item.id}`}>
                    Edit task
                  </label>
                  <input
                    id={`edit-task-${item.id}`}
                    className="rounded-lg border border-border bg-input px-2 py-1 text-sm text-foreground outline-none"
                    value={editingText}
                    onChange={(event) => setEditingText(event.target.value)}
                    autoFocus
                    required
                  />
                  <div className="flex gap-2">
                    <Button
                      type="submit"
                      size="sm"
                      className="h-11"
                      disabled={busyId === item.id}
                    >
                      Save
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      className="h-11"
                      variant="outline"
                      onClick={() => setEditingId(null)}
                      disabled={busyId === item.id}
                    >
                      Cancel
                    </Button>
                  </div>
                </form>
              ) : (
                <>
                  {/* coherence-audit-2026-08-30.md F4. This page could
                      change seven of a task's fields and had no way to reach
                      the page that changes the other four -- so priority,
                      notes, lead days and the bill were unreachable from the
                      surface somebody actually works in. */}
                  <Link
                    to={`/tasks/${item.id}`}
                    className={`task-text block text-sm leading-snug break-words hover:underline ${
                      item.status === "completed"
                        ? "text-muted-foreground line-through decoration-accent"
                        : "text-foreground"
                    }`}
                  >
                    {item.text}
                  </Link>
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                    {/* ui-second-pass-plan.md F2a: the one screen that shows
                        a project heading at all still didn't tie it to the
                        rows under it. A plain marker rather than a link --
                        the project section is already on this same page,
                        right above. */}
                    {itemProject && (
                      <span className="rounded-full border border-border px-2.5 py-0.5">
                        {itemProject.title}
                      </span>
                    )}
                    {item.status === "completed" && item.completed_at ? (
                      <span>Completed {formatShortDate(item.completed_at)}</span>
                    ) : (
                      age && <span>{age}</span>
                    )}
                    <label className={dueDatePillClass(item)}>
                      <input
                        type="date"
                        aria-label={`Change due date for ${item.text}`}
                        className="w-[6.4rem] border-0 bg-transparent text-inherit outline-none"
                        value={item.due_date ?? ""}
                        onChange={(event) =>
                          changeDueDate(item, event.target.value || null)
                        }
                        disabled={busyId === item.id}
                      />
                    </label>
                    {item.tags.map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5"
                        style={{ borderColor: tagColor(tag), color: tagColor(tag) }}
                      >
                        {tag}
                        <button
                          type="button"
                          aria-label={`Remove tag ${tag}`}
                          className="opacity-70 hover:opacity-100"
                          onClick={() => removeTag(item, tag)}
                          disabled={busyId === item.id}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                    <label
                      className={
                        "inline-flex cursor-text items-center gap-1 rounded-full border border-dashed border-border px-2 py-0.5 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 [@media(hover:none)]:opacity-100"
                      }
                    >
                      <span aria-hidden="true">🏷</span>
                      <input
                        type="text"
                        aria-label={`Add tags to ${item.text}`}
                        className="w-16 border-0 bg-transparent text-foreground outline-none placeholder:text-muted-foreground"
                        placeholder="+ tag"
                        value={tagDrafts[item.id] ?? ""}
                        onChange={(event) =>
                          setTagDrafts((current) => ({
                            ...current,
                            [item.id]: event.target.value,
                          }))
                        }
                        onBlur={(event) => addTags(item, event.target.value)}
                        disabled={busyId === item.id}
                      />
                    </label>
                    <label
                      className={recurrencePillClass(item)}
                      style={
                        item.recurrence !== "none"
                          ? { color: "var(--color-status-today)" }
                          : undefined
                      }
                    >
                      <span aria-hidden="true">↻</span>
                      <select
                        aria-label={`Repeat ${item.text}`}
                        className="border-0 bg-transparent text-inherit outline-none"
                        value={item.recurrence}
                        onChange={(event) =>
                          changeRecurrence(item, event.target.value as TaskRecurrence)
                        }
                        disabled={busyId === item.id}
                      >
                        {(Object.keys(RECURRENCE_LABELS) as TaskRecurrence[]).map(
                          (value) => (
                            <option key={value} value={value}>
                              {RECURRENCE_LABELS[value]}
                            </option>
                          ),
                        )}
                      </select>
                    </label>
                  </div>
                </>
              )}
            </div>
            {editingId !== item.id && !selectMode && (
              <div className="flex flex-none items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 [@media(hover:none)]:opacity-100">
                <button
                  type="button"
                  className="rounded-md border border-border px-2 py-1 text-xs whitespace-nowrap text-muted-foreground hover:border-foreground/30 hover:text-foreground"
                  onClick={() => startEditing(item)}
                  disabled={busyId === item.id}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="rounded-md border border-border px-2 py-1 text-xs whitespace-nowrap text-muted-foreground hover:border-foreground/30 hover:text-foreground"
                  onClick={() =>
                    changeStatus(
                      item,
                      item.status === "completed" ? "active" : "completed",
                    )
                  }
                  disabled={busyId === item.id}
                >
                  {item.status === "completed" ? "Reopen" : "Mark complete"}
                </button>
                <button
                  type="button"
                  className="rounded-md border border-border px-2 py-1 text-xs whitespace-nowrap text-muted-foreground hover:border-foreground/30 hover:text-foreground"
                  onClick={() => changeStatus(item, "archived")}
                  disabled={busyId === item.id}
                >
                  Archive
                </button>
              </div>
            )}
          </article>
          );
        })}
        {visibleItems.length === 0 && (
          <div className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
            {items.length === 0
              ? "This area is ready for its first item."
              : "No tasks match this view."}
          </div>
        )}
      </div>
    </section>
  );
}
