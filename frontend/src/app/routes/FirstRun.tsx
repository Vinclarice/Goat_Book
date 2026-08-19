import { getCookie } from "../../api";

/**
 * What a brand-new account sees on the Day page instead of three empty
 * sections.
 *
 * `product-stories.md` S1 is the story this exists for. Its "done means" asks
 * that the first screen offer **one obvious thing to do rather than six
 * concepts** -- and what it found was Focus saying "choose from your action
 * items below", Action items saying "nothing due today", and Routines
 * explaining what a routine is, to somebody who has no areas, no tasks and no
 * routines. Three empty states, none of which can be acted on, is the six
 * concepts by another route.
 *
 * **The signal is areas, not emptiness.** An established person having a quiet
 * Tuesday has an empty day too, and showing them onboarding would be worse
 * than showing them nothing. Nobody can have a task without an area, so no
 * areas means nobody has started -- which is a fact about the account rather
 * than about the date being looked at.
 *
 * One form, and it makes an area *and* a first task, because that is what
 * `new_list` already does and because "name a container" is not a thing anyone
 * wants to do. It is a plain Django post for the reason the Agenda's copy of
 * it gives: creating an area navigates to the new area anyway, so there is
 * nothing for the SPA layer to do.
 */
export function FirstRun({ newAreaUrl }: { newAreaUrl: string }) {
  return (
    <section className="space-y-6" aria-labelledby="first-run-heading">
      <div className="space-y-3">
        <h2 id="first-run-heading" className="font-sans text-xl font-bold tracking-tight">
          Start with one thing you mean to do.
        </h2>
        {/* The product's thesis in two sentences, on the surface where it is
            about to become true, rather than a tour of the vocabulary. */}
        <p className="max-w-prose text-muted-foreground">
          Clarice keeps what you choose. Write down the first thing on your
          plate and the area of life it belongs to — work, home, whatever you
          call it — and this page becomes the record of what you decided and
          what happened to it.
        </p>
      </div>

      <form
        className="grid max-w-md gap-3"
        method="post"
        action={newAreaUrl}
      >
        <input
          type="hidden"
          name="csrfmiddlewaretoken"
          value={getCookie("csrftoken")}
        />

        <div className="space-y-1">
          <label className="text-sm font-semibold" htmlFor="first-run-text">
            The first thing on your plate
          </label>
          <input
            id="first-run-text"
            className="min-h-11 w-full rounded-sm border border-border-strong bg-input px-3 text-foreground outline-none"
            name="text"
            placeholder="Call the dentist"
            required
            autoFocus
          />
        </div>

        <div className="space-y-1">
          <label className="text-sm font-semibold" htmlFor="first-run-title">
            The area it belongs to
          </label>
          <input
            id="first-run-title"
            className="min-h-11 w-full rounded-sm border border-border-strong bg-input px-3 text-foreground outline-none"
            name="title"
            placeholder="Home"
            maxLength={100}
          />
          {/* Said rather than left to be discovered, because `new_list` really
              does fall back to the task's own text and somebody who leaves
              this blank should not be surprised by what they get. */}
          <p className="text-sm text-muted-foreground">
            Leave this empty and the area takes the name of the task.
          </p>
        </div>

        <button
          type="submit"
          className="touch-target mt-1 inline-flex min-h-11 items-center justify-center rounded-sm border border-text bg-text px-6 font-sans text-sm font-semibold text-bg transition-colors hover:bg-transparent hover:text-text"
        >
          Add it
        </button>
      </form>

      {/* The second half of S1's four minutes -- capture a thought, plan a day
          -- and the box that does it is already on this page, below. Pointed
          at rather than duplicated. */}
      <p className="max-w-prose text-sm text-muted-foreground">
        Not ready to commit to anything? Anything on your mind can go straight
        into the box further down this page. Capture never asks what it is.
      </p>
    </section>
  );
}
