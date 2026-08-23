import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";

import { apiV1 } from "../../api/client";

/**
 * What a project came to — **S12**.
 *
 * > A project completes. Vince wants a retrospective he did not have to write
 * > from memory.
 *
 * **Shown on completion, and not before.** A retrospective of a running project
 * is a status report, which the brief already is; the question *what did this
 * come to* only has an answer once the answer has stopped changing.
 *
 * **Unlike the brief, this loads without being asked.** The brief is gated
 * because the Attention Policy permits a queue only inside a ritual somebody
 * chose to open — and marking a project complete *is* that ritual. Having just
 * declared the work over, being shown what it came to is the thing asked for,
 * not an interruption.
 *
 * **Week by week rather than one pair of numbers.** A project that started well
 * and stalled and one that ground along evenly have the same totals, and only
 * the first is worth knowing about.
 */
export function ProjectRetrospective({ projectId }: { projectId: number }) {
  const queryClient = useQueryClient();
  const [learned, setLearned] = useState("");
  const [error, setError] = useState<string | null>(null);

  const queryKey = ["project-retrospective", projectId];
  const { data, isFetching } = useQuery({
    queryKey,
    queryFn: async () => {
      const { data, error } = await apiV1.GET(
        "/api/v1/projects/{project_id}/retrospective",
        { params: { path: { project_id: projectId } } },
      );
      if (error) throw error;
      return data;
    },
  });

  /* Seeded from the server once it arrives, the same way the purpose and
     outcome boxes are: a controlled textarea that started empty would blank
     what is already written for as long as the request is in flight. */
  useEffect(() => {
    if (data) setLearned(data.learned);
  }, [data]);

  const save = useMutation({
    mutationFn: async (next: string) => {
      const { data, error } = await apiV1.PATCH("/api/v1/projects/{project_id}", {
        params: { path: { project_id: projectId } },
        body: { learned: next },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey });
    },
    onError: () => setError("Couldn't save that."),
  });

  function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    save.mutate(learned);
  }

  if (isFetching && !data) {
    return (
      <section className="mt-6 border-t border-border pt-4">
        <p className="text-sm text-muted-foreground">Looking back…</p>
      </section>
    );
  }
  if (!data) return null;

  const planned = data.met + data.unfinished;

  return (
    <section className="mt-6 border-t border-border pt-4">
      <h2 className="text-sm font-bold">What this came to</h2>

      {/* The denominator is said out loud, and set-aside is deliberately not in
          it: a pin dropped on purpose was a decision, not a commitment that
          failed, and counting it against him would make deliberate pruning look
          like slippage. Same rule the weekly review keeps. */}
      <p className="mt-1 text-sm text-muted-foreground">
        {planned > 0
          ? `You finished ${data.met} of the ${planned} things you pinned to a day for this.`
          : "Nothing was ever pinned to a day for this."}
        {data.set_aside > 0 &&
          ` You set aside ${data.set_aside} more on purpose — not the same as unfinished.`}
      </p>

      {data.weeks.length > 0 && (
        <div className="mt-3 overflow-x-auto">
          {/* Every week including the quiet ones. A fortnight of silence in the
              middle of a quarter is the most legible thing a retrospective can
              show, and a list of only the busy weeks hides exactly that. */}
          <table className="text-sm">
            <thead>
              <tr className="text-muted-foreground">
                <th className="pr-4 text-left font-normal">Week of</th>
                <th className="pr-4 text-right font-normal">Met</th>
                <th className="pr-4 text-right font-normal">Unfinished</th>
                <th className="text-right font-normal">Set aside</th>
              </tr>
            </thead>
            <tbody>
              {data.weeks.map((week) => (
                <tr key={week.week_start}>
                  <td className="pr-4">{week.week_start}</td>
                  <td className="pr-4 text-right">{week.met}</td>
                  <td className="pr-4 text-right">{week.unfinished}</td>
                  <td className="text-right">{week.set_aside}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data.quiet_says && (
        /* One sentence, not a run of empty rows. Silence inside the work is the
           finding and gets a row each; silence after it is one fact — the gap
           between the work stopping and somebody saying so. Rendering it as
           rows made a three-week project read as a six-month one. */
        <p className="mt-2 text-sm text-muted-foreground">{data.quiet_says}.</p>
      )}

      {data.decisions.length > 0 && (
        <div className="mt-4">
          <h3 className="text-sm font-bold">What you decided along the way</h3>
          <ul className="mt-2 space-y-2">
            {data.decisions.map((decision) => (
              <li key={decision.id} className="rounded-lg border border-border px-3 py-2">
                <p className="text-sm font-medium">{decision.question}</p>
                <p className="text-sm">Chose: {decision.chose}</p>
                {decision.considered && (
                  <p className="text-sm text-muted-foreground">Over: {decision.considered}</p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.notes.length > 0 && (
        <div className="mt-4">
          <h3 className="text-sm font-bold">Notes that became work here</h3>
          {/* Recorded provenance, not retrieval -- the line between a brief and
              a retrospective. Every note here became a task in this project,
              along a chain of columns somebody wrote. */}
          <ul className="mt-2 space-y-2">
            {data.notes.map((note) => (
              <li key={note.id} className="rounded-lg border border-border px-3 py-2">
                <p className="text-sm">{note.text}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      <form onSubmit={handleSave} className="mt-4">
        <label htmlFor="project-learned" className="block text-sm font-bold">
          What would you do differently?
        </label>
        {/* The one thing on this page no row can answer, which is why it is the
            only stored part of a retrospective that is otherwise entirely
            derived. It is offered here rather than demanded at completion: the
            lesson arrives while reading the rest, not before it. */}
        <p className="text-sm text-muted-foreground">
          Kept for next time — it shows up in the brief of every project you start after this.
        </p>
        <textarea
          id="project-learned"
          rows={3}
          value={learned}
          onChange={(event) => setLearned(event.target.value)}
          placeholder="What would you tell yourself at the start of this?"
          className="mt-1 w-full rounded-lg border border-border bg-input px-2 py-1 text-sm"
        />
        <Button
          type="submit"
          size="sm"
          variant="secondary"
          className="mt-1"
          disabled={save.isPending || learned.trim() === (data.learned ?? "").trim()}
        >
          Save
        </Button>
        {error && <p className="mt-1 text-sm text-destructive">{error}</p>}
      </form>
    </section>
  );
}
