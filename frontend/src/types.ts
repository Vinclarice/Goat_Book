export type TaskStatus = "active" | "completed" | "archived";
export type TaskRecurrence = "none" | "daily" | "weekly" | "monthly";
export type ListColorKey =
  | "sky"
  | "sage"
  | "amber"
  | "lilac"
  | "coral"
  | "azure"
  | "blush"
  | "straw";

export interface TaskListSummary {
  id: number;
  title: string;
  url: string;
}

export interface Task {
  id: number;
  text: string;
  status: TaskStatus;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  archived_at: string | null;
  due_date: string | null;
  position: number;
  tags: string[];
  recurrence: TaskRecurrence;
  // Plain text, never Markdown. "" means no notes -- the API normalises
  // blank input to the empty string so this is never null.
  notes: string;
  // Just the id -- title/url live once in the page's top-level `lists`
  // array (see AgendaListSummary / ArchiveWorkspaceData.lists) instead of
  // being repeated on every task.
  list_id: number;
  // Covers both update (PATCH) and delete (DELETE); it's the same
  // endpoint either way.
  url: string;
  edit_url: string;
}

// release-d-plan.md 2: what a subtask actually is. No due date, no tags,
// cannot recur -- it dies with its task rather than carrying an independent
// archive state, so it has exactly one boolean instead of Task's three-way
// status.
export interface ChecklistStep {
  id: number;
  text: string;
  position: number;
  is_done: boolean;
  completed_at: string | null;
  // Whether this step reappears when its task's next recurring occurrence
  // is spawned. Only meaningful when the task actually recurs.
  carries_forward: boolean;
  task_id: number;
  // update and delete hit the same endpoint, same shape as Task.url.
  url: string;
  promote_url: string;
}

export interface TaskWorkspaceData {
  list: {
    id: number;
    title: string;
    create_item_url: string;
    reorder_url: string;
  };
  items: Task[];
}

export interface ArchiveWorkspaceData {
  items: Task[];
  lists: TaskListSummary[];
}

export type AgendaBucketKey =
  | "overdue"
  | "today"
  | "week"
  | "later"
  | "someday";

export interface AgendaBucket {
  key: AgendaBucketKey;
  label: string;
  collapsed: boolean;
}

export interface AgendaListSummary {
  id: number;
  title: string;
  url: string;
  create_item_url: string;
  open_count: number;
  overdue_count: number;
  color_key: ListColorKey;
}

export interface AgendaWorkspaceData {
  /** The server's idea of today, as YYYY-MM-DD. Bucketing compares due
   * dates against this as plain strings, which keeps the client and the
   * daily digest agreeing about what "overdue" means. */
  today: string;
  username: string;
  archive_url: string;
  archived_count: number;
  new_list_url: string;
  settings_url: string;
  daily_digest: boolean;
  buckets: AgendaBucket[];
  items: Task[];
  completed_today: Task[];
  lists: AgendaListSummary[];
}
