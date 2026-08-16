# One capture surface — the plan for Heron

Vince · August 15, 2026 · **active. Steps 1, 2, 3 and 4a shipped and verified in
production August 15 as `DEPLOYED-2026-08-15/1200`. 4b and 5 built the same day
and await one deployment together — Vince's call, so that Heron lands whole.**

4a was verified on the droplet: the live schema carries `captured_at` and
returns a node, the Inbox sweep drained its last capture, and an offline capture
from the phone was walked end to end. 4b and 5 are verified by the full suites
plus a clean build — **production verification owed, and 4b carries an
irreversible migration**; see the pre-flight check under 4b.

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

4b. **Retire the Inbox.** *Built August 15, 2026; not yet deployed.*
   `/capture/`'s pages, forms, services, admin and tests are gone, along with
   `Capture`, `Idea`, and `migrate_inbox`, which retires with the models it
   moved. `capture/migrations/0008_delete_idea_capture` drops the two tables.
   Inbox and Ideas left both navs — the SPA's `SideNav` and the Django
   `base.html` — and `inbox_count`, `inbox_url` and `ideas_url` left the `/nav`
   payload. **`inbox_count` was the only number in the nav that measured a
   backlog, and nothing replaces it**; there is now a test asserting no nav key
   ends in `_count` except `archived_count`, because a bare nav entry invites
   somebody to add one.

   **The migration is irreversible and the app stays installed.** Django needs
   `capture` in `INSTALLED_APPS` for 0008 to run at all; removing the app in the
   same change would leave two tables in production that no migration can reach.
   Deleting the app is a follow-up, after the next deploy.

   Three things broke that had nothing to do with capture, and all three were
   latent rather than caused:

   - **`base.html` reversed `capture_inbox` and `ideas`**, so every
     Django-rendered page 500'd. Caught by the suite immediately.
   - **The generated migration would not reverse.** `idea_owner_status_idx`
     covers `owner`, and unapplying `DeleteModel` runs before unapplying
     `RemoveField` — so a rewind rebuilt the table and then indexed a column it
     had not re-added. Fixed with a `RemoveIndex` first.
   - **Four migration-rewind tests only rolled their own app forward** in
     teardown, leaving `capture` behind. Harmless for as long as every table had
     a live model, because the inter-test flush truncates by model; fatal the
     moment a table had none. They now roll the whole graph forward, which is
     what their comment already claimed and what `accounts` had always done.

   *The step that makes the whole thing worth doing: one place to type.*

5. **Settle the surviving surface's canonical URL.** *Decided August 15, 2026 —
   Vince's call. It is `/mind/`, and it does not move.*

   This step was written as *move `/mind/` to the URL 4b frees*, on the reasoning
   that the prefix was always temporary and `/capture/` was the obvious home.
   The first half was true and the second did not survive being asked directly.

   **`/capture/` was freed and deliberately not taken.** Nine routes sit under
   `/mind/` — capture, review, concepts, search, numbers, share, the manifest,
   and the tag and commitment actions — so `/capture/` would have named the
   smallest thing in the room, and `/capture/concepts/` reads as nonsense.
   Scattering them across the root instead (`/capture/`, `/review/`,
   `/concepts/`, `/search/`, all free) would have put a second "review" beside
   the task core's weekly one and spread a single core across four paths, ending
   the property that made this step cheap in the first place.

   Set against a rename with no winner: a live PWA home-screen shortcut and
   every bookmark, both of which a move breaks. **"Temporary" was a reason to
   reconsider the name once the collision was gone, not an obligation to move.**

   So the change is subtraction — the word *temporary* comes out of
   `clarice/urls.py`, `mind/urls.py`, both navs and their tests, and is replaced
   by the reason it is permanent. It stays one line and everything under it
   stays relative, so this is settled rather than welded.

   **4a is what made this a free choice.** `/api/v1/capture` is the
   application's, not a core's, and never moved with the prefix. Had the phone
   been pointed at `/mind/` instead, this step would have had to move an
   endpoint a queued client posts to — and a 301 or 302 would have broken it
   silently, since OkHttp converts a redirected POST to a GET.

## What this settled after all

- **Where the knowledge core's other pages live.** Listed below as unanswerable
  by this plan; step 5 answered it. They stay together under `/mind/`, which is
  a different root from the task core's `/app/` — two cores, two homes, one
  login and one nav reaching both.
- **Whether `Idea`'s notes and links survive the migration.** Yes, both, and
  automatically rather than by hand: notes became a revision and `related_ideas`
  became a confirmed `relates_to` edge, which is exactly what a person's own
  undirected link is. The two in production went through unexamined because the
  general rule turned out to be obvious once written.

## What this does not settle

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
