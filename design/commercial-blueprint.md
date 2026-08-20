# Clarice — commercial blueprint

Vince · written August 12, 2026 · corrected against the code August 16, 2026

## What this is

The output of a twelve-part audit run on August 12, 2026 across the backend,
frontend, security, tests and CI, infrastructure, product, Android, the data
layer, the two-core split, user journeys, architectural patterns and AI strategy.
`architecture-trajectory.md` §5 puts release G behind "a deliberate decision that
Clarice should have users who are not you"; this document is that decision being
taken, and what it costs.

**Most of it is now a record.** Part 1 is closed, Part 2's question was answered
by the merger, and Phase 0 of Part 6 is done. What is still live is Part 8's
refusals, the open recommendations flagged below, and **Part 9's three remaining
decisions** — is this a business, which wedge, and mobile native versus
responsive web. Part numbers are cited from code; they do not move.

## The verdict, stated plainly

**The engineering is not the problem. In several specific, nameable ways it is
better than commercial average.** Zero IDOR across six apps — every ID-taking
surface scopes ownership in the lookup rather than checking afterwards. No raw
SQL, no file upload, no SSRF, no open redirect: not merely no bugs, no attack
surface. No secret ever committed. Migrations genuinely follow
expand–migrate–contract. Scoped tokens have no scope-blind default, so an
endpoint that forgets to think about scope fails to construct. Zero
TODO/FIXME/HACK in the non-test tree. 937 Django tests in 73 seconds with
near-zero mocking, real HTTP against real Postgres, positive controls on every
ownership rejection. Clocks are injected; history is snapshotted so it cannot be
silently rewritten.

**What is missing is the commercial substrate, and it was missing entirely.** No
billing, no plan model, no entitlement check. ~~No terms, no privacy policy.~~
**Both published August 19, 2026**, at `/privacy/` and `/terms/`. No
analytics of any kind, so every product decision to date is n=1 introspection. No
onboarding, no help, no in-product explanation of six invented concepts. No
import from any competitor. One outbound channel, a 07:00 email, which contains
no link. The legal blocker of the list — account deletion and data export —
**shipped August 16, 2026**: deletion with a thirty-day grace period, and an
export holding every owned row as JSON alongside readable Markdown.

**And a stranger cannot become a user.** Signup creates the account
`is_active=False` (`src/accounts/forms.py:77`) and an admin ticks a checkbox
(`src/accounts/admin.py:25`). `src/accounts/emails.py` has six functions and
**none of them tells the user they were approved.** The funnel terminates at a
manual gate with no callback. That is the first sixty seconds of this product
today.

The strategic risk is not technical. It is that the project's centre of gravity
has moved into its own planning apparatus: 33 files and 5,540 lines of design
prose for a three-user app, six separate commits spent correcting stale document
statuses, and six of the last seven work items shipping outside the release
structure that supposedly governs them.

## Part 1 — Broken right now

**Closed. All ten, as of August 15, 2026.** What each defect was, what fixed it,
and the two that turned out to have been fixed before this list admitted it, are
in [`roadmap-history.md`](roadmap-history.md) under *Production defects — Part 1,
opened August 12 and closed August 15*. Code comments cite these by number
(`defect 2`, `defect 5`, `defect 9`, `defect 10`); that is where they resolve.

**Three lessons outlived the defects**, because each cost a session to relearn:

- **A signal that is always red carries no information.** CI failed seventeen
  consecutive runs and stopped being read.
- **A fix does not repair what the defect already wrote.** Defect 2 filed real
  routine records against the wrong date, and nothing recorded which auth path
  created a row, so a repair would have to guess at a durable record. Left
  deliberately.
- **This list twice described finished work as open**, which cost more than the
  defects did. If a list like this exists again, check the code before believing
  it.

**There is no live defect list now.** When there is one again it belongs here and
nowhere else; `CLAUDE.md`, which carried a second copy of this one, links here.

## Part 2 — The two cores

**Answered August 13, 2026, and settled in code by August 15.** Not by either
option this section offered: Clarice is absorbed into Second Mind, ending as one
application with a knowledge core and a **Superlists** task core. `Capture` and
`Idea` are retired — not in order to "be a very good task app," but because a
better implementation of the same ambition existed, with a node model, a concept
layer, a detector registry and measured precision figures.

Two findings outlive the answer. **The precedent**: products that unified
successfully made *one primitive* serve both — Notion and Tana have a node that
can gain a checkbox, Amplenote's note *is* the task container — while products
that stayed split put tasks inside notes, so knowledge is primary. `Node` and
`Item` are two primitives with a one-way conversion, which is the shape to watch.
**The trap**: nobody accumulates material in a store they cannot search, so a
feature gated on volume never fires. It was broken deliberately for the knowledge
core, and not for the task core.

**One recommendation survives: full-text search over the task core's own
material.** The knowledge core has it — `mind/models.py` carries a
`SearchVectorField` and two `GinIndex`es over `Node` and `Revision`. The task
core has none: the only search over tasks is `icontains`, and the Agenda, Area
and Archive boxes are `Array.includes()` over data already in the browser. A
daily journal entry is not searchable by any means at all, and there is no date
picker anywhere in the frontend — reaching a day twelve weeks back means clicking
"the week before" twelve times. Scope: `Item.text`, `Item.notes` and
`DailyEntry`'s three fields, behind one surface. See `roadmap.md`'s Track D.

## Part 3 — Feature verdicts

### Add

**Essential to the thesis**

- Full-text search over the task core (above). Highest leverage single item here.
- **Task priority.** A to-do core with recurrence, routines, pauses and snapshot
  denominators, and no priority field, is unbalanced.
- **Onboarding and a first action on the landing surface.** A new user lands on
  `/app/day` (the default `landing_surface`) which has no affordance that creates
  anything. The "Start your first area" CTA exists only on `/agenda`, which that
  user never sees.
- **An approval email** — or removal of the approval gate entirely.

**Valuable, not essential**

- A deferred/start date distinct from `due_date`, so snooze stops erasing the
  original commitment.
- Completing and adding a task from the Day page. The daily loop's core act
  currently requires navigating away, by explicit design decision
  (`DayRoute.tsx:117`) — taken before Day was the home surface.
- Date navigation: a picker on `/app/day`, a week jump on `/app/review`.
  `/day/:date` currently has no UI entry point at all.
- Links in the digest email. It presently ends "Open Clarice to work through
  them." with nothing clickable.
- Streaks or a habit heatmap. For a product whose sharpest differentiator is
  quantified practice, "you're on day 34" is table stakes and is absent.
- Task move between areas. `item_detail` PATCH accepts six fields and `list` is
  not among them (`src/lists/api.py:197`), so a misfiled task stays misfiled.

**Explicitly not yet:** graph view, spaced repetition, calendar/ICS, command
palette, AI synthesis. All correctly deferred; **none has a trigger**, which is
the finding rather than the list.

### Remove / retire

- `src/app/routes/` — an empty directory tree.
- `static/bootstrap/` — 8.4 MB still in the tree after retirement.
- `src/lists/api.py` + `api_urls.py` — seven hand-rolled endpoints that own
  *every task mutation*, with a different error envelope from `/api/v1/`, no
  OpenAPI description, and an undocumented "exactly one field per PATCH" rule
  every client must know. Finish the migration or stop paying for both.
- The README's no-JavaScript claim. `/dashboard/` is a bare redirect
  (`src/lists/views.py`), `app_shell.html` is an empty div plus a script, and
  there is no `<noscript>` anywhere. Delete the claim rather than restoring the
  behaviour.
- Raise the 44px touch floor into `button.tsx` rather than patching call sites.
  The default is `h-8` (32px) and no variant reaches 44px — including "Save the
  day" and "Save the review", the two pages that *do* have phone tests, which
  measure overflow but not target height.

## Part 4 — Architecture

The honest name for the current shape is **a layered modular monolith with
transaction-script services, separate read modules, and invariants pushed into
SQL constraints, sliced by Django app.** That is deliberate and coherent, not
tutorial residue. `principles.md`'s read/write split is the best-kept principle
in the codebase, enforced by a test that asserts against *executed SQL*.

Three real gaps, all boundary problems rather than pattern problems.

**A rule mirrored into three languages, now with a constants test and still no
conformance test.** `bucket_for` lives in `src/lists/agenda.py`,
`frontend/src/agenda.ts` and `android/.../AgendaFormatting.kt`;
`WEEK_HORIZON_DAYS` likewise. Since August 18, 2026
`lists/tests/test_mirrored_business_rules.py` fails when a mirrored *constant*
disagrees — demonstrated first by setting the horizon to 14 in Python and
TypeScript and watching all three suites stay green. **Behaviour is still
unchecked**: three implementations can hold the same constant and disagree about
a boundary.

This section's diagnosis of the cause was right and is sharper than it knew.
`/api/v1/agenda` ships every task unbucketed, so the server owns the rule on
paper and ships inputs in practice — and it turns out the server already
computes buckets at four call sites, with `BucketKey` already in the contract.
That makes it a payload gap rather than an architecture, which
[`mirrored-rules-brief.md`](mirrored-rules-brief.md) works out for the redesign.

**No enforced module boundaries, so a comment can stand in for an invariant.**
The `lists`/`capture` instance was resolved by deleting every file involved,
which settles nothing about the general problem: there is still no enforcement,
only prose. `daily/api_v1.py:20` imports schema classes from `lists.api_v1` and
`routines.api_v1`, so a field added to `TaskOut` for the Agenda silently changes
the Day contract for all three clients.

**Contract-first stops short of the clients, though not of mutations.** The
generated `frontend/src/api/schema.ts` does carry writes — 16 post, 6 patch, 3
delete. What it has not displaced is the hand-written parallel client and type
set beside it (`api.ts`, `types.ts`), and Android still hand-parses every field.
`types.ts` matches `TaskOut` field-for-field today: duplication waiting to drift,
not drift already observed.

### Adopt

| | Effort | Why |
|---|---|---|
| **Serve the date policy in the payload** | S | Add `bucket` to `TaskOut`, `week_horizon_days` and `snooze_presets` to the agenda payload; two of three implementations then delete. Highest ROI item here |
| `.importlinter` contracts in CI | S | ~30 lines, still absent; would have caught all three couplings above |
| A written five-context map | S | Planning / Practice / Knowledge / Reflection / Identity, with `Tag` named as a shared kernel rather than an accident of history |
| `contract.py` per context | M | Breaks the sibling-schema coupling in `daily/api_v1.py` |
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
in `src/` is a good implicit decision that should be written down. Event sourcing
(same objection, larger). Feature folders (the Django app *is* the slice).
Pact (three clients, one repo, one developer — the generated schema plus
`tsc --noEmit` is the same guarantee for free). A feature-flag service (needs a
second environment to pay off). The outbox pattern (needs a queue and multiple
workers to exist first). **Renaming `lists`, `Item`, or the app packages** —
`architecture-trajectory.md` §7 already refused this and was right.

## Part 5 — The commercial substrate

**Activation.** ~~Give `/app/day` a first action. Give `/` something other than
a login form.~~ **Both shipped August 18, 2026.** ~~Send the user an email when
their account goes live.~~ **Shipped August 19** — and it was promised by three
surfaces for a day before anything sent it.

**The admin gate stays, deliberately.** This item said "remove it or automate
it"; Vince's call on August 18 was neither, because the site is invitation-only
and a stranger who finds the form should reach a queue rather than an account.
What was removed instead is the *silence*: confirming an address is
self-service now, and the two waits are told apart. `product-stories.md` owns
what that costs — S1 stays impossible on this one point, and says so.

Still open here: explain the six invented concepts — Area, Project, Checklist
Step, Compass, Focus, "call it enough" — somewhere in the product, once.

**Lifecycle and legal.** ~~Export and deletion~~ shipped August 16, which also
settles the immediate-versus-grace-period question in favour of thirty days.
~~Still open: terms, a privacy policy, and a named subprocessor list — Sentry
and Resend are already processing user data.~~ **All three closed August 19**:
the privacy policy names DigitalOcean, Resend and Sentry as the three
processors, says what each receives, and is precise about what Sentry is
configured *not* to be sent. **Not lawyer-reviewed, and the trigger for
changing that is broader beta testing** — `roadmap.md` carries the three things
a professional read would want.

**Instrumentation.** There is no analytics of any kind. Shipping a positioning
wedge with no way to tell whether it landed is the most expensive mistake
available here. Minimum: an activation funnel and a weekly-review completion
rate, which is the metric the differentiation rests on.

**Operations.** External uptime monitoring, `/healthz` and
`restart_policy: unless-stopped` shipped — the largest risk reduction per hour in
the whole audit. Still open, in this order:

- ~~**SHA-tagged images and a rollback path.**~~ Done August 18, 2026: the image
  carries the commit's abbreviated SHA and four are kept on the host, so a bad
  deploy has something to go back to. **A 502 maintenance page is still open**,
  and so is the limit worth remembering — rolling the image back does not roll
  the database back, so a deploy that migrated is undone by the restore drill or
  not at all.
- **Logs off the host.** `recreate: true` destroys the container **and its logs**
  every deploy, and gunicorn has no `--access-logfile`, so there are no HTTP
  access logs at all.
- ~~**A scheduled backup-freshness check.**~~ Done August 18, 2026, in CI rather
  than on the droplet: it needs `doctl` authenticated, so scheduling it on the
  box meant putting a DigitalOcean token there. Run against production while
  wiring it — backups were 16 hours old and current. **Still open beside it:**
  `~/.secret-key` lives on exactly one filesystem, and losing it invalidates
  every session and outstanding reset token.

**Scale — measured August 12, and half of it is now obsolete.** `/api/v1/agenda`
took **1,828ms** against a 20k-row test database. The audit blamed a global
sequential scan of `lists_item` on `Item` having no `owner` column; **that
premise is dead** — `owner` shipped August 14 (`lists/models.py:152`, derived at
`:273`) — and it was never where the time went anyway: only ~24ms of the 1,828ms
was SQL. The rest is Python serializing an ~8MB response, because **there is no
pagination anywhere in the product**, which the owner column does nothing about.
Two things remain open: pagination, and an owner-leading index — `Item.Meta`
indexes `(status, due_date)` and `(list, status, due_date)`, neither starting
with owner. Query counts are healthy and flat; the `select_related` discipline is
real. The figure has not been re-measured since the schema changed.

**Billing.** No payment processor, no plan model, no entitlement check, and no
pricing or packaging work anywhere in the design corpus — the topic is one
sentence in `roadmap.md`. Choosing the wedge is what unblocks this.

## Part 6 — Sequence

**Phases 2 through 5 are superseded, August 20, 2026**, by
[`clarice-v3-plan.md`](clarice-v3-plan.md). Part 9 #1 was answered *personal
tool, with an intent to invite* — which removes Phase 4's wedge-then-billing
entirely, empties most of what Phase 3 had left, and replaces the destination
those phases were sequencing toward. **Phases 0 and 1 below stand**, and the
phase *numbers* stay readable because code and documents cite them. Read the
rest as the record of a sequence that was correct for a different answer.

**Phase 0 — stop the bleeding. Done August 15**: Part 1's ten defects, CI first,
because until it was green no other signal in this document was readable.

**Phase 1 — make production observable and the deploy safe. Partly done.** The
remainder is Part 5's Operations list, plus the tooling that needs no new tests
because it protects the ones that exist: `.importlinter`, a schema-drift check,
`coverage`, ruff, ESLint, and a DR runbook.

**Phase 2 — make it one product. Largely cancelled** by the merger (Part 9 #3).
What survives is task-core search, pagination, serving the date policy in the
payload, and deleting `static/bootstrap/`.

**Phase 3 — four to six weeks. Make a stranger able to become a customer.**
Self-service signup with email verification, onboarding and a first action, terms
and privacy policy, analytics, a support path for signed-in users, and the
landing page — export and deletion are already done. This phase produces **zero
new task management capability**, and that is the point of naming it as a phase.

**Phase 4 — the wedge, then billing.** Pick the positioning, build the two or
three features that make it true, instrument it, then charge.

**Phase 5 — "Read my week."** A bounded, read-only, opt-in weekly briefing.
Design it alongside Phase 3 rather than after it, because it needs exactly what
Phase 3 produces — a privacy policy, export, and a signup flow.

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
Clarice is meaningfully ahead of Todoist and TickTick.

**C. "The private, self-hostable daily OS."** Zero telemetry, a working Docker
and Ansible deploy, scoped tokens, a Keystore-encrypted mobile queue. Sidesteps
billing complexity and onboarding-at-scale, and matches the codebase's actual
shape — but it is a small market with a high support load.

The weakest option is competing head-on as a task manager, which is where the
roadmap's momentum currently points.

**On AI**, the deferral was sound on foundations and wrong on ordering. The gate
— "several months of weekly reviews actually being used" — is measured against
one person and may never fire; re-gate it on something a cohort can satisfy. The
asymmetry the vision document missed: AI usefulness scales with corpus size for
idea-resurfacing and next-week planning and **not** for summarising a week you
can already enumerate, so week one is as tractable as week two hundred. The cost
comparison is the argument against the feature everyone will ask for: a bounded
weekly briefing runs on the order of **$0.59/user/month** at frontier pricing; an
open-ended chat over the corpus is **$36–180** with no natural cap.

*(This section also called embeddings and pgvector over-engineering, because a
year of one user's data is ~150k tokens and fits in one context window. True of
the task core, overtaken by the merger: the knowledge core ships sentence
embeddings with a measured shadow evaluation. `mind/models.py` is the authority.)*

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
3. ~~**Second brain: invest or retire?**~~ **Answered August 13, 2026: invest,
   elsewhere.** Part 2 carries the reasoning; the consequence for this document
   is that Phase 2 is largely cancelled.
4. **Mobile: full native client, or freeze and go responsive web?** The audit's
   recommendation is freeze — `android-full-client-plan.md`'s core assumption
   ("mostly an Android build-out, not a backend rebuild") has been falsified
   twice, and only 13 of the 40 `/api/v1/` operations are token-reachable — the
   rest default to `django_auth`, which a phone does not have. Responsive web
   serves iOS simultaneously, and iOS is currently half the addressable market
   and entirely absent.
5. ~~**Documentation: what gets archived?**~~ **Answered August 16, 2026.** Every
   document this item named as stale is now a stub pointing at
   [`roadmap-history.md`](roadmap-history.md); [`README.md`](README.md) indexes
   the corpus and owns which document owns which fact.
