import { Component, type ReactNode } from "react";
import { createRoot } from "react-dom/client";

import { ArchiveManager } from "./ArchiveManager";
import { TaskWorkspace } from "./TaskWorkspace";
import type { ArchiveWorkspaceData, TaskWorkspaceData } from "./types";

function readData<T>(id: string): T {
  const element = document.getElementById(id);
  if (!element?.textContent) throw new Error(`Missing bootstrap data: ${id}`);
  return JSON.parse(element.textContent) as T;
}

interface BoundaryProps {
  rootId: string;
  fallbackId: string;
  children: ReactNode;
}

class MountBoundary extends Component<BoundaryProps> {
  componentDidCatch(error: Error) {
    console.error("A Clarice enhancement stopped unexpectedly.", error);
    const root = document.getElementById(this.props.rootId);
    const fallback = document.getElementById(this.props.fallbackId);
    if (root) root.hidden = true;
    if (fallback) fallback.hidden = false;
  }

  render() {
    return this.props.children;
  }
}

function mountTaskWorkspace() {
  const rootElement = document.getElementById("task-workspace-root");
  const fallback = document.getElementById("task-workspace-fallback");
  if (!rootElement || !fallback) return;

  const data = readData<TaskWorkspaceData>("task-workspace-data");
  createRoot(rootElement).render(
    <MountBoundary
      rootId="task-workspace-root"
      fallbackId="task-workspace-fallback"
    >
      <TaskWorkspace initialData={data} />
    </MountBoundary>,
  );
  rootElement.hidden = false;
  fallback.hidden = true;
}

function mountArchiveManager() {
  const rootElement = document.getElementById("archive-manager-root");
  const fallback = document.getElementById("archive-manager-fallback");
  if (!rootElement || !fallback) return;

  const data = readData<ArchiveWorkspaceData>("archive-manager-data");
  createRoot(rootElement).render(
    <MountBoundary
      rootId="archive-manager-root"
      fallbackId="archive-manager-fallback"
    >
      <ArchiveManager initialData={data} />
    </MountBoundary>,
  );
  rootElement.hidden = false;
  fallback.hidden = true;
}

try {
  mountTaskWorkspace();
  mountArchiveManager();
} catch (error) {
  console.error("Clarice enhancements could not start.", error);
}
