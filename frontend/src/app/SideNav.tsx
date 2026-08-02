import { useState } from "react";
import { NavLink, useLocation } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { colorForKey } from "../agenda";
import { apiV1 } from "../api/client";
import styles from "./sidenav.module.css";

/** The one nav, on every SPA page.
 *
 * It navigates and nothing else. Clicking a list here opens that list rather
 * than filtering the agenda -- filtering lives in each page's own header, as
 * chips. That split is what lets a single nav mean the same thing on the
 * agenda, a list, and the archive; the old agenda sidebar could not, because
 * a "filter the agenda" control has no meaning on the archive page.
 *
 * See design/side-nav-mockup.html.
 */
export function SideNav() {
  const location = useLocation();
  const queryClient = useQueryClient();
  const [logoutError, setLogoutError] = useState("");
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
  const lists = data?.lists ?? [];

  const logout = useMutation({
    mutationFn: async () => {
      const { error } = await apiV1.POST("/api/v1/me/logout", {});
      if (error) throw new Error("Couldn't log out. Please try again.");
    },
    onSuccess: () => {
      // A full navigation, not a router push: the session backing every
      // query is gone, so continuing to render an authenticated SPA would
      // only produce a screenful of 401s. Clearing the cache first stops
      // anything refetching on the way out.
      queryClient.clear();
      window.location.assign("/");
    },
    onError: (caught: Error) => setLogoutError(caught.message),
  });

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
        {/* A Django page, not an SPA route, so a plain anchor: React Router
            would try to handle /capture/ itself and 404 inside the shell. */}
        <a className={styles.link} href={data?.inbox_url ?? "/capture/"}>
          Inbox
          {data && data.inbox_count > 0 && (
            <span className={styles.count}>{data.inbox_count}</span>
          )}
        </a>
        {/* No count: unlike the inbox, a pile of ideas isn't a backlog to
            work down, so a number next to it would read as pressure. */}
        <a className={styles.link} href={data?.ideas_url ?? "/capture/ideas/"}>
          Ideas
        </a>
        <NavLink to="/archive" className={navLinkClass}>
          Archive
          {data && data.archived_count > 0 && (
            <span className={styles.count}>{data.archived_count}</span>
          )}
        </NavLink>
      </div>

      <div className={styles.group}>
        <h3>Lists</h3>
        {lists.length === 0 && <p className={styles.empty}>No lists yet.</p>}
        {lists.map((each) => (
          <NavLink
            key={each.id}
            to={`/lists/${each.id}`}
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

      <div className={styles.group}>
        <h3>Account</h3>
        <NavLink to="/preferences" className={navLinkClass}>
          Preferences
        </NavLink>
        <a className={styles.link} href={data?.settings_url ?? "/accounts/settings/"}>
          Settings
        </a>
        {/* In the nav rather than on a preferences page, so it is reachable
            from every SPA route -- including the mobile disclosure, which
            renders this same markup. */}
        <button
          type="button"
          className={styles.link}
          onClick={() => {
            setLogoutError("");
            logout.mutate();
          }}
          disabled={logout.isPending}
        >
          Log out
        </button>
        {logoutError && <p className={styles.empty}>{logoutError}</p>}
      </div>

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
