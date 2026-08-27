import { NavLink } from "react-router";
import { useQuery } from "@tanstack/react-query";

import { apiV1 } from "../api/client";

/** The task core's sub-nav: which surface of this core you are looking at.
 *
 * The second of the two navigation levels. The app bar above it -- server
 * rendered, in _app_bar.html -- says which *core* you are in and is identical
 * everywhere. This says which surface within the task core, and has a
 * counterpart in mind/base.html doing the same job for the knowledge core.
 *
 * These four used to be a "Views" group inside the side nav, which is why the
 * side nav had to mean two things at once: a place to switch surfaces and a
 * list of what the core contains. Splitting them is what lets the rail be
 * contents and nothing else.
 *
 * Rendered by React rather than by Django, unlike the bar, and the reason is
 * the active marker: which of these is current changes on client-side
 * navigation, with no request for the server to answer. The bar has no such
 * problem -- the core only changes on a full page load.
 */
export function ViewNav() {
  const { data } = useQuery({
    queryKey: ["nav"],
    queryFn: async () => {
      const { data, error } = await apiV1.GET("/api/v1/nav");
      if (error) throw error;
      return data;
    },
  });

  return (
    <nav className="border-b border-border" aria-label="Views">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 px-4 sm:px-6 min-h-11">
        {/* Undated on purpose, so the link always means "today" rather than
            whichever day was current when the nav rendered. */}
        <Entry to="/day">Today</Entry>
        <Entry to="/agenda">Agenda</Entry>
        {/* Undated for the same reason as Today: the week you are in, not the
            one this nav last rendered in. */}
        <Entry to="/review">Review</Entry>
        {/* Undated like Today and Review, and for the same reason: the month
            you are in, not the one this nav last rendered in.

            Here rather than behind a link on the Day page, which is where
            they shipped and where nobody found them. A route reachable from
            exactly one other page is not the same as a surface, and this nav
            is what says which surfaces exist. */}
        <Entry to="/calendar">Calendar</Entry>
        {/* **Money, not Bills, since August 27, 2026.** The surface holds
            bills now and income shortly, and a nav entry saying Bills would
            not survive a salary line. Renamed at the cheap moment rather than
            after something pointed at it. */}
        <Entry to="/money">Money</Entry>
        <Entry to="/archive">
          Archive
          {data && data.archived_count > 0 && (
            <span className="font-mono text-xs tabular-nums text-muted-foreground">
              {data.archived_count}
            </span>
          )}
        </Entry>
      </div>
    </nav>
  );
}

function Entry({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        [
          "touch-target font-sans text-sm inline-flex items-center gap-2 border-b-2 py-1",
          isActive
            ? "border-accent font-semibold text-text"
            : "border-transparent text-muted-foreground hover:text-text",
        ].join(" ")
      }
    >
      {children}
    </NavLink>
  );
}
