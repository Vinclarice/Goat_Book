# Clarice — commercial blueprint

Vince · written August 12, 2026 · supersedes nothing yet, decides several things

## What this is

`roadmap.md` says what is active and deferred. `architecture-trajectory.md` says
what order things go in and why. Both were written for a personal tool with
three users, and both are honest about it — `architecture-trajectory.md` §5 puts
release G behind "a deliberate decision that Clarice should have users who are
not you."

This document is that decision being taken, and what it costs. It is the output
of a twelve-part audit run on August 12, 2026 across the backend, frontend,
security, tests and CI, infrastructure, product, Android, data layer, the
two-core split, user journeys, architectural patterns, and AI strategy. Every
claim below was verified against code or a command that was actually run; where
a finding is an estimate it says so.

It answers three questions that were asked together and turn out to be one
question:

1. What stands between Clarice and a commercial product?
2. The project has grown two cores — productivity and second brain. What
   should be added, removed, or modified?
3. What architectural patterns would genuinely improve this?

## The verdict, stated plainly

**The engineering is not the problem. In several specific, nameable ways it is
better than commercial average.** The audit found zero IDOR across six apps —
every ID-taking surface scopes ownership in the lookup rather than checking
afterwards. There is no raw SQL, no file upload, no SSRF, no open redirect: not
merely no bugs, no attack surface. No secret has ever been committed. The
migration history genuinely follows expand–migrate–contract. The idempotency
contract is textbook. Scoped tokens have no scope-blind default, so an endpoint
that forgets to think about scope fails to construct. There are zero
TODO/FIXME/HACK comments in the non-test tree. The Django suite is 937 tests in
73 seconds with near-zero mocking, running real HTTP against real Postgres, with
positive controls on every ownership rejection. Clocks are injected. History is
snapshotted so it cannot be silently rewritten.

**What is missing is the commercial substrate, and it is missing entirely.**
There is no billing, no plan model, no entitlement check. No account deletion
and no data export — a legal blocker, not a feature gap, with Sentry and Resend
already processing user data. No terms, no privacy policy. No analytics of any
kind, so every product decision to date is n=1 introspection. No onboarding, no
help, no in-product explanation of six invented concepts. No import from any
competitor. One outbound channel, a 07:00 email, which contains no link.

**And a stranger cannot become a user.** Signup creates the account
`is_active=False` (`src/accounts/forms.py:77`) and an admin ticks a checkbox
(`src/accounts/admin.py:25`). `src/accounts/emails.py` contains exactly three
functions — support message, pending-signup notice to admins, lockout notice to
admins. **None of them tells the user they were approved.** The funnel
terminates at a manual gate with no callback. That is the first sixty seconds of
this product today.

The strategic risk is not technical. It is that the project's centre of gravity
has moved into its own planning apparatus: 35 files and ~11,000 lines of design
prose for a three-user app, six separate commits spent correcting stale document
statuses, and six of the last seven work items shipping outside the release
structure that supposedly governs them.

## Part 1 — Broken right now

These are defects in production or in the pipeline today, not commercial
readiness items. They are ordered by how quickly they should be fixed, and none
of them is large.

> **Status, August 14, 2026.** Nine of the ten are fixed — **1** (CI green again,
> across five jobs), **2** (the wrong day), **3** and **4** (the dropped Tailwind
> styles), **5** (the white screen), **7** and **8** (the Android queue's lock and
> its backup exclusion), **10** (Sentry locals) — plus **9** in part.
> Each is marked in place rather than deleted, because what a defect was is the
> part worth keeping.
>
> **Nothing in Part 1 is open in code.** Nine are fixed; **6 is closed as
> won't-fix** (see its entry). What remains is the half of **9** that is not
> code: nothing polls `/healthz`. **3 and 4 turned out
> to have been fixed on August 12** and this document said otherwise for two
> days; that is the second time Part 1 has claimed finished work was open, so
> check the code before believing a line here.
> See `CLAUDE.md` for the live list — this document is the analysis, not the
> tracker.
>
> **One fix does not repair what it prevented.** Defect 2 wrote real records
> against the wrong date for as long as it existed, and correcting the code
> leaves those rows exactly as they are. They cannot be found reliably either:
> the fix removes the difference between a token-written row and a
> session-written one, and nothing ever recorded which path created a
> `RoutineOccurrence`. A repair would have to guess, on a durable record, which
> is the thing `principles.md` refuses. Left alone deliberately, and named here
> so it is a decision rather than an oversight.

**1. ~~CI has failed 17 consecutive runs.~~ Green again August 14, 2026**
(`fd4a8d7`, run 31849757672) — and it needed more than the one cause below. The
`mind` suite was not in CI at all, `postgres:18` carries no pgvector for
`CreateExtension("vector")`, and the browser job could no longer use SQLite once
the knowledge core's migrations existed. Five jobs, all passing.

The original finding, which remained true for four more days: last green was
2026-08-10T20:39, and every run since had failed. `17aec20` added a Postgres default at
`src/clarice/settings.py:288`, and its own comment asserts "DJANGO_DATABASE_URL
still overrides it, which is exactly what CI does." That is true of the `django`
job and **false of the `browser` job**, which deliberately has no Postgres
service (`.github/workflows/ci.yml:50`). The Playwright suite now dies in
`setup_databases` and never reaches a test. Two consequences: the only suite that
loads the real bundle in a real browser has been dark for two days, and
`14810ba` — the locator fix — has never been verified by CI, because the database
failure masks it. Red has stopped carrying information.

**2. ~~Token-authenticated writes record the wrong day.~~ Fixed August 14, 2026**
(`6da41c8`) — at `_resolve_scoped_token`, the seam both token paths already
share, rather than at the endpoints. The suggestion below was
`TokenAuth.authenticate`, which would have missed `token_or_session_required`
and left half the surface; and the knowledge core turned out to carry the same
defect in its own resolver, so it was fixed in the same commit. Rows written
before it are still wrong — see the status note above. `TimeZoneMiddleware`
runs before Ninja resolves a bearer token, so `request.user` is anonymous and the
middleware deactivates (`src/accounts/middleware.py:21`). Its own docstring says
"a future date-bearing token endpoint has to activate the owner's zone itself."
Five such endpoints have since shipped and none does:
`src/routines/api_v1.py:159,185,218` and `src/daily/api_v1.py:282,292,316`. An
Android user outside `America/New_York` logging a routine writes into the wrong
`RoutineOccurrence` period — a durable record `principles.md` says must not be
silently wrong. There is a real user in Indonesia. Fix inside
`TokenAuth.authenticate` (`src/accounts/auth.py:72`), where the owner is first
known, so both auth paths converge.

**3. ~~Screen-reader-only labels are rendering as visible text.~~ Fixed
August 12, 2026** (`2986ed6`, already in production) — every use is `sr-only`
now, and that class is present in the built CSS. Verified by grep, not by the
commit message: this entry said otherwise for two days.
`.visually-hidden` is used 13 times across `AgendaWorkspace.tsx`,
`TaskWorkspace.tsx` and `ArchiveManager.tsx`, and is **defined in zero shipped
stylesheets** — verified by parsing the built CSS. It only ever existed in
Bootstrap's utilities, retired with `site.css`. Stray "Task", "Area", "Due date",
"Search your agenda" are on screen on the Agenda, Area and Archive pages right
now. Newer code correctly uses `sr-only`; this is an unswept rename.

**4. ~~The side nav has no active-page highlight.~~ Fixed August 12, 2026**
(`2986ed6`, already in production) — the same commit, the same root cause. All
five variables `sidenav.module.css` reads are declared in the shipped CSS. `sidenav.module.css`
references `var(--border)`, `var(--text)`, `var(--accent)`, `var(--accent-subtle)`
and `var(--muted-foreground)` — **zero declarations each** in the shipped CSS,
while Tailwind v4's `@theme` emits `--color-border` and `--color-text`. An
invalid `var()` unsets the whole declaration, so the nav has lost its right
border, its hover feedback, and its current-page indicator. Same root cause as
3: a token rename that CSS modules didn't follow, and nothing type-checks CSS.

**5. ~~Any render exception is a white screen.~~ Fixed August 14, 2026**
(`0428efb`) — `AppBoundary`, wrapped outermost in `src/app/main.tsx` so it
catches the providers and router as well as route content. The only `componentDidCatch` is
at `frontend/src/main.tsx:26`, inside the island entry point that no template
references any more. `app/main.tsx` mounts the router with no boundary.

**6. ~~Tags are dropped on one of two promotion routes.~~ Will not be fixed —
decided August 14, 2026.** Not data loss, which this entry did not say: the Idea
is marked `PROMOTED` and keeps `promoted_task`, so the tags remain on it and
remain reachable. Against a two-line fix stands a model the merger retires and
no known affected row. Deliberate, so that the next reader does not spend the
fifteen minutes deciding again. `promote_to_task`
(Capture → Item) carries them (`src/capture/services.py:135`);
`promote_idea_to_task` (Idea → Item) calls `create_item(for_list, idea.text)`
with no tags (`:232`). Same user intent, different outcome by route.
`second-mind-discovery-plan.md` §4.2 declared this closed having audited only the
hops out of Capture.

**7. ~~The Android capture queue has no lock.~~ Fixed August 13, 2026** -- a process-wide lock on the companion object, not `@Synchronized`, because MainActivity and CaptureWorker each construct their own `CaptureQueue` over one store, so a per-instance monitor would have passed a shared-queue test and protected nothing. Covered by a two-thread test over two instances. `grep -rn 'Mutex\|synchronized\|
withLock' android/app/src/main/` returns nothing. `CaptureQueue.add/delivered/
update` each load → mutate → save, and `CaptureViewModel.submit()` races
`CaptureWorker.doWork()` in the same process. Interleaving `add` against
`delivered` loses the new capture permanently, and the window opens while the
network is active — when someone is most likely typing. This is the one failure
the app exists to prevent.

**8. ~~The Android queue is not excluded from backup.~~ Fixed August 13-14, 2026** -- in `backup_rules.xml`, and then in `backup_rules_legacy.xml` a day later, because the first fix reached only API 31+ while minSdk still admits 26.
`android/app/src/main/res/xml/backup_rules.xml` excludes only the token file.
The queue store rides cloud backup and device transfer; the Keystore key does
not travel; decrypt returns null and the queue reads as empty. Unsent thoughts
vanish silently on phone upgrade — by the file's own stated reasoning, applied to
the token and not the queue.

**9. ~~Nothing would tell you the site is down at 3am.~~ Half fixed.** `restart_policy: unless-stopped` shipped in `b2e16b2` and `/healthz` in `fd896c6`; **nothing polls it yet**, which is the half that still matters. Sentry reports errors
from a *running* application. A dead container, dead host, expired certificate or
hung gunicorn produces zero events, which is indistinguishable from a quiet
night. There is no `/healthz` for anything to poll, and `deploy-playbook.yaml`
sets **no `restart_policy`**, so Docker's default `no` means a reboot or OOM kill
takes the site down until you personally intervene.

**10. ~~Sentry can ship private note text.~~ Fixed August 14, 2026** (`bbfc38d`). `include_local_variables` defaults to
`True` and is independent of `send_default_pii=False`. Any 500 inside a capture
or daily-entry path sends the stack frame's locals — `text`, `intentions`,
`notes` — to a third party. The code comments assert the opposite.

**Also, cheaply:** `src/app/routes/` is an empty directory tree; the deploy runs
`migrate` *after* recreating the container (`deploy-playbook.yaml:259` then
`:292`), so new code serves traffic against the old schema for the migration's
duration; `frontend/openapi.json` has drifted 146 lines from the server and no CI
step diffs it; and CLAUDE.md plus `settings.py:279` both still justify Postgres
with `nulls_distinct=False`, a flag deliberately dropped in
`0027_retire_subtask_fields.py:18`. Staying on Postgres is still right — four
partial unique indexes need it — but the stated reason is stale.

## Part 2 — The two cores

### What is actually true

The split is real, and **the boundary is not the app label. It is the rendering
stack.**

Core A — productivity — is `lists`, `routines`, `review`, `daily`: 13 models,
~5,990 lines, every one of the 13 SPA routes, 31 Ninja endpoints plus 7 legacy
hand-rolled ones.

Core B — the second brain — is `capture`: 2 models, ~924 lines, **zero SPA
routes**, three Django templates, and exactly one API endpoint, which exists only
so Android can post. `SideNav.tsx` reaches it with a raw anchor and carries a
comment explaining why React Router cannot.

**Leaving your second brain means leaving the application.** That single fact is
worth more than any conceptual argument about whether these belong together.

An `Idea` has eight fields. No `updated_at`, so you cannot tell whether one has
ever been revisited. No title/body distinction — `text` is both, with `notes` as
a second undifferentiated `TextField`. And there is **no full-text search
anywhere in the product**: `grep -rn 'SearchVector\|SearchQuery\|
TrigramSimilarity\|GinIndex\|pg_trgm' src/` returns nothing. The only search over
ideas is `text__icontains`; the Agenda, Area and Archive boxes are
`Array.includes()` over data already in the browser. A daily journal entry is
not searchable by any means at all, and there is no date picker anywhere in the
frontend — reaching a day twelve weeks back means clicking "the week before"
twelve times.

The index `idea_owner_status_idx` was added *specifically for a ranked search
that was never built*, with a comment saying so.

### The verdict

> **Answered August 13, 2026, and not by either option this section offered.**
> The two-core question is settled by Second Mind: a separate project that
> Clarice is absorbed into, ending as one application with a knowledge core and
> a **Superlists** task core. See `roadmap.md`'s opening section.
>
> This section's framing survives the answer and its diagnosis was right —
> "leaving your second brain means leaving the application," the seam is
> one-directional and lossy, and the current middle is the worst of the three
> available options. The resolution is the third thing it named without
> expecting: **`Idea` is retired, but not in order to "be a very good task
> app."** It is retired because a better implementation of the same ambition
> exists elsewhere, with a node model, a concept layer, a detector registry
> and measured precision figures. The self-sealing trap named below is broken
> the way this section said it would have to be — deliberately, not by waiting.

**One product, but the claim is currently unearned in code.**

The strongest "one product" argument is already written and is good: *the Daily
Page is a lens over durable records, not a new place to copy them*. Under that
thesis Core B is not a side feature — it is the retention half of one loop. A
thought arrives; triage decides whether it needs *action* or *retention*; the
review reads both back. `Tag` already spans both cores. The review already
queries both. The unit of value is identical in each: a thing you wrote down and
don't want to lose.

The strongest "split them" argument is that the seam is one-directional and
lossy. Nothing flows from work back to knowledge — completing a task produces no
retained material, and a year of finished work generates zero. All three
promotion FKs use `related_name="+"`, so from a task you cannot find the idea or
capture it came from. The review *knows* about stale captures and renders them as
inert `<span>` text with no way to act on them.

The precedent is unkind to the current configuration. Products that unified
successfully made *one primitive* serve both — Notion and Tana have a node that
can gain a checkbox; Amplenote's note *is* the task container. Products that
stayed split put tasks inside notes, so knowledge is primary. Clarice has neither:
two primitives, a one-way conversion, knowledge subordinate to tasks. That is
roughly where Evernote's reminders and Mem's early to-dos landed.

There is also a self-sealing trap worth naming. `second-mind-discovery-plan.md`
§1 defers search until there is volume. Nobody accumulates ideas in a store they
cannot search. Something has to break that loop deliberately, and it will not be
broken by waiting.

**So: do not split. But either invest enough in Core B that the loop closes, or
retire `Idea` and be a very good task app.** The current middle — a knowledge
core at ~900 lines with 1,616 lines of tests, absent from the SPA, unsearchable,
unexportable — is the worst of the three, because it carries the maintenance and
vocabulary cost of a second core while delivering almost none of its value.

### Three moves that make the two cores one product

> **Two of the three are cancelled, August 13, 2026; one survives with a
> different justification.**
>
> **M1 (bring Core B into the SPA) is cancelled** — building an SPA home for
> `Capture` and `Idea` would be investment in the half that does not survive
> the merger.
>
> **M3 (close the loop backwards) is cancelled** as stated. Its insight is
> right and is answered structurally rather than by four `related_name`
> renames: in Second Mind every capture is a node, so provenance is not a
> pointer that has to be maintained in the correct direction.
>
> **M2 (full-text search) survives, narrowed.** Not cross-core — over
> Clarice's own material, `Item.text`, `Item.notes` and `DailyEntry`'s three
> fields, which is a real gap in the half Clarice keeps. See `roadmap.md`'s
> Track D entry.

**M1. Bring Core B into the SPA.** A real Ninja API for `Capture` and `Idea`;
`/app/inbox` and `/app/ideas` routes; retire the Django templates. Everything
else is blocked on this, and the Android full-client direction needs exactly this
API anyway — two payoffs for one build.

**M2. Cross-core full-text search.** Postgres `SearchVector` + GIN over
`Item.text`, `Item.notes`, `Idea.text`, `Idea.notes`, `Capture.text` and
`DailyEntry`'s three fields, behind **one** search surface. This is what makes
the second core worth having, and searching only one core would re-inscribe the
split. Cheap on Postgres 15; the index intended for it already exists.

**M3. Close the loop backwards.** Rename the four `related_name="+"`
declarations and surface "came from" on the task detail page — nearly free. Then
add a "what did I learn?" prompt at task completion: the first path in this
product's history from work to knowledge, and the only intervention that
generates the material every deferred second-brain feature is waiting on.

## Part 3 — Feature verdicts

### Add

**Essential to the thesis**

- Cross-core full-text search (M2). Highest leverage single item in this document.
- Inbox and Ideas as SPA routes with a real API (M1).
- Backlinks from task to idea/capture (M3).
- **Account export and deletion.** Legal obligation, and a private second brain
  with no exit is a trust problem before it is a feature gap.
- **Task priority.** A to-do core with recurrence, routines, pauses and snapshot
  denominators, and no priority field, is unbalanced.
- **Onboarding and a first action on the landing surface.** A new user lands on
  `/app/day` (the default `landing_surface`) which has no affordance that creates
  anything. The "Start your first area" CTA exists only on `/agenda`, which that
  user never sees.
- **An approval email** — or removal of the approval gate entirely.

**Valuable, not essential**

- `Idea.updated_at`. One field; makes "has this been revisited" answerable.
- A deferred/start date distinct from `due_date`, so snooze stops erasing the
  original commitment.
- Completing and adding a task from the Day page. The daily loop's core act
  currently requires navigating away, by explicit design decision
  (`DayRoute.tsx:117`) — that decision should be revisited now that it is the
  home surface.
- Date navigation: a picker on `/app/day`, a week jump on `/app/review`.
  `/day/:date` currently has no UI entry point at all.
- Links in the digest email. It presently ends "Open Clarice to work through
  them." with nothing clickable.
- Streaks or a habit heatmap. For a product whose sharpest differentiator is
  quantified practice, "you're on day 34" is table stakes and is absent.
- Bulk triage and keyboard shortcuts in the Inbox. A 40-item backlog is
  currently 40 sequential page loads.
- Task move between areas. `item_detail` PATCH accepts six fields and `list` is
  not among them (`src/lists/api.py:197`), so a misfiled task stays misfiled.

**Explicitly not yet:** graph view, spaced repetition, calendar/ICS, command
palette, AI synthesis. All correctly deferred; none has a trigger.

### Remove / retire

- `src/app/routes/` — an empty directory tree.
- The dead island layer: `frontend/src/main.tsx`, `frontend_assets()` in
  `frontend_tags.py`, and the `app` JS Rollup entry. No template references any
  of the three mount points; it still builds and ships.
- `static/bootstrap/` — 8.4 MB still in the tree after retirement.
- The Django `/capture/` template stack, once M1 lands.
- `src/lists/api.py` + `api_urls.py` — seven hand-rolled endpoints that own
  *every task mutation*, with a different error envelope from `/api/v1/`, no
  OpenAPI description, and an undocumented "exactly one field per PATCH" rule
  every client must know. Finish the migration or stop paying for both.
- `Idea.Status.REFERENCE` — merge into `EXPLORING`. Its own model comment says
  the two are "the same shape of object," and then ships them as two filters.
- The README's no-JavaScript claim. `/dashboard/` is a bare redirect
  (`src/lists/views.py:15`), `app_shell.html` is an empty div plus a script, and
  there is no `<noscript>` anywhere. Delete the claim rather than restoring the
  behaviour.

### Modify

- `promote_idea_to_task` must carry tags, with the regression test.
- Snooze should not overwrite `due_date`; add `deferred_until`.
- The review's ideas and captures must be actionable, not text. The query is
  already there; it just refuses to let you act on it.
- Unify discard semantics — `Capture` discard is soft, `Idea` delete is hard.
- `Idea.text`/`Idea.notes` → `title`/`body`, or merge. Two undifferentiated
  `TextField`s with no rule about which holds what will harden.
- Raise the 44px floor into `button.tsx` rather than patching call sites.
  Default is `h-8` (32px), no variant reaches 44px, and 41 of 49 usages are
  unpatched — including "Save the day" and "Save the review", the two pages that
  *do* have phone tests, which measure overflow but not target height.

## Part 4 — Architecture

The honest name for the current shape is **a layered modular monolith with
transaction-script services, separate read modules, and invariants pushed into
SQL constraints, sliced by Django app.** That is deliberate and coherent, not
tutorial residue. `principles.md`'s read/write split is the best-kept principle
in the codebase, enforced by a test that asserts against *executed SQL*.

Three real gaps, and they are all boundary problems rather than pattern problems.

**A rule mirrored into three languages with no conformance test.**
`bucket_for` exists in `src/lists/agenda.py:131`, `frontend/src/agenda.ts:37` and
`android/.../AgendaFormatting.kt:17`. `WEEK_HORIZON_DAYS` likewise. Each has its
own tests; none tests the others. The duplication grows once per client, and the
cause is a contract decision — `/api/v1/agenda` ships every task unbucketed and
each client buckets it. The server owns the *rule* on paper and ships *inputs* in
practice.

**No enforced module boundaries, so a comment can stand in for an invariant.**
Two comments assert a boundary that does not exist, in mirror image:
`src/lists/api_v1.py:217` says of capture "no FK, no import the other way" while
`capture/services.py:12` and `capture/views.py:10` both import `lists`; and
`src/capture/models.py:79` says "nothing in lists imports this" while
`lists/api_v1.py` imports `Capture` and queries it three lines below its own
comment. Both are wrong, each about the other. Separately, `daily/api_v1.py:20`
imports schema classes from `lists.api_v1` and `routines.api_v1`, so a field
added to `TaskOut` for the Agenda silently changes the Day contract for all three
clients.

**Contract-first stops short of every mutation.** The generated
`frontend/src/api/schema.ts` covers reads only, so the frontend keeps a parallel
hand-written client and a parallel hand-written type set that has already
drifted, and Android hand-parses every field.

### Adopt

| | Effort | Why |
|---|---|---|
| Delete the dead island layer | S | Removes a build entry and 99 lines of misleading bootstrap |
| **Serve the date policy in the payload** | S | Add `bucket` to `TaskOut`, `week_horizon_days` and `snooze_presets` to the agenda payload; two of three implementations then delete. Highest ROI item here |
| `.importlinter` contracts in CI | S | ~30 lines; would have caught all three couplings above |
| A written five-context map | S | Planning / Practice / Knowledge / Reflection / Identity, with `Tag` named as a shared kernel rather than an accident of history |
| `contract.py` per context | M | Breaks the `lists ⇄ capture` cycle and the sibling-schema coupling |
| Migrate `lists/api.py` onto Ninja | L | Deletes two parallel client layers, gives Android a schema. Do it *after* the linter, so something holds the new boundary |
| `Item.status` transition table | S | Collapses ten guard sites into one mapping |
| A job queue | M | See Part 5 |

### Avoid, and why

Repositories and unit-of-work (a QuerySet is a repository; `reads.py` is already
the query facade). Hexagonal (the only port that ever mattered — the clock — is
already injected, without the pattern). **Domain events, an event bus, or Django
signals** — they would create derived state that can drift, in a codebase whose
best property is that history cannot be silently rewritten; `review` computing
from source rows on demand is the stronger design, and the absence of any signal
in `src/` is a good decision made implicitly that should be written down. Event
sourcing (same objection, larger). Feature folders (the Django app *is* the
slice; splitting would fragment shared service helpers). Pact (three clients, one
repo, one developer — the generated schema plus `tsc --noEmit` is the same
guarantee for free). A feature-flag service (needs a second environment to pay
off). The outbox pattern (needs a queue and multiple workers to exist first).
**Renaming `lists`, `Item`, or the app packages** — `architecture-trajectory.md`
§7 already refused this and was right.

## Part 5 — The commercial substrate

**Activation.** Remove the admin gate or automate it, and send the user an email
when their account goes live. Give `/app/day` a first action. Give `/` something
other than a login form. Explain the six invented concepts — Area, Project,
Checklist Step, Compass, Focus, "call it enough" — somewhere in the product, once.

**Lifecycle and legal.** Export and deletion. Terms, privacy policy, and a named
subprocessor list — Sentry and Resend are already processing user data. Decide
the immediate-versus-grace-period question that `roadmap.md:369` has been holding
open.

**Instrumentation.** There is no analytics of any kind. Shipping a positioning
wedge with no way to tell whether it landed is the most expensive mistake
available here. Minimum: an activation funnel and a weekly-review completion
rate, which is the metric the differentiation rests on.

**Operations, in this order.** External uptime monitoring plus a `/healthz` plus
`restart_policy: unless-stopped` — roughly four hours, and the largest risk
reduction per hour in the whole audit. Then fix the deploy: migrate before
recreate, SHA-tagged images, a rollback path, a 502 maintenance page. Then get
logs off the host: `recreate: true` destroys the container **and its logs** every
deploy, and gunicorn has no `--access-logfile`, so there are no HTTP access logs
at all. Then backups: 24-hour RPO with 7-day retention, a freshness check that
exists but is scheduled nowhere, and `~/.secret-key` living on exactly one
filesystem — losing it invalidates every session and outstanding reset token.

**Scale, measured not guessed.** The agenda's hottest query does a **global
sequential scan** of `lists_item`, because `Item` has no `owner` column and no
index can cover owner+status+due_date when owner is not on the table. Measured
against a 20k-row test database, `/api/v1/agenda` takes 1,828ms — of which ~24ms
is SQL and the rest is Python serializing an ~8MB response, because **there is no
pagination anywhere in the product**. Query counts are healthy and flat; the
`select_related` discipline is real. The problem is volume, and the fix is
`Item.owner` plus pagination, both cheapest now.

**Billing.** No payment processor, no plan model, no entitlement check, and no
pricing or packaging work anywhere in 11,000 lines of design prose — the topic is
one sentence at `roadmap.md:556`. Choosing the wedge is what unblocks this.

## Part 6 — Sequence

**Phase 0 — one week. Stop the bleeding.** Everything in Part 1. Start with CI,
because until it is green every other signal in this document is unreadable.
Nothing else in this plan should start while the pipeline cannot fail a deploy.

**Phase 1 — two to three weeks. Make production observable and the deploy
safe.** Uptime monitoring, `/healthz`, restart policy, migrate-before-recreate,
SHA-tagged images with a rollback path, logs off the host, backup freshness
scheduled, a DR runbook. Add `.importlinter`, a schema-drift check, `coverage`,
ruff and ESLint — none of which need new tests; they protect the ones that exist.

**Phase 2 — four to six weeks. Make it one product.** M1, M2, M3. Serve the date
policy in the payload. `Item.owner` and pagination. Delete the dead island layer
and `static/bootstrap/`. This is the phase that answers the two-core question in
code rather than in prose.

**Phase 3 — four to six weeks. Make a stranger able to become a customer.**
Self-service signup with email verification, onboarding and a first action,
export and deletion, terms and privacy policy, analytics, a support path for
signed-in users, and the landing page. This phase produces **zero new task
management capability**, and that is the point of naming it as a phase.

**Phase 4 — the wedge, then billing.** Pick the positioning, build the two or
three features that make it true, instrument it, then charge.

**Phase 5 — "Read my week."** A bounded, read-only, opt-in weekly briefing.
Design it alongside Phase 3 rather than after everything, because it needs
exactly what Phase 3 produces — a privacy policy, export, and a signup flow —
and building those twice is waste.

## Part 7 — Positioning

Three candidate wedges came out of the audit. The recommendation is the first two
together, because they are one story.

**A. "The productivity tool that tells you the truth about your week."** The moat
is the denominator. `DailyFocus` snapshots what was *chosen*, not what was due;
`released_at` distinguishes a decommitment from a failure; `WeeklyReview` stamps
the figure the person concluded from. Almost no competitor can report an honest
finish rate, because none of them stores the denominator — and it cannot be
retrofitted onto last year's data.

**B. "Quantified practice — habits with targets, not checkboxes."** Cadence plus
target quantity plus a human unit plus partial credit plus deliberate skip plus
pause, with history that survives editing the routine. This is the one place
Clarice is meaningfully ahead of Todoist and TickTick, and the vision document
already calls it a central reason the product exists.

**C. "The private, self-hostable daily OS."** Zero telemetry, a working Docker
and Ansible deploy, scoped tokens, a Keystore-encrypted mobile queue. This
sidesteps billing complexity and onboarding-at-scale, and matches the codebase's
actual shape — but it is a small market with a high support load.

The weakest option is competing head-on as a task manager, which is where the
roadmap's momentum currently points: three of the last five work items were
Tailwind redesigns of task surfaces.

On AI: the deferral was sound on foundations and is wrong on ordering. The gate —
"several months of weekly reviews actually being used" — is measured against one
person and may never fire. Re-gate it on something a cohort can satisfy. And note
the one asymmetry the vision document missed: AI usefulness scales with corpus
size for idea-resurfacing and next-week planning, and **not** for summarising a
week you can already enumerate. Week one is as tractable as week two hundred. A
year of one user's data is ~150k tokens and fits in a single context window, so
retrieval is not a problem this product has — embeddings and pgvector would be
over-engineering by an order of magnitude. A bounded weekly briefing costs on the
order of $0.59/user/month at frontier pricing; an open-ended chat over the corpus
costs $36–180 with no natural cap. That comparison is the argument against the
feature everyone will ask for.

## Part 8 — What this blueprint refuses

- **A rewrite.** Three independent reviews already agreed and were right: the
  testing culture, the injected clock, the isolation tests and the documented
  honesty are worth more than the migrations they cost to build around.
- **Renaming `lists` or `Item`.** Migration churn for no behaviour change. The
  vocabulary migration at the API boundary already works and is test-guarded.
- **Building a second core's worth of PKM features before search exists.** Search
  is what makes retention worth anything; a graph view over an unsearchable store
  is decoration.
- **AI before Phase 3.** Not on principle — on sequencing. It needs the privacy
  policy, export and signup that Phase 3 produces.
- **Adding another long planning document.** This one is deliberately the
  shortest thing that can carry the decisions. The audit found the doc corpus is
  itself now a liability, and the fix is fewer, shorter, current documents — not
  another 70KB plan.

## Part 9 — Decisions only Vince can make

1. **Is Clarice a business, a product with users, or a personal tool?** Phases 3
   through 5 are conditional on this and nothing else. The audit cannot answer it
   and neither can the roadmap.
2. **Which wedge?** A+B together is the recommendation; C is the delivery model
   most compatible with where the code is today. They are not mutually exclusive
   but they order the work differently.
3. ~~**Second brain: invest or retire?**~~ **Answered August 13, 2026:
   invest, elsewhere.** Second Mind is a separate project and Clarice is
   absorbed into it; `Capture` and `Idea` are retired because something better
   replaces them. Part 2 carries the reasoning. This also reorders Part 6:
   Phase 2 ("make it one product") is largely cancelled, while Phase 0 and
   Phase 1 — the defects and the operations work — are untouched by the merger
   and are the only things in this document with a claim on the next stretch of
   work.
4. **Mobile: full native client, or freeze and go responsive web?** The audit's
   recommendation is freeze — `android-full-client-plan.md`'s core assumption
   ("mostly an Android build-out, not a backend rebuild") has been falsified
   twice, only 14 of 38 v1 operations are token-reachable, and there is no Idea
   API at all. Responsive web serves iOS simultaneously, and iOS is currently
   half the addressable market and entirely absent.
5. **Documentation: what gets archived?** `bittern-plan.md` and `crane-plan.md`
   still describe themselves as active; `release-d-plan.md` says "not yet run
   against production"; `ui-second-pass-plan.md` calls itself the opening brief
   for a release that does not exist; and `roadmap-history.md` stops at Dunlin
   while eight further lines of work have shipped. The release letters have also
   forked — `architecture-trajectory.md` §5 says F is "wider horizons" while
   `roadmap.md` says F is the second mind.
