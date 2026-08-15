# One capture surface — the plan for Heron

Vince · August 15, 2026 · **active plan, nothing shipped yet**

Ends the crossover the merger deliberately left open. Two capture surfaces
become one: `/mind/` writing a `Node` survives, `/capture/` writing a `Capture`
retires, and `Capture` and `Idea` go with it. The authority on why is Second
Mind's [`two-cores.md`](../../dev/Clarice_secondmind/docs/two-cores.md); the
state of play as of today is in this repository's own audit of the two routes.

## The decision that unblocked this

**A typed tag becomes a confirmed concept — Vince's call, August 15, 2026.**

This was the one real trade. The Inbox models tags as first-class rows in
`lists.Tag`; the knowledge core deliberately models none, on the position that
structure should emerge rather than be declared at entry. Neither side is
obviously right, and picking either as-is loses something real.

The reconciliation: **the gravity gate exists to filter the system's guesses.**
Three mentions spanning a day is the price an *extracted* candidate pays before
it earns a question, because extraction over-generates on purpose. A person
typing a tag is not a guess and owes that gate nothing — it is exactly the
"somebody confirmed this" signal the concept layer is built around.

So a tag at capture skips straight to a confirmed `ConceptCandidate` plus an
explicit `Mention`. Tagging survives, the concept layer gains a second way to
grow that does not wait months for gravity, and the two structures stop being
parallel.

**Almost no new machinery.** `ConceptCandidate` already has `label`,
`confirmed_at` and `reason`; `propose_mention(..., origin=EXPLICIT)` already
self-confirms. This is wiring.

## Order of operations

Each step deploys on its own and leaves the application working. That is the
same discipline `two-cores.md` used, and it is why the merger shipped in a day.

1. **A typed tag becomes a confirmed concept.**
   At the knowledge core's capture endpoints, each tag resolves to a confirmed
   concept for that owner and an explicit mention on the node. Replaces the
   current placeholder, which records tags on the activity event under the note
   *"tags kept, not yet modelled"* — and backfills the tags already sitting
   there, since they are a real record of what somebody typed.
   *Ships alone. Android starts contributing structure the day it lands.*

2. **A task inherits its node's concepts as tags.**
   `confirm_actionable` passes the node's confirmed concept labels to
   `create_item(tags=...)`. This closes the last functional gap between the two
   routes: accepting a commitment from a tagged thought currently produces an
   untagged task.
   *Ships alone.*

3. **Move existing captures into the graph.**
   A one-time command in the shape of `import_second_mind`: every `Capture`
   becomes a `Node` carrying its original `created_at`, its tags as confirmed
   concepts, and its resolution. **An unresolved capture is the one that
   matters** — it is somebody's untriaged thought, and the whole point is that
   it stops needing triage. Resolved ones keep their link to whatever they
   became.
   *Needs a production row count first: locally there are zero captures and zero
   ideas, so the local run proves the mechanism and nothing about the volume.*

4. **Retire the Inbox.**
   Delete `/capture/`'s pages, the task core's `/api/v1/capture`, and the
   `Capture` and `Idea` models. Check first that nothing on the phone still uses
   the task-core capture scope — `Backends.kt` routes capture to the knowledge
   core, but `capture:write` still exists as a token scope and that is worth
   confirming rather than assuming.
   *The step that makes the whole thing worth doing: one place to type.*

5. **Move the surviving surface to its canonical URL.**
   `/mind/` was always temporary and appears in exactly one line of
   `clarice/urls.py`. With `/capture/` freed by step 4, the obvious home is
   there. Old paths redirect rather than break — a phone with a home-screen
   shortcut should not need reinstalling.

## What this does not settle

- **Where the knowledge core's other pages live.** Review, concepts, search and
  numbers move with the prefix in step 5, but whether they belong under the same
  root as the task core's agenda is a navigation question this plan does not
  answer.
- **Whether `Idea`'s notes and links survive the migration.** An Idea has notes
  and `related_ideas`; a Node has revisions and edges. The mapping is obvious in
  shape and needs a decision about whether links become confirmed edges or are
  dropped. Zero Ideas exist locally, so this may be moot — check production.
- **Anything about the daily page, routines or reviews.** They are the task
  core's and are untouched by this.

## How this gets verified

Two things beyond the suites, because both are how today's defects were found:

- **A journey test per step**, in `src/mind/tests/test_journeys.py`. Step 2's is
  the obvious one: capture with tags, accept the commitment, and assert the task
  carries them.
- **Walk it.** Every defect found on August 15 came from doing the thing a
  person does rather than from reading code, and three of them were in seams
  that had thorough unit coverage on both sides.
