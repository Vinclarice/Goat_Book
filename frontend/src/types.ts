export type TaskStatus = "active" | "completed" | "archived";
export type TaskRecurrence = "none" | "daily" | "weekly" | "monthly";

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
  list: TaskListSummary;
  update_url: string;
  delete_url: string;
  edit_url: string;
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
