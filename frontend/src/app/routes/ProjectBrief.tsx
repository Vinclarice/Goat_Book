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
 * Three sections became five on August 22, 2026 — **S16's other two nouns**.
 * The story's done-means is *notes, decisions and sources*, and this reached one
 * of three from `kestrel` until `Source` and `Decision` shipped hours apart.
 *
 * **The two new sections are reached through recorded provenance**, not through
 * a second retrieval: a source is here because a note above came out of it, a
 * decision because it cites one. So each reason is a fact the person can check
 * rather than a score they must trust — the same argument the material section
 * makes, one model over.
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

  /* Five sections now, and all five have to be empty for the brief to be.
     Missing one here would have shown "nothing bears on this" above a list of
     decisions, which is the sort of contradiction a reader stops trusting a
     surface over. */
  const empty =
    data &&
    !data.material.length &&
    !data.questions.length &&
    !data.commitments.length &&
    !data.sources.length &&
    !data.decisions.length &&
    !data.learned_before.length;

  return (
    <section className="mt-6 border-t border-border pt-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="secondary" onClick={() => setAsked(true)} disabled={isFetching}>
          {isFetching ? "Looking…" : "What bears on this?"}
        </Button>
        <span className="text-sm text-muted-foreground">
          Prior notes, questions, what you read, what you decided — nothing is changed
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
          {data.decisions.length > 0 && (
            <div>
              <h3 className="text-sm font-bold">What you decided</h3>
              {/* `considered` is the half a note cannot keep: eighteen months
                  later the alternatives are the part you have forgotten, and
                  S11 exists because of it. */}
              <p className="text-sm text-muted-foreground">
                Choices made while looking at this material, and what else was on the table.
              </p>
              <ul className="mt-2 space-y-2">
                {data.decisions.map((decision) => (
                  <li
                    key={decision.id}
                    className="rounded-lg border border-border px-3 py-2"
                  >
                    <p className="text-sm font-medium">{decision.question}</p>
                    <p className="text-sm">
                      Chose: {decision.chose}
                      {/* Shown but marked. A replaced decision presented as
                          current is worse than omitting it -- and omitting it
                          would remove the part that makes keeping the record
                          worth anything. */}
                      {decision.superseded && (
                        <span className="text-muted-foreground"> — later replaced</span>
                      )}
                    </p>
                    {decision.considered && (
                      <p className="text-sm text-muted-foreground">
                        Over: {decision.considered}
                      </p>
                    )}
                    <p className="mt-1 text-xs text-muted-foreground">{decision.reason}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {data.sources.length > 0 && (
            <div>
              <h3 className="text-sm font-bold">What you read</h3>
              <p className="text-sm text-muted-foreground">
                Sources this material came out of — reached through what you wrote, not by title.
              </p>
              <ul className="mt-2 space-y-2">
                {data.sources.map((source) => (
                  <li
                    key={source.id}
                    className="rounded-lg border border-border px-3 py-2"
                  >
                    <p className="text-sm">
                      {source.title}
                      {source.author && (
                        <span className="text-muted-foreground"> — {source.author}</span>
                      )}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">{source.reason}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {data.learned_before.length > 0 && (
            <div>
              <h3 className="text-sm font-bold">What earlier projects taught you</h3>
              {/* S12's "kept for next time". A lesson stored where only its own
                  finished project can show it has been filed, not kept -- and
                  the moment it matters is the next project, which is this one.
                  Named with its source, because a lesson with no source is an
                  aphorism and he cannot judge whether it still applies. */}
              <ul className="mt-2 space-y-2">
                {data.learned_before.map((lesson) => (
                  <li
                    key={lesson.project_id}
                    className="rounded-lg border border-border px-3 py-2"
                  >
                    <p className="text-sm">{lesson.learned}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      from {lesson.project_title}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {data.provenance_says && (
            /* D5's discipline, one axis over: an empty section cannot
               distinguish "nothing bears on this" from "nothing records where
               it came from", and today the second is the true one. The read
               carries the sentence so two surfaces cannot phrase one silence
               differently. */
            <p className="text-sm text-muted-foreground">{data.provenance_says}</p>
          )}
          {data.abandon_if && (
            /* S10's second clause -- "still there when he is deciding whether
               to continue" -- and the brief is the moment of deciding. The
               field has existed since S10 shipped and the payload dropped it,
               so nobody ever saw it here. Last, because it is the question you
               ask after reading the rest rather than before. */
            <div className="rounded-lg border border-border px-3 py-2">
              <h3 className="text-sm font-bold">What would tell you it went wrong</h3>
              <p className="text-sm">{data.abandon_if}</p>
            </div>
          )}
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
