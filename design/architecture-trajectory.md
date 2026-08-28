# Clarice — architecture and release trajectory

Vince · drafted August 2, 2026 · reduced August 16, 2026

## 1. What this document is for

[`README.md`](README.md) says which document owns which fact. This one answers
the question none of the others do: **what must be true of everything built
here, and what this project has decided not to do.** It exists because three
architectural reviews arrived within a week, each proposing a different
multi-month plan, and because the rate of AI-assisted implementation means the
cost of an unstated convention is now measured in weeks rather than years.

It is deliberately not a task list. Where it names work, that work still earns
a focused spec in `design/` before it starts, exactly as
[`roadmap.md`](roadmap.md) requires.

**On provenance.** Two of the three reviews were produced in conversation
outside this repository and a reader cannot open them. Everything §3 concludes
is therefore argued from files that are here, and §7's refusals stand on that
evidence alone — the reviews supplied the questions, not the answers.

## 2. The superlists ledger — closing the account

Clarice began as the Test-Driven Development with Python tutorial project, and
the standing assumption in every outside review has been that it is a tutorial
app carrying tutorial debt. The migration history says that assumption is close
to spent.

| Tutorial residue | Status | Evidence |
| --- | --- | --- |
| Email address as `User` primary key | **Paid.** Numeric PK, with group and permission relationships preserved by email lookup across the swap. | `accounts/0004`, `lists/0010`–`0011` |
| Passwordless magic-link auth | **Paid.** Real username/password auth, legacy accounts backfilled, the `Token` model deleted cleanly in the same migration that replaced it. | `accounts/0003` |
| SQLite in production | **Paid.** Managed Postgres in production; CI runs every suite against `pgvector/pgvector:pg17`. See §3 on local development — it is not the same claim. | `MIGRATION.md`, `.github/workflows/ci.yml` |
| Server-rendered task UI | **Paid, and deliberately bounded.** The task UI is SPA-only; `dashboard` and `archive` are one-line redirects into it. | `lists/views.py` |
| Anonymous lists, then bolted-on ownership | **Paid, August 2, 2026.** `0028` deletes the ownerless rows, `0029` makes the column required. Charter rule 1 now holds for every model. | `lists/0028`–`0029` |
| A recurring commitment has no identity across its occurrences | **Paid forward, August 2, 2026.** Crane 0a added `RecurringCommitment` and the `Item.commitment` key `_spawn_next_occurrence` now writes. Occurrences archived before that date stay unlinked and always will. | `lists/0022`–`0023`, `lists/services.py` |
| `Item` as the only operational model | **Mostly paid.** `RecurringCommitment`, `ChecklistStep` and `Project` are their own tables and `Item.parent` is retired; status, due dates, recurrence, tags and notes still share one row, deliberately. | `lists/models.py`, `lists/0022`–`0034` |
| Hand-rolled JSON endpoints beside `/api/v1/` | **Outstanding, unscheduled.** `lists.api` owns item create/reorder/detail. The v1 router's docstring is a rule for *not* moving them — "Item mutations … stay on the hand-rolled lists.api endpoints" — not a migration schedule, and nothing in `roadmap.md` schedules one. | `lists/api_urls.py`, `lists/api_v1.py` |
| The app is still called `lists` | **Outstanding, cosmetic.** Left alone deliberately: renaming buys no behaviour and costs migration churn. The API already says `/tasks/{item_id}`. | `lists/api_v1.py` |

Two outstanding, both deliberate, down from five when this ledger was drafted.
What closed each of the others is in
[`roadmap-history.md`](roadmap-history.md) rather than here.

**One limit is worth stating as plainly as the defect was.** No migration can
link occurrences that were already archived before `Item.commitment` existed:
reconstructing them would mean matching on `(list, text, recurrence)`, which
merges distinct tasks sharing a title and splits any series that was ever
renamed. Declined deliberately — an audit-proof gap beats invented history.

**The consequence for planning.** The interesting risk to Clarice is no longer
behind it. Retrospective cleanup is bounded and nearly finished, and making it
the organising principle of the next six months would be planning against the
wrong threat. The live risk is forward: `lists/0001` is dated July 17, 2026,
and in the month since, seven models have become **thirty-six** across two cores
(~~twenty-five~~, recounted August 28, 2026 — the growth rate this paragraph
warns about was itself understated by eleven).
A second generation of scar tissue is still preventable; the first is nearly
paid off. That is what §4 is for.

## 3. Three reviews, refereed

Two external reviews (recorded here as Chat and Gemini) and this project's own
audit examined the same codebase within days of each other. Their agreements
are worth recording because independent convergence is evidence; their
disagreements because two proposals would have caused real damage if executed —
and because one of my own dissents was wrong, which is recorded below rather
than quietly dropped.

**Where all three agree.** `List.owner` should be made non-null now. `Item` is
overloaded and needs a redesign, but not inside Crane. The SPA migration was
not a mistake — the product's ambition changed, and no path through a Django
tutorial avoids that pivot. The Capture/Idea split was the correct call. Rich
authored content is eventually needed and is not needed yet. Row-level security
is deferred until sharing or real tenancy exists. And the testing culture —
outside-in TDD, the injected clock, first-class isolation tests, documented
architectural honesty — is the asset to protect above all the rest.

An agreement worth singling out: Chat's independent description of what a
routine occurrence needs — target snapshots, historical logging, target met in
one action, partial close, explicit skip, correction history — reproduced the
`RoutineOccurrence` design already settled in [`crane-plan.md`](crane-plan.md)
§3, including the same unresolved question about a satisfied-but-partial close.
Two passes reaching the same model by different routes was the strongest
available signal that Crane 0 was right, and it shipped that way.

### Where I was wrong: Postgres in local development

Chat proposed moving local development onto Postgres. I dissented, quoting
`settings.py`'s own comment that "nothing about this app's schema depends on
Postgres-only behavior yet." **That comment was stale and the dissent was
wrong**, for two reasons — only one of which was visible at the time.

**The schema does depend on Postgres.** `mind.Mention.mention_unique` is
`nulls_distinct=False` — Postgres 15+ only — and the `mind` migrations run
`CreateExtension("vector")`. Django builds the test database from *every* app's
migrations whichever labels are under test, so SQLite, or a stock Postgres
image, fails in `setup_databases` before a single test runs. The reason
originally given here was `Item.Meta`'s `unique_active_item`, which SQLite
silently declined to create; `lists/0027` removed that flag once dropping
`Item.parent` left the constraint's fields all non-nullable. **The rule
outlived its first reason**, which is why the reason is restated correctly
rather than dropped — three documents were still citing the retired one on
August 16.

**And SQLite changes the concurrency the harness runs under, which bit for
real.** August 2, 2026: the browser job went red across two commits on an
`IndexError` inside Django's `apply_converters` — a result set read while
another statement was in flight. `manage.py test` puts SQLite in memory, an
in-memory database cannot be reached by a second connection, so
`LiveServerTestCase` hands the test's own connection to the server thread while
`ThreadedWSGIServer` serves each request on a thread of its own. One connection,
several threads, since the suite was written; four green runs beforehand were
luck. It failed identically in CI, so this one was never a local-versus-CI
divergence at all, which makes "the machine will notice" thinner still. The fix
— naming the test database so it becomes a file — is a SQLite-specific
workaround for a problem Postgres does not have, kept because anyone may still
run these locally on SQLite.

### Where this project dissents

**Going headless.** Gemini's Phase 2 proposes deleting `src/lists/templates/`,
including `base.html` and `app_shell.html`, and serving a compiled `index.html`
from the root. This would break the application. `app_shell.html` is not legacy
— it is the page that renders the SPA, resolving the theme, loading the styles
and mounting `#app-root` for every `/app/...` route; there is no Vite-built root
document waiting to replace it. `base.html` is extended by every account flow,
the contact form, the token page, the 403 and lockout pages, and — pointedly —
`new_list_form.html`, the one extending template that actually lives in the
directory proposed for deletion, rendered by `lists/views.py` when a new-list
POST fails validation. Removing these would delete authentication in the name of
removing debt.

`roadmap-history.md`'s boundary has two halves with different force: "The task
UI is now SPA-only. Capture and account surfaces **can remain** Django-rendered
where that is the better fit." The first is settled; the second is a permission,
not a commitment. Those surfaces may migrate later on their own merits. What is
not on the table is deleting them as cleanup.

**A local-first sync phase.** Chat's Phase 5 proposes a staged sync programme.
The sync problem Clarice actually has is already solved, narrowly and well, by
the Android client's encrypted queue and owner-scoped idempotency contract.
Generalising it into browser persistence before a second client needs it is
optimising an imagined workflow — the thing `principles.md` explicitly warns
against. What is cheap is giving each *new* table the primitives a future sync
would need, at the moment it is created. That belongs in the charter below, not
in a phase of its own.

**A new `knowledge` app.** Chat's seven-domain model listed Knowledge as future
work to be stood up beside the task core. Refused at the time because
`capture.Capture` and `capture.Idea` already held that ground. **Overtaken
rather than upheld:** the knowledge core arrived by merger on August 14, 2026 as
`src/mind/`, and `Capture` and `Idea` were deleted the next day. The refusal
that survives is the narrower one in §7 — no universal Node or Block model *in
the task core* — and §7 says why living in the same tree is not a reversal.

**PgBouncer, and infrastructure ordering generally.** Gemini's Phase 3 proposes
connection pooling. The concurrency ceiling was upstream of the database:
`Dockerfile`'s gunicorn command set no worker or thread count, so the
application served on gunicorn's default before pooling could become the
constraint (§6 fixed that; pooling is still deferred). The same section proposes
deleting `infra/provision-postgres.sh` and `infra/restrict-database-user.sh` for
Terraform. Those are 98 and 173 lines of operational knowledge including the
non-obvious fact that every user on a shared DigitalOcean cluster can reach
every database on it unless explicitly restricted. Replacing them with
unrehearsed Terraform aimed at the only production host, with no staging to
rehearse against, inverts the order of safety.

**What neither review addressed.** Both produced fixed to-do lists. Neither
asked what rule should govern the tables that do not exist yet — which, given
the pace at which they are about to be created, is the question with the largest
expected value. That is §4.

## 4. The charter for new records

Eight rules for the design of any new model. Each costs close to nothing when a
table is created and is expensive or impossible to retrofit; that asymmetry is
the whole argument, and it is the same one `principles.md` makes about
reversible decisions.

Every rule below now cites a table that exists. Three of them cited unbuilt
sketches in `crane-plan.md` when this was drafted on August 2, 2026; all three
have since shipped.

**Before the rules: does this earn a model?** The charter makes new tables cheap
to get right, which makes it easier to create too many — the opposite failure
from the god table. The test is that **a concept earns its own model when it has
a different life cycle, not when it has a different name.** A Checklist Step
earns one: no due date, never in the agenda, cannot recur, dies with its parent.
A Project earns one against a List, because a project completes and a list never
does. A Habit does *not* earn one against a Routine — `target_quantity=1,
unit=""` already is a habit, and the difference is data rather than schema. An
Area does not earn one against a List; that is a rename at most. When the answer
is no, the concept is a field, a status, or a word in the interface.

**1. Owned at birth.** Every root record carries a non-null owner foreign key in
its first migration. *Precedent:* `Tag` (`lists/0015`) got this right; `List`
(`lists/0007`) did not, five days earlier, and it took two migrations and a live
audit to fix in `0028`–`0029`. *Cost now:* nothing. *Cost later:* exactly that,
plus every isolation test written in between proving a weaker guarantee than it
appeared to.

**2. A public identifier wherever a client may create the record offline.** An
additional UUID column, never a change of primary key. *Precedent:*
`mind.Node.public_id` — client-suppliable, unique, and the whole of the capture
API's idempotency guarantee for the Android queue. *Cost now:* one field. *Cost
later:* identity cannot be retrofitted onto records a device already holds, and
`principles.md`'s retry-safety rule has no database constraint behind it.

**3. Snapshot whatever a record's meaning depends on.** A record describing what
happened copies the values that give it meaning rather than reading them live.
*Precedent:* `RoutineOccurrence.target_quantity` and `unit` — a routine's target
changing from five to three must not rewrite last month's "4 of 5." *Cost
later:* the history is already wrong and nothing can recover it. This is
`principles.md`'s durable-records rule expressed as a schema habit.

**4. A read module and a service module, from the first slice.** Query and
derivation code answers questions; service code enforces invariants and mutates.
*Precedent:* `agenda.py` is query-only and `services.py` owns mutations;
`routines` and `daily` were built with the split from their first slice.

What this rule may **not** claim is that a shared definition prevents drift. The
counter-example is in this repository: `frontend/src/agenda.ts` once documented
two exports as mirroring Python authorities that did not exist. `principles.md`
allows a named mirror provided tests protect it. Since August 18, 2026 the
mirrored *constants* — `WEEK_HORIZON_DAYS`, `AGE_WORTH_MENTIONING` — are
protected by `lists/tests/test_mirrored_business_rules.py`, which reads all three
languages. The mirrored *logic* — `bucket_for`, `next_weekday`, `snooze_presets`,
the weekday constants — is still protected by matching comments rather than a
test, so this rule is half satisfied and the half that is missing is the harder
one. See §6, and `mirrored-rules-brief.md` for why deleting two of the three
copies would be worth more than testing them.

**5. Reference, never copy.** A surface displays a record; it does not own a
duplicate that can drift. *Precedent:* the Daily Page embeds the agenda query
rather than copying task state onto the day, and a task's project is pure
computation (`item.list.project`) with nothing stored to keep in sync. *Cost
later:* two sources of truth for whether something is done, and review metrics
that cannot be trusted.

**6. State the deletion decision in the model, and say what an offline client
would see.** Soft or hard, undoable or not, decided when the table is created.
*Precedent:* `Project` deletes hard and its Areas survive unparented, argued in
its own docstring; `mind.Node` soft-deletes via `deleted_at`, with archive as a
separate state. *The second half is the one that gets forgotten:* a hard delete
is invisible to a client that was offline when it happened, so any record
covered by rule 2 also needs a tombstone or a change-cursor entry. *Cost later:*
a device that silently resurrects deleted records.

**7. Index the query the feature actually runs.** *Precedent:* `Item` carries
four purposeful indexes, one of which — `(commitment, created_at)` — nothing
queries yet, because it backs the series read every trend and streak in release
F will run and it costs a line now. *Cost now:* one `Meta.indexes` entry.

**8. Repeating things carry a template and dated occurrences.** Anything that
happens more than once splits into a durable template holding the rule and dated
occurrence rows holding what actually happened, each occurrence pointing back at
its template. *Precedent:* `RecurringCommitment` with `Item.commitment`, and
`Routine` with `RoutineOccurrence`. *The counter-example was in production*
until August 2, 2026: recurring tasks were a chain of rows whose only connection
was a matching text string. *Cost now:* one foreign key. *Cost later:* the
history exists but cannot be assembled, and no migration can invent links after
the fact.

The shape to keep consistent across every occurrence table: owner, a foreign key
to the template, the date or period covered, a snapshot of what was expected
(rule 3), an outcome, and when that outcome was decided. Keep it a documented
convention rather than an abstract base class — a shared base invites putting
more on it, which is how the last overloaded table started.

**Applying it to Crane 0.** `Routine` and `RoutineOccurrence` as sketched in
`crane-plan.md` §3 satisfied rules 3, 5 and 8 and largely rule 7 — the
`(routine, period_start)` unique constraint creates on Postgres exactly the index
the logging path's "this routine, this period" lookup needs. Three gaps were
named against the sketch, and **all three were closed in the shipped
`src/routines/` rather than inherited**, as that app's own docstrings record:
`RoutineOccurrence` had no owner foreign key at all, reaching its owner only
through `Routine`, which failed rule 1 and made every isolation test on it a
two-hop assertion; the sketch was a single `models.py` with no read or service
module, which failed rule 4; and rules 2 and 6 were unaddressed.

**What the charter buys.** Rules 3 and 8 exist because analysing past
performance is a stated product ambition, and that ambition is decided at write
time rather than at read time. Once every repeating thing has a template, dated
occurrences and a snapshot of what was expected, one review-and-analytics read
module can serve all of them — and a set of questions becomes answerable with no
further tables:

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
rows. Their home is release F. Their cost was paid in Crane 0.

## 5. The release arc

**Cut on August 16, 2026.** This section sequenced Crane through G and had
become a second home for facts it did not own — it gave release F a different
subject than `roadmap.md` gave it.

**What is active or deferred lives in [`roadmap.md`](roadmap.md); what shipped
lives in [`roadmap-history.md`](roadmap-history.md).** Neither is restated here.

The one durable rule the section carried is now in `roadmap.md` under *Release
practice*: **a letter is the next position in a sequence, claimed by whatever
ships next.** Nothing is reserved for a subject that has not started.

## 6. The infrastructure track

Infrastructure work does not ship features and should not be numbered as a
release. It runs alongside, ordered by what unblocks what, with each item's
trigger stated so it can be deferred honestly rather than quietly.

**Done, kept short — the verdict and the reason that outlives it, nothing
more.** The narrative is in [`roadmap-history.md`](roadmap-history.md).

- ~~**Move local development onto Postgres**, and correct `settings.py`'s stale
  comment.~~ **Done August 11, 2026**, for both the reasons in §3 — the schema
  one and the concurrency one that bit for real. `docker-compose.yml` provides a
  local `pgvector/pgvector:pg17` container matching CI's; `settings.py`'s `DEBUG`
  branch defaults `DJANGO_DATABASE_URL` to it. **The local suite is no longer
  SQLite by default**, which several tests now assert against rather than assume.
- ~~**Rate-limit the landing page's login form.**~~ **Done August 3, 2026.** `/`
  is a `LoginView`, so `POST /` authenticated exactly as `POST
  /accounts/login/` did while only the latter was throttled. `location = /` now
  carries a 5r/m limit keyed on the request method, so only POSTs are counted:
  throttling GETs would have traded a real availability risk for no security
  gain.
- ~~**Set gunicorn's worker and thread count explicitly.**~~ **Done August 3,
  2026**, and measuring first changed the answer. The droplet has one core,
  458MB and no swap, so the usual `(2 × cores) + 1` would have been actively
  harmful: three workers is roughly 204MB against ~152MB available, and the OOM
  killer takes the container rather than the site merely slowing. Two workers
  was still too tight — the next deploy's `apt-mark manual docker.io` was
  OOM-killed (rc 137) at "Install nginx and certbot". It is one worker and four
  threads now, plus a 1GB swapfile at swappiness 10 placed ahead of the apt
  tasks it protects.

  **The error is worth more than the number.** The container was sized at rest
  against available memory, when what mattered was the peak the *host* needs
  while apt and dpkg run. A container that fits is not the same as a host that
  can still maintain itself.
- ~~**Make `List.owner` non-null:** audit live rows, backfill or remove
  orphans, then a schema migration.~~ **Done August 2, 2026.** Of the two
  branches this line offered, **remove** was chosen: an ownerless List is
  unreachable, because every read in the application is owner-scoped, so the
  rows deleted are ones no user could see. `0028` deletes them and prints its
  counts, `0029` makes the column required — separate migrations because a
  deletion and a schema change that depends on it should be reviewable and
  revertible apart. Irreversible by design; `0028`'s reverse is a stated no-op
  rather than a lie.
- ~~**Copy a recurring task's own `notes` onto its next occurrence.**~~ **Done
  August 2, 2026**, with a regression test asserting both halves of the symmetry
  so neither can regress alone.
- ~~**Reconcile `frontend/src/agenda.ts` with `lists/agenda.py`.**~~ **Done
  August 2, 2026, by deleting the claim rather than restoring the authority** —
  both exports were genuinely client-only, and writing Python nobody calls purely
  to make a comment true would have been dead code defending a comment.

  **The residual, stated so it is not mistaken for finished:** the mirror claims
  that *are* real still have no test proving the two sides agree. Cross-language
  agreement wants a mechanism — probably serving the constants in the payload
  rather than duplicating them.
- ~~**Give `Idea` the index its future search will need.**~~ **Superseded.**
  Shipped August 2, 2026; `Idea` was deleted with the capture surface on August
  15. Search over the knowledge core is `src/mind/`'s problem now.
- ~~**Add a content security policy.**~~ **Done August 3, 2026, report-only to
  begin with** — this was the genuine remaining gap, X-Frame-Options and
  content-type-nosniff being covered already.
  `clarice.middleware.ContentSecurityPolicyMiddleware` attaches a per-request
  nonce and the policy naming it. `script-src` has no `'unsafe-inline'` — the
  one deliberate inline script, theme resolution before first paint, gets the
  nonce. `style-src` keeps it, stated as a trade: `app_shell.html` has an inline
  `<style>` block and React writes inline style *attributes*, which a nonce
  cannot cover.

  **Report-only is not a way to defer knowing.** `ContentSecurityPolicyTest`
  loads both shells in a real Chromium and asserts nothing was reported — and
  separately that the theme script actually *ran*, since a mismatched nonce
  would leave the page rendering while the script silently did not. Switching to
  enforcement is a one-line header change once real use has stayed quiet.

**Next, because it gates everything below it.** A staging environment.
`CLAUDE.md` already identifies its absence as the reason read-only diagnosis
must precede any redeploy that would overwrite evidence, and every remaining
item here is safer to rehearse than to attempt live.

**Designed August 11, 2026 and deliberately deferred; the shape and the
remaining steps are in
[`staging-environment-plan.md`](staging-environment-plan.md).** Designing it
surfaced a real gap before it could bite: `settings.py`'s `DEBUG` had only two
states, neither of which fit a `"staging"` value safely — pulled into a tested
`clarice/deployment.py::is_debug()`, the same "function with a test, not a
branch in a config file" pattern `monitoring.py` already used. That shipped;
the droplet has not, and provisioning it is Vince's own step and a real
spending decision.

**Then, in this order, each only once staging exists.**

- **An asynchronous task queue.** Contact mail, password reset and the axes
  lockout notification all send synchronously inside the request — a latency and
  failure-mode problem before it is a scale problem, and every background job a
  later release wants will otherwise invent its own.
- **Terraform for cloud resources**, written against staging first and promoted
  to production only after it has provisioned something real. Ansible keeps host
  configuration. `provision-postgres.sh` and `restrict-database-user.sh` remain
  production's known-good path until Terraform has replaced them in fact rather
  than in intent.
- **Independent long-retention encrypted backups with a rehearsed restore.** A
  backup nobody has restored is a belief, not a control.

  **No longer behind staging — August 26, 2026**, answering
  `security-and-resilience-plan.md`'s D3. **The ordering rested on rehearsal
  needing somewhere to rehearse**, and the drill of August 19 disproved that by
  running end to end against a paid scratch cluster and passing. So the second
  half of this line is *done* and the first half was never the part that needed
  staging.

  **And the case for it got stronger the same day.** `clarice-v4-plan.md`'s V1
  was answered as *Vince plus one invited person*, so the managed seven-day
  window is now the whole bound on undoing a bad migration **against somebody
  else's data**. A migration whose damage is noticed on day eight is not
  recoverable, and she cannot notice it, restore it, or know it happened.
- **CI-built immutable images, health and readiness checks, and a rollback
  runbook.**

**Deferred, with named triggers.** Connection pooling, once a real connection
ceiling is observed. Row-level security, at Sharing or paying tenants. Broad API
rate limiting, when `/api/v1/` serves anyone not already trusted — note that an
individual unauthenticated route already meets that trigger on its own and does
not need this item to move.

**Dropped, August 16, 2026: `Item`'s parent/recurrence rules as check
constraints.** The appeal was real — `Item.Meta` already carries
`valid_item_status_timestamps`, so expressing cross-field validity in SQL was a
precedent set inside the model. Both premises are gone: `lists/0027` retired
`Item.parent` and `Item.always_recurs`, so there is no subtask to constrain and
no `set_always_recurs` to mirror.

## 7. What this plan refuses

Recording refusals matters as much as recording plans, because an unrecorded
refusal gets re-proposed every time a new reviewer reads the codebase — which
happened three times in one week, and is why each entry below carries its
reason rather than just its verdict.

**Scope, stated August 13, 2026: these refusals bind the task core and nothing
else.** The knowledge core in `src/mind/` is **not governed by this document** —
see [`principles.md`](principles.md) §Scope, which draws the line by kind of rule
rather than by directory. It does exactly what two entries below refuse: a **node
model with facets and typed edges**, from a **fresh start**. Neither is a
reversal, and living in the same tree does not make it one — a refusal reached
inside the task domain, on this codebase's evidence, does not extend to a
different project with a different premise. *Starting over* below refuses
discarding **this** repository's testing culture, which the knowledge core
carries over rather than discards.

The list is unamended.

- **A universal Node or Block model.** It would trade strong invariants and
  clear queries for flexibility the task core has never asked for. Task,
  Checklist Step, Project, Daily Entry and Routine Occurrence stay distinct, per
  `principles.md`'s lightweight DDD.
- **A headless Django backend.** Rejected on the evidence in §3:
  `app_shell.html` *is* the SPA's delivery page, and every server-rendered
  surface that survives — the account flows, the contact form, the token page,
  the 403 and lockout pages — extends `base.html`. Deleting the template
  directory deletes authentication. This refusal does not depend on how many
  templates there are at any moment; it depends on there being no Vite-built
  root document and no SPA route for logging in.
- **Renaming the `lists` app or the `Item` model.** Migration churn for no
  behaviour change. The vocabulary migration happens at the API boundary, where
  it has already started.
- **A local-first sync programme before a client needs one.** Charter rules 2
  and 6 keep the option open at near-zero cost; the programme waits for a second
  client.
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

Six of the questions this section opened were answered on August 2 and 3, 2026
and are recorded where they were decided: Crane 0's widening, release D's
pairing of three design cycles, what a `List` is (Area in vocabulary, with
`Project` as its own model), whether the rest of the `Item` split happens
(`ChecklistStep`, promotable to a task), whether release E happens next (no),
and the five open questions in `crane-plan.md` §6. See
[`release-d-plan.md`](release-d-plan.md) and `crane-plan.md`.

What remains genuinely open:

- ~~**Does release G exist?** Everything in it is conditional on deciding that
  Clarice should have users who are not you.~~ **Not answered — rehomed August
  26, 2026.** This is [`clarice-v4-plan.md`](clarice-v4-plan.md)'s **V1**,
  *does anybody other than Vince ever use Clarice*, and that file owns it: it
  prices both branches, names the spine that is correct either way, and is the
  reason the question can stay open honestly. **The letter G is the stale part**
  — it was spent on the merger as `godwit` on August 15, 2026, and §5 above
  records that speculatively attaching a subject to a letter is exactly what
  this document stopped doing. Two homes for one question is the drift
  `README.md` exists to prevent, so this one links rather than restates.
- **Is rich authored content release E, or earlier?** Overtaken in the
  knowledge core, which ships `Node` and `Revision`, and still open in the task
  core, where the trigger it named — real use of written material — now belongs
  to `src/mind/` and so may never fire here at all.
- ~~**Does the charter go into `principles.md`?** §4 is a set of design standards
  and that is what `principles.md` is for; its stated bar is "a concrete project
  example **or** prevents a named risk," and every rule clears the second half —
  so this is a judgement about timing, not eligibility. The original argument
  for waiting was that three rules cited designs rather than shipped code. That
  is no longer true, so the question is now live rather than answered by
  default.~~ **Answered August 26, 2026: it stays here, and `principles.md`
  links to it.**

  **Eligibility was never the question and the citations are.** Comments across
  `src/`, `frontend/`, `android/` and `infra/` cite `architecture-trajectory.md`
  **§4** by that name and number — ~~around forty-five~~ **seventy-seven files
  at the August 28, 2026 recount**, and no number is kept here now, because this
  one only grows and the argument does not depend on its size — and several
  models — `WeeklyOutcome`,
  `PlanningSession`, `Item`'s sidecars — carry rule-by-rule compliance against
  it. **Moving the text makes every one of those cite a section that is not
  there**, and the file resolving is not the same as the section resolving.

  **What the move was for was discoverability**, and a line in `principles.md`
  pointing here buys that for nothing. Which is this tree's own rule arriving at
  its own question: *if a document needs a fact it does not own, link to the
  owner rather than restating it.*
