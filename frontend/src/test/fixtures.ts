import type { Task } from "../types";

export function task(overrides: Partial<Task> = {}): Task {
  return {
    id: 1,
    text: "Write tests",
    status: "active",
    created_at: "2026-07-24T12:00:00-04:00",
    updated_at: "2026-07-24T12:00:00-04:00",
    completed_at: null,
    archived_at: null,
    list: {
      id: 1,
      title: "Programming",
      url: "/lists/1/",
    },
    update_url: "/api/items/1/",
    delete_url: "/api/items/1/",
    ...overrides,
  };
}
