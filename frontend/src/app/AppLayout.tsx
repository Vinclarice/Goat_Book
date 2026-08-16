import { useEffect, useRef } from "react";
import { Outlet, useLocation } from "react-router";

import { DeletionBanner } from "./DeletionBanner";
import { SideNav } from "./SideNav";
import styles from "./sidenav.module.css";

// Matches sidenav.module.css's breakpoint from the other side: the CSS
// collapses the nav at max-width 760px, so "wide" starts one pixel above.
// If one moves, the other has to.
const WIDE = "(min-width: 761px)";

/** Wraps every SPA route so the nav is genuinely persistent -- it stays
 * mounted across navigations rather than being re-rendered per page, which
 * is also what keeps its query from refetching on every click.
 *
 * Below the breakpoint the nav collapses into a <details> disclosure, and
 * navigating closes it, since a menu left open over the page you just asked
 * for is the entire complaint about mobile drawers.
 *
 * Above the breakpoint the disclosure is held open. That is not cosmetic:
 * the CSS hides the <summary> up here, so a closed disclosure is one that
 * nothing can reopen, and a browser that skips rendering a closed
 * disclosure's contents (Firefox does; Chromium currently does not) shows
 * an empty 210px gutter where the nav should be. Relying on how an engine
 * treats a closed <details> is what shipped that bug.
 */
export function AppLayout() {
  const location = useLocation();
  const disclosure = useRef<HTMLDetailsElement>(null);
  const wide = useRef<MediaQueryList | null>(null);

  useEffect(() => {
    const query = window.matchMedia(WIDE);
    wide.current = query;
    const sync = () => {
      if (disclosure.current) disclosure.current.open = query.matches;
    };
    sync();
    query.addEventListener("change", sync);
    return () => query.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    // Only a phone-sized disclosure should close on navigation; doing it at
    // desktop width would re-seal the nav on the first click.
    if (wide.current?.matches) return;
    if (disclosure.current?.open) disclosure.current.open = false;
  }, [location.pathname]);

  return (
    <div className={styles.shell}>
      <details className={styles.disclosure} ref={disclosure}>
        <summary aria-label="Menu">☰ Menu</summary>
        <SideNav />
      </details>
      <main>
        {/* Above the outlet, so it is the first thing on every route rather
            than something a page can scroll past. See DeletionBanner: a
            scheduled erasure visible only where it was scheduled is one
            somebody can forget for thirty days. */}
        <DeletionBanner />
        <Outlet />
      </main>
    </div>
  );
}
