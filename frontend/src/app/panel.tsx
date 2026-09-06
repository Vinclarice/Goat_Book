import { useCallback, type ReactNode } from "react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { Link, matchPath, useLocation, useNavigate } from "react-router";

import { cn } from "@/lib/utils";

/**
 * Detail that opens instead of navigating — app-overhaul-plan.md rule 2.
 *
 * The plan's premise is that the page is bounded the way the list is: seven
 * sections stand, and everything else opens from them. What makes that
 * possible without losing anything is that a panel is still a *route* — it
 * keeps its URL, its deep link and the back button, and gives up only its
 * place in a navigation.
 *
 * **A panel is not a modal**, in the sense the plan refuses. It closes, it can
 * be linked to, and the back button reaches it. What it borrows from a dialog
 * is focus management and Escape, which are the parts a hand-rolled overlay
 * always gets wrong.
 */

/**
 * The paths that open as panels, in one list.
 *
 * `AppRoutes` renders exactly these in its panel outlet and `backgroundFor`
 * decides on exactly these, so the route table and the mechanic cannot come to
 * disagree about what a panel is. Increment 1 has one entry on purpose:
 * `/tasks/:taskId` is the smallest complete instance, and it is also
 * `coherence-audit-2026-08-30.md`'s F3 repair rather than only a mechanic.
 */
export const PANEL_ROUTES = ["/tasks/:taskId"] as const;

/** The page a deep-linked panel sits on when there is nothing behind it. */
const DEEP_LINK_BACKGROUND = { pathname: "/day", search: "", hash: "" };

type PartialLocation = {
  pathname: string;
  search?: string;
  hash?: string;
  state?: unknown;
};

/**
 * Which page the main routes should render, given where we are.
 *
 * `null` means *not a panel* — render one set of routes, exactly as before.
 * Anything else is the page the panel is sitting on, and the caller renders
 * both.
 *
 * **A deep link gets the day rather than a full-page fallback.** The
 * alternative is two presentations of the same detail, one in a panel and one
 * as a page, which is `coherence-audit-2026-08-30.md`'s F3 rebuilt on purpose:
 * what you can do to a task must not depend on which page you met it on. It is
 * also the shape increment 7 arrives at anyway, when the day is the only page
 * there is.
 */
export function backgroundFor(location: PartialLocation) {
  const isPanel = PANEL_ROUTES.some((path) =>
    matchPath(path, location.pathname),
  );
  if (!isPanel) return null;

  const carried = (location.state as { background?: PartialLocation } | null)
    ?.background;
  return carried ?? DEEP_LINK_BACKGROUND;
}

/**
 * A link that opens a panel over wherever it was clicked.
 *
 * The page you came from travels in history state, so closing the panel puts
 * you back on it rather than on a guess. Every call site that used to render a
 * plain `<Link to={/tasks/...}>` becomes one of these, which is the whole of
 * the change at those five call sites.
 */
export function PanelLink({
  to,
  className,
  children,
}: {
  to: string;
  className?: string;
  children: ReactNode;
}) {
  const location = useLocation();
  return (
    <Link to={to} state={{ background: location }} className={className}>
      {children}
    </Link>
  );
}

/**
 * What closing a panel means, which depends on how you arrived.
 *
 * Opened from a page, closing is **back** — history is right, the page behind
 * is already mounted, and its scroll position survives. Deep-linked into a
 * fresh tab there is nothing behind, and `navigate(-1)` would leave the
 * application entirely; so it replaces onto the same background
 * `backgroundFor` chose, which is the page already rendered underneath.
 *
 * `replace` rather than push, so a closed panel does not sit in history
 * waiting to be reopened by the back button.
 */
export function usePanelClose() {
  const navigate = useNavigate();
  const location = useLocation();
  const carried = (location.state as { background?: PartialLocation } | null)
    ?.background;

  return useCallback(() => {
    if (carried) navigate(-1);
    else navigate(DEEP_LINK_BACKGROUND.pathname, { replace: true });
  }, [carried, navigate]);
}

/**
 * The container. Everything a panel route renders goes inside one of these.
 *
 * `onClose` rather than a route decision of its own: what closing *means*
 * depends on how you arrived — back, if there is somewhere to go back to, and
 * a replace onto the background if the panel was deep-linked into a fresh tab.
 * That is `AppRoutes`'s question, and keeping it there leaves this component
 * testable without a router.
 */
export function Panel({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    /* **`modal={false}`, and no overlay, and both are the same decision.**
       Radix's modal mode marks everything outside the dialog `aria-hidden` and
       inert, and a scrim over the page makes it unclickable — so the page
       behind would be *visible and dead*, which is trapping with extra steps
       and is what the plan refuses in as many words.

       Found by a test rather than by taste: `TaskDetailRoute.test.tsx`'s
       "seeds the second task when navigating straight from one to another"
       renders its link outside the route on purpose, and modal mode made that
       link unreachable to a screen reader and to the keyboard.

       What is kept from a dialog is the half worth having: focus moves in on
       open and returns on close, and Escape works. */
    <DialogPrimitive.Root
      modal={false}
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogPrimitive.Portal>
        {/* A sheet from the right on a desktop and the whole screen on a
            phone. The page stays visible *and usable* beside it at width,
            which is the point of a panel over a navigation: you can still see
            and reach what you were doing. */}
        <DialogPrimitive.Content
          // Radix warns without a description; this content is a whole
          // editing surface rather than a sentence, and the title names it.
          aria-describedby={undefined}
          /* **A click on the page behind does not close this.** Radix closes a
             non-modal dialog on any outside interaction, which is right for a
             popover and wrong for a sheet the plan says you should be able to
             work beside: the first scroll or click on the page you kept open
             would dismiss the thing you opened.

             A panel is a route, so it closes the way a route does — Escape,
             the Close button, or the back button. Nothing ambient.

             Caught by "seeds the second task when navigating straight from one
             to another": clicking a link outside the panel fired a close and a
             navigation at once, and the close won. */
          onPointerDownOutside={(event) => event.preventDefault()}
          onInteractOutside={(event) => event.preventDefault()}
          className={cn(
            "fixed inset-0 z-50 flex flex-col bg-background",
            "sm:inset-y-0 sm:right-0 sm:left-auto sm:w-full sm:max-w-2xl sm:border-l sm:border-border sm:shadow-lg",
            "data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0",
            "sm:data-open:slide-in-from-right sm:data-closed:slide-out-to-right",
          )}
        >
          <div className="flex items-center gap-3 border-b border-border px-4 py-3">
            <DialogPrimitive.Title className="min-w-0 flex-1 truncate font-sans text-sm font-semibold">
              {title}
            </DialogPrimitive.Title>
            {/* Says what it closes. "Close" alone is what every panel in the
                application will say once increment 2 lands, and a screen
                reader hearing the fourth one deserves better than that. */}
            <DialogPrimitive.Close
              className="touch-target shrink-0 rounded-sm border border-border px-3 py-1.5 font-sans text-sm hover:border-text"
              aria-label={`Close ${title}`}
            >
              Close
            </DialogPrimitive.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
            {children}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
