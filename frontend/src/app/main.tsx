import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router";

import { AppLayout } from "./AppLayout";
import { AgendaRoute } from "./routes/AgendaRoute";
import { ArchiveRoute } from "./routes/ArchiveRoute";
import { DevUiGallery } from "./routes/DevUiGallery";
import { ListRoute } from "./routes/ListRoute";
import { PreferencesRoute } from "./routes/PreferencesRoute";
import { TaskDetailRoute } from "./routes/TaskDetailRoute";

// openapi-fetch never throws on a non-2xx response (it returns
// {data, error}), so TanStack Query can't tell a permanent 404/401 apart
// from a transient network failure -- without this, every route's own
// Vitest suite sets retry: false locally, but the real app would retry
// (and hang on "Loading...") for ordinary cases like a deleted list or
// an archived task.
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

const rootElement = document.getElementById("app-root");

if (rootElement) {
  createRoot(rootElement).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter basename="/app">
          <Routes>
            {/* Everything sits inside AppLayout so the side nav stays
                mounted across navigations instead of re-rendering (and
                re-fetching) on every click. */}
            <Route element={<AppLayout />}>
              <Route path="/agenda" element={<AgendaRoute />} />
              <Route path="/lists/:listId" element={<ListRoute />} />
              <Route path="/tasks/:taskId" element={<TaskDetailRoute />} />
              <Route path="/archive" element={<ArchiveRoute />} />
              <Route path="/preferences" element={<PreferencesRoute />} />
            </Route>
            {/* Outside the layout: it's a component gallery, not a page of
                the app, and Django 404s it outside DEBUG anyway --
                see lists.views.spa_shell */}
            <Route path="/dev/ui" element={<DevUiGallery />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  );
}
