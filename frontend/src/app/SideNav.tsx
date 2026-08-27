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
/** The last twelve months, newest first, as first-of-month dates.
 *
 * Twelve because a year is the span a person compares against -- *what did
 * this cost last August* -- and because a longer list stops being scannable
 * in a rail. Computed rather than fetched: the months a person can look at are
 * every month, and asking a server which ones exist would make an empty
 * February unreachable.
 */
function recentMonths() {
  const now = new Date();
  return Array.from({ length: 12 }, (_, back) => {
    const date = new Date(now.getFullYear(), now.getMonth() - back, 1);
    const iso = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-01`;
    return {
      iso,
      label: date.toLocaleDateString(undefined, {
        month: "long",
        year: date.getFullYear() === now.getFullYear() ? undefined : "numeric",
      }),
    };
  });
}

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

  /* **Months, but only on Money.** Vince's call, August 27, 2026, against the
     recommendation that this rail stay contents-only: the month you are
     reading is what you navigate by there, and prev/next arrows at the top of
     the page make jumping four months back four clicks.
     
     The concern, recorded rather than argued: this rail's own docstring says
     it says *what is in here*, and a contextual group makes it say two things
     depending on where you are -- which is the split ViewNav was created to
     undo. If it starts feeling wrong, the fix is a column on the Money page
     itself, not more contextual groups. */
  const onMoney = location.pathname.startsWith("/money");
  const months = onMoney ? recentMonths() : [];

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
      {months.length > 0 && (
        <div className={styles.group}>
          <h3>
            <Link to="/money" className={styles.headingLink}>
              Months
            </Link>
          </h3>
          {/* The monthly pass, above the months rather than among them: it is
              an action and they are places, and a list that mixes the two is
              the reading problem this rail already has one of. Vince asked for
              it here rather than only as a link on Money -- a ritual you do
              twelve times a year should not need finding. */}
          <NavLink to="/money/balances" className={navLinkClass} end>
            <span className={styles.name}>Update balances</span>
          </NavLink>
          <NavLink to="/money/history" className={navLinkClass} end>
            <span className={styles.name}>History</span>
          </NavLink>
          {months.map((each) => (
            <NavLink
              key={each.iso}
              to={`/money/month/${each.iso}`}
              className={navLinkClass}
              title={each.label}
              end
            >
              <span className={styles.name}>{each.label}</span>
            </NavLink>
          ))}
        </div>
      )}

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
