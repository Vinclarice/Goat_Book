export type TaskStatus = "active" | "completed" | "archived";

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
  list: TaskListSummary;
  update_url: string;
  delete_url: string;
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
