# One capture surface — the plan for Heron

Vince · August 15, 2026 · **active. Steps 1, 2, 3 and 4a shipped August 15;
4b and 5 remain.** 4a verified by 974 Django, 686 pytest and 271 frontend tests
plus a clean build; production verification still owed.

Ends the crossover the merger deliberately left open. Three capture surfaces
become one: `/mind/` writing a `Node` survives, `/capture/` writing a `Capture`
retires, and `Capture` and `Idea` go with it. The authority on why is Second
Mind's [`two-cores.md`](../../dev/Clarice_secondmind/docs/two-cores.md); the
state of play as of today is in this repository's own audit of the two routes.

**Three, not two — corrected August 15, 2026.** This document counted `/capture/`
and `/mind/` and missed the SPA Day page's quick-capture box
(`frontend/src/app/routes/DayRoute.tsx`), which posts to `/api/v1/capture` on
session auth. Retiring that endpoint would have broken the Day page as well as
the phone.

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
   concepts, and its resolution. Resolved ones keep their link to whatever they
   became.

   **Production, checked August 15, 2026: 34 captures, 8 of them unresolved,
   and 2 ideas.** Those numbers change what this step is for.

   The 8 unresolved are somebody's untriaged thoughts, and the point of the
   crossover is that they stop needing triage. But **the 26 resolved ones are
   the reason to migrate all of them**: the corpus is the binding constraint on
   this entire core. Three detectors rest on argument rather than evidence
   because there is no material, and the gravity gate cannot see recurrence in a
   corpus of four notes. Thirty-four real captures with real timestamps spread
   over months is the largest single body of material available, and it is
   currently sitting inside the model being deleted.

   So this is not cleanup that happens to preserve data. **It is the step that
   gives the detectors something to work on**, and it should run before anybody
   judges whether they are any good.

   Two ideas is small enough that their `notes` and `related_ideas` can be
   mapped by hand if the automatic answer is unclear — see below.

4a. **One `/api/v1/capture`, writing a node.** *Shipped August 15, 2026.*
   The check step 4 asked for came back the opposite way round, and that changed
   the step. **`Backends.kt` does not route capture to the knowledge core** on
   any build ever shipped: `secondMindBaseUrl` defaults to `""`, so `isSplit` is
   false and `capture` is literally the same object as `workspace`. Every thought
   typed on the phone posts to the task core's `/api/v1/capture`, and deleting it
   would have drained the offline queue into 404s.

   So the endpoint keeps its URL, its bearer token and its `capture:write` scope
   and changes what it writes — a `Node`, via `services.capture_idempotent`,
   shared with `/mind/api/v1/capture` so the two cannot drift. The router moved
   from `capture/api_v1.py` to `mind/api_v1.py`; the `capture` app now serves
   nothing on `/api/v1/`, which is what makes 4b a deletion rather than a
   migration. No APK rebuild, no second login, and one `/api/v1/` for the whole
   application.

   `mind/urls.py` predicted exactly this: the two definitions of
   `/api/v1/capture` were "the dual-write question arriving early, and it is
   answered when facets land — one capture endpoint that writes a node and
   optionally a task." Facets landed.

   **It also fixed a live defect.** Android sends `captured_at` from both call
   sites; this endpoint's schema was `text` and `tags` only, so Ninja dropped it
   silently and every queued thought was stamped with the moment the network came
   back. That was fixed once already — on `/mind/api/v1/capture`, which nothing
   calls. The fix had shipped to the wrong endpoint and the defect stayed live
   for a day.

4b. **Retire the Inbox.**
   Delete `/capture/`'s pages, `capture/services.py`, and the `Capture` and
   `Idea` models. Unblocked by 4a: nothing writes a `Capture` any more except
   `/capture/new/`'s own form, which goes with it.
   *The step that makes the whole thing worth doing: one place to type.*

5. **Move the surviving surface to its canonical URL.**
   `/mind/` was always temporary and appears in exactly one line of
   `clarice/urls.py`. With `/capture/` freed by step 4b, the obvious home is
   there. Old paths redirect rather than break — a phone with a home-screen
   shortcut should not need reinstalling.

   **4a made this a pages-only move**, which is what makes an ordinary redirect
   safe. `/api/v1/capture` is the application's, not a core's, and does not move
   with the prefix. Had the phone instead been pointed at `/mind/`, this step
   would have broken it a second time — and with a 301 or 302, silently: OkHttp
   converts a redirected POST to a GET.

## What this does not settle

- **Where the knowledge core's other pages live.** Review, concepts, search and
  numbers move with the prefix in step 5, but whether they belong under the same
  root as the task core's agenda is a navigation question this plan does not
  answer.
- **Whether `Idea`'s notes and links survive the migration.** An Idea has notes
  and `related_ideas`; a Node has revisions and edges. Notes map to a revision
  cleanly; whether a link becomes a confirmed edge is the real question. There
  are **two** in production, which is few enough to decide by looking at them
  rather than by writing a general rule.
- **Anything about the daily page, routines or reviews.** They are the task
  core's and are untouched by this. The daily page's quick-capture box is the
  exception, and only because it posts to the endpoint 4a converted.
- **The knowledge core's second API.** `/mind/api/v1/` has its own `login`,
  `me`, `tokens` and `capture`, backed by `mind.ApiToken` — a second token table
  in an application with one user table. It was built so a native client could
  point at a separate Second Mind server, which never happened, and 4a means it
  never will. Almost certainly zero tokens issued in production; worth checking
  on the box before removing.
- **Android's split machinery.** `Backends.isSplit`, `secondMindBaseUrl`, the
  second `Connector`, the second Keystore slot and Settings' "reconnect
  workspace" flow are all for a two-origin world the merger ended. Dormant and
  harmless; removing it needs an APK rebuild and is not needed for correctness.

## How this gets verified

Two things beyond the suites, because both are how today's defects were found:

- **A journey test per step**, in `src/mind/tests/test_journeys.py`. Step 2's is
  the obvious one: capture with tags, accept the commitment, and assert the task
  carries them.
- **Walk it.** Every defect found on August 15 came from doing the thing a
  person does rather than from reading code, and three of them were in seams
  that had thorough unit coverage on both sides.
