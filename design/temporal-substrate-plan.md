# Temporal substrate — focused spec

Vince · focused spec · written August 20, 2026 · **not started**

## What this is

Teaching memory what happened, so that a recollection can answer *what was
going on around this* and *what developed afterward* — and so that what cues a
resurfacing can be a person's present rather than the sentence they just typed.

**The trigger, and it fired three times independently.** Written up as a brief
rather than left as direction because three separate lines of thinking arrived
at the same missing piece on the same afternoon:

1. A recollection with context needs *what was happening around it* and *what
   developed afterward*. Neither has a read.
2. Prospective recall needs a present-context cue, and today the only present
   the knowledge core can see is the text of the capture in front of it.
3. A weekly instrument's most valuable reading — where intention and attention
   disagree — needs both sides of the product in one place.

All three resolve the same way, which is what makes this one piece of work and
not three.

## What is already there, and what is not

**The knowledge core is a semantic index of thoughts.** Its twenty-one reads in
[`mind/queries.py`](../src/mind/queries.py) are adjacency in *meaning* —
`nodes_mentioning`, `confirmed_mentions_of`, `search_ranked`,
`confirmed_concept_labels`, similarity, threads. Two of them are already the
shape recollection wants: `material_bearing_on`
([`queries.py:580`](../src/mind/queries.py)) and `context_for_question`
([`queries.py:722`](../src/mind/queries.py)). Salience has more machinery than
the documents credit — `attention_tier`, `is_due_for_review`, `review_state`.

**The task core is a temporal index of a life**, and none of it reaches memory.
[`review/reads.py`](../src/review/reads.py) is week-grained end to end —
`week_bounds`, `completed_in_week`, `planned_in_week`, `written_in_week`,
`habits_in_week`, `recent_weeks`, `typical_week_for`. `DailyFocus` snapshots
what was *chosen*, and `released_at`
([`daily/models.py:165`](../src/daily/models.py)) is how a pin ends, so a
decommitment can be told from a failure. `WeeklyReview` stamps the figure a
person concluded from.

**Neither can see the other, and the schema says so exactly:**

- **Memory has two intake pipes.** `Node` is created in exactly two places in
  the tree — `capture` ([`mind/services.py:204`](../src/mind/services.py)) and
  thread articulation ([`mind/services.py:1381`](../src/mind/services.py)). A
  `Facet` attaches to a `node`, a `daily.DailyEntry`, or a `lists` task
  ([`mind/models.py:338`](../src/mind/models.py) and the comment above it).
- **`EventType` has 23 values and every one is about a note**
  ([`mind/models.py:775`](../src/mind/models.py)) — captured, revised,
  concept\_\*, facet\_\*, mention\_\*, edge\_\*, hypothesis\_\*,
  thread\_articulated, imported, archived, purged. Nothing about a task, a day,
  a week, a commitment, an outcome or a routine.
- **So the most carefully guarded structure in the codebase is a note log, not
  a life log.** `ActivityEvent` is append-only by database trigger
  ([`mind/migrations/0002_invariant_triggers.py`](../src/mind/migrations/0002_invariant_triggers.py))
  with exactly one hole, for account erasure
  ([`0015_erasure_exemption`](../src/mind/migrations/0015_erasure_exemption.py)).
  It is the right structure with the wrong vocabulary.

**The one seam that exists runs the wrong way for this.** `confirm_actionable`
([`mind/services.py:662`](../src/mind/services.py)) has the knowledge core
reach into the task core, imported inside the function precisely so the
direction stays visible. Under this work the dependency wants to run the other
way, and D1 below is that question.

## What this inherits rather than rediscovers

Three lessons are already paid for and are repeated here only as *inherit
this*:

- **A node-less event is already legal.** `MAINTENANCE_RAN`
  ([`mind/models.py:802`](../src/mind/models.py)) is owner-scoped and
  node-less, "unlike everything above it." The model does not have to bend to
  hold an event whose subject is a task.
- **Adding a second cross-core foreign key is a move already made.** `Facet`
  gained `entry` after `task`, and the comment at
  [`mind/models.py:335`](../src/mind/models.py) settles it: *"crossing into
  `daily` is the same move rather than a new kind of one."* `ActivityEvent`
  gaining the same nullable subjects is that move a third time, not a new
  precedent.
- **A quiet log reads as a quiet life, and this project has been caught by it
  twice.** `MAINTENANCE_RAN` exists so `/numbers/` can tell *ran and found
  nothing* from *never ran*, "which no amount of counting rows can
  distinguish"; `retirement_gate`'s miss condition needs a non-zero baseline
  "or a quiet start reads as an improvement." D5 is that lesson arriving a
  third time, this time where a user can see it.

## The hard part: ingesting facts without building an event bus

`commercial-blueprint.md` Part 4 refuses domain events, an event bus and Django
signals, on the grounds that they "create derived state that can drift, in a
codebase whose best property is that history cannot be silently rewritten." It
is right, and this work must not quietly reverse it.

**The line: memory ingests facts, not derivations.**

- *"This commitment was released on the 14th"* is a fact. It is what happened,
  it is already recorded, and an append-only row is the honest home for it.
- *"This project is stalling"* is a derivation. It stays computed on demand out
  of source rows, the way `review` does it today.

The distinction is not stylistic. A fact cannot drift because nothing recomputes
it; a derivation stored is a second copy of an answer that will diverge from the
question. **Nothing in this work may write a row that a read could have
produced.**

## Scope — what becomes an event

**Slice 1 emits only where a durable decision already exists**, because those
are the points that already survive a redesign:

| Core | Emitted when |
|---|---|
| `lists` | a task is completed, released, or its commitment changes |
| `daily` | a focus is pinned, and when it is released (`released_at` already records it) |
| `review` | a week is reviewed, an intention set, an outcome chosen |

**Deferred by name**, so their absence is a decision and not an oversight:
routine occurrences, project pause and resume, area changes, and every
task-field edit that is not a change of commitment. The last of those is the
one to be careful with — a log that records every keystroke of a task's text is
a log nobody can read.

## Increments, in order

**The first three are invisible**, which is the same shape unified search had
and is deliberate: the substrate has to be trustworthy before anything reads
from it.

1. **The vocabulary, emitting nothing.** `EventType` gains its life-event
   values; `ActivityEvent` gains the nullable subject foreign keys `Facet`
   already carries. Migration only. The acceptance is that the append-only
   trigger still refuses `UPDATE` and `DELETE` on the widened table, and that
   `accounts.services.purge_account` still clears an owner completely —
   `mind/tests/test_erasure.py` is the test that must keep passing on purpose.
2. **The task core emits.** `lists`, `daily` and `review` write events at the
   service functions where they already record something durable. No backfill,
   no reads, nothing surfaced. D1 is answered in code here.
3. **Backfill what carries its own timestamp.** A management command, over
   completed items, released pins and stamped reviews. **Nothing invented**:
   where a source row has no recorded time, no event is written. Reconstructed
   events are marked as such, so a later reading can tell a record from a
   re-presentation.
4. **`around()` — element 2.** Given an owner and an instant, what else is in
   the log nearby. The first read that crosses, and the first time a note can
   answer *what was going on when I wrote this*. Tested, unsurfaced.
5. **`since()` — element 5.** What developed after a node, which needs D4's
   bearing rule and is the increment most likely to produce noise. If D4 cannot
   be answered honestly, **stopping at four is the correct outcome** rather
   than shipping a read that pads a recollection with everything that happened
   afterward.
6. **One visible thing, on a surface that already exists.** Temporal context
   attached to the node page or the search result rather than a new
   recollection page — the same reasoning search's own D2 used, and for the
   same reason: a new surface would separate this from the instruments that
   judge whether it works.

## Open decisions — Vince's, not this document's

1. **D1. Which direction does the seam run?** Does `lists` import `mind` to
   emit, does `mind` expose a thin ingest function the task core calls, or does
   the write go through a module in `clarice/` belonging to neither? **Search's
   own D1 predicted this question** — it answered "the endpoint lives beside
   capture" while recording that search belongs to neither core, and named
   `clarice/search.py` as where the question would be asked again. This is that
   second asking, one document later.
2. **D2. How far back does backfill reach, and how is a reconstructed event
   marked?** The whole argument for this work is that the task core already
   holds the history; the whole argument against inventing it is that this
   codebase deliberately left defect 2's misdated routine records alone rather
   than guess at a durable record. `Facet.origin`'s `EXPLICIT` / `INFERRED`
   split is the obvious shape to copy.
3. **D3. Payload snapshot, or foreign key only?** `ActivityEvent` already has
   both — a `payload` and a node FK — so there is precedent either way. A FK
   can cascade away; a payload cannot drift but duplicates what the source row
   says. The answer probably differs per event type, which is itself a decision.
4. **D4. What makes a later event *bear on* an earlier node?** Element 5's
   rule, and the one that decides whether *what developed afterward* is a
   recollection or a list of everything that happened since. Candidates: a
   shared confirmed concept, an explicit edge, the same project, or temporal
   proximity gated by similarity. `dormant_thread`'s stance is the one to
   inherit — precision over recall, because a stream of poor connections
   "teaches the person to skim past the review surface, and no later
   improvement recovers that."
5. **D5. Can the log answer absence?** A recollection that ends *"since then,
   nothing has been recorded"* is only honest if the log can prove it was
   looking. `MAINTENANCE_RAN` is the precedent and the question is whether
   every emitting surface needs an equivalent, or whether absence claims are
   simply refused in the presentation until they can be earned.

## What this refuses

- **An event bus, domain events, or Django signals.** See *The hard part*
  above; the refusal in `commercial-blueprint.md` Part 4 stands and this work
  is shaped to keep it standing.
- **Moving `Item` into `Node`.** The inversion this serves is conceptual —
  task-core records become citable evidence — not a merge of two primitives.
  `architecture-trajectory.md` §7's refusal is untouched.
- **Building the recollection surface.** The seven-element recollection and the
  answerable briefing are what this unblocks, not what it delivers. They earn
  their own briefs, after there is something to read from.
- **Inventing history.** No event without a recorded timestamp on the source
  row.
- **A second event log.** `ActivityEvent` is the log; it gains a vocabulary,
  not a sibling.

## A correction this brief owed `product-stories.md`, since made

That file's three-loop table said *"The second brain is not a fourth loop. It is
the memory of the third one."* Vince's call, August 20, 2026: **that was wrong**
— memory is the substrate, and the three loops are tempos of reading and writing
it. **Corrected in `product-stories.md` the same day**, which owns the fact and
now carries what the old line was hiding. Recorded here only because this brief
was written against the corrected model before the correction landed.

## Where the facts live

Whether this is active, deferred or open is [`roadmap.md`](roadmap.md)'s. What
shipped and how it was verified is
[`roadmap-history.md`](roadmap-history.md)'s. The knowledge core's design
authority is `design-concept.md` in Second Mind's own `docs/`, and nothing here
overrides it — the facet and event models are its, and this brief widens a
vocabulary rather than proposing a design. How the product scores is
[`product-stories.md`](product-stories.md)'s, including the correction above.
