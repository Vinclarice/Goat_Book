# The application overhaul — one page — focused spec

**The whole application becomes one page.** Both cores, every surface. Vince,
September 6, 2026: *"So I do want to go ahead and rebuild it to just be one
page."*

[`app-overhaul-audit-2026-09-06.md`](app-overhaul-audit-2026-09-06.md) is the
diagnosis and owns the eight findings; this plan does not restate them. Its
one-sentence version is the premise here: **one login, one API, one palette, and
about thirty places to stand.**

**This is the largest thing this repository has attempted**, and it is written
knowing that. It is also the third time the same move has been made at a smaller
scale — Money collapsed a silo into a module, Superlists 2.0 collapsed a core
into a page — so the shape is not speculative. What is new is the scope.

---

## The one rule everything else follows

**The page is bounded the way the list is.**

Superlists 2.0's insight was that a day's commitments must be a *set you chose*
rather than everything that exists, and that the list stays useful precisely
because it refuses to grow. The same argument applies one level up: **a page
that shows today is useful for the same reason a list that holds today is.**

So the page holds today, and everything else *opens* from it.

---

## The design, as rules

1. **There is one place to stand.** One route. Every navigation entry that
   currently says *go somewhere else* is either absorbed into it or deleted.

2. **Detail opens; it does not navigate.** A task, a note, a concept, a person,
   a source, a bill, a month, a week — each keeps a URL, is deep-linkable, and
   answers the back button. **What none of them keeps is a nav entry.** You
   arrive at one by opening something in front of you, never by deciding to go
   there from a menu.

   **This is what resolves G3 rather than contradicting G1.** `Note` and
   `Person` need front doors and get them — as things you can open from the
   page, not as the twelfth and thirteenth entries in a sub-nav.

3. **The spine is the day.** The bounded list, the line under it, the log of
   what happened, the pool beside it — Superlists 2.0's page, unchanged in
   meaning. The knowledge core's material hangs off the same spine because it
   already does: the composer writes a `Node`, and rule 6's log is a read over
   records that already carry a time.

4. **Capture stays server-rendered, and stays at `/mind/`.** The property worth
   protecting is a page you can type into with a thumb that loads instantly, and
   **that property belongs to capture, not to browsing concepts.** `/mind/` and
   `/mind/share/` keep their templates and their zero bytes of JavaScript. The
   other ten surfaces in that core move.

   Verified rather than assumed: the Android client posts to `/api/v1/capture`
   (`ClariceApi.kt:264`) and never loads a page, so **the phone is untouched by
   this plan** — including its encrypted offline queue, which `CLAUDE.md` warns
   is exactly what a confident deletion here would drain into 404s.

5. **Nothing that has a URL loses it.** Every retired surface redirects.
   `/agenda` → `/day` is the precedent and it is a rule rather than a courtesy,
   because the installed PWA has **two live shortcuts** pointing at
   `/mind/review/` and `/mind/search/`, and `CLAUDE.md` names bookmarks as the
   reason `/capture/` was freed and deliberately not taken.

6. **One navigation, and it shrinks to almost nothing.** `ViewNav` and
   `SideNav` both retire — a sub-nav that says *which surface* has one surface
   to name, and a rail that says *what is in here* is already down to one group
   (G2). **The app bar loses its Cores nav too**: there is one place to go.
   What it keeps is identity, Contact, the account and Log out, each of which
   [`_app_bar.html`](../src/lists/templates/_app_bar.html) defends in a comment
   worth reading before touching.

7. **No new models.** [`architecture-trajectory.md`](architecture-trajectory.md)
   §4 governs and is not overridden by anything here. This is a surface
   overhaul; a concept earns a model when it has a different life cycle, and
   nothing here has one.

---

## What is on the page, and what opens from it

**On the page — today, and only today:**

| Section | Where it comes from |
|---|---|
| Appointments | `appointments/`, shipped September 4 |
| The bounded list, and the line | `daily`, Superlists 2.0 rules 1–4 |
| The log — what happened today | `clarice/day_log.py`, rule 6 |
| The composer | `clarice/composer.py`, four destinations |
| The pool, beside it | `lists/agenda.py`'s `pool_for` |
| The day, read back — leftovers and their three moves | `daily/reads.py`, rule 7 |
| One search box | `/mind/search/`'s machinery, which already reads both cores |

**Opens from it, each addressable, none in a navigation:**

Task · Note · Concept · Person · Decision · Source · Question ·
Bill · a Money month · Balances · History · Categories ·
the week's Review · the Archive · a Project · Preferences · Ask · Numbers

**Seventeen things that open, seven sections that stand.** Against roughly
thirty places to stand today.

---

## Increments

**Ordered so the Day page is last.** Vince chose on September 6 to leave
Superlists 2.0's acceptance running, and that fortnight ends around **September
18**. Sequencing preserves it at no cost: every increment before 7 touches
surfaces the fortnight is not measuring, so the evidence survives and nothing
waits.

0. **The fortnight, and its friction log.** Running now, no code. Superlists
   2.0's acceptance needs ordinary use to about September 18;
   [`app-overhaul-audit-2026-09-06.md`](app-overhaul-audit-2026-09-06.md)'s
   closing section asks that it also carry one sentence a day — *what did you
   have to leave the day page to do, and what did you not do because of where
   it lived*. **This is D2 and it is Vince's.** Without it the usability half
   of this plan is unevidenced and every increment below says so.

1. ~~**The panel mechanic, proven on one thing.** Task detail — `/tasks/:id` —
   becomes something that opens rather than somewhere you go: URL kept, back
   button honoured, focus managed, closable. Nothing else moves.~~
   **Shipped September 6, 2026.** `panel.tsx` holds the mechanic —
   `PANEL_ROUTES`, `backgroundFor`, `PanelLink`, `usePanelClose` and `Panel` —
   and `AppRoutes` renders two sets of routes at once when a panel is open.
   The five links to `/tasks/:id` became `PanelLink`s; the path is unchanged
   and every bookmark still works.

   **Chosen as the first because it is also a repair.**
   [`coherence-audit-2026-08-30.md`](coherence-audit-2026-08-30.md)'s F3 is
   that what you can do to a task depends on which page you met it on; one
   panel opened from everywhere is that finding's answer, not just a mechanic.

   **What building it taught, and it sharpened this plan's own refusal.** *Not
   a modal* turned out to be three separate settings rather than a sentiment,
   and **a test found each one**:

   - Radix's modal mode marks the page behind `aria-hidden` and inert, so it
     is *visible and dead*. Caught by an existing test that renders a link
     outside the route on purpose. `modal={false}`.
   - A scrim over that page is the same mistake in CSS. The overlay was
     deleted rather than restyled.
   - A non-modal dialog closes on any outside interaction, which would dismiss
     the panel the moment you touched the page it is meant to sit beside.
     Caught by the same test, where a click on a link fired a close and a
     navigation at once and the close won. Outside interaction is now
     prevented; a panel closes the way a route does — Escape, its Close
     button, or the back button.

   **Two things were repaired in passing rather than silently.** The task
   page's *"← Back to the agenda"* fallback outlived the Agenda by two days and
   now says the day; and the delete confirmation's test was matching
   `role="dialog"` bare, which the panel made ambiguous — it has carried an
   `aria-label` all along and the test now uses it, which is what a person
   hearing two dialogs needs too.

   **D4 is not yet answered.** Only one kind of panel exists, so nothing has
   had the chance to stack.

2. **The knowledge core stops being a second application.** Concepts, Read,
   Decisions, Then, Pending, Numbers and Ask become panels, and **`Note` and
   `Person` get the indexes they have never had** (G3). Ten surfaces retire
   with redirects; `/mind/` and `/mind/share/` keep their templates.

   **The largest increment, and the one that ends the first complaint.** It is
   also where the cost of D1 is actually paid, so it is worth stating plainly
   what is spent: browsing the graph stops being instant-loading and
   JavaScript-free. Capture does not.

   **Split in two on September 6, 2026, before it was started, because it had
   a hidden half.** `mind/api_v1.py` is **one GET and seven POSTs** — the GET
   is search. Every one of those ten surfaces is a Django view reading models
   directly, so there is no API for a panel to consume and "make them panels"
   silently contained "build the knowledge core's read API first".

   - **2a. The read API.** GETs on `mind/api_v1.py` for the ten surfaces, plus
     the schema regeneration and `generate:api` that
     [`CLAUDE.md`](../CLAUDE.md) requires before the SPA can type against them.
     **Pure addition: no UI changes and `/mind/` keeps working throughout**, so
     it is independently shippable and independently wrong-able.
     **A router in `mind/api_v1.py`, never a second API** — `CLAUDE.md` is
     explicit, and the knowledge core's own `NinjaAPI` was deleted on August
     15 having never been called.

     Struck here as each lands, because 2a is many small commits rather than
     one, and an increment that ships in pieces is the kind that gets
     mis-remembered as finished:

     - ~~**Concepts** — index and detail~~ **September 6, 2026.**
       `GET /concepts`, `GET /concepts/{public_id}`. Session-only. Mirrors
       `views.concepts` and `views.concept` rather than improving on them,
       **including the evidence sentences** — a candidate that showed its count
       without them would be a quieter surface, not the same one. One
       deliberate divergence: an unknown id is a **404** where the page
       redirects to the index, because a panel needs to know it asked for
       something that is not there.
     - ~~**Sources** / *Read* — index and detail~~ **September 6, 2026.**
       `GET /sources`, `GET /sources/{public_id}`, the latter carrying
       `what_grew_from` — notes and the tasks they became, **reached along the
       chain rather than stored**, so a source cannot disagree with the task
       core about what came of anything.
     - ~~**Decisions** — index and detail~~ **September 6, 2026.**
       `GET /decisions`, `GET /decisions/{public_id}`. **`due` is not a list**,
       and modelling it as one is a mistake this made and a test caught:
       `decisions_to_revisit` returns the dated ones *and a count of those
       waiting on a condition in words*, because only the dated ones can be
       found by a query and saying how many cannot is the difference between a
       read that is incomplete and one that is misleading.
     - ~~**Notes** — index (new, G3)~~ **September 6, 2026.** `GET /notes`,
       newest first, `live_nodes` and nothing wider, with `total` counted
       before slicing. **The one part of 2a that mirrors no view**, because
       there was none: this is the front door capture has never had.
     - ~~**People** — index (new, G3)~~ **September 6, 2026.** `GET /people`,
       confirmed people only — a candidate is the system's guess and the
       soft-apply rule keeps a guess out of a directory of the people in
       somebody's life; and people only, because `views.person` redirects a
       motif rather than rendering one.
     - Note detail and person detail — **split off from their indexes on
       purpose.** `views.note`'s context has twenty keys and `views.person`'s
       carries commitments and a name's shape across time. The front doors were
       the gap G3 named and are worth closing alone; these are their own piece.
     - Review / *Pending*
     - *Then* — this time before
     - Numbers
     - Start
     - Dump and Ask

     **`Dump` is a writing surface and may belong with capture rather than
     here.** Rule 4 keeps `/mind/` and `/mind/share/` server-rendered for the
     thumb-typing property, and Dump is bulk entry — the same property, one
     surface further out. Noticed while enumerating; not decided.
   - **2b. The panels.** The SPA consumes 2a; the ten surfaces retire with
     redirects, including the PWA's two shortcuts.

   **Recorded rather than discovered mid-increment**, which is the whole
   argument for having read the code before writing the increment. It also
   confirms increment 3's estimate rather than undermining it: search is *"a
   move rather than a build"* precisely because it is the one thing here that
   already has its GET.

3. **One search box, on the page.** `/mind/search/`'s machinery already reads
   `Item`, `DailyEntry` and `Node`, so this is a move rather than a build. It
   retires the app bar's Search entry and the knowledge core's — G6's duplicate
   — and the PWA shortcut redirects.

4. **Money becomes one panel.** Landing, month, balances, history and
   categories inside it; the rail's contextual *Months* group goes, which
   `SideNav.tsx` already names as the right fix if it ever felt wrong. G7.
   [`module-score.md`](module-score.md) reads *not yet* for Money and this does
   not by itself move it.

5. **Review, Archive and Projects.** Three more panels. Superlists 2.0's D3 and
   D4 — the fate of `List`, `Project` and `Tag` — stop being deferrable here,
   because a page with no rail has nowhere to put a Projects group that is not
   a panel.

6. **The navigation retires.** `ViewNav`, `SideNav`, and the app bar's Cores
   nav. `sidenav.module.css` goes with them.

7. **The Day becomes the page.** After September 18. The sections above merge
   into one route, `/day` and the new route become the same thing, and every
   redirect written in 1–6 lands here.

8. **The PWA follows.** `scope` widens from `/mind/` to `/`, `start_url` stays
   at capture — **the phone's front door is capture and the desktop's is the
   page**, which is the shape rule 4 already argues for — and the two shortcuts
   repoint. Android needs no build: it posts to an API.

---

## What this refuses

- **A visual redesign for its own sake.** The palette is already shared —
  `mind/base.html` compiles from the same `@theme` and the theme toggle governs
  both cores (G5). **What makes an application look like one product is being
  one product**, and increments 2 and 6 do more for that than a restyle would.
  A deliberate visual pass is available as its own increment and is **D7**, not
  an assumption.
- **Deleting `/api/v1/capture`, `/mind/` or `/mind/share/`.** Rule 4.
- **A mobile application rewrite.** `android/` is a client of one API and this
  plan does not touch it.
- **Any new model.** §4.
- **Rewriting the app bar's reasoning.** Increment 6 removes one nav from it.
  Everything else in that file is argued in a comment and the audit calls it the
  best-argued file in the tree.
- **A modal.** Rule 2 says panels open; it does not say they trap. Anything that
  cannot be closed, deep-linked or reached by the back button is not what this
  plan means.

---

## Decisions

- ~~**D1. Does `/mind/` leave server rendering?**~~ **Answered September 6,
  2026: yes, except capture.** Vince chose the whole app, both cores. The
  qualification is this plan's, from evidence rather than compromise — the
  manifest's `scope`, `start_url` and share target all point at capture, and
  `ClariceApi.kt` posts to an API. **Ten surfaces move; two stay.**
- **D2. Does the fortnight carry a friction log?** Open, Vince's, and
  time-sensitive — it only works if it starts now. Not code.
- **D3. What is the one route called?** `/` is the honest answer if there is one
  page, but `/day` is what the fortnight is being measured on and what every
  habit points at. Deferred to increment 7, where it costs one redirect either
  way.
- **D4. Do panels stack?** Opening a Person from a Note from the log is three
  deep. A stack is more machinery; one-at-a-time is simpler and may be wrong.
  Answerable by building increment 1 and using it.
- **D5. What happens to `List`, `Project` and `Tag`?** Superlists 2.0's D3 and
  D4, forced by increment 5. The tables are untouched behind a retired
  interface and the decision is whether that is permanent.
- **D6. Does Money's month rail survive inside its panel?** Twelve months is
  what makes Money navigable and a panel is a worse place for a rail.
- **D7. Is there a deliberate visual pass?** *How it looks* was one of Vince's
  four complaints and this plan answers it structurally. Whether that is enough
  is a judgement he makes after increment 2, when there is one thing to look at.

---

## Acceptance

**Scored by using it, not by looking at it.**
[`module-score.md`](module-score.md) learned that on Money — its first verdict
read *works*, was taken three days after shipping by the person who built it,
and became *not yet* after one real walkthrough. This plan is far larger and the
same trap is correspondingly cheaper to fall into.

- **The friction log's answer gets shorter.** D2's one sentence a day is the
  before-measurement; the same question asked two weeks after increment 7 is the
  after. **If Vince still has to leave the page for the same things, the overhaul
  failed regardless of how few routes remain.**
- **The page is used on ordinary days**, `recall.attendance_between`, the same
  instrument Superlists 2.0 uses and for the same reason.
- **The nineteen journeys in [`product-stories.md`](product-stories.md) do not
  regress.** This plan moves surfaces, not capabilities; anything that drops
  below *works* is a defect in the move.
- **Surfaces you can decide to visit fall from about thirty to one.** The only
  criterion here that a tree can verify, and deliberately the least important
  of the four.

---

## Where the facts live

- [`app-overhaul-audit-2026-09-06.md`](app-overhaul-audit-2026-09-06.md) — the
  eight findings and the diagnosis. Not restated here.
- [`superlists-2.0-plan.md`](superlists-2.0-plan.md) — the day's rules, which
  this plan keeps whole, and the acceptance increment 0 is protecting.
- [`coherence-audit-2026-08-30.md`](coherence-audit-2026-08-30.md) — F3 is
  increment 1's second reason; F5 and F6 recur as G6 and G3.
- [`modules.md`](modules.md) — the charter for surfaces. Increment 4 is a test
  of it.
- [`architecture-trajectory.md`](architecture-trajectory.md) §4 — models, never
  overridden here.
- [`_app_bar.html`](../src/lists/templates/_app_bar.html) — read before
  increment 6.
