import { FormEvent, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
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

import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { RouteFailure } from "./RouteFailure";
import { TaskWorkspace } from "../../TaskWorkspace";

export function AreaRoute() {
  const { areaId } = useParams();
  const id = Number(areaId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);

  const { data, error: loadError, isPending, refetch } = useQuery({
    queryKey: ["area", id],
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/areas/{area_id}", {
        params: { path: { area_id: id } },
      });
      if (!response.ok || !data) throw new RequestFailed(response.status);
      setTitle(data.area.title);
      return data;
    },
  });

  const renameMutation = useMutation({
    mutationFn: async (newTitle: string) => {
      const { data, error } = await apiV1.PATCH("/api/v1/areas/{area_id}", {
        params: { path: { area_id: id } },
        body: { title: newTitle },
      });
      if (error) throw new Error(typeof error === "string" ? error : "Rename failed.");
      return data;
    },
    onSuccess: (updated) => {
      setRenameError(null);
      setTitle(updated.title);
      queryClient.setQueryData(["area", id], (current: typeof data) =>
        current ? { ...current, area: { ...current.area, title: updated.title } } : current,
      );
    },
    onError: (mutationError: Error) => setRenameError(mutationError.message),
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const { error } = await apiV1.DELETE("/api/v1/areas/{area_id}", {
        params: { path: { area_id: id } },
      });
      if (error) throw error;
    },
    onSuccess: () => navigate("/agenda"),
  });

  // Only fetched for the "join a project" picker -- an area with no
  // project shown yet doesn't need the full list until someone opens it.
  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/projects");
      if (!response.ok || !data) throw new RequestFailed(response.status);
      return data;
    },
    enabled: !data?.project,
  });

  const projectMutation = useMutation({
    mutationFn: async (projectId: number | null) => {
      const { data, error } = await apiV1.PATCH("/api/v1/areas/{area_id}/project", {
        params: { path: { area_id: id } },
        body: { project_id: projectId },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      refetch();
      // This area's tasks change whichever project's open_task_count the
      // sidebar shows -- the one it just left, the one it just joined, or
      // both.
      queryClient.invalidateQueries({ queryKey: ["nav"] });
    },
  });

  function handleRename(event: FormEvent) {
    event.preventDefault();
    renameMutation.mutate(title);
  }

  function handleJoinProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const projectId = Number(new FormData(event.currentTarget).get("project_id"));
    if (projectId) projectMutation.mutate(projectId);
  }

  if (isPending) return <p className="p-6">Loading…</p>;
  if (loadError || !data) return <RouteFailure status={statusOf(loadError)} onRetry={() => refetch()} />;

  // ui-second-pass-plan.md F5: "a rename that looks like an edit field
  // until you notice the button." Disabled until the title actually
  // differs says there's nothing to save yet, rather than reading as a
  // live field with an inert button sitting beside it.
  const titleChanged = title.trim() !== data.area.title;

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      <Link to="/agenda" className="text-sm text-muted-foreground hover:text-foreground">
        ← Back to today
      </Link>

      <div className="flex items-start justify-between gap-4">
        <form onSubmit={handleRename} className="flex-1 flex flex-col gap-2">
          <label htmlFor="area-title" className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
            Area name
          </label>
          <div className="flex gap-2">
            <input
              id="area-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={100}
              required
              className="flex-1 rounded-lg border border-border bg-input px-3 py-1.5 text-lg font-bold text-foreground"
            />
            <Button type="submit" disabled={renameMutation.isPending || !titleChanged}>
              Save name
            </Button>
          </div>
          {renameError && <p className="text-sm text-destructive">{renameError}</p>}
        </form>

        {data.archived_count > 0 && (
          <a
            href={data.archive_url}
            className="text-sm text-muted-foreground hover:text-foreground whitespace-nowrap pt-6"
          >
            {data.archived_count} archived
          </a>
        )}
      </div>

      {/* Above the task list on purpose: a project is the coarser grouping.
          project-workspace-plan.md inverted the old containment (an Area
          held many Projects); an Area now optionally belongs to at most
          one. */}
      {data.project ? (
        <div className="flex items-center justify-between gap-2 rounded-lg border border-border px-4 py-2 text-sm">
          <span>
            Part of{" "}
            <Link to={`/projects/${data.project.id}`} className="font-bold hover:underline">
              {data.project.title}
            </Link>
          </span>
          <Button
            variant="ghost"
            size="sm"
            disabled={projectMutation.isPending}
            onClick={() => projectMutation.mutate(null)}
          >
            Remove from project
          </Button>
        </div>
      ) : (
        projects && projects.length > 0 && (
          <form
            onSubmit={handleJoinProject}
            className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm"
          >
            <label htmlFor="area-project" className="text-muted-foreground">
              Add to a project
            </label>
            <select
              id="area-project"
              name="project_id"
              className="rounded-lg border border-border bg-input px-2 py-1"
            >
              {projects.map((each) => (
                <option key={each.id} value={each.id}>
                  {each.title}
                </option>
              ))}
            </select>
            <Button type="submit" size="sm" disabled={projectMutation.isPending}>
              Add
            </Button>
          </form>
        )
      )}

      <TaskWorkspace initialData={data} />

      {/* ui-second-pass-plan.md F5: "two destructive actions with different
          scopes on one screen." Deleting the area used to sit directly
          above Projects' own per-row Delete project buttons -- two
          differently-scoped destructive actions a glance apart. Moved to
          its own section after everything else on the page, so reaching it
          takes a deliberate scroll past the area's own content rather than
          a stray click beside a much narrower delete. */}
      <div className="border-t border-border pt-6 space-y-2">
        <h2 className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
          Danger zone
        </h2>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="destructive" size="sm">
              Delete area
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete this area?</AlertDialogTitle>
              <AlertDialogDescription>
                <strong>{data.area.title}</strong> and all of its tasks will be permanently
                removed. This cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Keep area</AlertDialogCancel>
              <AlertDialogAction onClick={() => deleteMutation.mutate()}>
                Delete area permanently
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  );
}
