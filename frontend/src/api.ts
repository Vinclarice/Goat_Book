import type { Task, TaskRecurrence, TaskStatus } from "./types";

interface ApiErrors {
  [field: string]: string[];
}

interface ApiResponse<T> {
  data?: T;
  spawned?: Task;
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

export function updateTaskTags(task: Task, tags: string[]): Promise<Task> {
  return request<Task>(task.url, "PATCH", { tags });
}

export function updateTaskRecurrence(
  task: Task,
  recurrence: TaskRecurrence,
): Promise<Task> {
  return request<Task>(task.url, "PATCH", { recurrence });
}

export interface StatusUpdateResult {
  task: Task;
  /** Set when completing a recurring task auto-archives it and creates
   * the next occurrence in the same request. */
  spawned?: Task;
}

export async function updateTaskStatus(
  task: Task,
  status: TaskStatus,
): Promise<StatusUpdateResult> {
  const payload = await requestPayload<Task>(task.url, "PATCH", { status });
  return { task: payload.data as Task, spawned: payload.spawned };
}

export async function deleteTask(task: Task): Promise<number> {
  const result = await request<{ deleted: number }>(task.url, "DELETE");
  return result.deleted;
}

export function reorderTasks(
  url: string,
  orderedIds: number[],
): Promise<Task[]> {
  return request<Task[]>(url, "POST", { ordered_ids: orderedIds });
}
