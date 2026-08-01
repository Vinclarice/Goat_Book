import { FormEvent, useMemo, useState } from "react";

import {
  createSubtask,
  createTask,
  reorderTasks,
  updateTaskDueDate,
  updateTaskParent,
  updateTaskRecurrence,
  updateTaskStatus,
  updateTaskTags,
  updateTaskText,
} from "./api";
import { formatDate } from "./format";
import styles from "./workspace.module.css";
import type { Task, TaskRecurrence, TaskStatus, TaskWorkspaceData } from "./types";

const RECURRENCE_LABELS: Record<TaskRecurrence, string> = {
  none: "Doesn't repeat",
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
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

interface Props {
  initialData: TaskWorkspaceData;
}

export function TaskWorkspace({ initialData }: Props) {
  const [items, setItems] = useState(initialData.items);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [newText, setNewText] = useState("");
  const [newDueDate, setNewDueDate] = useState("");
  const [newTags, setNewTags] = useState("");
  const [newRecurrence, setNewRecurrence] = useState<TaskRecurrence>("none");
  const [tagFilter, setTagFilter] = useState<string | null>(null);
  const [tagDrafts, setTagDrafts] = useState<Record<number, string>>({});
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingText, setEditingText] = useState("");
  const [busyId, setBusyId] = useState<number | "new" | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [draggedId, setDraggedId] = useState<number | null>(null);
  // Collapsed rather than expanded state, so a newly-loaded list shows
  // everything and only deliberate collapsing hides anything.
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const [addingSubtaskFor, setAddingSubtaskFor] = useState<number | null>(null);
  const [subtaskDraft, setSubtaskDraft] = useState("");

  const canReorder = filter === "all" && query.trim() === "" && tagFilter === null;

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
    return items.filter((item) => {
      const matchesFilter = filter === "all" || item.status === filter;
      const matchesQuery =
        !normalizedQuery || item.text.toLocaleLowerCase().includes(normalizedQuery);
      const matchesTag = !tagFilter || item.tags.includes(tagFilter);
      return matchesFilter && matchesQuery && matchesTag;
    });
  }, [filter, items, query, tagFilter]);

  /** Flattens the visible tasks into render order, parents followed by their
   * own children. A child whose parent was filtered out is rendered at the
   * top level rather than hidden: the filter said to show it, and nesting it
   * under something that isn't on screen would just lose it. */
  const rows = useMemo(() => {
    const visibleIds = new Set(visibleItems.map((item) => item.id));
    const childrenOf = new Map<number, Task[]>();
    for (const item of visibleItems) {
      const parentId = item.parent?.id ?? null;
      if (parentId !== null && visibleIds.has(parentId)) {
        childrenOf.set(parentId, [...(childrenOf.get(parentId) ?? []), item]);
      }
    }
    const out: { item: Task; depth: number }[] = [];
    for (const item of visibleItems) {
      const parentId = item.parent?.id ?? null;
      if (parentId !== null && visibleIds.has(parentId)) continue;
      out.push({ item, depth: 0 });
      if (collapsed.has(item.id)) continue;
      for (const child of childrenOf.get(item.id) ?? []) {
        out.push({ item: child, depth: 1 });
      }
    }
    return out;
  }, [collapsed, visibleItems]);

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

  /** Folds the subtasks a status change also moved back into the list. An
   * archived one leaves altogether -- this page never shows archived tasks --
   * and the rest take their new status. Without this a child ticked off by
   * its parent's completion keeps rendering as open, and one whose parent
   * archived itself keeps rendering at all: rows() promotes a child whose
   * parent is missing to the top level, so it would sit there looking like a
   * root task until the next reload. */
  function applyCascade(items: Task[], cascaded: Task[]): Task[] {
    if (cascaded.length === 0) return items;
    const moved = new Map(cascaded.map((child) => [child.id, child]));
    return items.flatMap((item) => {
      const child = moved.get(item.id);
      if (!child) return [item];
      return child.status === "archived" ? [] : [child];
    });
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusyId("new");
    try {
      const created = await createTask(
        initialData.list.create_item_url,
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
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to add task.");
    } finally {
      setBusyId(null);
    }
  }

  async function changeStatus(task: Task, status: TaskStatus) {
    setError("");
    setNotice("");
    setBusyId(task.id);
    try {
      const { task: updated, spawned, cascaded } = await updateTaskStatus(
        task,
        status,
      );
      if (updated.status === "archived") {
        setItems((current) => {
          const withoutArchived = applyCascade(current, cascaded).filter(
            (item) => item.id !== updated.id,
          );
          // The spawned occurrence arrives without its fresh copies of the
          // subtasks, which the server made in the same breath. Nothing here
          // knows them, so the list is only right again after a reload --
          // see design/roadmap.md, Track A.
          return spawned ? [...withoutArchived, spawned] : withoutArchived;
        });
        setNotice(
          spawned
            ? "Task completed — next occurrence added."
            : "Task moved to Done & archived.",
        );
      } else {
        setItems((current) =>
          applyCascade(current, cascaded).map((item) =>
            item.id === updated.id ? updated : item,
          ),
        );
        setNotice(status === "active" ? "Task reopened." : "Task completed.");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update task.");
    } finally {
      setBusyId(null);
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
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update due date.");
    } finally {
      setBusyId(null);
    }
  }

  async function commitTags(task: Task, rawValue: string) {
    const tags = parseTagInput(rawValue);
    const unchanged =
      tags.length === task.tags.length &&
      tags.every((tag, index) => tag === task.tags[index]);
    if (unchanged) {
      setTagDrafts((current) => {
        const next = { ...current };
        delete next[task.id];
        return next;
      });
      return;
    }
    setError("");
    setNotice("");
    setBusyId(task.id);
    try {
      const updated = await updateTaskTags(task, tags);
      replaceItem(updated);
      setTagDrafts((current) => {
        const next = { ...current };
        delete next[task.id];
        return next;
      });
      setNotice("Tags updated.");
      if (tagFilter && !updated.tags.includes(tagFilter)) {
        setTagFilter(null);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update tags.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleReorder(nextItems: Task[], parentId: number | null) {
    const previous = items;
    setItems(nextItems);
    setError("");
    try {
      // The server takes one sibling group and requires the complete set, so
      // this sends every task under `parentId` -- including any the current
      // filter or search is hiding -- not just what's on screen.
      await reorderTasks(
        initialData.list.reorder_url,
        nextItems
          .filter((item) => (item.parent?.id ?? null) === parentId)
          .map((item) => item.id),
        parentId,
      );
    } catch (caught) {
      setItems(previous);
      setError(caught instanceof Error ? caught.message : "Unable to reorder tasks.");
    }
  }

  function handleDrop(targetId: number) {
    if (draggedId === null || draggedId === targetId) {
      setDraggedId(null);
      return;
    }
    const dragged = items.find((item) => item.id === draggedId);
    const target = items.find((item) => item.id === targetId);
    setDraggedId(null);
    if (!dragged || !target) return;

    const draggedParent = dragged.parent?.id ?? null;
    const targetParent = target.parent?.id ?? null;
    // Dragging across nesting levels is deliberately not a reorder: changing
    // a task's parent is an explicit promote/demote, so a drag that lands in
    // another group is refused rather than silently reparenting.
    if (draggedParent !== targetParent) {
      setError("Drag reorders within one group. Use promote or demote to move a task.");
      return;
    }

    const currentIndex = items.findIndex((item) => item.id === dragged.id);
    const targetIndex = items.findIndex((item) => item.id === target.id);
    if (currentIndex === -1 || targetIndex === -1) return;
    const next = [...items];
    const [moved] = next.splice(currentIndex, 1);
    next.splice(targetIndex, 0, moved);
    handleReorder(next, draggedParent);
  }

  function toggleCollapsed(id: number) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleAddSubtask(event: FormEvent, parent: Task) {
    event.preventDefault();
    const text = subtaskDraft.trim();
    if (!text) return;
    setError("");
    setNotice("");
    setBusyId(parent.id);
    try {
      const created = await createSubtask(
        initialData.list.create_item_url,
        text,
        parent.id,
      );
      setItems((current) => [...current, created]);
      setSubtaskDraft("");
      setAddingSubtaskFor(null);
      setNotice(`Added "${created.text}" under "${parent.text}".`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to add subtask.");
    } finally {
      setBusyId(null);
    }
  }

  async function handlePromote(task: Task) {
    setError("");
    setNotice("");
    setBusyId(task.id);
    try {
      const updated = await updateTaskParent(task, null);
      replaceItem(updated);
      setNotice(`"${updated.text}" is now a task of its own.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to promote task.");
    } finally {
      setBusyId(null);
    }
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
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to edit task.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section aria-labelledby="task-workspace-heading">
      <h2 id="task-workspace-heading" className="visually-hidden">
        Tasks
      </h2>

      <form className={styles.addForm} onSubmit={handleCreate}>
        <label htmlFor="react-new-task">Add another item</label>
        <div className={styles.inputRow}>
          <input
            id="react-new-task"
            className="form-control"
            value={newText}
            onChange={(event) => {
              setNewText(event.target.value);
              setError("");
            }}
            onFocus={() => setError("")}
            placeholder="What is next?"
            required
            disabled={busyId === "new"}
          />
          <button className="btn btn-primary" disabled={busyId === "new"}>
            {busyId === "new" ? "Adding…" : "Add item"}
          </button>
        </div>
        <div className={styles.addExtras}>
          <label className={styles.dueDateField} htmlFor="react-new-task-due">
            Due date <span className="visually-hidden">(optional)</span>
            <input
              id="react-new-task-due"
              type="date"
              className="form-control"
              value={newDueDate}
              onChange={(event) => setNewDueDate(event.target.value)}
              disabled={busyId === "new"}
            />
          </label>
          <label className={styles.dueDateField} htmlFor="react-new-task-tags">
            Tags <span className="visually-hidden">(optional, comma separated)</span>
            <input
              id="react-new-task-tags"
              type="text"
              className="form-control"
              value={newTags}
              onChange={(event) => setNewTags(event.target.value)}
              placeholder="groceries, chores"
              disabled={busyId === "new"}
            />
          </label>
          <label className={styles.dueDateField} htmlFor="react-new-task-recurrence">
            Repeats
            <select
              id="react-new-task-recurrence"
              className="form-control"
              value={newRecurrence}
              onChange={(event) =>
                setNewRecurrence(event.target.value as TaskRecurrence)
              }
              disabled={busyId === "new"}
            >
              {(Object.keys(RECURRENCE_LABELS) as TaskRecurrence[]).map((value) => (
                <option key={value} value={value}>
                  {RECURRENCE_LABELS[value]}
                </option>
              ))}
            </select>
          </label>
        </div>
      </form>

      <div className={styles.toolbar}>
        <div className={styles.filters} aria-label="Filter tasks">
          {(["all", "active", "completed"] as Filter[]).map((value) => (
            <button
              key={value}
              type="button"
              className={filter === value ? styles.filterActive : styles.filter}
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
            >
              {value === "active" ? "Open" : value[0].toUpperCase() + value.slice(1)}
              <span>{counts[value]}</span>
            </button>
          ))}
        </div>
        <label className={styles.search}>
          <span className="visually-hidden">Search tasks</span>
          <input
            className="form-control"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search this list"
          />
        </label>
      </div>

      {allTags.length > 0 && (
        <div className={styles.tagFilters} aria-label="Filter by tag">
          {allTags.map((tag) => (
            <button
              key={tag}
              type="button"
              className={styles.tagChip}
              style={{
                backgroundColor: tagFilter === tag ? tagColor(tag) : "transparent",
                borderColor: tagColor(tag),
              }}
              aria-pressed={tagFilter === tag}
              onClick={() => setTagFilter((current) => (current === tag ? null : tag))}
            >
              {tag}
            </button>
          ))}
        </div>
      )}

      <div className={styles.feedback} aria-live="polite">
        {error && (
          <p className={`${styles.error} invalid-feedback d-block`} data-task-error>
            {error}
          </p>
        )}
        {!error && notice && <p>{notice}</p>}
      </div>

      <div className="list-items" id="id_list_table">
        {rows.map(({ item, depth }, index) => (
          <article
            key={item.id}
            style={depth > 0 ? { marginInlineStart: "2rem" } : undefined}
            className={`list-item ${
              item.status === "completed" ? "is-completed" : ""
            } ${isOverdue(item) ? styles.overdue : ""} ${
              draggedId === item.id ? styles.dragging : ""
            }`}
            draggable={canReorder}
            onDragStart={() => setDraggedId(item.id)}
            onDragOver={(event) => {
              if (canReorder) event.preventDefault();
            }}
            onDrop={(event) => {
              event.preventDefault();
              handleDrop(item.id);
            }}
            onDragEnd={() => setDraggedId(null)}
          >
            <span className={styles.itemLead}>
              {canReorder && (
                <span
                  className={styles.dragHandle}
                  aria-hidden="true"
                  title="Drag to reorder"
                >
                  ⠿
                </span>
              )}
              {depth > 0 ? (
                <span className="item-number" aria-hidden="true">
                  ↳
                </span>
              ) : (
                <span className="item-number">
                  {String(index + 1).padStart(2, "0")}
                </span>
              )}
              {item.subtask_counts.total > 0 && (
                <button
                  type="button"
                  onClick={() => toggleCollapsed(item.id)}
                  aria-expanded={!collapsed.has(item.id)}
                  aria-label={`${
                    collapsed.has(item.id) ? "Show" : "Hide"
                  } subtasks of ${item.text}`}
                  className="text-sm text-muted-foreground"
                >
                  {collapsed.has(item.id) ? "▸" : "▾"} {item.subtask_counts.done}/
                  {item.subtask_counts.total}
                </button>
              )}
            </span>
            <div className="task-copy">
              {editingId === item.id ? (
                <form
                  className={styles.editForm}
                  onSubmit={(event) => saveEdit(event, item)}
                >
                  <label className="visually-hidden" htmlFor={`edit-task-${item.id}`}>
                    Edit task
                  </label>
                  <input
                    id={`edit-task-${item.id}`}
                    className="form-control"
                    value={editingText}
                    onChange={(event) => setEditingText(event.target.value)}
                    autoFocus
                    required
                  />
                  <div className={styles.inlineActions}>
                    <button
                      className="btn btn-primary btn-sm"
                      disabled={busyId === item.id}
                    >
                      Save
                    </button>
                    <button
                      className="btn btn-outline-light btn-sm"
                      type="button"
                      onClick={() => setEditingId(null)}
                      disabled={busyId === item.id}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <>
                  <span className="task-text">{item.text}</span>
                  <small>
                    Created <time dateTime={item.created_at}>{formatDate(item.created_at)}</time>
                    {item.status === "completed" && " · Completed"}
                    {item.due_date && (
                      <>
                        {" · "}
                        {isOverdue(item) ? "Overdue: " : "Due "}
                        <time dateTime={item.due_date}>{formatDueDate(item.due_date)}</time>
                      </>
                    )}
                  </small>
                  <label className={styles.dueDateInline}>
                    <span className="visually-hidden">Change due date for {item.text}</span>
                    <input
                      type="date"
                      className="form-control form-control-sm"
                      value={item.due_date ?? ""}
                      onChange={(event) =>
                        changeDueDate(item, event.target.value || null)
                      }
                      disabled={busyId === item.id}
                    />
                  </label>
                  <div className={styles.tagRow}>
                    {item.tags.map((tag) => (
                      <span
                        key={tag}
                        className={styles.tagPill}
                        style={{ backgroundColor: tagColor(tag) }}
                      >
                        {tag}
                      </span>
                    ))}
                    <label className={styles.tagEdit}>
                      <span className="visually-hidden">Edit tags for {item.text}</span>
                      <input
                        type="text"
                        className="form-control form-control-sm"
                        placeholder="Add tags…"
                        value={tagDrafts[item.id] ?? item.tags.join(", ")}
                        onChange={(event) =>
                          setTagDrafts((current) => ({
                            ...current,
                            [item.id]: event.target.value,
                          }))
                        }
                        onBlur={(event) => commitTags(item, event.target.value)}
                        disabled={busyId === item.id}
                      />
                    </label>
                    <label className={styles.recurrenceInline}>
                      <span className="visually-hidden">Repeat {item.text}</span>
                      <select
                        className="form-control form-control-sm"
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
                    {item.recurrence !== "none" && (
                      <span className={styles.recurrenceBadge}>
                        ↻ {RECURRENCE_LABELS[item.recurrence]}
                      </span>
                    )}
                  </div>
                </>
              )}
            </div>
            {editingId !== item.id && (
              <div className="task-actions">
                <button
                  className="btn btn-outline-light btn-sm"
                  type="button"
                  onClick={() => startEditing(item)}
                  disabled={busyId === item.id}
                >
                  Edit
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  type="button"
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
                  className="btn btn-outline-light btn-sm"
                  type="button"
                  onClick={() => changeStatus(item, "archived")}
                  disabled={busyId === item.id}
                >
                  Move to archive
                </button>
                {/* One level only, so a subtask offers promote instead. */}
                {item.parent ? (
                  <button
                    className="btn btn-outline-light btn-sm"
                    type="button"
                    onClick={() => handlePromote(item)}
                    disabled={busyId === item.id}
                  >
                    Promote
                  </button>
                ) : (
                  <button
                    className="btn btn-outline-light btn-sm"
                    type="button"
                    onClick={() => {
                      setAddingSubtaskFor(item.id);
                      setSubtaskDraft("");
                    }}
                    disabled={busyId === item.id}
                  >
                    Add subtask
                  </button>
                )}
              </div>
            )}

            {addingSubtaskFor === item.id && (
              <form
                className={styles.editForm}
                onSubmit={(event) => handleAddSubtask(event, item)}
              >
                <label
                  className="visually-hidden"
                  htmlFor={`new-subtask-${item.id}`}
                >
                  New subtask under {item.text}
                </label>
                <input
                  id={`new-subtask-${item.id}`}
                  className="form-control"
                  placeholder="Add a subtask…"
                  value={subtaskDraft}
                  onChange={(event) => setSubtaskDraft(event.target.value)}
                  autoFocus
                  disabled={busyId === item.id}
                />
                <button
                  className="btn btn-primary btn-sm"
                  type="submit"
                  disabled={busyId === item.id}
                >
                  Add
                </button>
                <button
                  className="btn btn-outline-light btn-sm"
                  type="button"
                  onClick={() => setAddingSubtaskFor(null)}
                >
                  Cancel
                </button>
              </form>
            )}
          </article>
        ))}
        {visibleItems.length === 0 && (
          <div className={styles.empty}>
            {items.length === 0
              ? "This list is ready for its first item."
              : "No tasks match this view."}
          </div>
        )}
      </div>
    </section>
  );
}
