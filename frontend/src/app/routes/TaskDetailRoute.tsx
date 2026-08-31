import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";

import {
  createChecklistStep,
  deleteChecklistStep,
  deleteTask,
  promoteChecklistStep,
  updateChecklistStepCarriesForward,
  updateChecklistStepDone,
  moveTaskToArea,
  updateTaskBill,
  updateTaskLeadDays,
  updateTaskPriority,
  updateTaskDueDate,
  updateTaskNotes,
  updateTaskCadenceMode,
  updateTaskRecurrence,
  updateTaskStatus,
  updateTaskTags,
  updateTaskText,
} from "../../api";
import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { RouteFailure } from "./RouteFailure";
import type {
  CadenceMode,
  ChecklistStep,
  Task,
  TaskBill,
  TaskPriority,
  TaskRecurrence,
} from "../../types";

// Written as what the schedule *does*, not as the mode's name. "Anchored" and
// "floating" are the domain's words and mean nothing to somebody choosing
// between them at a task page.
const CADENCE_MODE_LABELS: Record<CadenceMode, string> = {
  anchored: "On the same date each time",
  floating: "A set time after I finish it",
};

/** The model's own labels, so the page and the admin do not disagree about
 *  what "high" is called. No "medium": an unmarked task already means
 *  ordinary -- see lists.models.Priority. */
const PRIORITY_LABELS: Record<TaskPriority, string> = {
  none: "No priority",
  high: "Pressing",
  low: "Whenever",
};

const RECURRENCE_LABELS: Record<TaskRecurrence, string> = {
  none: "Doesn't repeat",
  daily: "Daily",
  weekly: "Weekly",
  fortnightly: "Every two weeks",
  monthly: "Monthly",
  quarterly: "Quarterly",
  annual: "Annually",
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

  // Where a task *could* go. Read from the nav query the app already runs
  // rather than added to the task payload -- one definition of "your areas",
  // and on any page but the first render this is a cache hit.
  const { data: nav } = useQuery({
    queryKey: ["nav"],
    queryFn: async () => {
      const { data } = await apiV1.GET("/api/v1/nav");
      return data ?? null;
    },
  });


  const { taskId } = useParams();
  const id = Number(taskId);
  const navigate = useNavigate();
  const [task, setTask] = useState<Task | null>(null);
  // A sibling of `task` in the detail payload rather than a field on it: the
  // mode belongs to the series, and most tasks have no series at all.
  const [cadenceMode, setCadenceMode] = useState<CadenceMode | null>(null);
  const [areaRef, setAreaRef] = useState<{ id: number; title: string } | null>(null);
  const [text, setText] = useState("");
  const [tagsDraft, setTagsDraft] = useState("");
  const [notesDraft, setNotesDraft] = useState("");
  const [checklistSteps, setChecklistSteps] = useState<ChecklistStep[]>([]);
  const [stepDraft, setStepDraft] = useState("");
  const [stepCarriesForward, setStepCarriesForward] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const { data, isPending, isError, error: loadError, refetch } = useQuery({
    queryKey: ["task", id],
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/tasks/{task_id}", {
        params: { path: { task_id: id } },
      });
      if (!response.ok || !data) throw new RequestFailed(response.status);
      return data;
    },
  });

  // Seeded once per task, not on every settle of the query.
  //
  // These setters used to live inside the queryFn, so they re-ran on every
  // refetch -- and refetchOnWindowFocus is on with staleTime at 0, so an
  // alt-tab away from a half-written note and back replaced every character
  // with the server's value, with no message and no undo. PreferencesRoute
  // and DayRoute already carry this guard for the same reason; the ref holds
  // *which* task was seeded so navigating between two of them still loads
  // the second.
  //
  // Everything below is safe to freeze: each mutation writes its own result
  // back through setTask/setChecklistSteps rather than waiting for a
  // refetch, so nothing here depends on the query re-seeding it.
  const seededFor = useRef<number | null>(null);
  useEffect(() => {
    if (!data || seededFor.current === id) return;
    seededFor.current = id;
    setTask(data.task as Task);
    setCadenceMode(data.cadence_mode ?? null);
    setAreaRef(data.area);
    setText(data.task.text);
    setTagsDraft(data.task.tags.join(", "));
    setNotesDraft(data.task.notes);
    setChecklistSteps((data.checklist_steps ?? []) as ChecklistStep[]);
  }, [data, id]);

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
      refreshNav();
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
      refreshNav();
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
      refreshNav();
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
      refreshNav();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save notes.");
    } finally {
      setBusy(false);
    }
  }

  async function handleAddStep(event: FormEvent) {
    event.preventDefault();
    if (!Number.isFinite(id)) return;
    const text = stepDraft.trim();
    if (!text) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const created = await createChecklistStep(id, text, stepCarriesForward);
      setChecklistSteps((current) => [...current, created]);
      setStepDraft("");
      // Back to the default: opting a step out is a per-step decision, not a
      // mode you stay in for everything you add next.
      setStepCarriesForward(true);
      setNotice("Checklist step added.");
      refreshNav();
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
      refreshNav();
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
      refreshNav();
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
      refreshNav();
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
      refreshNav();
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
      refreshNav();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update recurrence.");
    } finally {
      setBusy(false);
    }
  }

  async function handleLeadDays(days: number) {
    if (!task) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const updated = await updateTaskLeadDays(task, days);
      setTask(updated);
      setNotice(days ? "Reminder set." : "Reminder off.");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to set the reminder.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleBill(bill: TaskBill | null) {
    if (!task) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const updated = await updateTaskBill(task, bill);
      setTask(updated);
      setNotice(bill === null ? "No longer a bill." : "Bill saved.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save the bill.");
    } finally {
      setBusy(false);
    }
  }

  async function handlePriority(priority: TaskPriority) {
    if (!task) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const updated = await updateTaskPriority(task, priority);
      setTask(updated);
      setNotice("Priority updated.");
      // The agenda orders within a day by it, so the counts a person sees
      // next are not the ones they just left.
      refreshNav();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to set the priority.");
    } finally {
      setBusy(false);
    }
  }

  async function handleMove(listId: number | null) {
    if (!task) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const updated = await moveTaskToArea(task, listId);
      setTask(updated);
      setAreaRef(
        listId === null
          ? null
          : nav?.areas.find((area) => area.id === listId) ?? null,
      );
      setNotice(listId === null ? "Task unfiled." : "Task moved.");
      // Both the old and the new area's counts changed, so the whole nav is
      // refetched rather than two entries patched.
      refreshNav();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to move the task.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCadenceMode(mode: CadenceMode) {
    if (!task) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const updated = await updateTaskCadenceMode(task, mode);
      setTask(updated);
      setCadenceMode(mode);
      setNotice("Schedule updated.");
      refreshNav();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update schedule.");
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
        navigate(areaRef ? `/areas/${areaRef.id}` : "/agenda");
        return;
      }
      setTask(updated);
      setNotice(updated.status === "active" ? "Task reopened." : "Task completed.");
      refreshNav();
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
      navigate(areaRef ? `/areas/${areaRef.id}` : "/agenda");
      refreshNav();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to archive task.");
      setBusy(false);
    }
  }

  /** Back out of the archive, so the two-step delete stays a two-step.
   *
   * Completed rather than active, matching the Archive's own restore: what
   * was archived was a finished thing more often than not, and
   * `services.restore_item` is the same call either surface makes.
   */
  async function handleRestore() {
    if (!task) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const { task: updated } = await updateTaskStatus(task, "completed");
      setTask(updated);
      setNotice("Task restored.");
      refreshNav();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to restore task.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!task) return;
    setError(null);
    setBusy(true);
    try {
      await deleteTask(task);
      refreshNav();
      navigate("/archive");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to delete task.");
      setConfirmingDelete(false);
      setBusy(false);
    }
  }

  if (isPending) return <p className="p-6">Loading…</p>;
  if (isError || !data) return <RouteFailure status={statusOf(loadError)} onRetry={() => refetch()} />;
  // One render sits between the data arriving and the effect above seeding
  // from it. That gap is a load, not a failure -- guarding it with
  // RouteFailure, as this line used to, would flash an error page over a
  // request that had just succeeded.
  // **`areaRef` is deliberately not part of this guard** --
  // coherence-audit-2026-08-30.md F3. It was, and `Item.list` has been
  // nullable since August 14, 2026, so an unfiled task rendered this line for
  // ever: the one class of task the task page could not show. `area` is null
  // in the payload on purpose, and every use of it below is now optional.
  if (!task) return <p className="p-6">Loading…</p>;

  const archived = task.status === "archived";

  // Whether "does this subtask come back next time?" is a question worth
  // asking at all. The flag exists on every subtask regardless; this only
  // decides whether the controls for it are worth the screen space.
  const repeats = task.recurrence !== "none";

  return (
    <div className="max-w-lg mx-auto px-4 py-8 space-y-6">
      <Link
        to={areaRef ? `/areas/${areaRef.id}` : "/agenda"}
        className="text-sm text-muted-foreground hover:text-foreground"
      >
        ← Back to {areaRef ? areaRef.title : "the agenda"}
      </Link>

      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-accent">
          {areaRef ? areaRef.title : "No area"}
        </p>
        <h1 className="text-2xl font-bold">Task detail</h1>
      </div>

      {archived && (
        /* coherence-audit-2026-08-30.md F3. An archived task had no page at
           all until August 30, 2026 -- the Archive could list it and delete
           it, and nothing could read it. It is readable here now, and not
           editable, which is the domain's own rule rather than a decision
           this page takes: every write service refuses an archived task with
           this exact sentence. */
        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          <p className="text-sm font-bold">This task is archived.</p>
          <p className="text-sm text-muted-foreground">
            Restore it before editing it. Everything below is a record of how
            it was when you archived it.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Button type="button" onClick={handleRestore} disabled={busy}>
              Restore
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfirmingDelete(true)}
              disabled={busy}
              className="text-destructive"
            >
              Delete permanently
            </Button>
          </div>
        </div>
      )}

      {confirmingDelete && (
        /* A confirmation rather than an undo, because there is no undo --
           principles.md is explicit that where none exists the act is not
           reversible however it looks. The Archive's own delete asks the same
           question; this is the second place it can be asked from, not a
           second rule. */
        <div
          role="dialog"
          aria-label="Delete this task permanently"
          className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 space-y-3"
        >
          <p className="text-sm text-destructive">
            This cannot be undone. The task, its checklist and its record go
            with it.
          </p>
          <div className="flex items-center gap-3">
            <Button
              type="button"
              onClick={handleDelete}
              disabled={busy}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/80"
            >
              Delete permanently
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfirmingDelete(false)}
              disabled={busy}
            >
              Keep it
            </Button>
          </div>
        </div>
      )}

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

      {/* Not bill-specific, which is why it sits out here rather than inside
          the bill below: "remind me before the MOT" is the same sentence.
          Zero is off, and a lead time changes nothing about when the task is
          *due* -- it is mentioned early, in a section of its own. */}
      <div className="space-y-1">
        <label htmlFor="task-lead-days" className="text-sm font-bold">
          Remind me in advance
        </label>
        <input
          id="task-lead-days"
          type="number"
          min={0}
          aria-label="Remind me in advance"
          defaultValue={task.lead_days}
          disabled={busy}
          onBlur={(event) =>
            handleLeadDays(Math.max(0, Number(event.target.value) || 0))
          }
          className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
        />
        <p className="text-sm text-muted-foreground">
          Days before it is due. Zero is off.
        </p>
      </div>

      {/* A bill is a recurring task with a number on it -- §4 said no to a
          primitive, and the vision document's own example is "pay rent every
          month". So this edits a sidecar rather than a different kind of
          thing, and the task above is untouched either way. */}
      <div className="space-y-1">
        <p className="text-sm font-bold">Bill</p>
        {task.bill === null ? (
          <Button
            type="button"
            variant="ghost"
            disabled={busy}
            onClick={() => handleBill({ amount: null, currency: "USD", payee: "" })}
          >
            This is a bill
          </Button>
        ) : (
          <div className="space-y-2 rounded-lg border border-border px-3 py-2">
            <div className="space-y-1">
              <label htmlFor="bill-amount" className="text-sm">
                Amount
              </label>
              <input
                id="bill-amount"
                aria-label="Amount"
                inputMode="decimal"
                defaultValue={task.bill.amount ?? ""}
                disabled={busy}
                onBlur={(event) =>
                  handleBill({
                    ...task.bill!,
                    amount: event.target.value.trim() || null,
                  })
                }
                className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="bill-payee" className="text-sm">
                Payee
              </label>
              <input
                id="bill-payee"
                aria-label="Payee"
                defaultValue={task.bill.payee}
                disabled={busy}
                onBlur={(event) =>
                  handleBill({ ...task.bill!, payee: event.target.value })
                }
                className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
              />
            </div>
            {/* An empty amount is a real state -- "the water bill, whatever
                it comes to" -- so this removes the bill rather than the
                number. */}
            <Button
              type="button"
              variant="ghost"
              disabled={busy}
              onClick={() => handleBill(null)}
            >
              Not a bill
            </Button>
          </div>
        )}
      </div>

      <div className="space-y-1">
        <label htmlFor="task-priority" className="text-sm font-bold">
          Priority
        </label>
        <select
          id="task-priority"
          value={task.priority}
          onChange={(event) => handlePriority(event.target.value as TaskPriority)}
          disabled={busy}
          className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
        >
          {(Object.keys(PRIORITY_LABELS) as TaskPriority[]).map((value) => (
            <option key={value} value={value}>
              {PRIORITY_LABELS[value]}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1">
        <label htmlFor="task-area" className="text-sm font-bold">
          Area
        </label>
        <select
          id="task-area"
          value={areaRef?.id ?? ""}
          onChange={(event) =>
            handleMove(event.target.value === "" ? null : Number(event.target.value))
          }
          disabled={busy}
          className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
        >
          {/* An unfiled task is a real task, so "no area" is an option a
              person can choose rather than only a state they arrive in. */}
          <option value="">No area</option>
          {(nav?.areas ?? []).map((area) => (
            <option key={area.id} value={area.id}>
              {area.title}
            </option>
          ))}
        </select>
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

      {task.recurrence !== "none" && cadenceMode !== null && (
        <div className="space-y-1">
          <label htmlFor="task-cadence-mode" className="text-sm font-bold">
            Next one is due
          </label>
          <select
            id="task-cadence-mode"
            value={cadenceMode}
            onChange={(event) =>
              handleCadenceMode(event.target.value as CadenceMode)
            }
            disabled={busy}
            className="w-full rounded-lg border border-border bg-input px-3 py-1.5"
          >
            {(Object.keys(CADENCE_MODE_LABELS) as CadenceMode[]).map((value) => (
              <option key={value} value={value}>
                {CADENCE_MODE_LABELS[value]}
              </option>
            ))}
          </select>
          <p className="text-xs text-muted-foreground">
            {cadenceMode === "anchored"
              ? "Keeps its date even if you finish late — right for rent or a bill."
              : "Counts from the day you finish — right for a filter or a haircut."}
          </p>
        </div>
      )}

      {/* The per-task Project select used to live here --
          project-workspace-plan.md 2 dropped the task-level override. A
          task's project comes from its Area now, so it's shown (and
          changed) on the Area's own page instead, not repeated here. */}

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
              {/* A switch, not a checkbox, and the difference is the point.
                * ui-second-pass-plan.md F1: this row used to carry two
                * <input type="checkbox"> elements asking two unrelated
                * questions -- the exact shape C2 complained about, and the
                * one thing release-d-plan.md 4 predicted would be
                * mechanical and was not. A checkbox reads as "tick this
                * when it is done"; a switch reads as a setting that stays
                * on. Different question, different control. */}
              {repeats && (
                <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <Switch
                    size="sm"
                    checked={step.carries_forward}
                    onCheckedChange={() => handleToggleStepCarriesForward(step)}
                    disabled={busy}
                    aria-label={`Carry ${step.text} forward next time`}
                  />
                  Carries forward
                </span>
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
          {/* The same question the row asks, so the same control. Leaving
            * this one a checkbox would trade C2's defect for a smaller
            * version of it. */}
          {repeats && (
            <span className="flex items-center gap-2 text-sm text-muted-foreground">
              <Switch
                size="sm"
                checked={stepCarriesForward}
                onCheckedChange={setStepCarriesForward}
                disabled={busy}
                aria-label="Bring this back on the next occurrence"
              />
              Bring this back on the next occurrence
            </span>
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

      {!archived && (
        <div className="flex items-center gap-3">
          <Button type="button" onClick={handleComplete} disabled={busy}>
            {task.status === "completed" ? "Reopen" : "Mark complete"}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={handleArchive}
            disabled={busy}
          >
            Move to archive
          </Button>
        </div>
      )}
    </div>
  );
}
