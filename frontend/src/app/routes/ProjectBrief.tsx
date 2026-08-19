import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";

import { apiV1 } from "../../api/client";

/**
 * What bears on this project — planning-assistant-plan.md increment 4.
 *
 * **Asked for, never implied**, and that is a design rule rather than a
 * performance preference. The Attention Policy permits a queue only inside a
 * ritual the person chose to open; a panel that retrieved on every render of a
 * page mostly wanting a title would be the unsolicited kind. `enabled` stays
 * false until the button is pressed, and `ProjectRoute.test.tsx` holds that as
 * a statement about executed requests rather than about intent.
 *
 * **Nothing here is a proposal.** Every item already exists and already belongs
 * to the person, so there is no confirm gate and no dismissal — a brief
 * assembles what is already theirs rather than claiming anything new about it.
 * That is also why opening one records nothing, unlike `/mind/review/`, which
 * stamps `first_surfaced_at` on purpose.
 *
 * Three sections because a piece of prior thinking, a loose end and a dated
 * commitment are three different things to do something about.
 */
export function ProjectBrief({
  projectId,
  hasPurpose,
}: {
  projectId: number;
  hasPurpose: boolean;
}) {
  const [asked, setAsked] = useState(false);

  const { data, isFetching, isError } = useQuery({
    queryKey: ["project-brief", projectId],
    enabled: asked,
    queryFn: async () => {
      const { data, error } = await apiV1.GET("/api/v1/projects/{project_id}/brief", {
        params: { path: { project_id: projectId } },
      });
      if (error) throw error;
      return data;
    },
  });

  const empty =
    data && !data.material.length && !data.questions.length && !data.commitments.length;

  return (
    <section className="mt-6 border-t border-border pt-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="secondary" onClick={() => setAsked(true)} disabled={isFetching}>
          {isFetching ? "Looking…" : "What bears on this?"}
        </Button>
        <span className="text-sm text-muted-foreground">
          Prior notes, unanswered questions and dated work — nothing is changed
        </span>
      </div>

      {isError && (
        <p className="mt-3 text-sm text-destructive">Couldn't gather that brief.</p>
      )}

      {empty && (
        /* An empty brief and an unanchored one look identical and mean opposite
           things. Saying which is the difference between "nothing of yours
           bears on this" and "you have not told me what this is". */
        <p className="mt-3 text-sm text-muted-foreground">
          {hasPurpose
            ? "Nothing you have written bears on this yet."
            : "This brief needs a purpose to work from — write one above and ask again."}
        </p>
      )}

      {data && !empty && (
        <div className="mt-3 space-y-4">
          <BriefSection
            heading="Still unanswered"
            items={data.questions}
            blurb="Questions you asked and nothing has answered."
          />
          <BriefSection
            heading="You wrote about this before"
            items={data.material}
            blurb="Notes that share wording appearing in almost none of your others."
          />
          {data.commitments.length > 0 && (
            <div>
              <h3 className="text-sm font-bold">Already committed</h3>
              {/* The only section that can be complete rather than merely
                  plausible: these are this project's own open tasks, not a
                  retrieval, so they carry no reason and need none. */}
              <p className="text-sm text-muted-foreground">
                Open work in this project, due before it is.
              </p>
              <ul className="mt-2 space-y-1">
                {data.commitments.map((task) => (
                  <li key={task.id} className="text-sm">
                    {task.text}
                    {task.due_date && (
                      <span className="text-muted-foreground"> — due {task.due_date}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

type BriefItem = {
  id: string;
  text: string;
  captured_at: string;
  reason: string;
  distinctive_terms: string[];
};

function BriefSection({
  heading,
  items,
  blurb,
}: {
  heading: string;
  items: BriefItem[];
  blurb: string;
}) {
  if (!items.length) return null;
  return (
    <div>
      <h3 className="text-sm font-bold">{heading}</h3>
      <p className="text-sm text-muted-foreground">{blurb}</p>
      <ul className="mt-2 space-y-2">
        {items.map((item) => (
          <li key={item.id} className="rounded-lg border border-border px-3 py-2">
            <p className="text-sm">{item.text}</p>
            {/* The reason is the mechanic, not decoration. Without it this
                panel can only say "related", which is the unfalsifiable label
                precision.md exists to avoid: a person can check "these share
                three words appearing in none of your other notes" and cannot
                check a score. */}
            <p className="mt-1 text-xs text-muted-foreground">{item.reason}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
