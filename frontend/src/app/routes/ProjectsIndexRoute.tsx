import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";

import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { formatDateOnly } from "../../format";
import type { Project } from "../../types";
import { ProjectComposition } from "./ProjectComposition";
import { RouteFailure } from "./RouteFailure";

/**
 * Every one of the caller's projects, open and completed alike -- the
 * nav's own Projects group only ever shows the open ones (same reason the
 * Agenda excludes completed tasks), so this is where a finished project
 * stays reachable. project-workspace-plan.md; the same gap /archive fills
 * for tasks.
 */
export function ProjectsIndexRoute() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [draftTitle, setDraftTitle] = useState("");
  const [draftDue, setDraftDue] = useState("");
  const [createError, setCreateError] = useState("");

  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/projects");
      if (!response.ok || !data) throw new RequestFailed(response.status);
      return data;
    },
  });

  // The predominant gap Vince named directly: creating a project used to
  // live only in the Agenda sidebar, a step removed from the page actually
  // about projects. Same shape as AgendaWorkspace's own createProject --
  // API-only, no Django form to post to, so a mutation and a router push
  // rather than a plain POST + reload.
  const createProject = useMutation({
    mutationFn: async () => {
      const { data, error } = await apiV1.POST("/api/v1/projects", {
        body: { title: draftTitle.trim(), due_date: draftDue || null },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["nav"] });
      navigate(`/projects/${project.id}`);
    },
    onError: () => setCreateError("Couldn't create that project."),
  });

  function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draftTitle.trim()) return;
    setCreateError("");
    createProject.mutate();
  }

  if (isPending) return <p className="p-6">Loading…</p>;
  if (error || !data) return <RouteFailure status={statusOf(error)} onRetry={() => refetch()} />;

  // The API already orders open before completed (Project.Meta.ordering) --
  // this only splits that single list into the two sections below, it
  // doesn't re-sort anything.
  // Three groups, not two -- v2 increment 3. A parked project is neither
  // finished nor being worked on, and leaving it among the open ones would
  // make the pause cosmetic exactly where somebody scans for what is active.
  //
  // Completed is tested first because `complete_project` clears the pause, so
  // the two can never both hold; the order is stated rather than relied on.
  const completed = data.filter((project) => project.is_completed);
  const paused = data.filter(
    (project) => !project.is_completed && project.paused_at,
  );
  const open = data.filter(
    (project) => !project.is_completed && !project.paused_at,
  );

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      <Link to="/agenda" className="text-sm text-muted-foreground hover:text-foreground">
        ← Back to today
      </Link>

      <h1 className="text-2xl font-bold">Projects</h1>

      <form onSubmit={handleCreate} className="flex flex-wrap items-center gap-2">
        <label htmlFor="new-project-title" className="sr-only">
          Project name
        </label>
        <input
          id="new-project-title"
          value={draftTitle}
          onChange={(event) => setDraftTitle(event.target.value)}
          maxLength={100}
          placeholder="New project name…"
          className="flex-1 min-w-48 rounded-lg border border-border bg-input px-3 py-1.5 text-sm"
        />
        <label htmlFor="new-project-due" className="sr-only">
          Due date (optional)
        </label>
        <input
          id="new-project-due"
          type="date"
          value={draftDue}
          onChange={(event) => setDraftDue(event.target.value)}
          className="rounded-lg border border-border bg-input px-2 py-1.5 text-sm"
        />
        <Button type="submit" size="sm" disabled={createProject.isPending || !draftTitle.trim()}>
          Create project
        </Button>
      </form>
      {createError && <p className="text-sm text-destructive">{createError}</p>}

      {data.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No projects yet. Start one above.
        </p>
      ) : (
        <div className="space-y-8">
          {/* Said once above the whole grid rather than repeated per card --
              the composition bar's per-segment name and count only surface
              on hover, which a touch device can't do at all. */}
          <p className="text-sm text-muted-foreground max-w-xl">
            Each project's colored strip shows how its open work is split
            across areas.
          </p>

          <ProjectGrid projects={open} />

          {paused.length > 0 && (
            <div className="space-y-3">
              <h2 className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                Paused
              </h2>
              {/* Dimmed like the completed group, because both are "not the
                  work in front of you" -- but kept above it, since a paused
                  project is one decision away from being active again and a
                  finished one is not. */}
              <ProjectGrid projects={paused} dimmed />
            </div>
          )}

          {completed.length > 0 && (
            <div className="space-y-3">
              <h2 className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                Completed
              </h2>
              <ProjectGrid projects={completed} dimmed />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ProjectGrid({ projects, dimmed = false }: { projects: Project[]; dimmed?: boolean }) {
  if (projects.length === 0) {
    return <p className="text-sm text-muted-foreground">Nothing open right now.</p>;
  }

  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {projects.map((project) => (
        <li key={project.id}>
          <Link
            to={`/projects/${project.id}`}
            className="flex h-full flex-col gap-3 rounded-lg border border-border bg-card p-4 hover:border-foreground/24"
          >
            <span
              className={
                project.is_completed
                  ? "font-bold text-muted-foreground line-through"
                  : "font-bold"
              }
            >
              {project.title}
            </span>

            <ProjectComposition areas={project.areas} dimmed={dimmed} />

            <span className="mt-auto text-sm text-muted-foreground">
              {project.areas.length === 1 ? "1 area" : `${project.areas.length} areas`}
              {" · "}
              {project.open_task_count} open
              {project.due_date && (
                <>
                  {" · "}
                  {project.is_overdue ? (
                    <span className="font-bold text-destructive">
                      ⚠ overdue · {formatDateOnly(project.due_date)}
                    </span>
                  ) : (
                    `due ${formatDateOnly(project.due_date)}`
                  )}
                </>
              )}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
