import { FormEvent, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";

import {
  createChecklistStep,
  deleteChecklistStep,
  promoteChecklistStep,
  updateChecklistStepCarriesForward,
  updateChecklistStepDone,
  updateTaskDueDate,
  updateTaskNotes,
  updateTaskRecurrence,
  updateTaskStatus,
  updateTaskTags,
  updateTaskText,
} from "../../api";
import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { RouteFailure } from "./RouteFailure";
import type { ChecklistStep, Task, TaskRecurrence } from "../../types";

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
  const [checklistSteps, setChecklistSteps] = useState<ChecklistStep[]>([]);
  const [createStepUrl, setCreateStepUrl] = useState("");
  const [stepDraft, setStepDraft] = useState("");
  const [stepCarriesForward, setStepCarriesForward] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { isPending, isError, error: loadError, refetch } = useQuery({
    queryKey: ["task", id],
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/tasks/{item_id}", {
        params: { path: { item_id: id } },
      });
      if (!response.ok || !data) throw new RequestFailed(response.status);
      setTask(data.task as Task);
      setListRef(data.list);
      setText(data.task.text);
      setTagsDraft(data.task.tags.join(", "));
      setNotesDraft(data.task.notes);
      setChecklistSteps((data.checklist_steps ?? []) as ChecklistStep[]);
      setCreateStepUrl(data.create_checklist_step_url ?? "");
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

  async function handleAddStep(event: FormEvent) {
    event.preventDefault();
    if (!createStepUrl) return;
    const text = stepDraft.trim();
    if (!text) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const created = await createChecklistStep(
        createStepUrl,
        text,
        stepCarriesForward,
      );
      setChecklistSteps((current) => [...current, created]);
      setStepDraft("");
      // Back to the default: opting a step out is a per-step decision, not a
      // mode you stay in for everything you add next.
      setStepCarriesForward(true);
      setNotice("Checklist step added.");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to add checklist step.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleToggleStep(step: ChecklistStep) {
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const updated = await updateChecklistStepDone(step, !step.is_done);
      setChecklistSteps((current) =>
        current.map((each) => (each.id === updated.id ? updated : each)),
      );
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to update checklist step.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleToggleStepCarriesForward(step: ChecklistStep) {
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const updated = await updateChecklistStepCarriesForward(
        step,
        !step.carries_forward,
      );
      setChecklistSteps((current) =>
        current.map((each) => (each.id === updated.id ? updated : each)),
      );
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to update checklist step.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handlePromoteStep(step: ChecklistStep) {
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      await promoteChecklistStep(step);
      // It is a task in its own right now, so it leaves the checklist.
      setChecklistSteps((current) => current.filter((each) => each.id !== step.id));
      setNotice(`"${step.text}" is now a task of its own.`);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to promote checklist step.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteStep(step: ChecklistStep) {
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      await deleteChecklistStep(step);
      setChecklistSteps((current) => current.filter((each) => each.id !== step.id));
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to remove checklist step.",
      );
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
  if (isError || !task || !listRef) return <RouteFailure status={statusOf(loadError)} onRetry={() => refetch()} />;

  // Whether "does this subtask come back next time?" is a question worth
  // asking at all. The flag exists on every subtask regardless; this only
  // decides whether the controls for it are worth the screen space.
  const repeats = task.recurrence !== "none";

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

      <div className="space-y-2">
        <h2 className="text-sm font-bold">
          Checklist{" "}
          {checklistSteps.length > 0 && (
            <span className="font-normal text-muted-foreground">
              {checklistSteps.filter((each) => each.is_done).length}/
              {checklistSteps.length}
            </span>
          )}
        </h2>

        {checklistSteps.length === 0 && (
          <p className="text-sm text-muted-foreground">No checklist steps yet.</p>
        )}

        {/* One checkbox per row, and it means exactly one thing: done or
         * not. Whether a step carries forward is a separate control that
         * only exists at all once the task repeats -- release-d-plan.md 2
         * is what this replaces: a subtask row used to carry two
         * identical-looking checkboxes for two different questions. */}
        <ul className="space-y-1">
          {checklistSteps.map((step) => (
            <li key={step.id} className="flex items-center gap-2">
              <input
                type="checkbox"
                id={`step-${step.id}`}
                checked={step.is_done}
                onChange={() => handleToggleStep(step)}
                disabled={busy}
              />
              <label
                htmlFor={`step-${step.id}`}
                className={
                  step.is_done
                    ? "flex-1 line-through text-muted-foreground"
                    : "flex-1"
                }
              >
                {step.text}
              </label>
              {repeats && (
                <label className="flex items-center gap-1 text-sm text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={step.carries_forward}
                    onChange={() => handleToggleStepCarriesForward(step)}
                    disabled={busy}
                    aria-label={`Carry ${step.text} forward next time`}
                  />
                  Carries forward
                </label>
              )}
              <button
                type="button"
                onClick={() => handlePromoteStep(step)}
                disabled={busy}
                className="text-sm text-muted-foreground hover:text-text"
                aria-label={`Promote ${step.text}`}
              >
                Promote
              </button>
              <button
                type="button"
                onClick={() => handleDeleteStep(step)}
                disabled={busy}
                className="text-sm text-muted-foreground hover:text-text"
                aria-label={`Remove ${step.text}`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>

        <form onSubmit={handleAddStep} className="space-y-2">
          <div className="flex items-center gap-2">
            <input
              type="text"
              aria-label="New checklist step"
              placeholder="Add a checklist step…"
              value={stepDraft}
              onChange={(event) => setStepDraft(event.target.value)}
              disabled={busy}
              className="flex-1 rounded-lg border border-border bg-input px-3 py-1.5"
            />
            <Button type="submit" variant="outline" disabled={busy}>
              Add
            </Button>
          </div>
          {repeats && (
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={stepCarriesForward}
                onChange={(event) => setStepCarriesForward(event.target.checked)}
                disabled={busy}
              />
              Bring this back on the next occurrence
            </label>
          )}
        </form>
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
