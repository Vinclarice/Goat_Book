import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";

import { apiV1 } from "./api/client";
import { RequestFailed } from "./api/failure";
import type { Project } from "./types";

/** A project's due date, which is a plain date rather than an instant.
 *
 * `format.ts`'s formatDate renders a timestamp and would turn 2026-09-30
 * into an evening in the browser's zone. Parsed into parts here instead so a
 * date the server calls the 30th never displays as the 29th.
 */
function formatDueDate(value: string): string {
  const [year, month, day] = value.split("-").map(Number);
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(year, month - 1, day));
}

function messageFrom(error: unknown, fallback: string): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

/**
 * Projects live on the Area page because a project belongs to exactly one
 * Area -- `Project.area` is required, and `set_task_project` refuses a task
 * from anywhere else. Rendering them anywhere else would show a grouping
 * next to work it cannot contain.
 *
 * release-d-plan.md 5 slice 8. Creating, completing and deleting only; which
 * tasks are in a project is set from the task's own detail page, alongside
 * every other single-field task edit.
 */
export function ProjectsPanel({ areaId }: { areaId: number }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  const queryKey = ["projects", areaId];

  const { data, isPending } = useQuery({
    queryKey,
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/projects", {
        params: { query: { area_id: areaId } },
      });
      if (!response.ok || !data) throw new RequestFailed(response.status);
      return data as Project[];
    },
  });

  function refresh() {
    setError(null);
    return queryClient.invalidateQueries({ queryKey });
  }

  const create = useMutation({
    mutationFn: async (title: string) => {
      const { data, error } = await apiV1.POST("/api/v1/projects", {
        body: { area_id: areaId, title, due_date: null },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      setDraft("");
      refresh();
    },
    onError: (caught) =>
      setError(messageFrom(caught, "Couldn't add that project.")),
  });

  const setCompleted = useMutation({
    mutationFn: async ({
      project,
      isCompleted,
    }: {
      project: Project;
      isCompleted: boolean;
    }) => {
      const { data, error } = await apiV1.PATCH("/api/v1/projects/{project_id}", {
        params: { path: { project_id: project.id } },
        body: { is_completed: isCompleted },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => refresh(),
    onError: (caught) =>
      setError(messageFrom(caught, "Couldn't update that project.")),
  });

  const remove = useMutation({
    mutationFn: async (project: Project) => {
      const { error } = await apiV1.DELETE("/api/v1/projects/{project_id}", {
        params: { path: { project_id: project.id } },
      });
      if (error) throw error;
    },
    onSuccess: () => refresh(),
    onError: (caught) =>
      setError(messageFrom(caught, "Couldn't delete that project.")),
  });

  function handleCreate(event: FormEvent) {
    event.preventDefault();
    const title = draft.trim();
    // Guarded here as well as at the server: an empty submit that produces a
    // round trip and an error banner is a worse answer than one that does
    // nothing, and the server still owns the rule.
    if (!title) return;
    create.mutate(title);
  }

  const projects = data ?? [];

  return (
    <section className="space-y-3" aria-labelledby="projects-heading">
      <div className="flex items-baseline justify-between gap-4">
        <h2 id="projects-heading" className="text-sm font-bold uppercase tracking-wide text-muted-foreground">
          Projects
        </h2>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {isPending ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : projects.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No projects in this area yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {projects.map((project) => (
            <li
              key={project.id}
              className="rounded-lg border border-border bg-card p-3 space-y-1"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-0.5">
                  <p
                    className={
                      project.is_completed
                        ? "font-bold text-muted-foreground line-through"
                        : "font-bold"
                    }
                  >
                    {project.title}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {project.open_task_count} open
                    {project.due_date && ` · due ${formatDueDate(project.due_date)}`}
                  </p>
                </div>

                <div className="flex shrink-0 gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={setCompleted.isPending}
                    onClick={() =>
                      setCompleted.mutate({
                        project,
                        isCompleted: !project.is_completed,
                      })
                    }
                  >
                    {project.is_completed ? "Reopen" : "Mark complete"}
                  </Button>

                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button size="sm" variant="destructive">
                        Delete project
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>
                          Delete {project.title}?
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                          Its tasks will stay in this area — deleting a project
                          removes the grouping, not the work.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Keep project</AlertDialogCancel>
                        <AlertDialogAction onClick={() => remove.mutate(project)}>
                          Delete permanently
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </div>

              {/* Said out loud rather than left to be assumed. Completing a
                  project deliberately does not touch its tasks (charter rule
                  5), and someone who expects it to tidy up would otherwise
                  find out by discovering the tasks later. */}
              {!project.is_completed && project.open_task_count > 0 && (
                <p className="text-xs text-muted-foreground">
                  {project.open_task_count} open{" "}
                  {project.open_task_count === 1 ? "task" : "tasks"} stay open if
                  you complete this.
                </p>
              )}
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={handleCreate} className="flex gap-2">
        <label className="sr-only" htmlFor="new-project">
          New project
        </label>
        <input
          id="new-project"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          maxLength={100}
          placeholder="Add a project…"
          className="flex-1 rounded-lg border border-border bg-input px-3 py-1.5 text-sm"
        />
        <Button type="submit" size="sm" disabled={create.isPending}>
          Add project
        </Button>
      </form>
    </section>
  );
}
