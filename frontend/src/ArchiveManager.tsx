import { useEffect, useMemo, useRef, useState } from "react";

import { deleteTask, updateTaskStatus } from "./api";
import { formatDate } from "./format";
import styles from "./workspace.module.css";
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
      className="lists-section archived-section"
      aria-labelledby="archive-heading"
      tabIndex={-1}
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">Kept for later</p>
          <h2 id="archive-heading">Done &amp; archived tasks</h2>
        </div>
        {items.length > 0 && <span className="list-count">{items.length} archived</span>}
      </div>

      {items.length > 0 && (
        <label className={styles.archiveSearch}>
          <span className="visually-hidden">Search archived tasks</span>
          <input
            className="form-control"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search archived tasks or areas"
          />
        </label>
      )}

      <div className={styles.feedback} aria-live="polite">
        {error && <p className={styles.error}>{error}</p>}
        {!error && notice && <p>{notice}</p>}
      </div>

      {items.length === 0 ? (
        <div className="archive-empty-state">
          <p>Tasks moved to the archive will stay here until you restore or delete them.</p>
        </div>
      ) : (
        <div className="list-panel archived-list-panel">
          {visibleItems.map((item) => {
            const itemArea = areaById.get(item.area_id);
            const itemProject = item.project_id ? projectById.get(item.project_id) : undefined;
            return (
            <article className="archived-task-row" key={item.id}>
              <span className="list-icon archive-icon" aria-hidden="true">✓</span>
              <span className="list-row-copy">
                <strong>{item.text}</strong>
                <small>
                  {itemArea && (
                    <>From <a href={itemArea.url}>{itemArea.title}</a> · </>
                  )}
                  {itemProject && (
                    <><a href={itemProject.url}>{itemProject.title}</a> · </>
                  )}
                  Created{" "}
                  <time dateTime={item.created_at}>{formatDate(item.created_at)}</time>
                </small>
              </span>
              <span className="task-actions">
                <button
                  className="btn btn-outline-light btn-sm"
                  type="button"
                  onClick={() => restore(item)}
                  disabled={busyId === item.id}
                >
                  Restore
                </button>
                <button
                  className="btn btn-outline-danger btn-sm"
                  type="button"
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
            <div className={styles.empty}>No archived tasks match your search.</div>
          )}
        </div>
      )}

      {pendingDelete && (
        <div className={styles.dialogBackdrop}>
          <div
            className={styles.dialog}
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-task-heading"
          >
            <p className="eyebrow">Permanent action</p>
            <h3 id="delete-task-heading">Delete this task?</h3>
            <p>
              “{pendingDelete.text}” will be permanently removed. This cannot be
              undone.
            </p>
            <div className="confirmation-actions">
              <button
                className="btn btn-outline-light"
                type="button"
                onClick={closeDeleteDialog}
                disabled={busyId === pendingDelete.id}
                autoFocus
              >
                Keep task
              </button>
              <button
                className="btn btn-danger"
                type="button"
                onClick={confirmDelete}
                disabled={busyId === pendingDelete.id}
              >
                {busyId === pendingDelete.id ? "Deleting…" : "Delete permanently"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
