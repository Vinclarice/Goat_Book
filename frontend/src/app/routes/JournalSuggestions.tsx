import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";

import { apiV1 } from "../../api/client";

type Suggestion = {
  id: number;
  text: string;
  reason: string;
  effect: string;
};

/**
 * What the day's writing read as a commitment — planning-assistant-plan.md
 * increment 2, slice D.
 *
 * **The card answers five questions**, and the fourth had no implementation
 * anywhere in this application before this component:
 *
 * - *Proposal* — the sentence, quoted.
 * - *Evidence* — that sentence is the evidence; it is the passage the parser
 *   actually read, not the whole day, so the claim can be checked rather than
 *   trusted.
 * - *Reason* — why it was read as a commitment.
 * - *Effect* — **what confirming will do.** Phrased by the server, because it
 *   depends on a decision the server made: a promise with no date makes a task
 *   with none, and somebody approving one should be told that rather than
 *   discover it in their agenda.
 * - *Decision* — accept, or say it is not a task.
 *
 * **Nothing happens without a decision.** No timer, no default, and silence
 * changes nothing — the proposal simply sits. Dismissing is remembered, so the
 * next save does not offer it again; that is what makes "not a task" a real
 * answer rather than a way of closing a box.
 *
 * Rendered only when there is something to answer. An always-present empty
 * panel is indistinguishable from one that failed to load, and it teaches
 * people to stop looking at that part of the page.
 */
export function JournalSuggestions({
  day,
  suggestions,
}: {
  day: string;
  suggestions: Suggestion[];
}) {
  const queryClient = useQueryClient();

  const answer = useMutation({
    mutationFn: async ({
      id,
      decision,
    }: {
      id: number;
      decision: "confirm" | "dismiss";
    }) => {
      const path =
        decision === "confirm"
          ? "/api/v1/suggestions/{suggestion_id}/confirm"
          : "/api/v1/suggestions/{suggestion_id}/dismiss";
      const { data, error } = await apiV1.POST(path, {
        params: { path: { suggestion_id: id } },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: (updated) => {
      // The server answers with the whole day, so the card disappears from
      // the same response that decided it -- no second fetch, and no window
      // in which the page disagrees with what just happened.
      if (updated) queryClient.setQueryData(["day", day], updated);
      // Accepting makes a task, which every other surface counts.
      queryClient.invalidateQueries({ queryKey: ["agenda"] });
      queryClient.invalidateQueries({ queryKey: ["nav"] });
    },
  });

  if (!suggestions.length) return null;

  return (
    <section className="space-y-2">
      <h2 className="text-sm font-bold">Read as a commitment</h2>
      <p className="text-sm text-muted-foreground">
        From what you wrote today. Nothing is created until you say so.
      </p>
      <ul className="space-y-2">
        {suggestions.map((suggestion) => (
          <li
            key={suggestion.id}
            className="rounded-lg border border-border px-3 py-2"
          >
            <p className="text-sm">{suggestion.text}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {suggestion.reason}
            </p>
            {/* Its own line, deliberately. Effect answers a different question
                from Reason — why this was proposed versus what saying yes
                does — and running them together as one grey sentence buries
                the half the person is actually agreeing to. */}
            <p className="mt-1 text-xs font-bold">{suggestion.effect}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="secondary"
                disabled={answer.isPending}
                onClick={() =>
                  answer.mutate({ id: suggestion.id, decision: "confirm" })
                }
              >
                Add to tasks
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={answer.isPending}
                onClick={() =>
                  answer.mutate({ id: suggestion.id, decision: "dismiss" })
                }
              >
                Not a task
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
