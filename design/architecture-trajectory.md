# Clarice — architecture and release trajectory

Vince · Crane through G · drafted August 2, 2026

## 1. What this document is for

Four planning documents now exist and they answer different questions.
[`daily-operating-system-vision.md`](daily-operating-system-vision.md) says
**why** — the product thesis and the practice it serves.
[`principles.md`](principles.md) says **how** work is designed, implemented and
verified. [`roadmap.md`](roadmap.md) says **what** is active now and what has
been deliberately deferred. [`crane-plan.md`](crane-plan.md) is the executable
plan for the release in front of us.

This document answers the question none of them do: **in what order do the
next several releases arrive, what must be true of everything built inside
them, and what has this project decided not to do.** It exists because three
architectural reviews arrived within a week, each proposing a different
multi-month plan, and because the rate of AI-assisted implementation means the
cost of an unstated convention is now measured in weeks rather than years.

It is deliberately not a task list. Where it names work, that work still earns
a focused spec in `design/` before it starts, exactly as `roadmap.md` requires.

**On provenance.** Two of the three reviews were produced outside this
repository, in conversation, and are summarised in §3 rather than quoted from a
tracked file. A reader cannot open them. Everything §3 concludes is therefore
argued from files in this repository, and §7's refusals stand on that evidence
alone — the reviews supply the questions, not the answers.

## 2. The superlists ledger — closing the account

Clarice began as the Test-Driven Development with Python tutorial project, and
the standing assumption in every outside review has been that it is a tutorial
app carrying tutorial debt. That assumption is close to spent, and the
migration history says so precisely.

| Tutorial residue | Status | Evidence |
| --- | --- | --- |
| Email address as `User` primary key | **Paid.** Numeric PK since `accounts/0004`, with group and permission relationships preserved by email lookup across the swap. | `accounts/migrations/0004_numeric_user_primary_key.py`, `lists/migrations/0010`–`0011` |
| Passwordless magic-link auth | **Paid.** Real username/password auth, legacy accounts backfilled, the `Token` model deleted cleanly in the same migration that replaced it. | `accounts/migrations/0003_username_password_auth.py` |
| SQLite in production | **Paid.** Managed Postgres in production; CI runs the Django suite against Postgres 18. See the local-development caveat below — it is not the same claim. | `MIGRATION.md`, `.github/workflows/ci.yml` |
| Server-rendered task UI | **Paid, and deliberately bounded.** The task UI is SPA-only; `dashboard` and `archive` are one-line redirects into it. | `lists/views.py`, `roadmap-history.md` |
| Anonymous lists, then bolted-on ownership | **Outstanding, cheap.** `List.owner` is still `null=True, blank=True` although every creation path supplies an owner and every view requires a login. `Tag` got this right at `0015`, five days later. | `lists/models.py`, `lists/migrations/0007_list_owner.py` |
| `Item` as the only operational model | **Outstanding, expensive.** Status, due dates, recurrence, tags, notes, one-level parent/child, `always_recurs` and archive grouping all live on one table. | `lists/models.py` |
| A recurring commitment has no identity across its occurrences | **Paid forward, August 2, 2026.** Crane 0a added `RecurringCommitment` and the `Item.commitment` key `_spawn_next_occurrence` now writes. Occurrences archived before that date stay unlinked and always will — see below. | `lists/migrations/0022`–`0023`, `lists/services.py` |
| Hand-rolled JSON endpoints beside `/api/v1/` | **Outstanding, unscheduled.** `lists.api` owns item create/reorder/detail. The v1 router's docstring is a rule for *not* moving them — "Item mutations … stay on the hand-rolled lists.api endpoints" — not a migration schedule, and nothing in `roadmap.md` schedules one. | `lists/api_urls.py`, `lists/api_v1.py` |
| The app is still called `lists` | **Outstanding, cosmetic.** Left alone deliberately: renaming buys no behaviour and costs migration churn. The API already says `/tasks/{item_id}`. | `lists/api_v1.py` |

Four items outstanding, down from five on August 2, 2026. One is a morning's
work, one is cosmetic and should stay that way, one is a decision nobody has
actually made yet, and one — `Item` — is a real domain redesign. The fifth was
the missing foreign key, and it is the one this document called most
consequential; Crane 0a paid it the same day, on the reasoning in
`crane-plan.md` §3.

**A correction worth making explicitly.** The `Item` overload and the
parent–child redesign are not the same item, and this document originally
conflated them. `roadmap.md` names a **parent–child domain redesign** whose
scope is "decide what a subtask *is* — a step, a dependent task, a checklist
item." That is one relationship. The wider claim — that `Item` should divide
into a Task, a Checklist Step and a Recurring Commitment — is a *proposal* made
by both external reviews and endorsed here, not a plan the roadmap has
committed to. Release D below is where that decision gets made; until then it
should not be quoted as settled.

**The missing occurrence link, in detail.** `_spawn_next_occurrence` builds a
recurring task's next occurrence with `Item.objects.create(list=..., text=..., due_date=..., recurrence=..., position=...)`, then copies the tag set and
clones the carried-forward children with their own `notes`, `position` and
`always_recurs`. What it never writes is any reference back to the item it came
from. So a fair amount of *content* carries forward while *identity* does not:
the only thing marking occurrence five of "Pay rent" as the same commitment as
occurrence four is that they share a text string in one list. Rename it and the
series splits silently in two; change its cadence and nothing records that it
ever had the old one.

**Fixed forward on August 2, 2026, and the limit is worth stating as plainly
as the defect was.** Crane 0a's `Item.commitment` means every occurrence
spawned from now on joins a durable series, and a data migration gave each
existing repeating task its own commitment so series begin today rather than
at each task's next completion. What no migration can do is link occurrences
that were already archived: reconstructing them would mean matching on
`(list, text, recurrence)`, which merges distinct tasks sharing a title and
splits any series that was ever renamed. That was declined deliberately — an
audit-proof gap beats invented history. Everything below describes the defect
as it stood, and remains true of rows predating the key.

The precise cost is narrower than "the review breaks," and worth stating
accurately. Crane 3's specified weekly gathering — completed work and recurring
commitments *from the preceding week* — is a one-week query over completion
timestamps, and today's schema answers it fine. What today's schema cannot do
is assemble those occurrences into a series across weeks, which is every trend,
streak and rate the vision document goes on to ask for. It is a missing
relationship rather than a crowded table, which is why it sits beside the `Item`
overload on this ledger rather than inside it.

One genuine defect surfaced while checking the above and belonged in a bug
report rather than a plan: the spawn copied each *child's* `notes` explicitly
but never the parent's own, so a recurring task with notes lost them on every
cycle. The asymmetry looked like an oversight rather than a decision, and was
fixed as one on August 2, 2026 — see §6. Forward-only for the same reason the
key is: notes dropped by earlier cycles were never written anywhere and cannot
be recovered.

**The consequence for planning.** The interesting risk to Clarice is no longer
behind it. Retrospective cleanup is bounded and nearly finished, and making it
the organising principle of the next six months would be planning against the
wrong threat. The live risk is forward: the product's ambition has outgrown its
domain model, and the whole migration history is sixteen days old — `lists/0001`
is dated July 17, 2026 and `Tag` arrived on July 29. Seven models exist today.
Crane alone introduces at least four more. A second generation of scar tissue
is still preventable; the first is nearly paid off.

## 3. Three reviews, refereed

Two external reviews (recorded here as Chat and Gemini) and this project's own
audit examined the same codebase within days of each other. Their agreements
are worth recording because independent convergence is evidence; their
disagreements are worth recording because two proposals would have caused real
damage if executed — and because one of my own dissents was wrong, which is
recorded below rather than quietly dropped.

**Where all three agree.** `List.owner` should be made non-null now. `Item` is
overloaded and needs a redesign, but not inside Crane. The SPA migration was
not a mistake — the product's ambition changed, and no path through a Django
tutorial avoids that pivot. The Capture/Idea split was the correct call and is
some of the project's best work. Rich authored content is eventually needed and
is not needed yet. Row-level security is deferred until sharing or real tenancy
exists. And the testing culture — outside-in TDD, the injected clock,
first-class isolation tests, documented architectural honesty — is the asset to
protect above all the rest.

An agreement worth singling out: Chat's independent description of what a
routine occurrence needs — target snapshots, historical logging, target met in
one action, partial close, explicit skip, correction history — reproduces the
`RoutineOccurrence` design already settled in [`crane-plan.md`](crane-plan.md)
§3, including the same unresolved question about a satisfied-but-partial close.
Two passes reaching the same model by different routes is the strongest
available signal that Crane 0 is right.

### Where I was wrong: Postgres in local development

Chat proposed moving local development onto Postgres. I dissented, quoting
`settings.py`'s own comment that "nothing about this app's schema depends on
Postgres-only behavior yet." **That comment is stale and the dissent was
wrong.**

`Item.Meta` defines `unique_active_item` with `nulls_distinct=False`, which its
own comment marks as "Postgres 15\+ only" and which is the entire reason one
constraint can cover both root tasks and subtasks. `lists/0020_item_parent.py`
is blunter: "On SQLite this constraint is silently not created, so the suite
has to run on Postgres for it to mean anything (CI does)."

So a local SQLite run does not merely use a different engine — it silently
omits a constraint that production enforces, and the local suite passes while
proving something weaker than it appears to. CI catches this, which is why it
has not bitten yet, but "the machine will notice" is a thin guarantee for the
step where a developer decides a change is finished. Moving local development
to Postgres has therefore been promoted to the immediate infrastructure list in
§6, and `settings.py`'s comment should be corrected in the same change.

**A second instance, August 2, 2026, and it did bite.** The browser job went
red and stayed red across two commits. The visible failure was a Playwright
timeout; underneath it `/api/v1/agenda` was returning 500 from a *session*
lookup, with `IndexError: list index out of range` inside Django's
`apply_converters` — a result set being read while another statement was in
flight. `manage.py test` puts SQLite in memory, an in-memory database cannot be
reached by a second connection, so `LiveServerTestCase` hands the test's own
connection to the server thread while `ThreadedWSGIServer` serves each request
on a thread of its own. One connection, several threads, since the suite was
written; four green runs beforehand were luck.

Two things are worth extracting rather than leaving in the commit. The first is
that this widens the claim above: SQLite does not only omit a constraint
Postgres enforces, it changes the *concurrency* the test harness runs under,
and it did so identically in CI — so this one is not a local-versus-CI
divergence at all, which makes "the machine will notice" thinner still. The
second is that the fix — naming the test database so it becomes a file — is a
SQLite-specific workaround for a problem Postgres does not have, since separate
connections are the default there. It is correct and it stays, because anyone
may still run these locally on SQLite. But it is one more thing the §6 item
would retire.

### Where this project dissents

**Going headless.** Gemini's Phase 2 proposes deleting `src/lists/templates/`,
including `base.html` and `app_shell.html`, and serving a compiled
`index.html` from the root. This would break the application.
`app_shell.html` is not legacy — it is the page that renders the SPA, resolving
the theme, loading `site.css` and mounting `#app-root` for every `/app/...`
route; there is no Vite-built root document waiting to replace it. `base.html`
is extended by sixteen templates: every account flow, the contact form, the
token page, the 403 and lockout pages, the Inbox and capture-edit triage
screens, the Ideas library, and — pointedly — `new_list_form.html`, the one
extending template that actually lives in the directory proposed for deletion,
rendered by `lists/views.py` when a new-list POST fails validation. Removing
these would delete authentication and triage in the name of removing debt.

The boundary in `roadmap-history.md` is worth quoting exactly, because its two
halves have different force: "The task UI is now SPA-only. Capture and account
surfaces **can remain** Django-rendered where that is the better fit." The
first sentence is settled. The second is a permission, not a commitment — those
surfaces may migrate later on their own merits. What is not on the table is
deleting them as cleanup.

**A local-first sync phase.** Chat's Phase 5 proposes a staged sync programme.
The sync problem Clarice actually has is already solved, narrowly and well, by
the Android client's encrypted queue and owner-scoped idempotency contract.
Generalising it into browser persistence before a second client needs it is
optimising an imagined workflow — the thing `principles.md` explicitly warns
against. What is cheap is giving each *new* table the primitives a future sync
would need, at the moment it is created. That belongs in the charter below, not
in a phase of its own.

**A new `knowledge` app.** Chat's seven-domain model lists Knowledge as future
work. It already exists: `capture.Capture` and `capture.Idea`, with documented
lineage rules, one-hop promotion pointers and a deliberate hard/soft deletion
asymmetry. Standing up a parallel app would re-solve a solved problem. What
Knowledge genuinely lacks is a discovery pass on relationships and retrieval,
which is release E.

**PgBouncer, and infrastructure ordering generally.** Gemini's Phase 3 proposes
connection pooling. The current concurrency ceiling is upstream of the
database: `Dockerfile`'s
`CMD ["gunicorn", "--bind", "0.0.0.0:8888", "clarice.wsgi:application"]` sets no
worker or thread count, so the application serves on gunicorn's default before
pooling could become the constraint. The same section proposes deleting
`infra/provision-postgres.sh` and `infra/restrict-database-user.sh` for
Terraform. Those are 98 and 173 lines of operational knowledge including the
non-obvious fact that every user on a shared DigitalOcean cluster can reach
every database on it unless explicitly restricted. Replacing them with
unrehearsed Terraform aimed at the only production host, with no staging to
rehearse against, inverts the order of safety.

**What neither review addressed.** Both produced fixed to-do lists. Neither
asked what rule should govern the tables that do not exist yet — which, given
the pace at which they are about to be created, is the question with the
largest expected value. That is §4.

## 4. The charter for new records

Eight rules for the design of any new model in Crane through G. Each costs
close to nothing when a table is created and is expensive or impossible to
retrofit; that asymmetry is the whole argument, and it is the same one
`principles.md` makes about reversible decisions.

**Two of these rules cite designs rather than code**, down from three on
August 2, 2026. Rules 3 and 5 point at `crane-plan.md`, which is an unbuilt
sketch — there is no `routines` app in `src/`, and the plan says its model
sketch is "illustrative of the shape, not final code to merge." They are named
here as intended precedents, not established ones. Rule 8 was in that group
until Crane 0a shipped `RecurringCommitment` and now cites a real migration.
Of the remaining six, five cite tables that exist and rule 4 cites a module
split rather than a table.

**Before the rules: does this earn a model?** The charter makes new tables
cheap to get right, which makes it easier to create too many — the opposite
failure from the god table and a real risk on the way to roughly seventeen
models. The test is that **a concept earns its own model when it has a
different life cycle, not when it has a different name.** A Checklist Step
earns one: no due date, never in the agenda, cannot recur, dies with its
parent. A Project earns one against a List, because a project completes and a
list never does. A Habit does *not* earn one against a Routine —
`target_quantity=1, unit=""` already is a habit, and the difference is data
rather than schema. An Area does not earn one against a List; that is a rename
at most. When the answer is no, the concept is a field, a status, or a word in
the interface.

**1. Owned at birth.** Every root record carries a non-null owner foreign key
in its first migration. *Precedent:* `Tag` (`lists/0015`) got this right;
`List` (`lists/0007`) did not, five days earlier, and still carries the nullable
column. *Cost now:* nothing. *Cost later:* a live-data audit plus two
migrations, and every isolation test written in between has been proving a
weaker guarantee than it appeared to.

**2. A public identifier wherever a client may create the record offline.** An
additional UUID column, never a change of primary key. *Precedent:*
`Capture.idempotency_key` — nullable, unique per owner, with browser captures
deliberately exempt by ordinary SQL NULL semantics. *Cost now:* one field.
*Cost later:* identity cannot be retrofitted onto records a device already
holds, and `principles.md`'s retry-safety rule has no database constraint
behind it.

**3. Snapshot whatever a record's meaning depends on.** A record describing
what happened copies the values that give it meaning rather than reading them
live. *Intended precedent:* `RoutineOccurrence.target_quantity` and `unit` in
`crane-plan.md` §3 — a routine's target changing from five to three must not
rewrite last month's "4 of 5." *Cost later:* the history is already wrong and
nothing can recover it. This is `principles.md`'s durable-records rule
expressed as a schema habit.

**4. A read module and a service module, from the first slice.** Query and
derivation code answers questions; service code enforces invariants and
mutates. *Precedent:* `agenda.py` is query-only and `services.py` owns
mutations, and that split is real and works.

What this rule may **not** claim is that a shared definition prevents drift,
because the live counter-example is in this repository. `bucket_for` and
`WEEK_HORIZON_DAYS` live in `agenda.py`, but `/api/v1/agenda` never calls
`bucket_for` — `workspace_data_for` emits bucket keys and labels, and the SPA
assigns items to buckets itself using a hand-maintained mirror in
`frontend/src/agenda.ts`. Only the digest command uses the Python one. That is
the mirror case `principles.md` explicitly allows, provided the authority is
named and tests protect it. It has since drifted anyway: `agenda.ts` documents
`SCOPES` and `summaryCounts` as mirroring `lists.agenda.SCOPES` and
`lists.agenda.summary_counts`, **and neither name exists anywhere in the Python
source.** Filter-scope semantics and summary counts are now defined only on the
client, under a comment asserting a server authority that is not there. See §6.

**5. Reference, never copy.** A surface displays a record; it does not own a
duplicate that can drift. *Precedent:* the vision document's own rule.
*Intended precedent:* Crane 1's slice 2, which embeds the agenda query rather
than copying task state onto the day. *Cost later:* two sources of truth for
whether something is done, and review metrics that cannot be trusted.

**6. State the deletion decision in the model, and say what an offline client
would see.** Soft or hard, undoable or not, decided when the table is created.
*Precedent:* already practised well and needing only generalisation — `Item`
archives with an `archive_group` so a cascade restores as a unit, `Capture`
resolves via `resolved_at` plus a `DISCARDED` resolution and supports undo, and
`Idea` deletes hard with the asymmetry argued in `services.delete_idea`'s
docstring. *What is missing* is the second half: a hard delete is invisible to
a client that was offline when it happened, so any record covered by rule 2
also needs a tombstone or a change-cursor entry. *Cost later:* a device that
silently resurrects deleted records.

**7. Index the query the feature actually runs.** *Precedent:* `Item` carries
four purposeful indexes and `Capture` one built for the Inbox's exact
`(owner, resolved_at, -created_at)` scan. `Idea` has ordering and no index at
all — and `Idea` is precisely what release E's search will query. *Cost now:*
one `Meta.indexes` entry.

**8. Repeating things carry a template and dated occurrences.** Anything that
happens more than once splits into a durable template holding the rule and
dated occurrence rows holding what actually happened, each occurrence pointing
back at its template. *Precedent, as of August 2, 2026:* `RecurringCommitment`
and `Item.commitment`, which apply the rule in a real migration — partially and
knowingly, since that template holds identity and not yet the rule itself.
*Intended precedent:* `Routine` and `RoutineOccurrence` in `crane-plan.md` §3.
*The counter-example was in production* until the same day: recurring tasks
were a chain of rows whose only connection was a matching text string. *Cost
now:* one foreign key. *Cost later:* the history exists but cannot be
assembled, and no migration can invent links after the fact — which is why the
occurrences archived before that date are unrecoverable and stay that way.

The shape to keep consistent across every occurrence table: owner, a foreign
key to the template, the date or period covered, a snapshot of what was
expected (rule 3), an outcome, and when that outcome was decided. Keep it a
documented convention rather than an abstract base class — a shared base
invites putting more on it, which is how the last overloaded table started.

**Applying it to Crane 0.** As drafted, `Routine` and `RoutineOccurrence`
satisfy rules 3, 5 and 8, and largely satisfy rule 7 — the
`(routine, period_start)` unique constraint creates on Postgres exactly the
index the logging path's "this routine, this period" lookup needs. Three gaps
to close before the migration is written: `RoutineOccurrence` has no owner
foreign key at all, reaching its owner only through `Routine`, which fails rule
1 and makes every isolation test on it a two-hop assertion; the sketch is a
single `models.py` with no read or service module, which fails rule 4; and
rules 2 and 6 are unaddressed — a UUID column and a sentence in each docstring.

**What the charter buys.** Rules 3 and 8 exist because analysing past
performance is a stated product ambition, and that ambition is decided at write
time rather than at read time. Once every repeating thing has a template, dated
occurrences and a snapshot of what was expected, one review-and-analytics read
module can serve all of them — and a set of questions becomes answerable with
no further tables:

- Streaks, and more usefully recovery time: how long after breaking one the
  person started again.
- Cadence drift — how far actual completion trails the due date, trending over
  months. That distinguishes a cadence that is wrong from a person who is
  failing, which is a distinction the product should be able to make.
- Completion rate by List, which is the quiet version of which areas of a life
  sustain it and which drain it.
- Load against closure: how many commitments came due in a week versus how many
  were closed — the honest test for systematic over-commitment.
- Time-to-close distributions for one-off tasks, from `created_at` to
  `completed_at`.
- Abandonment: a commitment whose occurrences stopped completing but which was
  never paused is probably dead. Surfacing that is exactly what "automations
  propose; people decide" was written for.

Without rule 8 none of these are queries; they are string matches over archived
rows. Their home is release F. Their cost is paid in Crane 0.

## 5. The release arc

Releases keep the alphabetic bird convention; names get chosen at release time
as they always have been. What matters here is the ordering argument, and the
ordering argument is one claim: **each release produces the evidence the next
one needs.** Nothing here is scheduled by appetite.

### Crane (C) — the day becomes the product

Already specified in [`crane-plan.md`](crane-plan.md) and
[`daily-operating-system-vision.md`](daily-operating-system-vision.md). Crane 0
settles the repetition domain — widened from routines alone and then narrowed
on August 2, 2026, with only the identity half built, as Crane 0a — shipped
that day; see §8 and `crane-plan.md` §3. Crane 1 ships the Daily Page —
entry, compass, focus,
embedded agenda, capture, home surface, and a phone-viewport pass over the
assembled page at slice 7. Crane 2 refines daily planning and implements
routines. Crane 3 is the first weekly review with the trustworthy denominators
its metrics need.

**Its thesis:** Clarice stops being a task application with a daily view and
becomes a record of a practice. Everything after this depends on that record
existing.

**Why Crane 0 should widen from routines to repetition.** The vision document
originally scoped it as "Routine and target domain design" — that heading still
stands, with a scope note added beneath it on August 2, 2026 recording this
argument. The brief is too narrow by exactly one model, and the reason is the
missing occurrence link in §2. Crane 0 is at this moment designing the very
shape recurring tasks lack: a durable template plus dated occurrences pointing
back at it. Designing it once for routines now and again for recurring
commitments at release D would leave Clarice with two mechanisms for "a thing
that repeats," built six months apart, only one of which can be read as a
series. Crane 3 is where that first bites: its one-week gathering works against
today's schema, but the trend and habit views the vision document asks for
immediately afterwards do not.

So the proposal is that Crane 0's brief becomes the repetition domain: one
pattern, two models — `Routine` with `RoutineOccurrence` for practice measured
toward a quantity, and a recurring commitment with its task occurrences for
discrete commitments. They stay separate tables. A routine accumulates progress
toward a target across a period; a task is discrete and either done or not.
Merging them would rebuild the overload being escaped, in a smaller costume.
What they share is the occurrence spine in §4's rule 8, which is what lets one
review layer read both.

**What this does not pull forward.** Under the narrowing recorded in §8,
nothing leaves `Item` at all — Crane 0a adds a foreign key and takes no field
away, so `recurrence` stays where it is until release D moves the whole
vocabulary at once. Parent and child stay for D too, where the evidence already
exists and nothing in Crane collides with it; archival and the unit-of-work
fields work and stay put. In the meantime the two runtime guards in `services.py` that
encode the parent/recurrence rules — `set_recurrence` and `set_always_recurs` —
are candidates for becoming database constraints, with the caveats in §6.

**Mobile web starts here, and is not finished here.** `roadmap.md` argues the
layout work should happen *inside* Crane so the home surface is built
mobile-aware rather than retrofitted, and `crane-plan.md` carries slice 7 as a
phone-viewport smoke pass over the assembled Daily Page. That covers one new
surface. The roadmap's Mobile web item is wider — triaging the Inbox,
completing a task and reading an Idea from a phone, plus reconciling the two
disagreeing breakpoints at 760px and 768px — and none of that is in
`crane-plan.md`. Its stated trigger is also not quite met: the condition is not
that M4's pilot finished but that "captures arrive from a phone daily" until
the triage friction is specific and observable, and the recorded pilot was a
single session. So Crane makes the new surface mobile-aware; the remaining
browser-wide pass keeps its roadmap trigger and lands when that trigger fires
— plausibly during D or E, not deferred to G.

**What it must not absorb:** the parent/child redesign and the UI overhaul,
both fenced off in `crane-plan.md` §5, and both release D.

### D — the commitment vocabulary

Two design cycles are already named in `roadmap.md`: the parent–child domain
redesign, and the web UI overhaul's second pass. They should be *designed*
separately, as the roadmap requires. They should **ship together**, and C2's
own evidence is the argument.

The recorded failure was a person needing three attempts to set up one
recurring parent with three children. Two independent defects caused it. A
parent's **Repeat** select sits above each child's **Repeats** checkbox, and
setting the first to None silently hides every instance of the second. And a
subtask row carries two visually identical checkboxes, the leading one
completing the task and a later one governing recurrence.

Both read as interface accidents. Neither is. The first pair have
near-identical names because the domain never decided whether a subtask is a
step, a dependent task or a checklist item — so recurrence had to be bolted
onto parents only, `always_recurs` onto children only, and the relation between
them left implicit. The second pair are indistinguishable because *completion*
and *recurrence* were never separated as concepts on a subtask; one row is
carrying two lifecycles because one model is. **The interface is confusing
because the model is undecided.** Relabelling over an undecided model moves the
confusion; redesigning the model behind the old interface leaves it invisible.

So: two briefs, one release, model decided first. This is where the remaining
half of the `Item`-splitting proposal from §2 gets decided on its merits — the
separation of a Task from a Checklist Step — using the expand/migrate/contract
sequence `principles.md` requires, with both shapes supported during the
compatibility window and no destructive rename. The recurrence half has already
left by then, at Crane 0. If the redesign concludes a smaller change suffices,
that is a legitimate outcome, not a failure.

**What a `List` is gets decided here too.** `List` today is an owner, a title
and an `updated_at`, with a colour derived from its id: a container with no
completion state, no due date and no goal. It does not need a narrower scope —
it is already narrow. It needs a decision. Naming it an Area or Context, a
bucket that never ends, is most of the work, and it is what makes `Project` a
genuinely new concept rather than a rename, because a project completes and an
area does not. Different life cycle, so under §4's test a Project earns its own
model. Note that nothing in `roadmap.md` or the vision document asks this
question — it was raised by Chat's review and is endorsed here — so it needs
adding to D's brief rather than being assumed to be in it.

**What promotes it:** Crane shipping. Deciding what a subtask *is* wants
evidence from a daily practice running against real commitments, and Crane 1
through 3 produces exactly that. Doing it first would be guessing with better
vocabulary.

### E — the second mind

The vision document's second-brain direction, currently the least built and
most often deferred half of the product. Its sequence is argued there and
should be followed literally: a discovery pass defining the boundary between an
idea, a reference, a project, a task and a routine; then the cheap
human-controlled interim — shared topic tags and a manually selected "related
idea" link, rendered as ordinary chips rather than a graph; then retrieval,
where `roadmap.md`'s Reference/Idea search candidate lands, with ranked
full-text search over the `reference` archive.

Two things join this release from elsewhere. **Cursor pagination**, because
search over a growing archive is the first query that genuinely needs it — at
today's row counts nothing else does. And **rich authored content**, if its
trigger has fired: the case for formatting was always about knowledge material
and daily writing, never task notes, so the settled boundary that notes remain
plain text survives intact while a `documents` domain gains real formatting.
That is one bounded model with a content format, a version and a sanitisation
policy — not a general block graph, and not a rewrite of anything already
storing text.

**What promotes it:** enough retained material that finding something again is
a felt problem rather than an anticipated one. That trigger was proposed here
and has since been written into `roadmap.md`'s Reference/Idea search candidate,
which previously had none — as, still, do Audit log and Time blocking, the two
remaining Track D entries. The discovery pass should precede the search work
either way.

### F — wider horizons

Crane orders the present and, at Crane 3, begins tracking the past — a weekly
review is already a backward look. F is where both widen: monthly and quarterly
review reusing the weekly model at longer windows, which the vision document
permits **only after weekly use proves helpful**; the audit log and general undo
that make more than task completion safely reversible; and time blocking, with
overlap prevented at the database layer, which is the first feature that plans
forward rather than records backward.

These belong together because they share a dependency: all three need history
that can be trusted. A quarterly view over unreliable records is worse than no
quarterly view, because it invites decisions.

**What promotes it:** several months of weekly reviews actually being used, and
enough routine-occurrence history to draw a trend from.

### G — the public product

`roadmap.md`'s remaining public-readiness work, plus two of its neighbouring
Later subsections that only make sense at the same moment. From
public-readiness: self-service signup with email verification, rate limiting
for capture, account export and deletion once the
immediate-versus-grace-period question is answered, and a privacy policy and
terms. From Later: the support path for signed-in users, whose own promotion
condition (B4, error monitoring) has already been met, and the public updates
page, which needs strangers to exist before it has a reader.

Two things this release is often described as containing and does not.
**Transactional email** shipped in Bittern — `EMAIL_HOST` defaults to Resend
and the provider decision is recorded in `bittern-plan.md`. **Signup rate
limiting** is done at the edge: `/accounts/signup/` is the only signup route
and nginx's 5r/m zone covers it. Both sat in `roadmap.md`'s remaining-work list
until August 2, 2026 and have now been struck there with a note. Capture is
still unthrottled and stays. The uncovered authentication surface is `/`, a
full login view the rate-limit block does not match — a defect, listed in §6,
not a release item. And **mobile web is not G's**: it begins in Crane and
completes on its own trigger, per the argument above.

**Ordering, stated correctly.** `roadmap.md` puts billing, support operations,
deeper legal requirements and horizontal scaling out of scope "until the
public-readiness bar is genuinely met." The dependency runs *that* way: G is
the precondition for the business question, not something the business question
gates. Row-level security therefore does not belong to G either — its trigger
is the Sharing work in Later, or paying tenants, both of which come after.

**What promotes it:** a deliberate decision that Clarice should have users who
are not Vince.

### After G — AI as assistance

Unchanged from the vision document, restated because it is the part most likely
to be pulled forward by enthusiasm. AI summarises evidence already in Clarice,
proposes rather than mutates, shows the records and time range behind each
suggestion, requires confirmation for every write, and is opt-in. It needs
trustworthy daily records, clear task state and real review behaviour first —
which is to say it needs Crane, D and F to have happened *and to have been
used*.

## 6. The infrastructure track

Infrastructure work does not ship features and should not be numbered as a
release. It runs alongside, ordered by what unblocks what, with each item's
trigger stated so it can be deferred honestly rather than quietly.

**Now, because they are small and something depends on them.**

- ~~**Move local development onto Postgres**, and correct `settings.py`'s
  stale comment.~~ **Done August 11, 2026.** Per §3, two reasons were named;
  one is resolved and one still stands. `unique_active_item` being silently
  uncreated on SQLite is **resolved as of release D's contract step**
  ([`release-d-plan.md`](release-d-plan.md) §5): dropping `Item.parent` left
  the constraint's fields all non-nullable, so `nulls_distinct=False` was
  removed as dead weight and the constraint (and `ChecklistStep`'s own) now
  creates on SQLite like any other — the local suite went from 7 silently
  skipped tests to 0 in the same change. What still stood was the
  concurrency difference: `LiveServerTestCase` hands one SQLite connection to
  several server threads, which is not how Postgres behaves, and that gap
  bit for real once already (§3's `IndexError` in `apply_converters`). That
  reason alone still justified the move, so it happened anyway even though
  the constraint gap had already closed.

  `docker-compose.yml` (new) provides a local Postgres 18 container matching
  CI's own service container exactly (`clarice`/`clarice`/`clarice`), on
  host port 5433 rather than 5432 to avoid clashing with another project's
  Postgres on this machine. `clarice/settings.py`'s `DEBUG` branch now
  defaults `DJANGO_DATABASE_URL` to that connection string instead of a
  `db.sqlite3` file, and the stale comment ("nothing about this app's
  schema depends on Postgres-only behavior yet") is corrected to say why the
  opposite is true. `DJANGO_DATABASE_URL` still overrides the default, which
  is exactly what CI does to reach its own service container. Verified: 933
  backend tests green against the container, `makemigrations --check`
  clean, `manage.py migrate` applies cleanly, and `unique_active_item`
  confirmed present via `psql \d lists_item` — the actual constraint this
  entry exists to stop silently disappearing.
- ~~**Rate-limit the landing page's login form.**~~ **Done August 3, 2026.**
  `/` is a `LoginView`, so `POST /` authenticated exactly as
  `POST /accounts/login/` did while only the latter was throttled. `location
  = /` now carries a 5r/m limit, keyed on the request method so that only
  POSTs are counted: the landing page is the public front door, and
  throttling its GETs would have traded a real availability risk for no
  security gain, since a GET returns a form rather than attempting a login.
  A second budget rather than a shared one, on the reasoning recorded in the
  template.
- ~~**Set gunicorn's worker and thread count explicitly.**~~ **Done August 3,
  2026, and it was not the one line this entry assumed.** Measuring first
  changed the answer: the droplet has one core, 458MB of RAM and **no swap**,
  and the container measured 94MB running gunicorn's default — a single sync
  worker, meaning production served one request at a time and any slow query
  blocked the site.

  The usual `(2 x cores) + 1` would have been actively harmful here: three
  workers is roughly 204MB against ~152MB available, with no swap to absorb
  it, so the OOM killer takes the container rather than the site merely
  slowing. It is now two workers and four threads — redundancy so one wedged
  worker is not an outage, threads for the concurrency, since nearly every
  request is "ask Postgres, wait, render" and a thread costs almost nothing
  where a worker costs ~55MB. `--max-requests` with jitter bounds any leak.

  **Corrected the same day, after it broke a deploy.** Two workers took the
  container to 154MB and left ~95MB free on the host — fine at rest, and not
  enough for the host's own maintenance. The next deploy's
  `apt-mark manual docker.io` thrashed for four minutes and was then
  OOM-killed (rc 137), failing the play at "Install nginx and certbot". Site
  stayed up, `dpkg --audit` stayed clean, deploy did not finish. It is one
  worker and four threads now.

  **The error is worth more than the number.** The container was sized at
  rest against available memory, when what mattered was the peak the *host*
  needs while apt and dpkg run. The planned check — "drop to one worker if it
  settles above 180MB" — measured the wrong thing and would never have fired
  at 154MB. A container that fits is not the same as a host that can still
  maintain itself.

  ~~**New item, and the one that actually resolves this: give the droplet
  swap.**~~ **Done August 3, 2026** (`a98196c`, same day as the finding
  above — this entry was simply never marked done). 458MB with no swap had
  no room for an application and routine package management at the same
  time, so every apt run was one memory-hungry step away from the same
  failure, regardless of gunicorn. A 1GB swapfile, swappiness 10, placed
  ahead of the apt tasks it protects and persisted across reboots via
  `/etc/fstab` — full detail in the deploy playbook's own comment. A larger
  droplet remains the alternative if swap ever proves insufficient, and is
  a spending decision rather than an engineering one.
- ~~**Make `List.owner` non-null:** audit live rows, backfill or remove
  orphans, then a schema migration.~~ **Done August 2, 2026**, as release D
  slice 6 — see [`release-d-plan.md`](release-d-plan.md) §5. Of the two
  branches this line offered, **remove** was chosen: an ownerless List is
  unreachable, because every read in the application is owner-scoped, so the
  rows deleted are ones no user could see. `0028` deletes them and prints its
  counts, `0029` makes the column required, and the two are separate
  migrations because a deletion and a schema change that depends on it should
  be reviewable and revertible apart.

  **The evidence that the exception cost more than the data was worth** is in
  this repository rather than in an argument: `0023` and `0026` each had to
  write an explicit ownerless skip-clause, and a third was coming. Charter
  rule 1 now holds for every model without one.

  **Not yet run against production.** Local development had zero ownerless
  rows, but that is the two-user SQLite database §3 already warns against
  trusting; `0028`'s printed counts against production are the first real
  evidence of how many existed. The deletion is irreversible by design — the
  reverse is a stated no-op rather than a lie, since nothing can reconstruct
  which List a deleted Item belonged to.
- ~~**Copy a recurring task's own `notes` onto its next occurrence.**~~ **Done
  August 2, 2026.** `_spawn_next_occurrence` now passes `notes` for the parent
  as it always did for the children, guarded by
  `RecurringParentTest.test_a_recurring_task_keeps_its_own_notes_on_the_next_occurrence`,
  which asserts both halves of the symmetry so neither can regress alone. It
  was a bug with a regression test rather than a design decision, and it did
  not wait on Crane 0.
- ~~**Reconcile `frontend/src/agenda.ts` with `lists/agenda.py`.**~~ **Done
  August 2, 2026, by deleting the claim rather than restoring the authority.**
  Both exports turned out to be genuinely client-only: the API delivers every
  open task and filtering happens on the client, so no server code has ever
  needed `SCOPES`, and `summary_counts` was never the same thing as
  `list_summaries`'s per-list counts. Writing Python nobody calls, purely to
  make a comment true, would have been dead code defending a comment. Both now
  say what they are, why the server has no equivalent, and what would move them
  server-side. Five of the file's seven mirror claims were accurate and are
  untouched.

  **The residual, stated so it is not mistaken for finished:** the claims that
  *are* real — `WEEK_HORIZON_DAYS`, `bucket_for`, `next_weekday`,
  `snooze_presets`, the weekday constants — still have no test proving the two
  sides agree. `principles.md` asks a named mirror to be protected by tests and
  this one is protected by matching comments. Cross-language agreement wants a
  mechanism, probably serving the constants in the payload rather than
  duplicating them, and that is a small design question rather than a line on
  this list.
- ~~**Give `Idea` the index its future search will need.**~~ **Done August 2,
  2026:** `(owner, status, -created_at)`, matching the library view's actual
  query — this owner's ideas, narrowed by status or excluding Promoted, newest
  first — rather than a guess at what search will want. It deliberately does
  not serve the substring `q` filter; that needs full-text or trigram support
  and is release E's decision.
- ~~**Add a content security policy.**~~ **Done August 3, 2026, report-only
  to begin with.** `clarice.middleware.ContentSecurityPolicyMiddleware`
  attaches a per-request nonce and the policy naming it.

  **Report-only is not a way to defer knowing.** The one inline script this
  application deliberately has — the theme resolution script, which must run
  before first paint or the page flashes the wrong theme — is handled with a
  nonce rather than left to surface as a violation nobody was surprised by.
  `script-src` therefore has no `'unsafe-inline'`, which is the whole point.
  `style-src` keeps it, stated as a trade rather than an oversight:
  `app_shell.html` has an inline `<style>` block and React writes inline
  style *attributes* for the area colour dots, which a nonce cannot cover.

  **The suite does the looking.** Report-only only helps if somebody reads
  the console, so `ContentSecurityPolicyTest` loads both shells in a real
  Chromium and asserts nothing was reported — and separately that the theme
  script actually *ran*, since a mismatched nonce would leave the page
  rendering while the script silently did not. Switching to enforcement is a
  one-line header change once real use has stayed quiet.

**Investigate, do not schedule yet: `Item`'s parent/recurrence rules as check
constraints.** The appeal is real — `Item.Meta` already carries
`valid_item_status_timestamps`, so expressing cross-field validity in SQL is a
precedent set inside this very model, and a constraint cannot be forgotten by a
new write path the way a service-layer guard can. But the two guards are not
the symmetric pair they look like, and writing a constraint from the shape
rather than the code would break the table:

- `set_recurrence` rejects only when a subtask is given a *non-`NONE`*
  recurrence. Setting `recurrence=NONE` on a subtask is legal, so the
  constraint is `parent_id IS NULL OR recurrence = 'none'`, not "subtasks may
  not have a recurrence column value."
- `set_always_recurs` rejects unconditionally on a root, but
  `Item.always_recurs` defaults to `True` and `create_item` writes that default
  for roots as well as children. Every existing root row therefore holds
  `always_recurs = True`, and any constraint restricting the flag to children
  fails against current data until those rows are backfilled. That is a data
  migration and a default change — not the free, behaviour-neutral migration it
  first appears to be.

So: worth doing, cheaper than release D, and not as cheap as it looks. It wants
its own small brief rather than a line on this list.

**Next, because it gates everything below it.** A staging environment.
`CLAUDE.md` already identifies its absence as the reason read-only diagnosis
must precede any redeploy that would overwrite evidence, and every remaining
item here is safer to rehearse than to attempt live.

**Decisions made and a real code gap closed, August 11, 2026 — see
[`staging-environment-plan.md`](staging-environment-plan.md).** A second
DigitalOcean droplet, not a second process on production's own (already
tight on memory); its own database on production's existing Postgres
cluster via `provision-postgres.sh`/`restrict-database-user.sh`'s existing
per-database restriction, not a second managed cluster. Designing it
surfaced a real gap before it could bite in production: `settings.py`'s
`DEBUG` had only two states, neither of which fit a `"staging"` value
safely — pulled into a tested `clarice/deployment.py::is_debug()`, the
same "function with a test, not a branch in a config file" pattern
`monitoring.py` already used. **Not yet provisioned** — the droplet, DNS,
and database creation are Vince's own steps (`doctl`, the SSH key and a
real spending decision, the same category deploying already is), detailed
in that plan's §5.

**Then, in this order, each only once staging exists.**

- **An asynchronous task queue.** Contact mail, password reset and the axes
  lockout notification all send synchronously inside the request — a latency and
  failure-mode problem before it is a scale problem, and every feature in E and
  F wanting a background job will otherwise invent its own.
- **Terraform for cloud resources**, written against staging first and promoted
  to production only after it has provisioned something real. Ansible keeps host
  configuration. `provision-postgres.sh` and `restrict-database-user.sh` remain
  production's known-good path until Terraform has replaced them in fact rather
  than in intent.
- **Independent long-retention encrypted backups with a rehearsed restore.** A
  backup nobody has restored is a belief, not a control.
- **CI-built immutable images, health and readiness checks, and a rollback
  runbook.**

**Deferred, with named triggers.** Connection pooling, once gunicorn is tuned
and a real connection ceiling is observed. Row-level security, at Sharing or
paying tenants. Broad API rate limiting, when `/api/v1/` serves anyone not
already trusted.

## 7. What this plan refuses

Recording refusals matters as much as recording plans, because an unrecorded
refusal gets re-proposed every time a new reviewer reads the codebase — which
has now happened three times in one week.

- **A universal Node or Block model.** It would trade strong invariants and
  clear queries for flexibility the product has never asked for. Task, Capture,
  Idea, Daily Entry and Routine Occurrence stay distinct, per `principles.md`'s
  lightweight DDD.
- **A headless Django backend.** Rejected on the evidence in §3: sixteen
  templates extend `base.html`, and `app_shell.html` *is* the SPA's delivery
  page.
- **Renaming the `lists` app or the `Item` model.** Migration churn for no
  behaviour change. The vocabulary migration happens at the API boundary, where
  it has already started.
- **A local-first sync programme before a client needs one.** Charter rules 2
  and 6 keep the option open at near-zero cost; the programme waits for a
  second client.
- **Row-level security or connection pooling now.** Both are real techniques
  with real operational cost, and neither has a problem to solve at three users
  and twenty-four task rows.
- **Deleting the provisioning scripts before Terraform has provisioned
  anything.** Staging, then Terraform against staging, then production.
- **Starting over.** All three reviews agreed independently: the testing
  culture, the injected clock, the isolation tests and the documented
  architectural honesty are worth more than the migrations they cost to build
  around. A cleaner schema without that culture would be a worse product.

## 8. Decisions this plan cannot make

- ~~**Does Crane 0 actually widen?**~~ **Answered August 2, 2026: yes, and then
  narrower than §5 proposed.** The identity half shipped ahead of Crane 1 the
  same day as `crane-plan.md` §3's Crane 0a — a thin `RecurringCommitment`
  holding owner and
  lifespan, plus the nullable `Item.commitment` key `_spawn_next_occurrence`
  never wrote. Additive only; no field leaves `Item` and no client changes. The
  vocabulary half — text, list and cadence moving onto a real template — goes to
  release D, where the parent–child redesign already has to decide what a
  subtask template is. **One argument in §5 did not survive the decision and is
  corrected rather than quietly dropped:** "designing the same shape twice" is
  weak, because §4 rule 8 deliberately makes the shape a documented convention
  instead of a base class, and that convention is already written — release D
  would be applying a recorded rule, not rediscovering it. What actually
  justified acting now is that the unlinkable history accrues fastest exactly
  when Crane turns Clarice into a daily practice.
- ~~**Does release D pair the two design cycles?**~~ **Answered August 2,
  2026: yes.** [`release-d-plan.md`](release-d-plan.md) is the brief for all
  three cycles together — the parent–child redesign, what `List` is, and the
  UI overhaul's sketch — on the argument §5 already made.
- ~~**What is a `List`?**~~ **Answered August 2, 2026: Area, and `Project`
  joins it as its own model.** `List` becomes Area in vocabulary only — no
  schema change, the same API-boundary rename already used for `Item` — and
  `Project` is a new model with its own completion state and due date, on the
  strength of completing being a different life cycle. See
  [`release-d-plan.md`](release-d-plan.md) §3.
- ~~**Does the rest of the `Item` split happen?**~~ **Answered August 2,
  2026: yes, a `ChecklistStep` model**, with the ability to promote a step
  into a full task — the one addition Vince asked for beyond what §2 and §5
  argued for. "The parent-child redesign was enough" was the other legitimate
  answer named here; it wasn't the one chosen. See
  [`release-d-plan.md`](release-d-plan.md) §2.
- ~~**Does release E happen next?**~~ **Answered August 3, 2026: no.** The
  Android device-testing branch and capture tags — merged onto `main` the
  same day — stay folded into release D rather than becoming a release of
  their own, and Vince decided alongside that merge that the next release to
  actually start is **F**, not E; the second mind is skipped for now rather
  than deferred to after it. Worth flagging rather than silently accepting:
  F's own promotion trigger above is several months of weekly reviews
  actually being used, and Crane's first weekly review is days old at the
  time of this decision. Whether F's work starts now or waits on that
  trigger anyway is not answered by this bullet either.
- **Does release G exist?** Everything in it is conditional on deciding that
  Clarice should have users who are not you.
- **Is rich authored content release E, or earlier?** Named here for the first
  time rather than left implicit, but its trigger is real use of Ideas as
  written material, and that has not happened yet.
- **Does the charter go into `principles.md`?** §4 is a set of design standards
  and that is what `principles.md` is for. Its stated bar is "a concrete
  project example **or** prevents a named risk," and every rule here clears the
  second half — so this is a judgement about timing, not eligibility. The
  argument for waiting is that three of the eight rules cite designs rather
  than shipped code; once Crane 0 and Crane 1 have applied the charter in a
  real migration, it probably belongs there and this section becomes a pointer.
- ~~**The other five open questions in `crane-plan.md` §6**~~ — the weekly
  occurrence anchor, progress correction history, home-surface reversibility,
  the carried-in checklist's sequencing, and Crane's shipping cadence — **are
  all answered as of August 2, 2026**, in that document rather than this one,
  which is where they belonged. Two are worth knowing here because they
  correct or use this file: the week anchor is Monday on the evidence of
  `agenda.py`'s existing snooze presets, not as a preference; and the
  decision that routine progress needs no entry-level log turns on §4's
  analytics list being answerable without one, plus the fact that a log is
  additive later where the missing foreign key was not.

  §6 is now empty of open questions. Three of the decisions this section
  once listed are answered above and carried into
  [`release-d-plan.md`](release-d-plan.md): release D's pairing, what a
  `List` is, and whether the rest of the `Item` split happens. What remains
  genuinely open is whether G exists, when rich authored content lands, and
  where the charter lives.
