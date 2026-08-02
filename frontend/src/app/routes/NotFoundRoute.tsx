import { Link } from "react-router";

/**
 * An unknown path inside the SPA.
 *
 * Distinct from RouteFailure's 404, and the difference is worth keeping:
 * that one means "the task or list you asked for is gone", this one means
 * "there was never a page at this address". Telling someone their work was
 * deleted because they mistyped a URL would be alarming and untrue.
 */
export function NotFoundRoute() {
  return (
    <div className="max-w-lg mx-auto px-4 py-12 space-y-3">
      <h1 className="text-xl font-bold">This page doesn't exist</h1>
      <p className="text-sm text-muted-foreground">
        The address you followed doesn't match anything in Clarice. Nothing has
        been deleted — the link was probably mistyped or out of date.
      </p>
      <Link className="text-sm font-bold text-accent hover:underline" to="/agenda">
        Go to Agenda
      </Link>
    </div>
  );
}
