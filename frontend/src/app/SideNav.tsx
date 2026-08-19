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
    <nav className={styles.nav} aria-label="Contents">
      {/* The Views group stood here -- Today, Agenda, Review, Archive -- and is
          now ViewNav, a sub-nav under the app bar. Second Mind went to the bar
          itself in the step before. What is left is what this rail was always
          best at and could never say plainly while it also held navigation:
          the things the task core *contains*.

          That is why the landmark is "Contents" and not "Main". There is no
          single main navigation any more, which is the point -- there is a bar
          that says which core, a sub-nav that says which surface, and this,
          which says what is in here. */}
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
