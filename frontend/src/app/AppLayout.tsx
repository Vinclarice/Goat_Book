import { useEffect, useRef } from "react";
import { Outlet, useLocation } from "react-router";

import { SideNav } from "./SideNav";
import styles from "./sidenav.module.css";

/** Wraps every SPA route so the nav is genuinely persistent -- it stays
 * mounted across navigations rather than being re-rendered per page, which
 * is also what keeps its query from refetching on every click.
 *
 * Below the breakpoint the nav collapses into a <details> disclosure. The
 * CSS does the showing and hiding; this only closes it after a navigation,
 * since a menu that stays open over the page you just asked for is the
 * entire complaint about mobile drawers.
 */
export function AppLayout() {
  const location = useLocation();
  const disclosure = useRef<HTMLDetailsElement>(null);

  useEffect(() => {
    if (disclosure.current?.open) disclosure.current.open = false;
  }, [location.pathname]);

  return (
    <div className={styles.shell}>
      <details className={styles.disclosure} ref={disclosure}>
        <summary aria-label="Menu">☰ Menu</summary>
        <SideNav />
      </details>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
