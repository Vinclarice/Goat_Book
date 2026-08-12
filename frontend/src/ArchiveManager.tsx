import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

import { deleteTask, updateTaskStatus } from "./api";
import { formatShortDate } from "./format";
import type { ArchiveWorkspaceData, Task } from "./types";

interface Props {
  initialData: ArchiveWorkspaceData;
}

export function ArchiveManager({ initialData }: Props) {
  const [items, setItems] = useState(initialData.items);
  // Tasks only carry an area_id -- title/url live once in `areas`.
  const areaById = useMemo(
    () => new Map(initialData.areas.map((each) => [each.id, each])),
    [initialData.areas],
  );
  // Same join, for project_id -- ui-second-pass-plan.md F2's third surface.
  const projectById = useMemo(
    () => new Map(initialData.projects.map((each) => [each.id, each])),
    [initialData.projects],
  );
  const [query, setQuery] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Task | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const workspaceRef = useRef<HTMLElement>(null);
  const deleteTriggerRef = useRef<HTMLButtonElement | null>(null);

  function focusWorkspace() {
    requestAnimationFrame(() => workspaceRef.current?.focus());
  }

  function closeDeleteDialog() {
    setPendingDelete(null);
    requestAnimationFrame(() => deleteTriggerRef.current?.focus());
  }

  useEffect(() => {
    if (!pendingDelete) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") closeDeleteDialog();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [pendingDelete]);

  const visibleItems = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return items;
    return items.filter(
      (item) =>
        item.text.toLocaleLowerCase().includes(normalized) ||
        (areaById.get(item.area_id)?.title ?? "")
          .toLocaleLowerCase()
          .includes(normalized),
    );
  }, [items, query, areaById]);

  async function restore(item: Task) {
    setBusyId(item.id);
    setError("");
    setNotice("");
    try {
      await updateTaskStatus(item, "completed");
      setItems((current) => current.filter((candidate) => candidate.id !== item.id));
      const areaTitle = areaById.get(item.area_id)?.title ?? "its area";
      setNotice(`Task restored to ${areaTitle}.`);
      focusWorkspace();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to restore task.");
    } finally {
      setBusyId(null);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    setBusyId(pendingDelete.id);
    setError("");
    setNotice("");
    try {
      await deleteTask(pendingDelete);
      setItems((current) =>
        current.filter((candidate) => candidate.id !== pendingDelete.id),
      );
      setNotice("Task permanently deleted.");
      setPendingDelete(null);
      focusWorkspace();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to delete task.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section
      ref={workspaceRef}
      className="max-w-3xl mx-auto px-4 py-8"
      aria-labelledby="archive-heading"
      tabIndex={-1}
    >
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="mb-1 text-xs font-bold uppercase tracking-wide text-muted-foreground">
            Kept for later
          </p>
          <h1 id="archive-heading" className="text-3xl font-bold tracking-tight">
            Done &amp; archived tasks
          </h1>
        </div>
        {items.length > 0 && (
          <span className="inline-flex min-h-11 items-center rounded-full border border-border px-4 text-sm text-muted-foreground whitespace-nowrap">
            {items.length} archived
          </span>
        )}
      </div>

      {items.length > 0 && (
        <label className="mb-5 flex h-11 w-full max-w-xs items-center gap-2 rounded-full border border-border px-3.5 text-sm text-muted-foreground focus-within:border-primary">
          <span className="sr-only">Search archived tasks</span>
          <span aria-hidden="true">⌕</span>
          <input
            className="w-full border-0 bg-transparent text-foreground outline-none placeholder:text-muted-foreground"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search archived tasks or areas"
          />
        </label>
      )}

      <div className="min-h-6 mb-2 text-sm" aria-live="polite">
        {error && <p className="text-destructive">{error}</p>}
        {!error && notice && <p className="text-muted-foreground">{notice}</p>}
      </div>

      {items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border px-5 py-6 text-sm text-muted-foreground">
          <p>Tasks moved to the archive will stay here until you restore or delete them.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {visibleItems.map((item) => {
            const itemArea = areaById.get(item.area_id);
            const itemProject = item.project_id ? projectById.get(item.project_id) : undefined;
            return (
            <article
              key={item.id}
              className="group flex items-start gap-3 rounded-xl border border-border bg-card px-4 py-3.5"
            >
              <span
                aria-hidden="true"
                className="mt-0.5 grid h-8 w-8 flex-none place-items-center rounded-lg border border-border text-sm text-muted-foreground"
              >
                ✓
              </span>
              <div className="min-w-0 flex-1">
                <strong className="block text-sm font-semibold text-foreground">
                  {item.text}
                </strong>
                <small className="mt-1 block text-xs text-muted-foreground">
                  {itemArea && (
                    <>From <a className="text-primary hover:underline" href={itemArea.url}>{itemArea.title}</a> · </>
                  )}
                  {itemProject && (
                    <><a className="text-primary hover:underline" href={itemProject.url}>{itemProject.title}</a> · </>
                  )}
                  {/* archived_at, not created_at -- this page is a record
                      of when work left the active list, not when it began.
                      Item's own CheckConstraint guarantees archived_at is
                      set for every status="archived" row, which is the
                      only status this page ever shows. */}
                  Archived{" "}
                  <time dateTime={item.archived_at!}>
                    {formatShortDate(item.archived_at!)}
                  </time>
                </small>
              </div>
              <span className="flex flex-none items-center gap-1.5 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 [@media(hover:none)]:opacity-100">
                <button
                  type="button"
                  className="inline-flex min-h-11 items-center rounded-md border border-border px-3 text-xs whitespace-nowrap text-muted-foreground hover:border-foreground/30 hover:text-foreground disabled:opacity-50"
                  onClick={() => restore(item)}
                  disabled={busyId === item.id}
                >
                  Restore
                </button>
                <button
                  type="button"
                  className="inline-flex min-h-11 items-center rounded-md border border-destructive/35 px-3 text-xs whitespace-nowrap text-destructive hover:bg-destructive/10 disabled:opacity-50"
                  onClick={(event) => {
                    deleteTriggerRef.current = event.currentTarget;
                    setPendingDelete(item);
                  }}
                  disabled={busyId === item.id}
                >
                  Delete
                </button>
              </span>
            </article>
            );
          })}
          {visibleItems.length === 0 && (
            <div className="rounded-lg border border-dashed border-border px-5 py-8 text-center text-sm text-muted-foreground">
              No archived tasks match your search.
            </div>
          )}
        </div>
      )}

      {pendingDelete && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4 backdrop-blur-sm">
          <div
            className="w-full max-w-md rounded-2xl border border-border bg-popover p-7 text-popover-foreground shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-task-heading"
          >
            <p className="mb-2 text-xs font-bold uppercase tracking-wide text-destructive">
              Permanent action
            </p>
            <h3 id="delete-task-heading" className="mb-3 text-lg font-bold">
              Delete this task?
            </h3>
            <p className="mb-6 text-sm text-muted-foreground">
              “{pendingDelete.text}” will be permanently removed. This cannot be
              undone.
            </p>
            <div className="flex flex-wrap justify-end gap-2.5">
              {/* Button's own size variants top out at h-9 (36px) -- none
                  reach the ~44px guideline this whole redesign otherwise
                  enforces via plain Tailwind classes, so it needs an
                  explicit override here. */}
              <Button
                type="button"
                variant="outline"
                className="h-11"
                onClick={closeDeleteDialog}
                disabled={busyId === pendingDelete.id}
                autoFocus
              >
                Keep task
              </Button>
              <Button
                type="button"
                variant="destructive"
                className="h-11"
                onClick={confirmDelete}
                disabled={busyId === pendingDelete.id}
              >
                {busyId === pendingDelete.id ? "Deleting…" : "Delete permanently"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
