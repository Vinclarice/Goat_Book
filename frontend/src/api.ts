import { apiV1 } from "./api/client";
import type { paths } from "./api/schema";
import type {
  CadenceMode,
  ChecklistStep,
  Task,
  TaskBill,
  TaskPriority,
  TaskRecurrence,
  TaskStatus,
} from "./types";

/**
 * Typed task and checklist writes — coherence-audit-2026-08-30.md F2.
 *
 * **This file used to be a second HTTP client.** It hand-rolled `fetch`, a
 * `{data, spawned, errors}` envelope, a CSRF header and an `ApiError` class,
 * and it talked to `lists.api`'s hand-rolled Django views — so every write to
 * the noun this application is named for sat outside the generated contract
 * while `tsc --noEmit` checked every Money call. What is left is a wrapper
 * layer over `apiV1`, which is a different thing: the requests are
 * type-checked against `openapi.json`, and the paths are literals the compiler
 * knows.
 *
 * **The exported signatures did not change, on purpose**, apart from the three
 * that took a URL and now take an id. Roughly thirty call sites across four
 * components catch a rejection and print `caught.message`, so these keep
 * throwing rather than returning openapi-fetch's `{data, error}` — rewriting
 * them all would have been churn in the same commit as a contract move, and
 * `principles.md` asks for one understandable purpose per commit.
 *
 * **`ApiError` is gone and nothing missed it.** It carried a field-keyed
 * `errors` dictionary that no component ever read: `firstError` collapsed it to
 * a single string, which is exactly what Ninja's `{"detail": "..."}` already
 * is.
 */

/** Reads a message out of whatever openapi-fetch handed back.
 *
 * Ninja answers `{"detail": "..."}` for an `HttpError` and a list of objects
 * for a 422 schema rejection, and the second only happens when a client sends
 * something its own types forbid — so it gets a short generic message rather
 * than an attempt to render pydantic's structure at a person.
 */
function messageFrom(error: unknown): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return "Something went wrong. Please try again.";
}

function fail(error: unknown): never {
  throw new Error(messageFrom(error));
}

/** One field per request, which is the endpoint's own discipline.
 *
 * Read straight off the generated contract rather than restated here, so the
 * day a field is added or removed server-side this stops compiling instead of
 * silently disagreeing. The server refuses two fields in one body; the type
 * cannot express that, and does not try.
 */
type TaskPatch = NonNullable<
  paths["/api/v1/tasks/{item_id}"]["patch"]["requestBody"]
>["content"]["application/json"];

async function patchTask(task: Task, body: TaskPatch): Promise<Task> {
  const { data, error } = await apiV1.PATCH("/api/v1/tasks/{item_id}", {
    params: { path: { item_id: task.id } },
    body,
  });
  if (error) fail(error);
  return data!.task as Task;
}

export async function createTask(
  areaId: number,
  text: string,
  dueDate?: string | null,
  tags?: string[],
  recurrence?: TaskRecurrence,
): Promise<Task> {
  const { data, error } = await apiV1.POST("/api/v1/areas/{area_id}/tasks", {
    params: { path: { area_id: areaId } },
    body: {
      text,
      due_date: dueDate ?? null,
      tags: tags ?? [],
      recurrence: recurrence ?? "none",
    },
  });
  if (error) fail(error);
  return data as Task;
}

export function updateTaskText(task: Task, text: string): Promise<Task> {
  return patchTask(task, { text });
}

export function updateTaskDueDate(
  task: Task,
  dueDate: string | null,
): Promise<Task> {
  return patchTask(task, { due_date: dueDate });
}

/**
 * File a task into a different Area, or out of every Area with `null`.
 *
 * `commercial-blueprint.md` Part 3 named the gap: `item_detail` PATCH took
 * six fields and `list` was not one of them, so a misfiled task stayed
 * misfiled. Moving Areas moves Projects too, because a Project hangs off the
 * Area rather than off the task.
 *
 * **The wire name is `area_id` since August 30, 2026**, where the old endpoint
 * said `list` — the ORM's column name on the boundary, which is half of
 * coherence-audit-2026-08-30.md F5. The argument's own name is unchanged.
 */
export function moveTaskToArea(task: Task, listId: number | null): Promise<Task> {
  return patchTask(task, { area_id: listId });
}

/** How pressing this is, relative to the rest. Writes through to the series,
 *  so a repeating task keeps it. */
export function updateTaskPriority(
  task: Task,
  priority: TaskPriority,
): Promise<Task> {
  return patchTask(task, { priority });
}

/** Mark a task as a bill, edit the one it is, or `null` to stop it being one.
 *
 *  The amount travels as a string for the same reason the column is a decimal:
 *  a JSON number would bring back the binary rounding both exist to avoid. */
export function updateTaskBill(
  task: Task,
  bill: TaskBill | null,
): Promise<Task> {
  return patchTask(task, { bill });
}

/** How many days before its due date this should be mentioned. Zero is off. */
export function updateTaskLeadDays(task: Task, days: number): Promise<Task> {
  return patchTask(task, { lead_days: days });
}

export function updateTaskTags(task: Task, tags: string[]): Promise<Task> {
  return patchTask(task, { tags });
}

export function updateTaskRecurrence(
  task: Task,
  recurrence: TaskRecurrence,
): Promise<Task> {
  return patchTask(task, { recurrence });
}

/** Whether a repeating task is fixed to the calendar or counts from completion.
 *
 * A separate request from `updateTaskRecurrence` rather than a second argument
 * to it: the endpoint takes exactly one field per PATCH, and this is a property
 * of the series rather than of this occurrence.
 */
export function updateTaskCadenceMode(
  task: Task,
  cadence_mode: CadenceMode,
): Promise<Task> {
  return patchTask(task, { cadence_mode });
}

export function updateTaskNotes(task: Task, notes: string): Promise<Task> {
  return patchTask(task, { notes });
}

/** Put a task into a project, or take it out with null.
 *
 * On the task's own endpoint rather than the project's, alongside every
 * other single-field task edit -- release-d-plan.md 5 slice 7. The server
 * refuses a project owned by somebody else (404) or one in another area
 * (409), so this does not re-check either.
 */
export interface StatusUpdateResult {
  task: Task;
  /** Set when completing a recurring task auto-archives it and creates
   * the next occurrence in the same request. */
  spawned?: Task;
  /** The fresh checklist steps cloned onto `spawned` by that same request.
   * Always an array so callers never branch on the field existing; empty
   * when the occurrence had no recurring steps. */
  spawnedChecklistSteps: ChecklistStep[];
}

export async function updateTaskStatus(
  task: Task,
  status: TaskStatus,
): Promise<StatusUpdateResult> {
  const { data, error } = await apiV1.PATCH("/api/v1/tasks/{item_id}", {
    params: { path: { item_id: task.id } },
    body: { status },
  });
  if (error) fail(error);
  return {
    task: data!.task as Task,
    spawned: (data!.spawned ?? undefined) as Task | undefined,
    spawnedChecklistSteps: (data!.spawned_checklist_steps ?? []) as ChecklistStep[],
  };
}

export async function deleteTask(task: Task): Promise<number> {
  const { data, error } = await apiV1.DELETE("/api/v1/tasks/{item_id}", {
    params: { path: { item_id: task.id } },
  });
  if (error) fail(error);
  return data!.deleted;
}

export async function reorderTasks(
  areaId: number,
  orderedIds: number[],
): Promise<Task[]> {
  const { data, error } = await apiV1.POST(
    "/api/v1/areas/{area_id}/tasks/reorder",
    { params: { path: { area_id: areaId } }, body: { ordered_ids: orderedIds } },
  );
  if (error) fail(error);
  return data as Task[];
}

export async function createChecklistStep(
  taskId: number,
  text: string,
  carriesForward = true,
): Promise<ChecklistStep> {
  const { data, error } = await apiV1.POST(
    "/api/v1/tasks/{task_id}/checklist-steps",
    {
      params: { path: { task_id: taskId } },
      body: { text, carries_forward: carriesForward },
    },
  );
  if (error) fail(error);
  return data as ChecklistStep;
}

async function patchStep(
  step: ChecklistStep,
  body: { text?: string; is_done?: boolean; carries_forward?: boolean },
): Promise<ChecklistStep> {
  const { data, error } = await apiV1.PATCH("/api/v1/checklist-steps/{step_id}", {
    params: { path: { step_id: step.id } },
    body,
  });
  if (error) fail(error);
  return data as ChecklistStep;
}

export function updateChecklistStepDone(
  step: ChecklistStep,
  isDone: boolean,
): Promise<ChecklistStep> {
  return patchStep(step, { is_done: isDone });
}

export function updateChecklistStepCarriesForward(
  step: ChecklistStep,
  carriesForward: boolean,
): Promise<ChecklistStep> {
  return patchStep(step, { carries_forward: carriesForward });
}

export function updateChecklistStepText(
  step: ChecklistStep,
  text: string,
): Promise<ChecklistStep> {
  return patchStep(step, { text });
}

export async function deleteChecklistStep(step: ChecklistStep): Promise<number> {
  const { data, error } = await apiV1.DELETE("/api/v1/checklist-steps/{step_id}", {
    params: { path: { step_id: step.id } },
  });
  if (error) fail(error);
  return data!.deleted;
}

/** Turns a step into a task of its own. Returns the new Task -- the step no
 * longer exists once this resolves. */
export async function promoteChecklistStep(step: ChecklistStep): Promise<Task> {
  const { data, error } = await apiV1.POST(
    "/api/v1/checklist-steps/{step_id}/promote",
    { params: { path: { step_id: step.id } } },
  );
  if (error) fail(error);
  return data as Task;
}

export async function reorderChecklistSteps(
  taskId: number,
  orderedIds: number[],
): Promise<ChecklistStep[]> {
  const { data, error } = await apiV1.POST(
    "/api/v1/tasks/{task_id}/checklist-steps/reorder",
    { params: { path: { task_id: taskId } }, body: { ordered_ids: orderedIds } },
  );
  if (error) fail(error);
  return data as ChecklistStep[];
}
