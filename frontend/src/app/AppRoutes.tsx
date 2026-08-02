import { Navigate, Route, Routes } from "react-router";

import { AppLayout } from "./AppLayout";
import { AgendaRoute } from "./routes/AgendaRoute";
import { ArchiveRoute } from "./routes/ArchiveRoute";
import { DayRoute } from "./routes/DayRoute";
import { DevUiGallery } from "./routes/DevUiGallery";
import { ListRoute } from "./routes/ListRoute";
import { NotFoundRoute } from "./routes/NotFoundRoute";
import { PreferencesRoute } from "./routes/PreferencesRoute";
import { TaskDetailRoute } from "./routes/TaskDetailRoute";

/**
 * The SPA's route table, kept separate from main.tsx so it can be rendered
 * inside a MemoryRouter by tests. main.tsx mounts to a real DOM node and
 * runs at import time, which made the table itself untestable -- and the
 * table is exactly where B2.1's blank-page defect lived.
 */
export function AppRoutes() {
  return (
    <Routes>
      {/* Everything sits inside AppLayout so the side nav stays mounted
          across navigations instead of re-rendering (and re-fetching) on
          every click. */}
      <Route element={<AppLayout />}>
        {/* Without this, a direct visit to /app/ matched no route at all
            and rendered an empty shell -- indistinguishable, to anyone
            looking at it, from a broken deploy. */}
        <Route index element={<Navigate to="/agenda" replace />} />
        <Route path="/agenda" element={<AgendaRoute />} />
        {/* Two paths, one component. The undated one asks the server what
            today is rather than trusting the browser's clock, because the
            day boundary belongs to the account's time zone. Slice 6 makes
            one of these the landing route; for now both are just
            reachable. */}
        <Route path="/day" element={<DayRoute />} />
        <Route path="/day/:date" element={<DayRoute />} />
        <Route path="/lists/:listId" element={<ListRoute />} />
        <Route path="/tasks/:taskId" element={<TaskDetailRoute />} />
        <Route path="/archive" element={<ArchiveRoute />} />
        <Route path="/preferences" element={<PreferencesRoute />} />
        {/* Inside the layout on purpose: someone who mistyped a URL still
            has the navigation to get anywhere else from. */}
        <Route path="*" element={<NotFoundRoute />} />
      </Route>
      {/* Outside the layout: it's a component gallery, not a page of
          the app, and Django 404s it outside DEBUG anyway --
          see lists.views.spa_shell */}
      <Route path="/dev/ui" element={<DevUiGallery />} />
    </Routes>
  );
}
