import { useQuery } from "@tanstack/react-query";
import { Navigate, Route, Routes, useParams } from "react-router";

import { apiV1 } from "../api/client";
import { AppLayout } from "./AppLayout";
import { AgendaRoute } from "./routes/AgendaRoute";
import { ArchiveRoute } from "./routes/ArchiveRoute";
import { CalendarRoute } from "./routes/CalendarRoute";
import { BalancesRoute } from "./routes/BalancesRoute";
import { HistoryRoute } from "./routes/HistoryRoute";
import { MoneyLandingRoute } from "./routes/MoneyLandingRoute";
import { MoneyRoute } from "./routes/MoneyRoute";
import { DayRoute } from "./routes/DayRoute";
import { DevUiGallery } from "./routes/DevUiGallery";
import { AreaRoute } from "./routes/AreaRoute";
import { NotFoundRoute } from "./routes/NotFoundRoute";
import { PreferencesRoute } from "./routes/PreferencesRoute";
import { ProjectRoute } from "./routes/ProjectRoute";
import { ProjectsIndexRoute } from "./routes/ProjectsIndexRoute";
import { ReviewRoute } from "./routes/ReviewRoute";
import { TaskDetailRoute } from "./routes/TaskDetailRoute";

/**
 * Sends a bare /app/ wherever a fresh login would have gone.
 *
 * Asks the nav endpoint rather than deciding here, so this and
 * lists.views.dashboard cannot drift into disagreeing about the same
 * preference. That makes the redirect asynchronous, where it used to be a
 * synchronous <Navigate> -- so it says "Loading…" rather than rendering
 * null while the answer is in flight. A blank /app/ is precisely the defect
 * B2.1 fixed, and a brief one on a slow connection still reads as a broken
 * deploy.
 *
 * If the answer never arrives it still lands somewhere, on the default,
 * rather than stranding anyone on an empty shell.
 */
function LandingRedirect() {
  const { data, isPending } = useQuery({
    queryKey: ["nav"],
    queryFn: async () => {
      const { data, error } = await apiV1.GET("/api/v1/nav");
      if (error) throw error;
      return data;
    },
  });
  if (isPending) return <p className="p-6">Loading…</p>;
  return (
    <Navigate
      to={data?.landing_surface === "agenda" ? "/agenda" : "/day"}
      replace
    />
  );
}

/**
 * Sends /app/lists/3 to /app/areas/3.
 *
 * Release D slice 5 renamed a List to an Area everywhere a person reads
 * one, the route path included. That is a deliberate break of an existing
 * URL, so the old spelling keeps working rather than 404ing on someone's
 * bookmark. `replace` so the dead path does not sit in history and reappear
 * on the back button.
 */
function LegacyListRedirect() {
  const { areaId } = useParams();
  return <Navigate to={`/areas/${areaId}`} replace />;
}

/**
 * The SPA's route table, kept separate from main.tsx so it can be rendered
 * inside a MemoryRouter by tests. main.tsx mounts to a real DOM node and
 * runs at import time, which made the table itself untestable -- and the
 * table is exactly where B2.1's blank-page defect lived.
 */
/** `/bills/2026-08` keeps working and keeps its month.
 *
 * A redirect that dropped the month would send somebody looking at August to
 * today, which is worse than a dead link because it looks like it worked.
 */
function RedirectToMonth() {
  const { month } = useParams();
  return <Navigate to={`/money/month/${month}`} replace />;
}

export function AppRoutes() {
  return (
    <Routes>
      {/* Everything sits inside AppLayout so the side nav stays mounted
          across navigations instead of re-rendering (and re-fetching) on
          every click. */}
      <Route element={<AppLayout />}>
        {/* Without this, a direct visit to /app/ matched no route at all
            and rendered an empty shell -- indistinguishable, to anyone
            looking at it, from a broken deploy. Where it goes is the
            server's answer, not a second one hard-coded here: see
            LandingRedirect. */}
        <Route index element={<LandingRedirect />} />
        <Route path="/agenda" element={<AgendaRoute />} />
        {/* Two paths, one component. The undated one asks the server what
            today is rather than trusting the browser's clock, because the
            day boundary belongs to the account's time zone. */}
        <Route path="/day" element={<DayRoute />} />
        <Route path="/day/:date" element={<DayRoute />} />
        {/* S13's second require. `/day/:date` had no UI entry point at all. */}
        <Route path="/calendar" element={<CalendarRoute />} />
        <Route path="/calendar/:month" element={<CalendarRoute />} />
        {/* A bill is a task with a sidecar; this is a read over them. */}
        {/* **The landing page is the module**, and the month is a view within
            it -- money-module-plan.md increment 8. /money showed August until
            August 27, 2026, which meant answering "how am I doing" by reading
            three lists and doing arithmetic. */}
        <Route path="/money" element={<MoneyLandingRoute />} />
        {/* Before /money/:month, or "balances" is read as a date and the
            monthly pass becomes an unparseable month. */}
        <Route path="/money/history" element={<HistoryRoute />} />
        <Route path="/money/balances" element={<BalancesRoute />} />
        <Route path="/money/balances/:month" element={<BalancesRoute />} />
        <Route path="/money/month" element={<MoneyRoute />} />
        <Route path="/money/month/:month" element={<MoneyRoute />} />
        {/* The old address, kept working. One person and a bookmark is enough
            reason -- `/capture/` is the precedent for how expensive a moved
            prefix is once anything points at it, and a redirect costs two
            lines against finding out later. */}
        <Route path="/bills" element={<Navigate to="/money/month" replace />} />
        <Route
          path="/bills/:month"
          element={<RedirectToMonth />}
        />
        {/* Same two-path shape as the day, for the same reason: the
            undated one lets the server say which week it is, since a week
            boundary belongs to the account's time zone. The dated one is
            what the "week before" link points at, and a review written on
            a Monday is about the week before. */}
        <Route path="/review" element={<ReviewRoute />} />
        <Route path="/review/:week" element={<ReviewRoute />} />
        <Route path="/areas/:areaId" element={<AreaRoute />} />
        {/* An Area used to be a List. Kept so a bookmark from before
            Release D slice 5 still lands on the page it named, rather
            than on the not-found route. */}
        <Route
          path="/lists/:areaId"
          element={<LegacyListRedirect />}
        />
        {/* project-workspace-plan.md: a project's own page, the gap the
            side nav's Projects group used to route around by sending every
            click to a parent Area instead. The index, a step further, is
            where a *completed* project stays reachable -- the nav's own
            group only shows open ones, same reason the Agenda excludes
            completed tasks. */}
        <Route path="/projects" element={<ProjectsIndexRoute />} />
        <Route path="/projects/:projectId" element={<ProjectRoute />} />
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
