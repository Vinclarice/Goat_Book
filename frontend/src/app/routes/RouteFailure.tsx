import { Link, useLocation } from "react-router";

import { Button } from "@/components/ui/button";

interface RouteFailureProps {
  /** HTTP status, or undefined when the request never got a response. */
  status?: number;
  /** Omitted when the failure is permanent and retrying cannot help. */
  onRetry?: () => void;
}

/**
 * What a route shows when its data could not be loaded.
 *
 * The reason this is shared rather than repeated: these four cases need
 * opposite things from the person reading them, and every route used to
 * offer the same "Something went wrong." to all of them. Telling someone
 * their task no longer exists when their connection dropped costs trust;
 * offering a login link for a 403 sends them round a loop that cannot
 * succeed.
 *
 * See design/bittern-plan.md, B2.1.
 */
export function RouteFailure({ status, onRetry }: RouteFailureProps) {
  const location = useLocation();

  if (status === 401) {
    // The SPA is mounted at /app, so location.pathname is missing that
    // prefix -- without it Django would send them back to a path that
    // doesn't exist. Preserved at all because someone who deep-linked to a
    // task should land on that task after logging in, not at the Agenda
    // having to find it again.
    const destination = encodeURIComponent(`/app${location.pathname}`);
    return (
      <Failure title="Your session has ended">
        <p className="text-sm text-muted-foreground">
          You have been signed out. Logging in again will bring you straight
          back here.
        </p>
        {/* A plain anchor, not a Link: the login page is Django-rendered
            and lives outside the SPA's router. */}
        <a
          className="text-sm font-bold text-accent hover:underline"
          href={`/accounts/login/?next=${destination}`}
        >
          Log in again
        </a>
      </Failure>
    );
  }

  if (status === 403) {
    return (
      <Failure title="You don't have access to this">
        <p className="text-sm text-muted-foreground">
          You no longer have access to this item. If you think that's wrong,
          the person who shared it can check.
        </p>
        <Link
          className="text-sm font-bold text-accent hover:underline"
          to="/agenda"
        >
          Back to Agenda
        </Link>
      </Failure>
    );
  }

  if (status === 404) {
    return (
      <Failure title="This is no longer here">
        <p className="text-sm text-muted-foreground">
          It no longer exists — it may have been deleted or archived.
        </p>
        <Link
          className="text-sm font-bold text-accent hover:underline"
          to="/agenda"
        >
          Go to Agenda
        </Link>
      </Failure>
    );
  }

  // Everything else, including a dropped connection that produced no status
  // at all. Treated as temporary on purpose: guessing "permanent" would
  // tell somebody their work is gone when their wifi blinked, which is the
  // one wrong answer here that loses trust rather than just time.
  return (
    <Failure title="Couldn't reach Clarice">
      <p className="text-sm text-muted-foreground">
        Something interrupted the connection. Nothing you have typed has been
        lost.
      </p>
      {onRetry ? (
        <Button variant="outline" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </Failure>
  );
}

function Failure({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="max-w-lg mx-auto px-4 py-12 space-y-3"
      role="alert"
      aria-live="polite"
    >
      <h1 className="text-xl font-bold">{title}</h1>
      {children}
    </div>
  );
}
