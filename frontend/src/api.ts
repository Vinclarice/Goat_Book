import type {
  CadenceMode,
  ChecklistStep,
  Task,
  TaskPriority,
  TaskRecurrence,
  TaskStatus,
} from "./types";

interface ApiErrors {
  [field: string]: string[];
}

interface ApiResponse<T> {
  data?: T;
  spawned?: Task;
  spawned_checklist_steps?: ChecklistStep[];
  errors?: ApiErrors;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly errors: ApiErrors = {},
  ) {
    super(message);
  }
}

export function getCookie(name: string): string {
  const cookie = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${name}=`));
  return cookie ? decodeURIComponent(cookie.slice(name.length + 1)) : "";
}

function firstError(errors: ApiErrors | undefined): string {
  if (!errors) return "Something went wrong. Please try again.";
  return Object.values(errors).flat()[0] ?? "Something went wrong. Please try again.";
}

async function requestPayload<T>(
  url: string,
  method: "POST" | "PATCH" | "DELETE",
  body?: object,
): Promise<ApiResponse<T>> {
  const response = await fetch(url, {
    method,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  let payload: ApiResponse<T>;
  try {
    payload = (await response.json()) as ApiResponse<T>;
  } catch {
    const message =
      response.status === 403
        ? "Your security token expired. Refresh the page and try again."
        : "The server returned an unexpected response. Please try again.";
    throw new ApiError(message, response.status);
  }
  if (!response.ok || payload.data === undefined) {
    throw new ApiError(firstError(payload.errors), response.status, payload.errors);
  }
  return payload;
}

async function request<T>(
  url: string,
  method: "POST" | "PATCH" | "DELETE",
  body?: object,
): Promise<T> {
  const payload = await requestPayload<T>(url, method, body);
  return payload.data as T;
}

export function createTask(
  url: string,
  text: string,
  dueDate?: string | null,
  tags?: string[],
  recurrence?: TaskRecurrence,
): Promise<Task> {
  return request<Task>(url, "POST", {
    text,
    due_date: dueDate ?? null,
    tags: tags ?? [],
    recurrence: recurrence ?? "none",
  });
}

export function updateTaskText(task: Task, text: string): Promise<Task> {
  return request<Task>(task.url, "PATCH", { text });
}

export function updateTaskDueDate(
  task: Task,
  dueDate: string | null,
): Promise<Task> {
  return request<Task>(task.url, "PATCH", { due_date: dueDate });
}

/**
 * File a task into a different Area, or out of every Area with `null`.
 *
 * `commercial-blueprint.md` Part 3 named the gap: `item_detail` PATCH took
 * six fields and `list` was not one of them, so a misfiled task stayed
 * misfiled. Moving Areas moves Projects too, because a Project hangs off the
 * Area rather than off the task.
 */
export function moveTaskToArea(task: Task, listId: number | null): Promise<Task> {
  return request<Task>(task.url, "PATCH", { list: listId });
}

/** How pressing this is, relative to the rest. Writes through to the series,
 *  so a repeating task keeps it. */
export function updateTaskPriority(
  task: Task,
  priority: TaskPriority,
): Promise<Task> {
  return request<Task>(task.url, "PATCH", { priority });
}

export function updateTaskTags(task: Task, tags: string[]): Promise<Task> {
  return request<Task>(task.url, "PATCH", { tags });
}

export function updateTaskRecurrence(
  task: Task,
  recurrence: TaskRecurrence,
): Promise<Task> {
  return request<Task>(task.url, "PATCH", { recurrence });
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
  return request<Task>(task.url, "PATCH", { cadence_mode });
}

export function updateTaskNotes(task: Task, notes: string): Promise<Task> {
  return request<Task>(task.url, "PATCH", { notes });
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
  const payload = await requestPayload<Task>(task.url, "PATCH", { status });
  return {
    task: payload.data as Task,
    spawned: payload.spawned,
    spawnedChecklistSteps: payload.spawned_checklist_steps ?? [],
  };
}

export async function deleteTask(task: Task): Promise<number> {
  const result = await request<{ deleted: number }>(task.url, "DELETE");
  return result.deleted;
}

export function reorderTasks(url: string, orderedIds: number[]): Promise<Task[]> {
  return request<Task[]>(url, "POST", { ordered_ids: orderedIds });
}

export function createChecklistStep(
  url: string,
  text: string,
  carriesForward = true,
): Promise<ChecklistStep> {
  return request<ChecklistStep>(url, "POST", {
    text,
    carries_forward: carriesForward,
  });
}

export function updateChecklistStepDone(
  step: ChecklistStep,
  isDone: boolean,
): Promise<ChecklistStep> {
  return request<ChecklistStep>(step.url, "PATCH", { is_done: isDone });
}

export function updateChecklistStepCarriesForward(
  step: ChecklistStep,
  carriesForward: boolean,
): Promise<ChecklistStep> {
  return request<ChecklistStep>(step.url, "PATCH", {
    carries_forward: carriesForward,
  });
}

export function updateChecklistStepText(
  step: ChecklistStep,
  text: string,
): Promise<ChecklistStep> {
  return request<ChecklistStep>(step.url, "PATCH", { text });
}

export async function deleteChecklistStep(step: ChecklistStep): Promise<number> {
  const result = await request<{ deleted: number }>(step.url, "DELETE");
  return result.deleted;
}

/** Turns a step into a task of its own. Returns the new Task -- the step no
 * longer exists once this resolves. */
export function promoteChecklistStep(step: ChecklistStep): Promise<Task> {
  return request<Task>(step.promote_url, "POST");
}

export function reorderChecklistSteps(
  url: string,
  orderedIds: number[],
): Promise<ChecklistStep[]> {
  return request<ChecklistStep[]>(url, "POST", { ordered_ids: orderedIds });
}
