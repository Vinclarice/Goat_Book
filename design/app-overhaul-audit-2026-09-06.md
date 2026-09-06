# Whole-application audit — September 6, 2026: both cores

**A record and a diagnosis, not a repair list.** The repairs belong to
[`app-overhaul-plan.md`](app-overhaul-plan.md), ~~which does not exist yet and
which this document is written to make writable~~ — **written the same day,
September 6, 2026**, after Vince read this and answered: *rebuild it to just be
one page*, the whole app, both cores. Nothing here is a production
defect: [`commercial-blueprint.md`](commercial-blueprint.md) Part 1 remains the
sole authority for that list and is still empty.

**Reviewed at:** `main` at `088d9ae`, working tree clean.

**Asked for by Vince, September 6, 2026**, in these words:

> *So actually I want to do an overhaul of the app*

Asked what that meant, he named **all four** of the readings offered: the two
halves are different applications; there are too many surfaces; how it looks;
and it does not work day to day. He also chose to leave Superlists 2.0's
acceptance running — so this is planned now and built after **September 18**,
and the Day page is out of scope until then.

**The predecessor.** [`coherence-audit-2026-08-30.md`](coherence-audit-2026-08-30.md)
asked a smaller version of this question seven days ago and scoped itself to
the task core. Its nine findings and six repairs stand; this document does not
re-litigate them. **The half it did not look at is the half that is a different
application**, which is where this one starts.

---

## What was actually run

**Nothing.** This is reading only, per [`principles.md`](principles.md). No
suite was executed for it and no page was opened. Every count below is from the
tree at `088d9ae` and is reproducible by the command beside it.

**This matters more than it usually does**, because one of the four complaints
cannot be answered this way at all — see *The finding that cannot be made by
reading*, which is the most important section here.

---

## The one-sentence diagnosis

**There is one application, one login, one API and one palette — and about
thirty places to stand.** Superlists 2.0 proved the remedy at the scale of one
core, by replacing many surfaces with one bounded page; nothing has been done
at the scale of the app, and the knowledge core has never had it done at all.

The August 30 sentence was *every seam is between something built before there
was a pattern and something built after*. That was true of the plumbing and it
has largely been repaired. **What is left is not plumbing. It is inventory.**

---

## Findings

### G1. Thirty places to stand, for one person

Counting index-level surfaces — somewhere you can decide to go, not a detail
page you arrive at:

| | Surfaces |
|---|---|
| Task core, in `ViewNav` | Today, Pool, Review, Calendar, Money, Archive — **6** |
| Money, inside itself | landing, month, balances, history, categories, bill detail — **6** |
| Task core, reachable only by link | `/areas/:id`, `/projects`, `/projects/:id`, `/tasks/:id`, `/preferences` — **5** |
| Knowledge core, in its sub-nav | Start, Capture, Dump, Concepts, Read, Decisions, Then, Pending, Search, Ask, Numbers — **11** |

```bash
grep -c "path(" src/mind/urls.py        # 33, counting detail and action routes
grep -n "Route path=" frontend/src/app/AppRoutes.tsx | wc -l
```

**Twenty-eight, and the true figure is higher** because `/mind/`'s thirty-three
routes include action endpoints that render pages on failure. For one user.
This is the complaint *too many surfaces* stated as a number, and it is the
finding the other three mostly reduce to.

### G2. The rail survived its own contents

`SideNav` renders **one group**: Projects. The Views group became `ViewNav` on
September 3; the Account group moved into the app bar; the Areas group was
deleted on September 4 by Superlists 2.0's increment 8. What is left is a
disclosure on a phone and a column on a desktop, holding a list of projects.

**And it still pays for what it no longer shows.** `SideNav.tsx:55` destructures
`areas` from `/api/v1/nav` and nothing renders it:

```bash
grep -n "areas" frontend/src/app/SideNav.tsx    # fetched, never used
```

**This one is mine, September 4**, and it is the smallest instance of the
pattern the whole audit is about: the container outlived the thing it held.

### G3. Two of the knowledge core's central nouns have no front door

`/mind/notes/<uuid>/` and `/mind/people/<uuid>/` render. `/mind/notes/` and
`/mind/people/` **do not exist** — there is no index for either:

```bash
grep -n "people\|notes" src/mind/urls.py
```

A Note is what capture writes and a Person is one of the four things the graph
is built to relate; both are reachable only by arriving from search, review or
another node's page. This is
[`coherence-audit-2026-08-30.md`](coherence-audit-2026-08-30.md)'s F6 — *no
front door* — in the core that audit did not examine, and twice over.

**It is also the counterweight to G1**: the answer to thirty surfaces is not
uniformly *fewer*. Two of the missing ones are load-bearing.

### G4. Capture is five call sites, and `CLAUDE.md` still says one surface

```bash
grep -rn "services.capture\|capture_idempotent" src/mind/views.py src/clarice/composer.py
```

`mind/views.py` at 178, 884, 893 and 1183, plus `clarice/composer.py:124`,
plus `/api/v1/capture` for the phone and the Day page. `CLAUDE.md` states
**"There is one capture surface — `/mind/`, writing a `Node`"**, which was true
when it was written and stopped being true on September 4, when the Day page's
composer began writing nodes.

**Recorded as a documentation defect, not a design one.** Rule 6 wanted the day
to feed the corpus and it does; what is stale is the sentence, and
`CLAUDE.md`'s own repeated lesson is what a stale sentence costs when it is
quoted as a reason.

### G5. The two halves differ in physics, not in paint

The colour seam is **already closed** and should not be re-opened as work.
`mind/base.html` calls `theme_resolution_script` and `token_styles`, so both
cores compile from one `@theme` and the theme toggle governs both. Its own
comment records that this was once two hand-maintained palettes.

What still differs is how the two halves *behave*:

| | Task core | Knowledge core |
|---|---|---|
| Navigation | client-side routing | full page loads |
| Writes | TanStack Query, optimistic | form posts |
| Components | shadcn primitives | hand-rolled `.btn`, `.chip` in one `<style>` block |
| JavaScript | a bundle | **none at all** |

**And the last row is a feature, deliberately bought.** `mind/base.html` says
the binding constraint is a page comfortable to type into with a thumb, loading
instantly. An overhaul that unifies by making `/mind/` a React route spends
that, and the spend has to be argued rather than assumed. ~~This is the
overhaul's central decision and it is D1 in the plan.~~ **Answered September 6,
2026, and the argument turned out to be narrower than the question**: the
manifest's `scope`, `start_url` and share target all point at *capture*, and
the phone posts to an API rather than loading a page. So ten surfaces move and
two stay — see the plan's rule 4.

### G6. Search appears twice; Review means two things

**Search** is in the app bar *and* in the knowledge core's sub-nav, pointing at
the same `/mind/search/`. On a `/mind/` page it is rendered twice, a few pixels
apart, in two different type treatments.

**Review** is the task core's weekly review at `/review` and the knowledge
core's resurfacing queue at `/mind/review/`. The UI already dodges this — the
sub-nav labels the second one *Pending* — so the collision is in the URLs, the
view names and the vocabulary, not on screen. It is
[`coherence-audit-2026-08-30.md`](coherence-audit-2026-08-30.md)'s F5 across
the core boundary rather than inside one.

### G7. Money is six surfaces because it was the first module

`/money` landing, month, balances, history, categories, bill detail — plus a
contextual *Months* group that makes the rail mean two things depending on
where you stand. That contextual group is documented in `SideNav.tsx` as taken
against the recommendation, with the escape hatch named: *if it starts feeling
wrong, the fix is a column on the Money page itself.*

[`module-score.md`](module-score.md) reads **not yet** for Money on Vince's own
sentence, after four defects in his first real walkthrough. **The overhaul
should not assume Money's shape is the module pattern's shape** —
[`modules.md`](modules.md) is the charter, and Money is one instance of it that
has been used once.

### G8. The knowledge core has never had a Superlists 2.0

Eleven sub-nav entries, each a place you must decide to visit. The task core
had this shape and it is exactly what Vince said he would not use. There is no
equivalent of *the bounded list* on the knowledge side: no single page that
says what today's knowledge work is, only eleven doors.

**`Start` is the closest thing and it is one of the eleven**, which is the
tell — a front page that has to be navigated to is not a front page.

---

## What is coherent, in fairness

An audit that only finds fault is one nobody can calibrate against.

- **The app bar is the best-argued file in the tree**, and every decision in it
  is defended in a comment: `core` passed rather than inferred, Search placed
  outside the Cores nav on purpose, one logout replacing two, Contact outside
  the authenticated branch. **Do not touch it without reading it.**
- **One palette, one theme toggle, one login, one API, one token table.** The
  merger's promises held.
- **`/mind/` loading with no JavaScript is a real property**, measured against a
  real constraint, and it is the thing most easily destroyed by an overhaul
  that means well.
- **Superlists 2.0 is the pattern, not just prior work.** One page, a bounded
  set, a line, a log, one pool beside it. G8 is the observation that it has a
  second half nobody has built.

---

## The finding that cannot be made by reading

**Three of the four complaints are answered above. The fourth — *it does not
work day to day* — is not, and it is the one that decides whether the other
three matter.**

This project has been wrong here twice, in writing:

- [`module-score.md`](module-score.md) read **works** for Money and now reads
  **not yet**. The first verdict was taken three days after shipping, by the
  person who built it, against a screen that already had data. Four defects
  turned up in the first real walkthrough.
- [`coherence-audit-2026-08-30.md`](coherence-audit-2026-08-30.md) records its
  own first answer as wrong: it consulted
  [`product-stories.md`](product-stories.md), found every task-core journey at
  *works*, and concluded there was nothing to say. **The score measures
  journeys end to end and is blind to the seams inside them.**

So the overhaul plan must not be written from this document alone.

**The proposal: the fortnight is already running, and it should be measured
rather than merely waited out.** Superlists 2.0's acceptance needs Vince using
the Day page on ordinary days until about September 18. That same fortnight can
answer this, at the cost of one sentence a day: **what did you have to leave the
day page to do, and what did you not do because of where it lived.**

`recall.attendance_between` already counts the days. What it cannot see is the
friction, and nothing in the tree can. **Whether that log happens is D2**, and
it is Vince's — if the answer is no, the plan gets written from eight findings
and says plainly that its usability half is unevidenced.

---

## Where the facts live

- [`coherence-audit-2026-08-30.md`](coherence-audit-2026-08-30.md) — the task
  core's nine seams and six repairs. Not restated here.
- [`superlists-2.0-plan.md`](superlists-2.0-plan.md) — the pattern G8 says the
  knowledge core lacks, its open decisions, and the acceptance now running.
- [`modules.md`](modules.md) — the charter for surfaces. Governs G7.
- [`architecture-trajectory.md`](architecture-trajectory.md) §4 — governs models,
  and is never overridden by the charter. Nothing here proposes one.
- [`module-score.md`](module-score.md), [`product-stories.md`](product-stories.md)
  — the two scoreboards, and both are named above for what they cannot see.
