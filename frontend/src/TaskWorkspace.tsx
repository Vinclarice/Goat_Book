import { FormEvent, useMemo, useState } from "react";

import {
  createTask,
  reorderTasks,
  updateTaskDueDate,
  updateTaskStatus,
  updateTaskText,
} from "./api";
import { formatDate } from "./format";
import styles from "./workspace.module.css";
import type { Task, TaskStatus, TaskWorkspaceData } from "./types";

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
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingText, setEditingText] = useState("");
  const [busyId, setBusyId] = useState<number | "new" | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [draggedId, setDraggedId] = useState<number | null>(null);

  const canReorder = filter === "all" && query.trim() === "";

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
      return matchesFilter && matchesQuery;
    });
  }, [filter, items, query]);

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
        initialData.list.create_item_url,
        newText,
        newDueDate || null,
      );
      setItems((current) => [...current, created]);
      setNewText("");
      setNewDueDate("");
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
      const updated = await updateTaskStatus(task, status);
      if (updated.status === "archived") {
        setItems((current) => current.filter((item) => item.id !== updated.id));
        setNotice("Task moved to Done & archived.");
      } else {
        replaceItem(updated);
        setNotice(status === "active" ? "Task reopened." : "Task completed.");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update task.");
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

  async function handleReorder(nextItems: Task[]) {
    const previous = items;
    setItems(nextItems);
    setError("");
    try {
      await reorderTasks(
        initialData.list.reorder_url,
        nextItems.map((item) => item.id),
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
    const currentIndex = items.findIndex((item) => item.id === draggedId);
    const targetIndex = items.findIndex((item) => item.id === targetId);
    setDraggedId(null);
    if (currentIndex === -1 || targetIndex === -1) return;
    const next = [...items];
    const [moved] = next.splice(currentIndex, 1);
    next.splice(targetIndex, 0, moved);
    handleReorder(next);
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

      <div className={styles.feedback} aria-live="polite">
        {error && (
          <p className={`${styles.error} invalid-feedback d-block`} data-task-error>
            {error}
          </p>
        )}
        {!error && notice && <p>{notice}</p>}
      </div>

      <div className="list-items" id="id_list_table">
        {visibleItems.map((item, index) => (
          <article
            key={item.id}
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
            {canReorder && (
              <span
                className={styles.dragHandle}
                aria-hidden="true"
                title="Drag to reorder"
              >
                ⠿
              </span>
            )}
            <span className="item-number">
              {String(index + 1).padStart(2, "0")}
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
              </div>
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
