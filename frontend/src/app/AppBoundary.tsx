import { Component, type ErrorInfo, type ReactNode } from "react";

/** The last thing between a thrown exception and a blank page.
 *
 * `commercial-blueprint.md` defect 5. The only boundary in this codebase was
 * `MountBoundary` in `src/main.tsx` -- the island entry point, which no
 * template references any more. `src/app/main.tsx` is what actually ships, and
 * it mounted the router bare, so one exception anywhere in a route unmounted
 * the entire application: white page, no message, no way back, and nothing to
 * tell it apart from the bundle failing to load.
 *
 * **It shows what happened, not what broke.** The error goes to the console
 * where it can be read and reported; the page says something a person can act
 * on. "Cannot read properties of undefined" on screen tells them nothing, and
 * reads as the application blaming itself at somebody who just wanted their
 * agenda.
 *
 * **The way out is a plain link, deliberately.** Recovery must not depend on
 * the router, the query client, or any state that might be what just failed --
 * a full navigation is the one action guaranteed to work when the cause is
 * unknown, which by definition it is here.
 *
 * A class, because error boundaries have no hook equivalent; React still
 * offers only `componentDidCatch`/`getDerivedStateFromError`.
 */

interface Props {
  children: ReactNode;
}

interface State {
  failed: boolean;
}

export class AppBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // console rather than a UI channel: this is for whoever is diagnosing it,
    // and it is what a browser-side error reporter would hook if one is ever
    // added. The component stack is the half that says *where*.
    console.error("Clarice stopped unexpectedly.", error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;

    return (
      <div
        role="alert"
        className="mx-auto flex max-w-md flex-col gap-4 px-6 py-16 text-center"
      >
        <h1 className="text-lg font-semibold">Something went wrong.</h1>
        <p className="text-muted-foreground text-sm">
          This page stopped before it finished loading. Nothing you had saved is
          affected — your tasks and notes are stored on the server, not here.
        </p>
        <p>
          <a
            className="underline underline-offset-4"
            href="/app"
            // A real navigation, not a router link. See the note above: what
            // failed is unknown, so the recovery path must not share anything
            // with it.
          >
            Go back to the agenda
          </a>
        </p>
      </div>
    );
  }
}
