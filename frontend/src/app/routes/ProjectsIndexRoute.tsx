import { Link } from "react-router";
import { useQuery } from "@tanstack/react-query";

import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { formatDateOnly } from "../../format";
import { RouteFailure } from "./RouteFailure";

/**
 * Every one of the caller's projects, open and completed alike -- the
 * nav's own Projects group only ever shows the open ones (same reason the
 * Agenda excludes completed tasks), so this is where a finished project
 * stays reachable. project-workspace-plan.md; the same gap /archive fills
 * for tasks.
 */
export function ProjectsIndexRoute() {
  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/projects");
      if (!response.ok || !data) throw new RequestFailed(response.status);
      return data;
    },
  });

  if (isPending) return <p className="p-6">Loading…</p>;
  if (error || !data) return <RouteFailure status={statusOf(error)} onRetry={() => refetch()} />;

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      <Link to="/agenda" className="text-sm text-muted-foreground hover:text-foreground">
        ← Back to today
      </Link>

      <h1 className="text-2xl font-bold">Projects</h1>

      {data.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No projects yet. Start one from the Agenda sidebar.
        </p>
      ) : (
        <ul className="space-y-2">
          {data.map((project) => (
            <li key={project.id}>
              <Link
                to={`/projects/${project.id}`}
                className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card p-3 hover:bg-muted"
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
                <span className="text-sm text-muted-foreground">
                  {project.open_task_count} open
                  {project.due_date && ` · due ${formatDateOnly(project.due_date)}`}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
