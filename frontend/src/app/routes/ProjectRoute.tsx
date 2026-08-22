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
import { ProjectBrief } from "./ProjectBrief";
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
  // What the project is for, in the person's own words --
  // planning-assistant-plan.md increment 3. Optional by design: requiring it
  // would put a writing task in front of somebody who wants to group three
  // areas.
  const [purpose, setPurpose] = useState("");
  const [outcome, setOutcome] = useState("");
  // What going wrong looks like — S10, and D4's answer that this is not
  // the outcome above. A tripwire you cannot tell from an ambition can
  // never be checked, so it gets its own box rather than sharing one.
  const [abandonIf, setAbandonIf] = useState("");

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
    // `?? ""` is belt and braces: the field is blank-not-null all the way
    // through, so the server never sends null. A textarea given undefined
    // would go uncontrolled and React would warn on the first keystroke.
    setPurpose(data.purpose ?? "");
    setOutcome(data.desired_outcome ?? "");
    setAbandonIf(data.abandon_if ?? "");
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

  const updatePurpose = useMutation({
    mutationFn: async (newPurpose: string) => {
      const { data, error } = await apiV1.PATCH("/api/v1/projects/{project_id}", {
        params: { path: { project_id: id } },
        // "" clears it, and absent means leave alone -- no null dance, unlike
        // due_date above. The field is blank-not-null, which frees null at the
        // boundary to mean exactly one thing.
        body: { purpose: newPurpose },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: (updated) => {
      setError(null);
      if (updated) setPurpose(updated.purpose);
      queryClient.setQueryData(queryKey, (current: typeof data) =>
        current && updated ? { ...current, purpose: updated.purpose } : current,
      );
    },
    onError: () => setError("Couldn't save that purpose."),
  });

  // What done looks like — v2 increment 3. Its own field and its own control,
  // mirroring the purpose above rather than sharing its save: they are two
  // answers a person gives at different moments, and one button writing both
  // would make "save" mean whichever box was touched last.
  const updateOutcome = useMutation({
    mutationFn: async (newOutcome: string) => {
      const { data, error } = await apiV1.PATCH("/api/v1/projects/{project_id}", {
        params: { path: { project_id: id } },
        body: { desired_outcome: newOutcome },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: (updated) => {
      setError(null);
      if (updated) setOutcome(updated.desired_outcome);
      queryClient.setQueryData(queryKey, (current: typeof data) =>
        current && updated
          ? { ...current, desired_outcome: updated.desired_outcome }
          : current,
      );
    },
    onError: () => setError("Couldn't save that outcome."),
  });

  // Its own control and its own save, mirroring the outcome above for the
  // reason given there: they are answers a person gives at different moments,
  // and one button writing both would make "save" mean whichever box was
  // touched last.
  const updateAbandonIf = useMutation({
    mutationFn: async (next: string) => {
      const { data, error } = await apiV1.PATCH("/api/v1/projects/{project_id}", {
        params: { path: { project_id: id } },
        body: { abandon_if: next },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: (updated) => {
      setError(null);
      if (updated) setAbandonIf(updated.abandon_if);
      queryClient.setQueryData(queryKey, (current: typeof data) =>
        current && updated
          ? { ...current, abandon_if: updated.abandon_if }
          : current,
      );
    },
    onError: () => setError("Couldn't save that."),
  });

  // Parked, not finished. A boolean on the same PATCH as `is_completed`,
  // because both answer "which state is this project in".
  const setPaused = useMutation({
    mutationFn: async (isPaused: boolean) => {
      const { data, error } = await apiV1.PATCH("/api/v1/projects/{project_id}", {
        params: { path: { project_id: id } },
        body: { is_paused: isPaused },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey });
    },
    onError: () => setError("Couldn't change that."),
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

  function handleSavePurpose(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    updatePurpose.mutate(purpose);
  }

  function handleSaveAbandonIf(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    updateAbandonIf.mutate(abandonIf);
  }

  function handleSaveOutcome(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    updateOutcome.mutate(outcome);
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
  // Trimmed on both sides, matching the server, so trailing whitespace alone
  // never enables the button and never writes.
  const purposeChanged = purpose.trim() !== (data.purpose ?? "").trim();
  const outcomeChanged = outcome.trim() !== (data.desired_outcome ?? "").trim();
  const abandonIfChanged =
    abandonIf.trim() !== (data.abandon_if ?? "").trim();

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

          {/* What this project is for. Optional, and the only field here a
              matcher reads: planning-assistant-plan.md increment 4 anchors a
              project's brief on exactly this text, which is why the empty
              hint says what is lost rather than just noting the blank. */}
          <form onSubmit={handleSavePurpose} className="mt-3">
            <label
              htmlFor="project-purpose"
              className="block text-sm text-muted-foreground"
            >
              Purpose
            </label>
            <textarea
              id="project-purpose"
              rows={2}
              value={purpose}
              onChange={(event) => setPurpose(event.target.value)}
              placeholder="What is this project for, and what would tell you it went wrong?"
              className="mt-1 w-full rounded-lg border border-border bg-input px-2 py-1 text-sm"
            />
            <div className="flex flex-wrap items-center gap-2 mt-1">
              <Button
                type="submit"
                size="sm"
                variant="secondary"
                disabled={updatePurpose.isPending || !purposeChanged}
              >
                Save purpose
              </Button>
              {!purpose.trim() && (
                <span className="text-sm text-muted-foreground">
                  No purpose written — a brief has nothing to work from yet
                </span>
              )}
            </div>
          </form>

          {/* What done looks like -- v2 increment 3. Beside the purpose rather
              than inside it: "why I am doing this" and "what would be true
              when it is finished" are different answers, and a person asked
              for both in one box writes one of them.

              It is also the second thing the brief retrieves against, and the
              more useful of the two for that — an outcome names concrete
              things ("the booking form is live") where a purpose names
              abstract ones, and concrete nouns are what the rare-term gate can
              select on.

              **S10's abandonment condition has its own box below**, since
              August 22 — D4 answered, and answered *two fields*: a tripwire you
              cannot tell from an ambition can never be checked. */}
          <form onSubmit={handleSaveOutcome} className="mt-3">
            <label
              htmlFor="project-outcome"
              className="block text-sm text-muted-foreground"
            >
              What done looks like
            </label>
            <textarea
              id="project-outcome"
              rows={2}
              value={outcome}
              onChange={(event) => setOutcome(event.target.value)}
              placeholder="What would be true when this is finished?"
              className="mt-1 w-full rounded-lg border border-border bg-input px-2 py-1 text-sm"
            />
            <div className="flex flex-wrap items-center gap-2 mt-1">
              <Button
                type="submit"
                size="sm"
                variant="secondary"
                disabled={updateOutcome.isPending || !outcomeChanged}
              >
                Save outcome
              </Button>
            </div>
          </form>

          {/* What going wrong looks like — S10's done-means, and the field its
              verdict turned on. Deliberately *below* the outcome and not
              beside it: they are the two ends of how a project finishes, and
              reading one immediately after the other is what makes the
              distinction obvious rather than a matter of remembering which box
              is which. */}
          <form onSubmit={handleSaveAbandonIf} className="mt-3">
            <label
              htmlFor="project-abandon-if"
              className="block text-sm text-muted-foreground"
            >
              What would tell you it went wrong
            </label>
            <textarea
              id="project-abandon-if"
              rows={2}
              value={abandonIf}
              onChange={(event) => setAbandonIf(event.target.value)}
              placeholder="What would mean this is worth stopping?"
              className="mt-1 w-full rounded-lg border border-border bg-input px-2 py-1 text-sm"
            />
            <div className="flex flex-wrap items-center gap-2 mt-1">
              <Button
                type="submit"
                size="sm"
                variant="secondary"
                disabled={updateAbandonIf.isPending || !abandonIfChanged}
              >
                Save
              </Button>
            </div>
          </form>

          <p className="text-sm text-muted-foreground mt-2">{data.open_task_count} open</p>

          <div className="mt-3 max-w-xs">
            <ProjectComposition areas={data.areas} dimmed={data.is_completed} />
            <p className="text-sm text-muted-foreground mt-2">
              Each color is one of this project's areas — a wider segment
              means more open work there.
            </p>
          </div>

          {/* Reads the live field rather than `data.purpose`, so writing a
              purpose and asking for a brief in the same visit stops offering
              the "needs a purpose" explanation the moment it stops being
              true. */}
          <ProjectBrief projectId={id} hasPurpose={Boolean(purpose.trim())} />
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {/* Said on the page, because a parked project that looked identical
              to an active one would make the state cosmetic. Not shown on a
              completed one: `complete_project` clears the pause, so the two
              can never both be true and only one of them is worth saying. */}
          {data.paused_at && !data.is_completed && (
            <span className="text-sm text-muted-foreground">Paused</span>
          )}
          {/* Offered only while the project is open. Pausing something already
              finished is a state with no meaning, and hiding the control is
              cheaper than a rule explaining why it does nothing. */}
          {!data.is_completed && (
            <Button
              size="sm"
              variant="secondary"
              disabled={setPaused.isPending}
              onClick={() => setPaused.mutate(!data.paused_at)}
            >
              {data.paused_at ? "Resume" : "Pause"}
            </Button>
          )}
          <Button
            size="sm"
            variant="secondary"
            disabled={setCompleted.isPending}
            onClick={() => setCompleted.mutate(!data.is_completed)}
          >
            {data.is_completed ? "Reopen" : "Mark complete"}
          </Button>
        </div>
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
