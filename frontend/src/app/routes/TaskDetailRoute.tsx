import { FormEvent, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";

import {
  updateTaskDueDate,
  updateTaskNotes,
  updateTaskRecurrence,
  updateTaskStatus,
  updateTaskTags,
  updateTaskText,
} from "../../api";
import { apiV1 } from "../../api/client";
import type { Task, TaskRecurrence } from "../../types";

const RECURRENCE_LABELS: Record<TaskRecurrence, string> = {
  none: "Doesn't repeat",
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
};

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

export function TaskDetailRoute() {
  const { taskId } = useParams();
  const id = Number(taskId);
  const navigate = useNavigate();
  const [task, setTask] = useState<Task | null>(null);
  const [listRef, setListRef] = useState<{ id: number; title: string } | null>(null);
  const [text, setText] = useState("");
  const [tagsDraft, setTagsDraft] = useState("");
  const [notesDraft, setNotesDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { isPending, isError } = useQuery({
    queryKey: ["task", id],
    queryFn: async () => {
      const { data, error } = await apiV1.GET("/api/v1/tasks/{item_id}", {
        params: { path: { item_id: id } },
      });
      if (error) throw error;
      setTask(data.task as Task);
      setListRef(data.list);
      setText(data.task.text);
      setTagsDraft(data.task.tags.join(", "));
      setNotesDraft(data.task.notes);
      return data;
    },
  });

  async function handleSaveText(event: FormEvent) {
    event.preventDefault();
    if (!task) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const updated = await updateTaskText(task, text);
      setTask(updated);
      setNotice("Task updated.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save task.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDueDate(dueDate: string | null) {
    if (!task) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const updated = await updateTaskDueDate(task, dueDate);
      setTask(updated);
      setNotice(dueDate ? "Due date updated." : "Due date cleared.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update due date.");
    } finally {
      setBusy(false);
    }
  }

  async function handleTags() {
    if (!task) return;
    const tags = parseTagInput(tagsDraft);
    const unchanged =
      tags.length === task.tags.length &&
      tags.every((tag, index) => tag === task.tags[index]);
    if (unchanged) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const updated = await updateTaskTags(task, tags);
      setTask(updated);
      setTagsDraft(updated.tags.join(", "));
      setNotice("Tags updated.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update tags.");
    } finally {
      setBusy(false);
    }
  }

  async function handleNotes() {
    if (!task) return;
    // Compared against the trimmed draft because the server trims too --
    // otherwise adding and removing a trailing space would fire a save that
    // changes nothing.
    if (notesDraft.trim() === task.notes) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const updated = await updateTaskNotes(task, notesDraft);
      setTask(updated);
      setNotesDraft(updated.notes);
      setNotice(updated.notes ? "Notes saved." : "Notes cleared.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save notes.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRecurrence(recurrence: TaskRecurrence) {
    if (!task) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const updated = await updateTaskRecurrence(task, recurrence);
      setTask(updated);
      setNotice("Recurrence updated.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update recurrence.");
    } finally {
      setBusy(false);
    }
  }

  async function handleComplete() {
    if (!task) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const { task: updated } = await updateTaskStatus(
        task,
        task.status === "completed" ? "active" : "completed",
      );
      if (updated.status === "archived") {
        // Completing a recurring task auto-archives it and spawns the
        // next occurrence -- it's no longer viewable at this URL.
        navigate(listRef ? `/lists/${listRef.id}` : "/agenda");
        return;
      }
      setTask(updated);
      setNotice(updated.status === "active" ? "Task reopened." : "Task completed.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update task.");
    } finally {
      setBusy(false);
    }
  }

  async function handleArchive() {
    if (!task) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      await updateTaskStatus(task, "archived");
      navigate(listRef ? `/lists/${listRef.id}` : "/agenda");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to archive task.");
      setBusy(false);
    }
  }

  if (isPending) return <p className="p-6">Loading…</p>;
  if (isError || !task || !listRef) return <p className="p-6">Something went wrong.</p>;

  return (
    <div className="max-w-lg mx-auto px-4 py-8 space-y-6">
      <Link
        to={`/lists/${listRef.id}`}
        className="text-sm text-muted-foreground hover:text-foreground"
      >
        ← Back to {listRef.title}
      </Link>

      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-accent">
          {listRef.title}
        </p>
        <h1 className="text-2xl font-bold">Task detail</h1>
      </div>

      <form onSubmit={handleSaveText} className="space-y-2">
        <label htmlFor="task-text" className="text-sm font-bold">
          Task
        </label>
        <div className="flex gap-2">
          <input
            id="task-text"
            value={text}
            onChange={(event) => setText(event.target.value)}
            required
            className="flex-1 rounded-lg border border-border bg-input px-3 py-1.5"
          />
          <Button type="submit" disabled={busy}>
            Save
          </Button>
        </div>
      </form>

      <div className="space-y-1">
        <label htmlFor="task-due-date" className="text-sm font-bold">
          Due date
        </label>
        <input
          id="task-due-date"
          type="date"
          value={task.due_date ?? ""}
          onChange={(event) => handleDueDate(event.target.value || null)}
          disabled={busy}
          className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
        />
      </div>

      <div className="space-y-1">
        <label htmlFor="task-tags" className="text-sm font-bold">
          Tags
        </label>
        <input
          id="task-tags"
          type="text"
          placeholder="Add tags…"
          value={tagsDraft}
          onChange={(event) => setTagsDraft(event.target.value)}
          onBlur={handleTags}
          disabled={busy}
          className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
        />
      </div>

      <div className="space-y-1">
        <label htmlFor="task-recurrence" className="text-sm font-bold">
          Repeat
        </label>
        <select
          id="task-recurrence"
          value={task.recurrence}
          onChange={(event) => handleRecurrence(event.target.value as TaskRecurrence)}
          disabled={busy}
          className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
        >
          {(Object.keys(RECURRENCE_LABELS) as TaskRecurrence[]).map((value) => (
            <option key={value} value={value}>
              {RECURRENCE_LABELS[value]}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1">
        <label htmlFor="task-notes" className="text-sm font-bold">
          Notes
        </label>
        <textarea
          id="task-notes"
          rows={5}
          placeholder="Anything worth remembering about this task…"
          value={notesDraft}
          onChange={(event) => setNotesDraft(event.target.value)}
          onBlur={handleNotes}
          disabled={busy}
          className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
        />
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {notice && !error && <p className="text-sm text-muted-foreground">{notice}</p>}

      <div className="flex items-center gap-3">
        <Button type="button" onClick={handleComplete} disabled={busy}>
          {task.status === "completed" ? "Reopen" : "Mark complete"}
        </Button>
        <Button type="button" variant="outline" onClick={handleArchive} disabled={busy}>
          Move to archive
        </Button>
      </div>
    </div>
  );
}
