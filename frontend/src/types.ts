export type TaskStatus = "active" | "completed" | "archived";
/** How a repeating task's next due date is worked out.
 *
 * "anchored" keeps the calendar rule -- the mortgage is due on the 1st whether
 * or not last month's was paid on time. "floating" counts from when the work
 * was actually done -- a furnace filter lasts a month from the change, not from
 * a date nobody acted on. Null when the task does not repeat at all.
 */
export type CadenceMode = "anchored" | "floating";

export type TaskRecurrence =
  | "none"
  | "daily"
  | "weekly"
  | "fortnightly"
  | "monthly"
  | "quarterly"
  | "annual";
/** No "medium": an unmarked task already means ordinary. */
export type TaskPriority = "none" | "high" | "low";

/** What a task costs, when it is a bill. Null on the task when it is not.
 *  `amount` is a string because the column exists to avoid binary rounding
 *  and a JS number would put it straight back. */
export interface TaskBill {
  amount: string | null;
  currency: string;
  payee: string;
}
export type AreaColorKey =
  | "sky"
  | "sage"
  | "amber"
  | "lilac"
  | "coral"
  | "azure"
  | "blush"
  | "straw";

export interface TaskAreaSummary {
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
  priority: TaskPriority;
  lead_days: number;
  bill: TaskBill | null;
  // Plain text, never Markdown. "" means no notes -- the API normalises
  // blank input to the empty string so this is never null.
  notes: string;
  // Just the id -- title/url live once in the page's top-level `areas`
  // array (see AgendaAreaSummary / ArchiveWorkspaceData.areas) instead of
  // being repeated on every task.
  //
  // Null for a task standing on its own, since August 14, 2026: a commitment
  // accepted from the knowledge core has no Area, because asking which one at
  // that moment is the filing question the design refuses to ask. Every lookup
  // through this already guards with `taskArea && ...`, so an unfiled task
  // renders without an area chip rather than with a broken one.
  area_id: number | null;
  // Null for most tasks. Derived through the task's own Area now --
  // project-workspace-plan.md 2 -- rather than settable on the task
  // directly: a task belongs to a project only by belonging to an Area
  // that's inside it.
  project_id: number | null;
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

// project-workspace-plan.md: a standalone workspace that can hold one or
// more Areas, inverted from release-d-plan.md 3's original "lives inside
// one Area" shape.
export interface ProjectArea {
  id: number;
  title: string;
  open_count: number;
  overdue_count: number;
  color_key: AreaColorKey;
}

export interface Project {
  id: number;
  title: string;
  due_date: string | null;
  is_completed: boolean;
  completed_at: string | null;
  created_at: string;
  // Annotated by the server's read, not derived here: the panel shows how
  // much is still open in a project without fetching its tasks.
  open_task_count: number;
  areas: ProjectArea[];
  // The server's own "today", never the browser's -- principles.md's
  // "the server owns business meaning" applied to the same overdue rule
  // tasks and areas already carry.
  is_overdue: boolean;
}

export interface TaskWorkspaceData {
  area: {
    id: number;
    title: string;
    create_item_url: string;
    reorder_url: string;
  };
  items: Task[];
  // Singular and optional -- project-workspace-plan.md 2 inverted this: an
  // Area belongs to at most one Project, not the other way around.
  project: AgendaProjectSummary | null;
}

export interface ArchiveWorkspaceData {
  items: Task[];
  areas: TaskAreaSummary[];
  projects: AgendaProjectSummary[];
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

export interface AgendaAreaSummary {
  id: number;
  title: string;
  url: string;
  create_item_url: string;
  open_count: number;
  overdue_count: number;
  color_key: AreaColorKey;
}

// ui-second-pass-plan.md F2: a task's project_id had nothing to join
// against, so its row could never show a project. url points at the
// project's own page -- project-workspace-plan.md gave it one.
export interface AgendaProjectSummary {
  id: number;
  title: string;
  url: string;
}

export interface AgendaWorkspaceData {
  /** The server's idea of today, as YYYY-MM-DD. Bucketing compares due
   * dates against this as plain strings, which keeps the client and the
   * daily digest agreeing about what "overdue" means. */
  today: string;
  username: string;
  archive_url: string;
  archived_count: number;
  settings_url: string;
  daily_digest: boolean;
  buckets: AgendaBucket[];
  items: Task[];
  completed_today: Task[];
  areas: AgendaAreaSummary[];
  projects: AgendaProjectSummary[];
}
