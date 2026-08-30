import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { apiV1 } from "../../api/client";

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
 * One form, and it makes an area *and* a first task, because "name a
 * container" is not a thing anyone wants to do. That pairing is the point of
 * the screen and it survives -- what changed is only how it is sent.
 *
 * **It was a plain Django POST to `new_list` until August 30, 2026** --
 * coherence-audit-2026-08-30.md F1. The reasoning it carried, that creating
 * an area navigates there anyway so the SPA layer has nothing to do, was true
 * in isolation and wrong in aggregate: it left the one container the task
 * core is built from as the only thing you could not make without a page
 * reload, and left `POST /api/v1/areas` unable to exist because nothing
 * needed it. The navigation still happens; it is just client-side now.
 *
 * **The area name stays optional and the server still decides the fallback.**
 * `create_list_with_item` takes the task's text when the title is blank,
 * which is what the copy below promises, and that promise is kept in one
 * place rather than two.
 */
export function FirstRun() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");

  const create = useMutation({
    mutationFn: async () => {
      const { data, error: failed } = await apiV1.POST("/api/v1/areas", {
        body: { title, first_task: text },
      });
      if (failed) throw failed;
      return data;
    },
    onSuccess: (area) => {
      // The rail is how somebody sees that the area now exists, and this is
      // the one moment in the product where it goes from empty to not.
      queryClient.invalidateQueries({ queryKey: ["nav"] });
      navigate(`/areas/${area.id}`);
    },
    onError: (failed: { detail?: string }) => {
      setError(failed?.detail ?? "That didn't work. Try again.");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!text.trim()) return;
    setError("");
    create.mutate();
  }

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

      <form className="grid max-w-md gap-3" onSubmit={handleSubmit}>
        <div className="space-y-1">
          <label className="text-sm font-semibold" htmlFor="first-run-text">
            The first thing on your plate
          </label>
          <input
            id="first-run-text"
            className="min-h-11 w-full rounded-sm border border-border-strong bg-input px-3 text-foreground outline-none"
            value={text}
            onChange={(event) => setText(event.target.value)}
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
            value={title}
            onChange={(event) => setTitle(event.target.value)}
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

        {error && <p className="text-sm text-destructive">{error}</p>}

        <button
          type="submit"
          disabled={create.isPending}
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
