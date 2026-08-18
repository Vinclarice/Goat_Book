import { FormEvent, useEffect, useRef, useState } from "react";
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

import { colorForKey } from "../../agenda";
import { apiV1 } from "../../api/client";
import { RequestFailed, statusOf } from "../../api/failure";
import { ProjectComposition } from "./ProjectComposition";
import { RouteFailure } from "./RouteFailure";

/**
 * A project's own page -- project-workspace-plan.md. It never had one
 * before: the side nav's Projects group used to route back to a project's
 * area instead, because a project lived inside exactly one. Now it's the
 * container, and this is where it lives.
 */
export function ProjectRoute() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [draftArea, setDraftArea] = useState("");
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState("");

  const queryKey = ["project", id];

  const { data, error: loadError, isPending, refetch } = useQuery({
    queryKey,
    queryFn: async () => {
      const { data, response } = await apiV1.GET("/api/v1/projects/{project_id}", {
        params: { path: { project_id: id } },
      });
      if (!response.ok || !data) throw new RequestFailed(response.status);
      return data;
    },
  });

  // Seeded once per project, not on every settle of the query.
  //
  // These setters used to live inside the queryFn, so they re-ran on every
  // refetch -- and this page does not need an alt-tab to lose an edit, since
  // four of its own mutations call refresh() below, which invalidates this
  // very query. Retyping the title and then adding an area reseeded the
  // field from the server and the rename was gone. PreferencesRoute and
  // DayRoute already carry this guard; the ref holds *which* project was
  // seeded so navigating between two of them still loads the second.
  //
  // Both renames write their own result back through setTitle/setDueDate in
  // onSuccess, so nothing depends on the query re-seeding them.
  const seededFor = useRef<number | null>(null);
  useEffect(() => {
    if (!data || seededFor.current === id) return;
    seededFor.current = id;
    setTitle(data.title);
    setDueDate(data.due_date ?? "");
  }, [data, id]);

  // Only fetched for the "add an area" picker.
  const { data: nav } = useQuery({
    queryKey: ["nav"],
    queryFn: async () => {
      const { data, error } = await apiV1.GET("/api/v1/nav");
      if (error) throw error;
      return data;
    },
  });

  function refresh() {
    setError(null);
    return queryClient.invalidateQueries({ queryKey });
  }

  // Neither field had an editable home anywhere before this: the create
  // form only ever set a title (due_date always null), and this page only
  // ever offered complete/reopen/delete. The API already supported both
  // (ProjectUpdateIn), so this is a frontend-only gap.
  const renameProject = useMutation({
    mutationFn: async (newTitle: string) => {
      const { data, error } = await apiV1.PATCH("/api/v1/projects/{project_id}", {
        params: { path: { project_id: id } },
        body: { title: newTitle },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: (updated) => {
      setError(null);
      if (updated) setTitle(updated.title);
      queryClient.setQueryData(queryKey, (current: typeof data) =>
        current && updated ? { ...current, title: updated.title } : current,
      );
      // The sidebar's own Projects group shows each project's title.
      queryClient.invalidateQueries({ queryKey: ["nav"] });
    },
    onError: () => setError("Couldn't rename that project."),
  });

  const updateDueDate = useMutation({
    mutationFn: async (newDueDate: string) => {
      const { data, error } = await apiV1.PATCH("/api/v1/projects/{project_id}", {
        params: { path: { project_id: id } },
        body: { due_date: newDueDate || null },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: (updated) => {
      setError(null);
      if (updated) setDueDate(updated.due_date ?? "");
      queryClient.setQueryData(queryKey, (current: typeof data) =>
        current && updated
          ? { ...current, due_date: updated.due_date, is_overdue: updated.is_overdue }
          : current,
      );
    },
    onError: () => setError("Couldn't update that due date."),
  });

  const setCompleted = useMutation({
    mutationFn: async (isCompleted: boolean) => {
      const { data, error } = await apiV1.PATCH("/api/v1/projects/{project_id}", {
        params: { path: { project_id: id } },
        body: { is_completed: isCompleted },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      refresh();
      // The nav's own Projects group only lists open projects -- see
      // SideNav.tsx -- so completing or reopening one changes whether it
      // belongs there at all, not just its own page.
      queryClient.invalidateQueries({ queryKey: ["nav"] });
    },
    onError: () => setError("Couldn't update that project."),
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const { error } = await apiV1.DELETE("/api/v1/projects/{project_id}", {
        params: { path: { project_id: id } },
      });
      if (error) throw error;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["nav"] });
      navigate("/agenda");
    },
  });

  const removeArea = useMutation({
    mutationFn: async (areaId: number) => {
      const { error } = await apiV1.PATCH("/api/v1/areas/{area_id}/project", {
        params: { path: { area_id: areaId } },
        body: { project_id: null },
      });
      if (error) throw error;
    },
    onSuccess: () => {
      refresh();
      // The area it just left may have been carrying open tasks, which
      // changes this project's own open_task_count in the sidebar.
      queryClient.invalidateQueries({ queryKey: ["nav"] });
    },
    onError: () => setError("Couldn't remove that area."),
  });

  const addArea = useMutation({
    mutationFn: async (areaId: number) => {
      const { error } = await apiV1.PATCH("/api/v1/areas/{area_id}/project", {
        params: { path: { area_id: areaId } },
        body: { project_id: id },
      });
      if (error) throw error;
    },
    onSuccess: () => {
      refresh();
      queryClient.invalidateQueries({ queryKey: ["nav"] });
    },
    onError: () => setError("Couldn't add that area."),
  });

  function handleAddArea(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const areaId = Number(new FormData(event.currentTarget).get("area_id"));
    if (areaId) addArea.mutate(areaId);
  }

  const createArea = useMutation({
    mutationFn: async (title: string) => {
      const { error } = await apiV1.POST("/api/v1/projects/{project_id}/areas", {
        params: { path: { project_id: id } },
        body: { title },
      });
      if (error) throw error;
    },
    onSuccess: () => {
      setDraftArea("");
      refresh();
    },
    onError: () => setError("Couldn't create that area."),
  });

  function handleCreateArea(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = draftArea.trim();
    if (!title) return;
    createArea.mutate(title);
  }

  function handleRename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = title.trim();
    if (trimmed) renameProject.mutate(trimmed);
  }

  function handleSaveDueDate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    updateDueDate.mutate(dueDate);
  }

  if (isPending) return <p className="p-6">Loading…</p>;
  if (loadError || !data) return <RouteFailure status={statusOf(loadError)} onRetry={() => refetch()} />;

  const areaIds = new Set(data.areas.map((each) => each.id));
  const availableAreas = (nav?.areas ?? []).filter((each) => !areaIds.has(each.id));
  // ui-second-pass-plan.md F5's pattern, applied to both fields here: a
  // Save button that stays disabled until its own field actually differs
  // reads as "nothing to save yet" rather than a live control sitting next
  // to an inert button.
  const titleChanged = title.trim() !== data.title;
  const dueDateChanged = dueDate !== (data.due_date ?? "");

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      <Link to="/agenda" className="text-sm text-muted-foreground hover:text-foreground">
        ← Back to today
      </Link>

      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
            Project
          </p>

          <form onSubmit={handleRename} className="flex items-center gap-2 mt-1">
            <label htmlFor="project-title" className="sr-only">
              Project name
            </label>
            <input
              id="project-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={100}
              required
              className={
                data.is_completed
                  ? "flex-1 min-w-0 -ml-1 rounded-lg border border-transparent bg-transparent px-1 py-0.5 text-2xl font-bold text-muted-foreground line-through hover:border-border focus:border-border focus:outline-none"
                  : "flex-1 min-w-0 -ml-1 rounded-lg border border-transparent bg-transparent px-1 py-0.5 text-2xl font-bold hover:border-border focus:border-border focus:outline-none"
              }
            />
            <Button type="submit" size="sm" variant="secondary" disabled={renameProject.isPending || !titleChanged}>
              Save name
            </Button>
          </form>

          <form onSubmit={handleSaveDueDate} className="flex flex-wrap items-center gap-2 mt-2">
            <label htmlFor="project-due" className="text-sm text-muted-foreground">
              Due date
            </label>
            <input
              id="project-due"
              type="date"
              value={dueDate}
              onChange={(event) => setDueDate(event.target.value)}
              className="rounded-lg border border-border bg-input px-2 py-1 text-sm"
            />
            <Button type="submit" size="sm" variant="secondary" disabled={updateDueDate.isPending || !dueDateChanged}>
              Save date
            </Button>
            {data.is_overdue && (
              <span className="rounded-full border border-destructive/30 bg-destructive/10 px-2 py-0.5 text-xs font-bold text-destructive">
                ⚠ Overdue
              </span>
            )}
            {/* A blank date input reads the same whether nothing was ever
                set or someone meant to fill it in and didn't -- this says
                which one it is. */}
            {!dueDate && <span className="text-sm text-muted-foreground">No due date set</span>}
          </form>

          <p className="text-sm text-muted-foreground mt-2">{data.open_task_count} open</p>

          <div className="mt-3 max-w-xs">
            <ProjectComposition areas={data.areas} dimmed={data.is_completed} />
            <p className="text-sm text-muted-foreground mt-2">
              Each color is one of this project's areas — a wider segment
              means more open work there.
            </p>
          </div>
        </div>
        <Button
          size="sm"
          variant="secondary"
          disabled={setCompleted.isPending}
          onClick={() => setCompleted.mutate(!data.is_completed)}
        >
          {data.is_completed ? "Reopen" : "Mark complete"}
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="space-y-3">
        <h2 className="text-sm font-bold uppercase tracking-wide text-muted-foreground">
          Areas
        </h2>

        {data.areas.length === 0 ? (
          <p className="text-sm text-muted-foreground">No areas in this project yet.</p>
        ) : (
          <ul className="space-y-2">
            {data.areas.map((area) => (
              <li
                key={area.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card p-3"
              >
                <Link to={`/areas/${area.id}`} className="flex items-center gap-2 hover:underline">
                  <span
                    className="w-2.5 h-2.5 rounded-full"
                    aria-hidden="true"
                    style={{ background: colorForKey(area.color_key) }}
                  />
                  <span className="font-bold">{area.title}</span>
                  <span className="text-sm text-muted-foreground">
                    {area.overdue_count > 0 && `⚠ ${area.overdue_count} · `}
                    {area.open_count} open
                  </span>
                </Link>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={removeArea.isPending}
                  onClick={() => removeArea.mutate(area.id)}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        )}

        {/* Two ways in: an existing Area to reassign, or a brand new one --
            Vince's call, August 10, 2026, that a new area is the
            predominant case for a project, not reassigning one that
            already exists elsewhere. */}
        <form onSubmit={handleCreateArea} className="flex items-center gap-2">
          <label htmlFor="project-new-area" className="sr-only">
            New area name
          </label>
          <input
            id="project-new-area"
            value={draftArea}
            onChange={(event) => setDraftArea(event.target.value)}
            maxLength={100}
            placeholder="New area name…"
            className="flex-1 rounded-lg border border-border bg-input px-3 py-1.5 text-sm"
          />
          <Button type="submit" size="sm" disabled={createArea.isPending}>
            Create area
          </Button>
        </form>

        {availableAreas.length > 0 && (
          <form onSubmit={handleAddArea} className="flex items-center gap-2">
            <label htmlFor="project-area" className="sr-only">
              Add an existing area
            </label>
            <select
              id="project-area"
              name="area_id"
              className="rounded-lg border border-border bg-input px-2 py-1 text-sm"
            >
              {availableAreas.map((each) => (
                <option key={each.id} value={each.id}>
                  {each.title}
                </option>
              ))}
            </select>
            <Button type="submit" size="sm" variant="secondary" disabled={addArea.isPending}>
              Add existing area
            </Button>
          </form>
        )}
      </div>

      <div className="border-t border-border pt-6 space-y-2">
        <h2 className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
          Danger zone
        </h2>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="destructive" size="sm">
              Delete project
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete this project?</AlertDialogTitle>
              <AlertDialogDescription>
                Its areas will stay — deleting a project removes the grouping, not
                the work.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Keep project</AlertDialogCancel>
              <AlertDialogAction onClick={() => deleteMutation.mutate()}>
                Delete permanently
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  );
}
