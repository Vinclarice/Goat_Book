import { Link, NavLink, useLocation } from "react-router";
import { useQuery } from "@tanstack/react-query";

import { colorForKey } from "../agenda";
import { apiV1 } from "../api/client";
import styles from "./sidenav.module.css";

/** The one nav, on every SPA page.
 *
 * It navigates and nothing else. Clicking an area here opens that area rather
 * than filtering the agenda -- filtering lives in each page's own header, as
 * chips. That split is what lets a single nav mean the same thing on the
 * agenda, an area, and the archive; the old agenda sidebar could not, because
 * a "filter the agenda" control has no meaning on the archive page.
 *
 * See design/side-nav-mockup.html.
 */
export function SideNav() {
  const location = useLocation();
  const { data } = useQuery({
    queryKey: ["nav"],
    queryFn: async () => {
      const { data, error } = await apiV1.GET("/api/v1/nav");
      if (error) throw error;
      return data;
    },
  });

  // Renders its own shell while loading rather than nothing: a nav that
  // appears a beat after the page does makes every navigation feel like a
  // layout shift.
  const areas = data?.areas ?? [];
  const projects = data?.projects ?? [];

  return (
    <nav className={styles.nav} aria-label="Main">
      <div className={styles.group}>
        <h3>Views</h3>
        {/* First, because Crane makes the day the home surface -- and
            present at all, which until slice 6 it was not: slices 1 to 5
            built a page reachable only by typing its URL. Undated on
            purpose, so the link always means "today" rather than whichever
            day was current when the nav rendered. */}
        <NavLink to="/day" className={navLinkClass}>
          Today
        </NavLink>
        <NavLink to="/agenda" className={navLinkClass}>
          Agenda
        </NavLink>
        {/* Beside the day rather than under Account, because a review is a
            view of the work and not a setting -- and present in the slice
            that builds it, since a surface nobody can reach has now been
            shipped twice. Undated, so the link always means the week you
            are in rather than whichever one the nav last rendered. */}
        <NavLink to="/review" className={navLinkClass}>
          Review
        </NavLink>
        {/* Second Mind stood here and now lives in the app bar, which is
            server-rendered and therefore present at /mind/ too -- so crossing
            into the knowledge core is no longer a one-way door. The rule that
            travelled with it still holds and is restated where it applies now:
            that entry must never grow a count.

            `mind_url` stays on the /api/v1/nav payload. Nothing here reads it
            any more, but the phone may, and removing a response field is a
            contract change rather than a tidy-up. */}
        <NavLink to="/archive" className={navLinkClass}>
          Archive
          {data && data.archived_count > 0 && (
            <span className={styles.count}>{data.archived_count}</span>
          )}
        </NavLink>
      </div>

      <div className={styles.group}>
        <h3>Areas</h3>
        {areas.length === 0 && <p className={styles.empty}>No areas yet.</p>}
        {areas.map((each) => (
          <NavLink
            key={each.id}
            to={`/areas/${each.id}`}
            className={navLinkClass}
            title={each.title}
          >
            <span
              className={styles.dot}
              aria-hidden="true"
              style={{ background: colorForKey(each.color_key) }}
            />
            <span className={styles.name}>{each.title}</span>
            <span
              className={`${styles.count}${each.overdue_count ? ` ${styles.warn}` : ""}`}
            >
              {each.overdue_count > 0 && (
                <span aria-label={`${each.overdue_count} overdue`}>
                  ⚠ {each.overdue_count} ·{" "}
                </span>
              )}
              {each.open_count}
            </span>
          </NavLink>
        ))}
      </div>

      {/* Its own group rather than nested under Areas -- ui-second-pass-plan.md
          F3, Vince's call. Flat across areas, same weight as the group above
          it. Completed projects never appear here: this group is ongoing
          work, the same reason the Agenda doesn't list completed tasks.
          Routes straight to the project's own page now --
          project-workspace-plan.md gave it one, closing the gap that used
          to send every click here back to a parent Area instead. */}
      <div className={styles.group}>
        <h3>
          <Link to="/projects" className={styles.headingLink}>
            Projects
          </Link>
        </h3>
        {projects.length === 0 && <p className={styles.empty}>No projects yet.</p>}
        {projects.map((each) => (
          <NavLink
            key={each.id}
            to={`/projects/${each.id}`}
            className={navLinkClass}
            title={each.title}
          >
            <span className={styles.name}>{each.title}</span>
            <span className={styles.count}>{each.open_task_count}</span>
          </NavLink>
        ))}
      </div>

      {/* The Account group stood here -- Preferences and Log out -- and both
          moved into the app bar, which reaches the Django pages and /mind/ as
          well as this shell. Logout in particular had to move rather than be
          duplicated: there were two of them with different mechanics, this
          button posting to /api/v1/me/logout and base.html posting a form, and
          a control that ends a session is the last one that should have two
          implementations. The form won because it needs no client code to work
          on all three surfaces.

          What is left in here is contents rather than navigation: the views
          this core offers, and the areas and projects it holds. */}

      {/* Keyed on the path so navigating closes the disclosure: on a phone
          the menu covering the page you just asked for is the whole
          complaint about drawers. */}
      <span hidden key={location.pathname} />
    </nav>
  );
}

function navLinkClass({ isActive }: { isActive: boolean }) {
  return isActive ? `${styles.link} ${styles.active}` : styles.link;
}
