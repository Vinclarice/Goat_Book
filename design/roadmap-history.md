# Clarice — Roadmap History

Vince · completed work and decision record · archived from `roadmap.md` on
August 1, 2026

The reasoning, deployment record and lessons behind completed work, kept out of
the active plan so that plan stays scannable. The active plan is
[`roadmap.md`](roadmap.md).

**Three deployments were missing from this file until August 26, 2026** —
`osprey`, `petrel` and the August 26 batch, the newest three there were. They
are written up below from their annotated tags, which were the only account of
them anywhere: `osprey` in particular appeared **nowhere in `design/`**, not
here and not in `roadmap.md`, while having moved four of this product's
nineteen journeys. Worth saying rather than quietly filling in, because this is
the one file the index calls unable to go stale — and it cannot, but it can be
incomplete, which reads the same to somebody looking for what happened.

## A bill earns its own model — August 31 – September 1, 2026, `DEPLOYED-2026-09-01/2247`, no bird

Sixteen commits and six migrations, deployed at 22:47 EDT (UTC-04:00) on
September 1, 2026 — `DEPLOYED-2026-09-01/2247`, image `clarice:d0a249f70354`.
Two of the migrations changed data irreversibly: `0057` deleted the tasks that
were bills, and `0059` dropped the `MoneyLine` table.

**Verified after the deploy rather than assumed.** The table is gone from
`information_schema`, all three `Bill` constraints are present, `migrate --check`
is clean, and the one real bill converted intact — *Dell Financial (Commenity)*,
due August 20, owed, 100.00 USD, with its series — alongside 23 untouched tasks
and one account. `catch_up_bills --dry-run` answers *would create 0*, which is
the right answer: that bill's next occurrence is September 20 and is not owed
yet.

**One thing was not verified and is named rather than assumed**: the hourly cron
entry itself. Reading root's crontab needs a password that is Vince's, and this
host does not log cron to the journal — the digest and the evening nudge do not
appear there either, so their absence proves nothing in either direction.

**No bird**, and held rather than refused, for the reason the Money module's own
codename is held: `module-score.md` still reads *not yet*, this is a modelling
change underneath a module nobody has used much, and `CLAUDE.md`'s rule is that
when it is arguable it is not a release.

**It began as one sentence with two things in it.** Vince, after using the
repaired Money module and adding a *Dell Community* account: *"I've added Dell
Commenity and its showing up but now there's a disconnect. Like it should be
tied to the payments. So I really think we need to separate bills from a task."*
The **disconnect** was that an account and the bill that pays it were unrelated
records — increment 7. The **diagnosis** was that a bill should not be a task —
increments 1 to 6, 8 and 9. Separating the two is the only reason this stayed
tractable.

### It overturned a refusal by satisfying the charter rather than waiving it

`money-module-plan.md` had refused a bill as its own model on August 27, citing
`architecture-trajectory.md` §4 — *a concept earns its own model when it has a
different life cycle, not when it has a different name.* §4 never named bills,
and **its test was met rather than set aside**: the qualifying difference had
been written into `roadmap.md` on August 28, one day after the refusal, and
nobody put the two side by side for three days.

The difference is that the same event — a period elapsing unfinished — must
produce opposite outcomes. Five missed bin rounds are five things that did not
happen and inventing them is fabricated history. **A payment you did not make is
still owed.** Two behaviours that cannot both live in one `status` field on one
model is exactly what §4 asks for.

**Recorded as a reversal of a decision, not of a mistake.** The refusal was
sound about *names*, and was made before the evidence that answered it existed.

### The reversal condition was met, priced, and declined

The plan named its own off-ramps in writing before any of it was built. One of
them triggered: reading two models on the daily surfaces was supposed to be the
signal that a product decision had been spent to buy a modelling one. It cost a
`bills` array on two payloads, a second query, and a section of its own on the
day page. **Vince's call, August 31: pay it.** Bills are still on the agenda and
the day, which is what decision 4 exists to protect.

**Naming the off-ramp in advance is what made that a decision rather than a
drift.** The alternative — noticing the cost afterwards and rationalising it —
is available to any plan that does not write the condition down first.

### What the split paid for, and what it cost

**Paid for.** `BillRow` is gone, and with it a paragraph explaining that a paid
*recurring* task is `ARCHIVED` rather than `COMPLETED` so settlement must never
be read from the status; `paid_at` has no such trap. The month endpoint's
hand-built row dict and `_bill_row_out` collapsed into one function over one
record. The task detail page stopped being taught, one field at a time, to hide
Priority, Area and Checklist and call itself *Bill detail* — a bill has none of
them, and `/money/bills/:id` is its own page.

**Cost.** Two shapes on the agenda and the day, the `bills` array above, and a
`catch_up` pass with a cron entry to keep it running.

**Deliberately dropped**: the archive. *Put away* was a task state a bill
inherited; a bill you neither pay nor delete is now simply owed. Zero rows were
affected, and the concept is gone rather than carried.

**Deliberately gained**: two open bills from one payee. That was refused before,
not by anything in the money domain but by `unique_active_item` reaching money
through the derived title *Pay Amazon*. Two invoices from one supplier in a
month is ordinary and the old model could not record it.

### Four things the increments found that the plan had not

**The plan's own ordering was wrong, and the flip found it.** Increment 4 was
written as though decision 4 broke at increment 5. It broke at 4: a bill created
after the write switch has no `Item` and vanishes from the day, *while bills
created before it stay* — an inconsistent break rather than a clean one. The
increments were resequenced.

**`0055` copied rather than moved, so every converted bill existed twice.** That
was the point while both reads were live and a duplicate the moment the writes
moved. The plan never said what happened to the task copies; `0057` deletes
them, and it is the other half of the conversion rather than a tidy-up.

**Increment 6 was worse than `roadmap.md` predicted.** That entry described
*paid in August, schedules September, July is gone*. Measured first, as it asked:
a monthly card bill due August 20 and unpaid held **one** occurrence and would
have held one in 2027, because the only producer of a successor was settling or
deleting the current one. The doctrine's cost was not a skipped period going
unrecorded — it was that **falling behind made the module go quiet**.

**Increment 8 was filed as housekeeping and was not.** `MoneyLine` carried a
not-negative CHECK; `Bill` had never been given one, so deleting the old model
would have ended a database guarantee silently. And the restore drill was
checking that constraint by name — after the drop it would have queried a
constraint that cannot exist, reported `no`, and failed at step 5 with a paid
scratch cluster running.

### What it taught: a guard is only as good as its second direction

The drill guard walked *declared → script* and *NOT_DRILLED → declared*, and
never *script → declared*. So a constraint **added** without a decision failed
the build, and a constraint **deleted** left its name in the drill and nothing
said a word. One asymmetry, invisible for as long as nothing was deleted.

That is the same shape as the `MoneyLine` CHECK itself: the guarantee was
enforced on the old model and never carried to the new one, and no test asked
whether the *replacement* still refused what its predecessor refused. **A
migration is where guarantees go missing**, because every test that named the
old one is deleted alongside it.

Both fixed, the second with the guard whose absence allowed it — mutation-tested
against a renamed constraint rather than trusted.

### Two mistakes worth keeping

**`git checkout -- <file>` is not an undo for one edit.** Used to revert a
deliberate mutation-test change, it reverted every uncommitted change in that
file — an increment's worth. Caught immediately by reading the diff. Copy the
file, or stage first.

**A rename script run twice rewrites its own prose.** The second pass over
`agenda.py` turned `task_id` into `id` inside a docstring that had just been
written to explain the rename, leaving it saying the key *"was spelled `id`"*.
Caught by reading the diff, not by any test — which is the argument for reading
diffs even when four suites are green.

### Where the pieces live

The plan is [`bill-as-a-model-plan.md`](bill-as-a-model-plan.md), reduced to a
stub that maps the sections code cites. The charter is
[`architecture-trajectory.md`](architecture-trajectory.md) §4. What the module
is and refuses is [`money-module-plan.md`](money-module-plan.md), which loses
one refusal to this and keeps the rest. How it scores is
[`module-score.md`](module-score.md), which reads **not yet** and is not moved
by any of this: the split is a modelling change, and the score is about use.

**One condition stays open** and is `roadmap.md`'s — whether replaying missed
periods produces a wall of arrears. It is promoted there as its own entry rather
than left inside this narrative.


## The Money module — August 27, 2026, codename held

Thirty-three commits and eight migrations, verified in production at 23:20 local
(UTC-04:00) — `DEPLOYED-2026-08-27/2320`, image `clarice:38d6a628279a`. The
narrative, every increment struck with its date, is in
[`money-module-plan.md`](money-module-plan.md) and is not restated here.

**It began as a complaint about a page, not a request for a module.** *"Why does
it exist? I can't actually do anything on that page (such as adding bills, which
is perhaps the most important thing)."* Bills was a report on records it gave you
no way to create, edit, pay or delete. What shipped is a landing page, income,
categories, account balances and twelve months of history with projections.

**The migration is the part worth keeping.** `makemigrations` answered the
`Bill` → `MoneyLine` rename with a `CreateModel` and a `DeleteModel`, which is a
correct-looking pair that drops the table and every row in it. `0048` is
hand-written — `RenameModel`, then the reverse accessor, the new column, and
`RemoveConstraint`/`AddConstraint` because Django has `RenameIndex` and no
`RenameConstraint`. Checked by counting rows in and rows out before it was
trusted. **The generator's output is a proposal about your data, and a rename is
where it is most confidently wrong.**

**Its one finding, four times over: the defect here is capability that exists and
is not reachable.** The sidecar silently dropped when a recurring bill spawned
its successor; the delete path would have taken the whole series; paid recurring
bills were invisible because they archive rather than complete; and `lead_days`
— the headline *warn me before the annual subscription renews* feature — was
already built, with nothing anywhere that let a person set it. Not one of these
was a broken component. Every one was two correct components nobody joined.

**And the guards caught four omissions that were mine**, in one day: an
undeclared dark service, three models missing from the export, three constraints
missing from the restore drill, and two releases missing from this file. The
lesson went into `CLAUDE.md` in the words it deserved — *remembering is not the
control; running them is.*

**No bird, and this one is held rather than refused.** It has a subject and it
moves what [`product-stories.md`](product-stories.md) tracks, so unlike the
August 26 batch below it is not excluded by
[`architecture-trajectory.md`](architecture-trajectory.md) §6. Vince has looked
at one of the six screens. **A codename is a claim that a body of work finished,
and finished is a judgement about use rather than about tests** — so the letter
stays open until he has used it. If it is still arguable when he has, *Release
practice* says that settles it the other way.

## The declare-or-refuse sweep — August 26, 2026

Not a release and not a deploy. **One pass over every open thread in `design/`,
asking `principles.md`'s question of each**: does this have a trigger, and can
that trigger fire? Recorded here because it changed the score without changing
any code, which is the kind of event this file exists to keep.

**It was made possible by answering V1**, and it was not possible before.
`clarice-v4-plan.md` had the fork open since August 22 — *does anybody other
than Vince ever use Clarice* — and had correctly said the spine was right either
way. The answer is **one other person and not the public**, and roughly a third
of the open threads turned out to be waiting on it.

**Twenty threads went in.** [`recommendations-2026-08-21.md`](recommendations-2026-08-21.md)
§5 had named the number as the risk on August 21 — *"that exceeds one person's
landing rate"* — and it was the item nobody adopted.

**Two became refusals.** S1, because public signup is a path that exists, costs
five lines, and will not be built; S18, because there are no strangers to switch
and **no archive to import**, which also struck v4's own spine item. Both are
*refused* rather than *impossible*: the first three verdicts describe the code
and the fourth describes a decision.

**Three were feelings and became numbers.** Search's fifth increment had gated
itself on *"long enough to say the sections are the right sections"*; the
planning assistant's ninth on *"a sample"* with no floor named; D18 on a
deadline that had already passed without anybody noticing. Each now has a
condition that can be checked rather than felt — ten misses, twenty confirmed
outcomes, one neighbourhood that reads wrong. **D14 was the precedent**, having
had the same defect fixed on August 22 by turning a feeling into a number on a
page.

**One trigger fired rather than closing.** Staging deferred itself in August on
the reasoning that *"Clarice does not yet hold real user data"*, and a second
person's login makes that false. Still deferred, on costs that have not changed
— but the reasoning is now written down where the next reader can disagree with
it, instead of standing on a fact that had quietly expired.

### What it taught: the dead code was the missing instrument

**`resolve_retrieval_miss` calls itself the strongest deletion candidate of
twelve dark services, and it is the opposite of one.** Nothing populates
`RetrievalMiss.resolved_node`, so a miss is recorded and can never be answered —
and a *resolved* miss is precisely the evidence that search's fifth increment
needs and that D14, the semantic index, is measured against. Its own declaration
names the trigger it is waiting for: *a surface for reviewing misses, which no
plan claims*.

**So a gate and its instrument were both open, in separate documents, each
waiting on the other.** The gate said *not enough evidence yet*; the instrument
said *nothing calls me, consider deleting*. Neither was wrong and nothing
connected them.

**The generalisation is worth more than the case.** This project is careful
about declaring dark code and careful about naming triggers, and does both in
different files — so **a deferral and the thing that would resolve it can each
be correctly recorded and never meet.** The sweep is what makes them meet, and
nothing schedules a sweep.

## The scoreboard runs out of impossible things — August 22–23, 2026, `osprey`

Twenty-one commits, verified in production at 02:58 on August 23
(`DEPLOYED-2026-08-23/0258`, image `clarice:391d7dff2003`), with five
migrations: `accounts` 0017, `lists` 0045 and 0046, `mind` 0026 and 0027.
**Four journeys moved, and after it the *impossible* pile held nothing that was
waiting on code.**

**What shipped**

- **S12, out of impossible — a project explains itself when it ends.** Planned
  against met, week by week across the project's life and judged at each week's
  end so that a past week's figure cannot move afterwards. What was
  deliberately set aside is counted apart from what was simply missed. The
  notes that became work here and the decisions taken on them are reached
  through **recorded provenance rather than retrieval** — the distinction the
  temporal substrate had just paid for. And `Project.learned`, the one thing no
  row can answer, kept for the next project's brief.
- **S1, out of impossible — invitation links.** The approval happens **when the
  link is minted**, so there is a person in the story and nobody left in a
  loop. `is_active` and `email_confirmed_at` come apart exactly as S1 had
  predicted they would a week earlier.
- **S16 and S10 gained their missing halves.** The brief now reaches notes,
  decisions and sources, each saying why it is there; and it carries the
  abandonment condition it had until then been **silently dropping**.
- **Five of the substrate's last decisions** — D5, D14, D15, D16 and D17. Each
  is kept with what it turned out to be in
  [`temporal-substrate-plan.md`](temporal-substrate-plan.md), and the
  narratives are in this file under *The temporal substrate*.

**What it taught: a green unit suite can hide a production 500, and the browser
suite is where it surfaces.** Run before the deploy, it found a fault live since
Release D — `complete_project` locked a row outside a transaction, and **every
unit test passed because `TestCase` supplied the transaction the code was
missing**. The test environment was standing in for the code. This is the
concrete case behind `CLAUDE.md`'s rule about anchoring an insertion above a
decorator rather than on the `def` line, and behind running the browser suite
when routing or session handling moves.

**One claim in its tag is wrong and is corrected here rather than in the tag.**
It closes with *"all nineteen substrate decisions closed."* Eighteen were.
**D18 — whether a neighbourhood is clock-bounded or episode-bounded — was open
then and is open now**: `clarice/recall.py` still carries
`DEFAULT_WINDOW = timedelta(hours=6)`, the ±6h proxy the decision exists to
question. The plan's own summary line said the same thing and was corrected on
August 26.

## A second factor on the admin — August 19–23, 2026, `petrel`

Verified in production at 15:10 on August 23 (`DEPLOYED-2026-08-23/1510`, image
`clarice:c518bdd29efa`). [`admin-mfa-plan.md`](admin-mfa-plan.md) entire, across
two deploys: increments 1 and 2 on August 19 (`66c1bfd`, live with `osprey`),
then 3 and 4 on the 23rd. `/admin/` now requires a verified device as well as a
staff account, and `/api/v1/login` refuses an account that has one. **The last
two shipped in a single deploy**, because splitting them leaves a window in
which a password alone still mints a ninety-day token.

**Enrol before enforcing** was the ordering that mattered, and the plan led with
it: getting it backwards means deploying a lock and then discovering you are
outside it.

### What shaped it, which was not TOTP

TOTP is a solved problem. **Four interactions in this codebase are not**, and
they decided the design.

- **`/api/v1/login` is a password-only path to a 90-day token, and it starts no
  session — so every session-based gate misses it.** A second factor on the web
  form and on `/admin/` while that endpoint stands is a second factor on one of
  two doors. The obvious fix — a `totp` field and a third box on the Connect
  screen — was **unavailable**, because `assembleRelease` produces nothing
  installable until the keystore in
  [`android-release-signing-plan.md`](android-release-signing-plan.md) exists
  and that is Vince's to generate by hand. So the endpoint **refuses** accounts
  with a confirmed device instead, which costs exactly what it was built to buy
  and is reversible the day a signed release can carry the field.
- **The export would not have leaked the seed, but only by accident.**
  `accounts/export.py` enumerates `OWNED_APPS`, and `otp_totp` and `otp_static`
  are simply not in it — the right outcome by the wrong mechanism, holding only
  until somebody adds the labels while tidying. The same lesson as D12, in the
  opposite direction: **a promise that is not checkable is not true**, so it got
  a test.
- **Erasure works by cascade and must keep working by cascade.** Nothing to
  build; `django-otp`'s devices carry an ordinary `CASCADE`. It got a test
  anyway, because *the cascade covers it* is a claim about a dependency's field
  definition, which is the kind of claim that is true until a major version.
- **`django-axes` cannot see a wrong six-digit code.** Axes counts failures at
  `authenticate()`, and verifying a token is a second step against an
  already-authenticated session — so the five-attempt lockout **does not apply
  to the second factor at all**. `django-otp`'s own `ThrottlingMixin` covers it,
  confirmed on 1.7.0 rather than assumed: `verify_is_allowed` refuses until
  `factor × 2^(n-1)` seconds have passed, and it is on by default.

**And two smaller ones.** unfold overrides admin templates, so `OTPAdminSite`'s
bundled login form would render into a template that does not know about it —
avoided by verifying on a project-owned view instead. And the enrolment QR is a
`data:` URI, which `img-src 'self' data:` already permits, so a new control did
not have to force open the CSP that §1.2 was about to promote to enforcing.

### The design, in one line

**Verification is a project-owned view and the admin only asks a question.**
`OTPMiddleware` supplies `is_verified()`, an `AdminSite` subclass requires it
alongside the staff check, and `/accounts/verify/` collects the code in this
application's own templates. The alternative was fewer lines and bought a
template collision plus a login screen that looked like neither core.

**Two things the plan did not anticipate, both found by running it.**
`django-otp`'s own README recipe — `admin.site.__class__ = VerifiedAdminSite` —
**does not work**: `admin.site` is a lazy proxy, so the assignment replaces the
proxy's class rather than the site's. `AdminConfig.default_site` is the real
hook, and it is not enough either, because unfold's `DefaultAppConfig.ready()`
assigns `admin.site` outright and discards it. `BasicAppConfig` is unfold's own
answer. The plan's §2.5 said unfold overrides admin templates; **it also
overrides the site.**

**And one thing found in a production log an hour after the first deploy**:
five successful logins at `/admin/login/` in a row. `AdminSite.login` redirects
to the index only when `has_permission()`, which is exactly what is false
without a second factor — so logging in bounced back to the login form and
**read as a wrong password**. `/accounts/verify/` existed and nothing pointed at
it. *Building the page is not wiring it up*, which is a rule this codebase
already had: the change meant to close a seam opened one.

**Enrolment was checked against production rather than taken on report**, and
that caught the first attempt landing on the wrong account — `Vrbeall01`, in
daily use and not staff, while `vince-admin` had none. Deploying then would
have been the lockout the plan's ordering exists to prevent.

**Its tag's closing line is wrong**: *"the invitation bar is now one item short:
the restore drill has still never been run."* The drill **ran on August 19,
2026 and passed** — [`MIGRATION.md`](../MIGRATION.md) owns that record. What is
true is narrower: a drill certifies the schema it ran against, and that schema
has since moved. The same sentence was live in `roadmap.md` and was struck
there on the same day it was written.

### Break-glass, and the bound it puts on the whole control

A lost phone and lost recovery codes leave one route: `docker exec clarice
./manage.py` on the droplet, deleting the device row. **Written down before
increment 4 shipped rather than after** — [`MIGRATION.md`](../MIGRATION.md)
under *Break-glass: locked out of the admin*, three situations in the order to
try them, because the moment it is needed is the worst moment to work it out.

**Stating it is also stating what this control is worth.** Shell access to the
droplet is equivalent to bypassing the second factor. That does not make MFA
pointless — it moves the bar from *knows a password* to *has shell on the host*,
which is an enormous move — but it does mean
[`security-and-resilience-plan.md`](security-and-resilience-plan.md)'s **D5,
what stands in front of port 22, is part of this control's strength** rather
than a neighbouring topic.

### Four refusals, kept because each would otherwise come back

- **Forcing a second factor on ordinary accounts.** Scope is staff, who are the
  accounts with reach beyond their own data. Ordinary accounts get it as an
  option when there are enough users for it to matter — and that needs a
  recovery path designed for people who are not Vince.
- **SMS.** SIM-swap is real and cheap, and it would need a new outbound provider
  on a host that cannot even reach SMTP.
- **Email.** The mailbox is a password-reset target, so it is substantially the
  same factor wearing a hat.
- **A remember-this-device cookie**, at this scale: a second credential with its
  own lifetime and its own theft story, to save one person a code.

## Security hardening and Django 5.2.17 — August 26, 2026, no codename

Twenty-one commits, no migrations, verified in production at 19:45
(`DEPLOYED-2026-08-26/1945`, image `clarice:f6de194e5a72`). The first deploy
since August 23 and the largest batch in a while: the note page's manual
linking, **five of the seven ranked items** in
[`security-and-resilience-plan.md`](security-and-resilience-plan.md), Django
5.2.17, and a great deal of corrected corpus.

**Three of its changes answer for themselves from outside**, which is why the
verification is worth keeping: `Server: nginx` with no version, so
`server_tokens` is off; `Strict-Transport-Security: max-age=31536000;
includeSubDomains`; and a `Content-Security-Policy` header that is no longer
Report-Only, nonce intact. `migrate --check` reported nothing pending and
`/healthz` returned 200.

**Two things had never met production traffic before that night** and are what
to watch: the enforcing CSP, which can break a page for a person rather than
for a scanner, and the two new nginx rate limits on `/api/v1/capture` and
`/admin/`.

**This one has no bird, and that is the rule rather than an omission.** It is
infrastructure and hygiene, which
[`architecture-trajectory.md`](architecture-trajectory.md) §6 already says is
not numbered as a release. The rule that decides it was written down on August
26 — see *Release conventions* at the end of this file.

## The day you can actually use — August 20, 2026, `moorhen`

Release M, in one deployment and verified in production on August 20 at 20:30
(`DEPLOYED-2026-08-20/2030`, image `clarice:b8591ee507f0`, all six migrations
applied and none pending). v3's *Usable* release: **the day stopped being a
list you fill in by hand.**

**What shipped**

- **The day drafts itself, and never pins.** `draft_day` proposes what has a
  claim on today, bounded by `typical_day_for`, and one **Plan my day** accepts
  the set. **No capacity, no proposal** — `typical_day_for` answers `None`
  below a five-day sample floor rather than zero, because *"no evidence yet"*
  and *"you have room"* call for opposite responses.
- **A brief that reports change, not state** — what was chosen yesterday and
  did not happen, what is inside its lead time, what has gone quiet. Everything
  in it is deliberately something the Day page does not already show, which is
  what stops it becoming the dashboard the destination refuses.
- **The closing ritual** — the day asked for while it is still true, with an
  honest denominator, plus an evening nudge that is **off by default**.
- **A calendar, and a bills month.** `/app/day/:date` had no UI entry point at
  all; reaching a day twelve weeks back meant clicking *the week before* twelve
  times. Bills are a **sidecar on `Item`, not a primitive** — §4 said no — and
  the month totals each currency apart, never as one number.
- **Task priority**, three values with no *medium*, and **`lead_days`**, so a
  thing can be said to be coming before it is due.
- **Quarterly and annual recurrence**, and **moving a misfiled task**.
- **The review block** — over-committed told from under-delivered, a finished
  week read under the sentence it was given, four verdicts movable in a day.
- **S2's other half**: the phone got the two verbs the browser's day had, which
  needed **no backend work at all** — every endpoint was already token-reachable
  and the client functions were already there.
- **`clarice/scheduled_mail.py`**, lifted out of `send_due_digest` as a pure
  refactor before a second sender could copy it, proved by that command's 32
  unchanged tests.

**What it taught**

- **"Can this be reached" is not "would anyone find it."** The calendar shipped
  behind one link on the Day page and bills behind one link on the calendar, and
  the first thing Vince said after the deploy was that he could not find either
  — or the brief. The arbiter already existed: a test named *"offers every
  surface of the task core"* enumerating `ViewNav`. **A surface reachable only
  from another surface is the un-switched-on seam wearing a nicer coat**, which
  is the fifth time that shape has turned up in a fortnight.
- **Published legal text is code.** The evening nudge made the privacy policy's
  *"the one recurring message is the daily summary"* false, and the fix had to
  ship in the same commit as the sender. Two tests hold it now, one asserting
  the old sentence is **gone**.
- **A token-surface test is a design question, not a chore.**
  `test_api_auth_surface` caught both new endpoints, and the honest answers
  differed: draft-accept stayed token-reachable because it is the same act as
  pinning and sits beside it; the calendar became session-only because it is a
  new surface the phone does not have.
- **A widened enum wants its arithmetic widened with it.** Quarterly and annual
  recurrence needed `_nth_occurrence_after` to carry a months multiplier, and
  the first test written for the annual case asserted a rule the domain does not
  have — that a 29 February commitment skips to the next leap year. The honest
  schedule is *the 29th, or the 28th when there is no 29th.*

**Verified before the deploy**, all at `b8591ee`: `makemigrations --check`
clean, both Python suites, 392 frontend tests with a clean `tsc --noEmit`, and
34 browser tests against a freshly built bundle. **Verified after**: site 200,
the running image tagged with the commit, all six migrations applied with none
pending, the amended privacy policy live, and all four cron entries present
including `clarice-closing-nudge`.

**Verified afterwards in a browser, which had not been done at all**: on
August 20, against seeded data, the brief rendered its three sections, the draft
proposed two of six and **Plan my day** accepted them in one click, the closing
summary picked up its denominator, the calendar showed per-day counts and
written marks across the month, and the bills month totalled 1264.99 USD and
40.00 GBP **apart**. That pass is the entry below in `roadmap.md`; it found two
copy defects and no broken page.

## The temporal substrate — August 20–22, 2026, `nightjar`

Thirty-one commits over two days, verified in production at 01:01 on August 22
(`DEPLOYED-2026-08-22/0101`, image `clarice:ec2c4cb7e084`, `mind` 0021–0025
applied with none pending). **The knowledge core had no way to open a note; it
came out of this with a face and a memory.**

The spec was [`temporal-substrate-plan.md`](temporal-substrate-plan.md), now a
stub. Its five tracks all closed.

**What shipped**

- **Track A — the time axis.** The one append-only log learned a *life*
  vocabulary beside its note one; `lists`, `daily` and `review` emit through
  `clarice/life_log.py`; `backfill_life_log` reconstructed what carried its own
  recorded timestamp and invented nothing; and `around()` and `since()` read
  it. **All twenty-one existing reads were adjacency in meaning**; these are
  adjacency in time and in provenance.
- **Track B — retrieval that knows why it is being asked.** Six modes named,
  the indexes demoted from final judges to candidate generators, eligibility
  per mode, and every result saying why it appeared. Measured per mode.
- **Track C — structured observations**, proposed from journal prose by rules
  rather than a model, and read with the denominator stated.
- **Track D — intake.** Session-aware budgeting *before* any dump surface
  existed, then the dump, then attachments, then orientation.
- **Track E — the reading surfaces**: the node page, the correction surface,
  the person page, the question box.

**Thirteen of nineteen decisions answered**, four of them taken by Claude at
Vince's direction rather than by Vince and marked as such in the plan. Six
survive the stub because they are about live behaviour rather than about work.

**What it taught**

- **A slice nothing calls is not closed**, which became a principle
  (`principles.md`, *Deliver vertical slices*) rather than a lesson. Twelve
  services in `src/mind/` had no production caller and **eleven were the undo
  half of a live pair** — `capture` had seven callers and `revise`,
  `delete_node`, `archive_node` had none. So the inventory was never twelve
  pieces of dead code: **it was one missing surface, listed eleven times**, and
  deleting them would have deleted half of eleven features immediately before
  building the page that needed them.
- **The order of an increment can be the whole safety of it.** Track D ships
  budgeting before the dump surface, because the first dump is the one that
  teaches somebody to skim past the review surface and that is not
  recoverable.
- **A refusal is a deliverable.** Increment 22 was declined in the morning and
  built in the evening, and the refusal was right both times — on nothing
  beneath it the question box is `search_ranked` with a prompt in front,
  failing *silently*, which is the property that made the thin version worth
  refusing. D7 closed the same way: not the cost of the fix but the shape of
  the failure, since server-side fetching on a one-host deployment risks
  credential disclosure on the machine holding every note.
- **A test caught a non-negotiable refusal being violated in code.** Track C's
  *other recorded mornings* was implemented as mornings whose previous day was
  absent from the drinking set — which admits every morning after a night
  nobody wrote in. **That is the sobriety inference itself**, and the test that
  caught it did so on its first run.
- **Four defects were fixed in a table that refuses `UPDATE` and `DELETE`
  before any of them could fire**, and the reason none had is not that they
  were mild: production's task core was too thin to reach them. The same
  emptiness that makes the substrate hard to demonstrate is what kept the
  permanent record clean.
- **Three project-wide guards were added and each has already caught
  something**: emitter idempotency, restore-drill coverage, and a dark-service
  contract that failed the moment `revise` gained a caller.
- **The browser found what green tests could not** — three times. A page
  listing its own capture under *what else was going on*; the log's vocabulary
  (`facet_confirmed`, `task_completed`) put in front of a person; and thirteen
  identical rows reading *a note that is no longer shown*.

**The thirteen decisions this answered**, with the reasoning each was
settled on, are kept below rather than in the stub — they are the record
of what was decided, which is exactly what a history file is for.

1. ~~**D1. Which direction does the seam run?**~~ **Answered August 20, 2026:
   a module in `clarice/` belonging to neither core** —
   [`clarice/life_log.py`](../src/clarice/life_log.py), the placement
   `clarice/search.py` has and `clarice/scheduled_mail.py` took a week later.
   **The payoff is an import that does not happen:** `lists`, `daily` and
   `review` name none of `mind`, `ActivityEvent` or `EventType`, because the
   vocabulary is re-exported there.

   **The cycle argument does not apply and was not the reason.** Both
   directions already exist — `lists/projects.py` imports `mind.queries` at
   module scope, and `mind` imports `lists` in three places. What decided it is
   that three apps creating rows would restate the emit rules three times, and
   two definitions of one thing is how they come to disagree.

   **A second answer travelled with it: both or neither.** `record` is called
   inside the caller's own atomic block and raises rather than swallowing, so a
   completion whose event could not be written is not a completion. Swallowing
   would make the log a sample and leave every read over it with a silent hole
   — the failure `MAINTENANCE_RAN` exists one layer up to prevent. This needed
   `complete_item` to become atomic, which it was not: two saves and a spawn,
   each committing alone.

2. ~~**D2. How far back does backfill reach, and how is a reconstructed event
   marked?**~~ **Answered August 20, 2026 — and taken by Claude at Vince's
   direction rather than by Vince, which is worth saying because this list is
   his.**

   **How far back: as far as the data goes, and no date cutoff.** The limit is
   not age, it is whether a timestamp exists; a horizon would discard real
   records to satisfy a number nobody chose.

   **The mark: `ActivityEvent.origin`, a column**, copying `Facet.origin`'s
   split as this entry suggested. **A column rather than a payload key**,
   because every read will want to label or exclude reconstructions and a JSONB
   lookup with no index is not what that should cost — and in an append-only
   table the cheap choice is the unfixable one. Distinct from `InferenceOrigin`
   and deliberately not reusing it: that one asks whether a thing was stated or
   inferred, which is about *content*. This is about *witness*.

   **The guess-nothing instinct held.** Defect 2's misdated routine records
   were left alone rather than reconstructed, and this follows it: four of the
   ten events have no honest source and are simply absent. **Under-recording is
   the safe direction** — a log that says less than happened can be added to,
   and one that says more cannot be corrected.

3. ~~**D3. Payload snapshot, or foreign key only?**~~ **Answered for slice 1
   only, August 20, 2026: a foreign key where one exists, and the payload for
   what has none.** The week's Monday is the single payload key slice 1 has,
   because a week is neither a task nor a day's entry — and a subject column
   invented for one cadence is a column the monthly and quarterly horizons
   would not fit.

   **Nothing snapshots a subject it could join to.** `WeeklyOutcome` already
   keeps its own text and its project's title; `DailyFocus.task_text` already
   snapshots the one case where a snapshot is the point. A third copy in an
   append-only row is a copy that can never be corrected, which is the one
   place a wrong value would outlive its fix. **Still open for later slices**,
   where an event may genuinely have no row behind it.

4. **D4. What makes a later event *bear on* an earlier node?** The rule
   deciding whether *what developed afterward* is a recollection or a list of
   everything since.

   ~~**An answer shape registered August 21**~~ — **answered and shipped
   August 21, 2026** (`c2d5b72`). The shape below is what was built, unchanged: the one honest development chain exists as fact —
   `Node` → actionable facet → `Item` → that task's later life events — and
   confirmed mentions and edges carry dates too. *Development along recorded
   provenance* is answerable without inventing anything; it is the
   similarity-based "bears on" that is not. Answered this way, `since()`
   ships narrow and honest, and increment 5's "stopping at four" outcome is
   only for the wide version.

   **What shipped adds one refusal the shape did not name**: edges reach
   forward and never backward. An edge drawn *toward* a note is the other
   note's development, and following it would quietly make *"what developed
   from X"* and *"what has since mentioned X"* the same question — the slide
   this decision exists to stop, one size smaller.

6. ~~**D6. Are roles new `FacetKind` values, or one kind with typed data?**~~
   **Answered August 21, 2026 — values, and `facet_one_live_per_kind` decided
   it.** `unique(node, kind)` over live facets means one kind holds one role,
   and roles are multi-valued by definition. The question below stands as
   asked; the answer is that it was not a judgement call in the end.

   Original text:
   `FacetKind` says a new kind should be a value rather than a table — but
   fourteen kinds each with their own validation is a different proposition from
   three, and they are multi-valued by design. `design-concept.md` owns the
   Attention Policy this feeds.

7. ~~**D7. Is URL intake worth reopening SSRF surface?**~~ **Answered August
   21, 2026: not yet, and the answer is a refusal with a trigger rather than a
   deferral.**

   **What tips it is the shape of the failure, not the cost of the fix.** An
   allowlist or an egress proxy is affordable. But server-side fetching on a
   one-host deployment means the application makes outbound requests to
   addresses a person supplies, and the interesting SSRF targets are on that
   host and on DigitalOcean's link-local metadata endpoint. A mistake there is
   not a bad row — it is credential disclosure, on the machine that also holds
   every note.

   **And the cheap half is most of the value.** Storing a URL as text, captured
   and searchable, is what makes *"that recipe I saved"* findable at all;
   fetching adds the body. `/mind/` already accepts a URL as content today and
   the Android share target already sends one, so nothing is missing that a
   person would notice as absent.

   **The trigger, so this can fire:** when Clarice has more than one human user,
   or when a recipe URL somebody saved is recorded as a retrieval miss because
   its text was not searchable. The first is a real change in the threat model;
   the second is evidence from the one instrument this project trusts. Either
   makes an egress proxy worth its weight — and `MissContext.SEARCH` already
   records the second without anything being built.

8. ~~**D8. What are the four metrics?**~~ **Answered August 21, 2026 — there
   are two.** Lookup and Recollection have honest signals; Planning has none
   yet and Resurfacing cannot have one. Saying so in `/numbers/` is the
   increment rather than a gap in it.

   Original text: Lookup, planning, recollection and
   resurfacing fail differently, and **a missed resurfacing leaves no trace at
   all.** If one of the four has no honest signal, say so rather than grading it
   by proxy.

   **One source registered August 21:** recollection can borrow the search
   page's `RetrievalMiss` button verbatim — *"there was more to that
   morning"* — giving one of the four modes an honest miss signal through a
   mechanism the codebase already trusts.

9. ~~**D9. Where do attachment bytes live?**~~ **Answered August 21, 2026:
   they are a row.** The question named its own deciding consideration — export
   and deletion ship every owned *row*, so a file that is not one breaks a
   promise that currently holds. As a row, export, purge and the restore drill
   all hold without knowing files exist, and `/privacy/`'s *three companies,
   each doing one job* stays true.

   **Postgres is not a blob store and that is the cost**, accepted at this
   scale — one person, a personal corpus, a managed backed-up database. The
   trigger for revisiting is `MAX_ATTACHMENT_BYTES` starting to hurt.

10. ~~**D10. Email intake — scope it, or defer with a trigger?**~~ **Answered
    August 21, 2026: deferred, with a trigger that can fire.**

    **The mail transport already runs in one direction only.** Resend sends;
    nothing receives. Inbound means a webhook endpoint with no session behind
    it, address-to-account mapping, spoofing (anybody can put your address in a
    `From:` header), attachment handling, and a spam surface — on an
    unauthenticated route, which is the one class of endpoint this project
    throttles by name.

    **What makes it a deferral rather than a refusal** is that unlike D7 the
    hazard is contained: a bad inbound message writes a note, and a note can be
    deleted. It is real work rather than a real risk.

    **The trigger:** when a capture arrives by being forwarded somewhere else
    first — a note whose content is an email somebody re-typed or pasted — or
    when the phone is not the fastest route in for material that already lives
    in a mailbox. Both are observable in the corpus rather than in an opinion,
    which is what `principles.md` means by a trigger that can fire.

11. ~~**D11. What shape is a per-occasion proposal budget?**~~ **Answered
    August 20, 2026: two budgets, and no backlog.** A *processing* budget
    bounding what is materialized at all, and an *attention* budget bounding
    what is shown now — see Part 4's flow. **The slow-release option was
    rejected on principle rather than on cost**: a queue dribbling out hundreds
    of findings is the Second Mind inbox this design refuses. And the scoping
    correction is the load-bearing half — **the budget covers every
    attention-producing mechanism**, including the synchronous commitment
    parser, not only the five connection detectors. The per-capture caps stay;
    they are correct for a capture.

12. ~~**D12. Is a dump a container node?**~~ **Answered August 20, 2026: no —
    a `CaptureSession` record.** `NodeSource.THREAD` is a semantic conclusion
    that participates in the graph; a dump is provenance. The session earns its
    own model under §4 because it has a life cycle and behaviour nodes do not,
    and a shared timestamp cannot carry duration, completion, a budget, prompts
    or processing state. Each node gets an optional session reference and no
    graph edges.

13. ~~**D13. Is voice intake in scope?**~~ **Answered August 20, 2026: not in
    the first slice, and the path is preserved.** Typed dumping validates the
    interaction first. Audio needs attachment storage, export, deletion and a
    privacy disclosure before it needs transcription — and **storing audio
    without searchable text does not deliver the assembly a dump is for.**
    Transcription remains an ML-policy question for `design-concept.md`, not an
    engineering one.

19. ~~**D19. Does recollection anchor on instants or subjects?**~~
    **Answered and shipped August 21, 2026** (`b15b77c`): **both, and the
    subject read is built on the instant one.** `around()` stays the
    primitive; `clarice.recall.context_of` unions it over the subject's own
    moments — its log events plus those of any task it grew into, which is
    `since()`'s provenance chain reaching back to include the capture.

    **The resolution the entry warned about turned out to be overlap.** Two
    moments twenty minutes apart produce nearly identical neighbourhoods, and
    a caller unioning them naively either shows everything twice or loses
    which moment each belongs to — both silent. So moments within a window of
    each other are **one occasion**, an occasion keeps its moments because a
    merged one has no single timestamp, and an event near two occasions is
    reported at the earlier one: the first time something turned up beside a
    subject is the fact worth keeping.

    **The caller it named was the note page**, which had anchored on
    `captured_at` because that was the one timestamp to hand — so a note
    turned into a task two months later had a second moment nothing could
    see.

## What this refuses

- **An event bus, domain events, or Django signals.** Facts, not derivations.
- **Moving `Item` into `Node`.** The inversion is conceptual;
  `architecture-trajectory.md` §7 is untouched.
- **Asking what a thing is at capture.** Roles are proposed and corrigible.
  Anything else rebuilds the `Capture → Idea → Task` pipeline Heron deleted,
  with fourteen new nouns instead of three.
- **Exclusive folders.** Roles are multi-valued; a recipe from Mum for Christmas
  is three roles and not a filing conflict.
- **One final ranking across modes**, and one blended metric over them.
- **A stored attention tier.** It is derived at read time on purpose, because "a
  stored tier is a second source of truth for something that changes with every
  capture."
- **Deciding the Attention Policy.** Part 2 proposes to `design-concept.md`.
- **Causal language over observations**, and reading an unrecorded night as a
  sober one.
- **Overhauling unified search.** It is the correct foundation; this sits above
  it.
- **A brain dump surface before session-aware budgeting exists.** The order is
  the whole safety of the feature.
- **Splitting a submission silently.** A fragment is what the person submitted.
  Multiline paste gets a preview and a question, never a guess.
- **A proposal backlog.** No queue slowly releasing session findings — that is
  the inbox this design refuses, on a timer.
- **A dump as a container node.** Provenance is a session record, not graph
  content.
- **Inventing history.** No event without a recorded timestamp on the source row.
- **A second event log.** `ActivityEvent` gains a vocabulary, not a sibling.
- **A generated answer.** Ask-your-memory returns passages that cite
  themselves, ranked and mode-aware; composing prose over them is an
  ML-policy question for `design-concept.md`, and nothing in this plan opens
  it. *Nothing generated anywhere* is a property this product has on purpose.

## A correction this brief owed `product-stories.md`, since made

That file's three-loop table said *"The second brain is not a fourth loop. It is
the memory of the third one."* Vince's call, August 20, 2026: **that was wrong**
— memory is the substrate, and the three loops are tempos of reading and writing
it. **Corrected in `product-stories.md` the same day**, which owns the fact.

## Where the facts live

Whether this is active, deferred or open is [`roadmap.md`](roadmap.md)'s. What
order the work goes in and toward what is
[`clarice-v3-plan.md`](clarice-v3-plan.md)'s. What shipped and how it was
verified is [`roadmap-history.md`](roadmap-history.md)'s. **The Attention
Policy, salience, and what each core owns are `design-concept.md`'s**, in Second
Mind's own `docs/` — Part 2 proposes to it and does not restate it. Literal
retrieval is [`search-plan.md`](search-plan.md)'s. How the product scores is
[`product-stories.md`](product-stories.md)'s.

**Verified before the deploy**, all at `ec2c4cb`: 1676 Django tests OK, 1018
passed and 6 xfailed under pytest, `makemigrations --check` clean. **Verified
after**: site 200, the running image tagged with the commit, all five
migrations applied with none pending, and every new route answering.

**What it leaves open, and none of it is a shortfall.** Six decisions, of which
~~**D16 is the one with a clock running**~~ — **answered August 22, see below.**
`product-stories.md` also needs re-scoring against what now exists; Unify's own
acceptance was *"S13 and S14 reach works"* and that was never checked.

### D16 — whose clock is a morning, and the answer that found a bug

**Answered August 22, 2026: the person's clock**, which required no new policy.
`per-user-time-zones-plan.md` decided this for the task core on August 1 and
`User.time_zone` has been the single place it is stored ever since. There was
never a second candidate; the knowledge core had simply never inherited the
first. The rule is now [`clarice/clocks.py`](../src/clarice/clocks.py).

**The part that needed deciding was not *which zone* but *whose*.**
`timezone.localdate()` reads the zone the middleware activated for **this
request** — the viewer's. That is right for *today*, where the viewer is the
subject, and wrong for the question the knowledge core keeps asking: *which day
was this note on?* That is a property of the record. `localdate` answers it
three different ways — the reader's zone in a request, `settings.TIME_ZONE` in a
management command, the owner's only by coincidence — so `day_for(owner,
instant)` takes the owner and the instant and nothing else.

**The entry's own symptom was wrong, and finding that out is what found the
real one.** Both this file and `roadmap.md` said *every observation Track C
records is stamped UTC*. It is not: Track C keys entirely on `DailyEntry.date`,
which `daily/api_v1.py::_today_for_request` has set from `timezone.localdate()`
since the day it was written. **The nights were always the person's nights.**
Nothing was accumulating against an undecided clock there, and the urgency the
decision was carrying was misplaced.

**The clock was running in S14 instead, and it had already cost something.**
`recall.what_surrounded` — *the day, the project and the week around one note*,
the whole of S14 — asked for the day with `node.captured_at.date()`, the **UTC**
date. For anyone west of UTC an ordinary evening note is stamped the next day,
so it asked for **tomorrow's** `DailyEntry`, found nothing, and rendered an
empty section. **No exception and no wrong number: a feature that quietly did
less than it claimed**, through a release and a verdict of *works* scored the
day before.

**The week join was the worse half**, because it does not come back empty. Weeks
start Monday, so a Sunday evening in New York is Monday in UTC — the note joined
to the **following** week and displayed that week's intention as the one it was
written under. A confidently wrong answer where the day gave a blank.

**Why the tests did not catch it, which is the transferable part.** Every test
of `what_surrounded` captured its notes at UTC midday, where the two clocks
agree. A fixture that picks a convenient hour is a fixture that has quietly
chosen the passing case — the same shape as `test_executable_file_modes`
reading the index rather than the filesystem, because both machines this is
built on lie about the mode.

**So the guard is a test rather than a note.**
`clarice/tests/test_a_day_names_its_clock.py` walks the AST of both cores and
fails on any `.date()` taken from an instant that did not name a zone first,
with an allowlist that itself fails if an entry stops being needed.
`accounts/middleware.py` already carries the sentence this is built on — *a note
telling the next person to remember something is not a mechanism* — written
after six token endpoints each forgot to activate the owner's zone despite a
docstring asking them to. This is the same mistake one core over.

**What else it swept up.** Four other sites took the UTC date: Track C's
ninety-day reflection window (a denominator this module exists to state
honestly, off by a boundary day), the decisions-due read from the day before,
the digest-staleness cutoff in `health.py`, and `scheduled_mail.py`'s own
three-line zone resolution — which was the *original* per-user day boundary,
reinvented nowhere else and now the extracted `clocks.zone_for`. The health
check is the one deliberate exception: its skew is **absorbed** with an extra
day of slack rather than removed, because it is an alerting path where a false
alarm is the expensive failure. It says so in place and in the allowlist.

### D16, part two — the same defect in the task core, and this one was posting

**Found by asking whether the rule held anywhere else**, the same afternoon.
The AST guard deliberately does not scan the task core, because there
`timezone.localdate()` is correct: the viewer *is* the subject. **Except where
there is no viewer.**

`scheduled_mail.deliver_once_a_day` worked out each recipient's local day and
passed it down, and that is not enough. **The reads underneath convert their own
timestamps.** `review.reads._local_date` calls `timezone.localtime`, which reads
the *active* zone — and a management command has no middleware, so every
recipient was composed in `settings.TIME_ZONE` whatever zone they had chosen.
`America/New_York` is both the setting and the default, so anybody who had never
changed theirs was right by coincidence, which is how it stayed hidden.

**For a recipient west of the setting it was posting a false number.**
`send_closing_nudge` asks `planned_in_week` what was finished today; a Los
Angeles task finished at 21:00 is 00:00 in New York, dated **tomorrow**, and
fails *finished on or before today*. The mail read:

> You finished 0 of 2.

an hour after they finished one. **Reproduced before it was fixed**, and the
test asserting it is `TheNudgeCountsInTheRecipientsClockTest`.

**Why the existing nine tests missed it, which is the same sentence twice in one
day.** The recipient was on the default zone and finished at 15:00 — a zone that
matches the setting and an hour where every clock agrees. Exactly the pair that
let `what_surrounded` ship. **A fixture that picks a convenient hour has quietly
chosen the passing case**, and that is now the thing to distrust first when a
suite is green over a clock.

**Fixed at the seam rather than at the reads**, which is a move this codebase
has already made once: `accounts.auth._resolve_scoped_token` activates the
owner's zone where the owner first becomes known, written after six token
endpoints each forgot to despite a docstring asking them to. The mailer now
composes inside `timezone.override(clocks.zone_for(user))` — `override` and not
the middleware's activate/deactivate pair, because this runs in a **loop** and
`deactivate` clears where `override` restores. One recipient must not be able to
change the zone the next one is composed in.

**The digest shared the exposure and had no test at all** —
`deliver_once_a_day` was only ever exercised through its two commands. It has
its own now, at the mailer level where the defect actually lived, so a third
scheduled message inherits the guarantee instead of the bug.

### D5 — the log can answer absence, and it needed no new row

**Answered August 22, 2026: yes.** The question was whether *"since then,
nothing has been recorded"* is honest, given the log can only prove it was
looking if something proves it. **The log's own other events are that proof.**

**`MAINTENANCE_RAN` is the precedent and is also the contrast.** A machine had
to be given a heartbeat because a pass that finds nothing leaves no other trace
at all. **A person leaves traces constantly** — every completion, every capture,
every confirmation — so the evidence already existed, and adding a heartbeat
beside it would have been a row a read could have produced. Part 1 forbids
exactly that, and this is the case where the rule paid.

`recall.attendance_between` counts the days in a window the log holds anything
for, excluding the subject's own events so the answer is evidence rather than a
tautology. The note page now distinguishes two sentences that had been one:

> you were recording on 14 of the 62 days since

> nothing else was recorded either, on any of those 62 days — so this is a gap
> in the log rather than a fact about the note

**A note that went nowhere while you were here every week is a finding. One that
went nowhere while the log holds nothing is not.** They had rendered identically.

**Third axis, same discipline, and the shape is now settled.** Track C counts
`nights_not_recorded`; D17 separates a silent year from one before the record;
this separates *nothing came of it* from *nobody was here*. And like the other
two it rests on D16 — *days you were recording* is a count of calendar days.

### D15 — the loop that had every piece except somebody saying something

**Answered August 22, 2026: wire it, into the mode** — which is both of D15's
right options at once, and was not available until that morning. **D15 named
Resurfacing as the natural home while Resurfacing was a `NotImplementedError`.**
D17 built it, and a mode with a page is a caller.

**What was dark.** `mark_reviewed` writes a `REVIEWED` event, `review_state`
folds those into a stretching interval, `is_due_for_review` reads it, and
`attention_tier` has a *review candidate* tier waiting on it. Every piece except
the one where a person says something. Production held two `reviewed` rows, both
owner-scoped from `/mind/review/` and none node-scoped, so `review_state`
returned zero for every node and the schedule had never once run.

**Deleting it was the real alternative and was rejected on the evidence rather
than on sunk cost.** Deriving the schedule from an append-only log instead of a
mutable `next_review` column is the expensive and correct half; and *burying*
stretching six times faster than *keeping* is the difference between a review
surface and a nag. That is designed behaviour with nowhere to happen.

`/mind/this-time-before/` now offers **keep** and **less often**, and notes whose
schedule has come round are a second Resurfacing generator beside the
anniversary — two cues that are different questions: *the date cues this*, and
*you asked to see this again*. **The length floor lifts for the second**, since
the floor exists because nobody asked, and here somebody did.

**Wiring it is safe because it stays opt-in.** `is_due_for_review` returns False
for a node never reviewed — *"a corpus of thousands would otherwise all become
due at once the moment the feature exists."* Nothing changes for anybody until
they answer something.

**And six of its tests passed on their first run**, which `principles.md` asks
to be named rather than enjoyed. Four were refusals that were vacuous because
`POST` was unhandled. One passed because there was only one generator to win.
**And one is the admission**: the review-candidate tier test passed all along,
because `mark_reviewed` has always been callable. Nothing was broken in the
code; the tier was unreachable *in the application*. A green test over a dark
seam is exactly what the seam rule exists to stop being mistaken for working
software.

### The one D15 broke on the way in

**Found in a browser minutes after wiring it, and it is the day's fourth
browser-only finding.** `since()` matches developments on `node=node`, so the
`REVIEWED` event D15 introduced landed under the note page's **"What came of
it"** — the page reported *reviewed* as something the note had grown into.

**It has not.** Saying *keep showing me this* is a decision about attention, not
a development of the thought. `since()` already refuses a shared concept and a
close embedding because *"presenting them as 'what came of this' would be a
similarity score wearing a causal word"*; this is the same slide with a
housekeeping row in place of a score. `NOT_A_DEVELOPMENT` now names it, and a
revision is deliberately not in it — the line is *about the note* against *the
thought moved*, and a rewrite is the thought moving.

**And it had silently eaten D5's sentence**, which is what makes it a defect
rather than a tidy-up. A chain with a `reviewed` row in it is not empty, so
`has_anything` was true for any note somebody had ever answered about — the page
stopped saying whether the log had been looking and started implying something
had come of the note. **Two decisions answered an hour apart, and the second
broke the first**, invisibly, in the direction of claiming more than was true.

### D14 — two of its three options were already closed, and the gate was a feeling

**Answered August 22, 2026, mostly by reading.**

**The API is refused by standing policy**, written in `mind/embeddings.py`
before the question was asked: *"Per the ML policy: self-hosted, deterministic
for a given model version, **no external call**, no per-use cost, nothing
generative."* D14 said this escalates to `design-concept.md` if it is ML policy
rather than deployment. **It is ML policy, and the policy already says no** —
embedding every note through a third party would be the largest change to this
product's privacy posture anyone has proposed.

**A smaller model is the same option cheaper**, not a third one.
`all-MiniLM-L6-v2` is already the small model; torch is what makes the
dependency large, and every self-hosted sentence encoder pulls it in.

**So one live option, and it was decided on August 18** — D4 of
`planning-assistant-plan.md`: installing it in the image *"waits for a corpus
large enough for the detector to have something to say."*

**What was genuinely still open is that the gate was not checkable, and that is
what this fixes.** *Large enough to have something to say* is a feeling; nothing
measured it, nothing reported it, and the deferral could only be revisited by
somebody happening to remember it. It is now **250 live notes**, reported on
`/mind/numbers/` with the distance to it, and stated with its reasoning: below
that the detector produces a demo rather than an accept rate, while the cost —
torch in every image, on every build, across the four the droplet keeps for
rollback — is paid forever. Revisable on purpose, like `DEFAULT_MIN_DORMANCY`'s
548 days. **A number somebody can disagree with is worth more than a sentence
nobody can check.**

**And the readiness line had been telling production to do something
impossible.** `detector_readiness` exists for one purpose — *"the difference
between no connections found and no connections possible"* — and for this
detector it gave a third answer that is neither: **"run manage.py
embed_nodes"**, a command that cannot run in production because the dependency
is deliberately absent. The one line whose job is to say what you are waiting
for was naming an action nobody can take. The same shape as the nginx comment
that claimed a rate cap it did not enforce.

### D17 — the cyclic axis, and the mode that had been refusing since increment 8

**Answered August 22, 2026: yes**, and answering it built `Mode.RESURFACING`
rather than merely deciding about it.

**The refusal it ended was five weeks old and was right.** Track B increment 8
gave five of the six modes their own eligibility rules and left Resurfacing
raising `NotImplementedError`, with the reason stated exactly: it *"needs
context this module does not yet take — outcomes, a period, **a present**."*
Falling back to Lookup's *admit everything* would have been four modes sharing
one contract, which is the state Part 2 exists to end.

**The present turns out to be the date**, which every person already has and
which costs nothing to know. *This time last year* is human temporal cueing at
its cheapest and most reliable, it derives from `occurred_at` alone — so Part
1's *facts, not derivations* holds with no row to write and no backfill to run —
and it needs no ML, no threshold anybody has to defend, no budget and nothing
switched on. That last part is why it could ship while **D14 is still open**: an
anniversary is a recorded fact, not a similarity score.

**It could not have been built before D16.** An anniversary is a claim about a
calendar day, and a calendar day does not exist until somebody says whose clock
it is on. `this_time_before` builds each year's window in the owner's zone;
verified in a browser, where a note written at 19:00 New York — 23:00 UTC, so
*the next day* by the old rule — lands on the day it was written.

**The absence discipline is the design rather than a caveat.** Three states, and
collapsing any two is the mistake: an **anniversary**; a **silent year**, where
you were recording and that day holds nothing; and a year **before the record**,
where you were not recording at all. The last two are indistinguishable in an
empty list and are completely different facts about somebody's life. This is
D5's shape and Track C's *"an unrecorded night is not a sober one"*, one axis
over. The page reads:

> nothing recorded on this day in 2024; you were not recording yet in 2022 and 2021.

**February 29 matches exactly and is never slid** to the 28th or to March 1.
Both are guesses about what somebody meant, and the whole reason this read was
affordable is that it needed none. The years that could not hold the date are
named instead.

**Two things the browser found that the tests had not.**

The page shows a one-word note reading *milk* and the **mode does not**, which
looks like a discrepancy and is the opposite trade taken deliberately. Nothing
here interrupts — somebody opened the page — so it is Lookup's bargain, where
every floor is a way to produce a miss and *milk* is a true thing that happened
that morning. A surface withholding it would be quietly editing somebody's own
day. Now documented and asserted, because it is one edit from becoming the
oversight it resembles.

And **two tests passed only because the calendar agreed with them**: the page
read `timezone.now()` and the fixtures were dated to the real today, so they
would have started failing tomorrow. `?on=` now names the day — which
`principles.md` asks for in these words, *pass dates and times into domain logic
rather than reading the current time inside it*, and which incidentally answers
*what was I doing last Christmas*.

## The week you can plan, and the material you can find — August 19–20, 2026, `lapwing`

Release L, across two deployments and verified in production on August 20 at
11:32 (`DEPLOYED-2026-08-20/1132`, image `clarice:612e23415830`). Two bodies of
work that turned out to be one release: **planning the week, and finding what
you wrote.**

**What shipped**

- **The planning assistant's second version, increments 1–8**
  (`DEPLOYED-2026-08-19/2338`): the weekly intention made reachable, capacity at
  day grain, a project that can say what done looks like and be parked, a
  check-in that opens with what the system believes, outcomes chosen from
  evidence, blockers answered where they are read, the week laid out by day and
  stress-tested, and scenario planning. **Nothing generates anything** — the
  part that feels most like an assistant is `draft_week` with one argument.
- **Unified search, four of five increments.** Generated `tsvector` columns with
  `GinIndex`es on `Item` and `DailyEntry`, `clarice/search.py` holding the one
  definition of how typed text becomes a query, `GET /api/v1/search`, and
  `/mind/search/` answering in three sections from one box.
- **The second factor's machinery**, installed and enforcing nothing. Enrolment
  before enforcement, deliberately inert.
- **Mail no longer waits on reverse DNS**, which had cost a browser-suite
  journey twelve seconds and two wrong diagnoses before anybody measured it.
- **Two test-infrastructure fixes**: a test database name derived from the
  checkout, and a CI check on recorded file modes.

**What it taught**

- **A claim about an absence goes stale the day the tree changes.**
  `roadmap.md` said there was *"no full-text search anywhere in the product —
  zero hits for `SearchVector`, `GinIndex` or `pg_trgm`."* True when written on
  August 13, false on the 14th when the merger brought `src/mind/` in. The
  substance survived — a journal entry was unfindable by any means — but the
  evidence sentence had been wrong for six days.
- **Check for a caller, not for existence.** D3 asked whether
  `RetrievalMiss.resolved_node` should widen to reach a task. It should not:
  **nothing has ever populated it.** `resolve_retrieval_miss` has no caller
  outside its own tests and no reader anywhere — **the fourth un-switched-on
  seam found in a fortnight**, after `/healthz`, the uninvoked detectors and
  `Backends.isSplit`. `CLAUDE.md` already said to check the build configuration
  rather than the branch; this generalises it.
- **A miss cannot be re-interpreted after the fact**, which is why the real
  defect D3 turned up was fixed *before* the deploy rather than after.
  `retrieval_miss_trend` feeds `retirement_gate`'s only condition measurable
  without interpretation, and it meant something exact while the page searched
  notes alone. Putting the same button under three sections made it ambiguous,
  and no later change could have recovered what the ambiguous ones meant.
- **Sectioned, never merged, is a refusal rather than a first version.**
  `SearchRank` compares documents within one set and means nothing across two,
  so a single ordered list would present a number that does not exist as
  relevance — and the failure would be silent.
- **A cleared precondition is not a trigger.** D4 said no to the command
  palette: search existing removes the argument *against* it without supplying
  one *for* it. What the question did turn up is that nothing in the task core
  linked to search at all.
- **Two increments were deliberately not shipped**, and both are the right
  outcome rather than a shortfall: search's fifth, nine deferred fields that
  want real use first, and the planning assistant's ninth, a ranking gated on a
  sample floor a corpus of 41 nodes has not cleared.

**Verified before the deploy**, all at `612e234`: `makemigrations --check`
clean; 1388 Django tests OK; 789 passed and 6 xfailed under pytest; 354 frontend
tests with a clean `tsc --noEmit`; 34 browser tests OK against a freshly built
bundle, run because the app bar was touched. **Verified after**: site 200,
`/mind/search/` answering 302 rather than 404, the running image tagged with the
commit, and all three migrations applied with none pending.

## The planning assistant — August 18–19, 2026, `kestrel`

An evidence-backed proposal inbox rather than a chatbot, in six increments, all
shipped and deployed on August 19 (`DEPLOYED-2026-08-19/1339`). The plan is a
stub; this is what it was and what it taught.

**The finding that shaped the whole thing came before any code.** The first
draft of the plan claimed the project already had "one proposal surface with
five producers" and that the confirmation rules were therefore universal. Vince
corrected it: there were **three** proposal systems with three record types,
three lifecycles, three surfaces, and measurement on one of them. That changed
the work from "add producers" to "build the contract those producers were
supposed to share", and the contract's six fields — producer, cited evidence,
proposed action, confirmation state, fingerprint, measurement — became the
spine of every increment.

**What shipped**

1. **Unresolved questions.** A *view* of the corpus rather than a claim about
   it, so it carries no fingerprint, no review window and no confirm gate — it
   cannot be wrong the way a proposal can, only stale. It reports how long each
   question has been open and which later notes came back to it, and answering
   is an epistemic facet: *"I settled this"* and *"this was never a question"*
   stay distinct because the second is the only correction the question
   heuristic will ever get.
2. **Commitments read out of the journal.** Per sentence, cited at the span,
   idempotent under editing, and confirmed into a real task.
3. **`Project.purpose`**, model to text area.
4. **Project briefs** — what bears on a project, each item carrying the terms
   that selected it, asked for and never pushed.
5. **The weekly review's loose ends** and what arrives before the next one.
6. **Next week drafted** against observed capacity.

**Four decisions, and two of them dissolved their own question.**

- **D1, generated prose: not yet**, with two firing conditions rather than a
  someday. Its useful output was noticing the plan had lumped three sites
  together: explaining one brief item hands over a purpose and a few spans, the
  weekly summary hands over everything written that week and recurs. The site
  that motivated the question fits the ML policy's carve-out worst.
- **D2, does S3 get built: the appetite test was declined rather than taken.**
  `product-stories.md` called S3 the sharpest test of appetite in the set — if
  estimates go unentered the story dies. Capacity now comes from `DailyFocus`
  history, so there are no estimates to go unentered. S3's `Requires` line lost
  `Item.effort` entirely; its verdict did not move, because nothing had been
  built yet, and saying so was the honest re-score.
- **D3, attention budgets: the question was posed wrongly.** Six caps already
  existed. What was broken was the *ordering* — confidence is not comparable
  across detectors (a flat 0.9, a flat 0.55, a computed `shared_count / 8`),
  so the review's five slots were rationed by whichever constants somebody
  picked while accept rate fed into nothing.
- **D4, `sentence-transformers`: tests yes, production no.** Two decisions
  wearing one number. It took **25 permanently skipped tests to zero** without
  changing the image.

**The lesson worth carrying: three silent-nothings in one day, all the same
shape.**

- `reads.loose_ends` filtered `node__owner` and went blind to every
  entry-backed facet — a section that would have looked empty and been trusted.
  Caught by a test written *before* a producer existed to expose it.
- `_table()` in `test_pages.py` found the accept-rate table by heading and, on
  a miss, fell back to the first table on the page. Renaming the heading
  silently redirected two tests to measure the readiness table. Its own
  docstring warned about exactly that failure and then implemented one.
- `material_bearing_on` was called without `source_node_id`, so a question
  counted toward its own document frequencies and the rare-term gate rejected
  every match. Two wrong diagnoses preceded the right one; a probe printing
  what the index actually returned found it in a minute.

Each kept working instead of complaining, and each produced a plausible empty
answer. **A value that degrades gracefully is a value that hides a bug**, and
in a system whose whole output is "here is what I found", finding nothing is
indistinguishable from working correctly.

**Two more things the build corrected in itself.** The journal producer was
written date-first, like capture's — and prose is full of dates that promise
nothing, while the canonical example (*"I still need to ask Maya about the
venue"*) carries none. The trigger became an undertaking, which is what the
plan's own card had said all along. And measurement covering only detectors had
left `retirement_gate` computing a worst accept rate from a population that
excluded the commitment parsers, so a parser accepting nothing could not lower
it — the gate could report health for a system half of which was unmeasured.

**Deployed twice, and the first one shipped nothing.** The playbook builds from
the working tree (`delegate_to: 127.0.0.1`), not from a git ref. The tree had
not been pulled, so the image was the code already running and no migration ran.
Harmless, and worth recording: pushing to `origin/main` is not the same as
updating the tree the image is built from, and nothing in the play output says
which commit it built.

**Verified before the deploy:** knowledge core 758 passed and 0 skipped, task
core 1222 OK including the browser suite against the built bundle, 325 frontend
tests across 21 files, build clean. Four additive migrations: `lists/0038`,
`mind/0016`, `mind/0017`, `review/0002`.

**What it deliberately did not do.** No generation anywhere — `v1 ships no
generation at all` is the ML policy holding rather than a corner cut. No second
review surface. No notifications. `semantic_echo` stays dark in production by
D4's decision. And S9 and S3 both moved as prerequisites rather than as
features, which is why `product-stories.md` gained a `WeeklyIntention` and lost
an `Item.effort` in the same day.

## Signing up, and the documents that let it be public — August 19, 2026

**Somebody could create an account and be told nothing at all.** Signup set
`is_active=False`, an admin ticked a box, and `accounts/emails.py` had six
functions of which not one wrote to the person waiting — no confirmation the
form had worked, no way to tell a minute's wait from a permanent one. Three of
`product-stories.md` S1's four requires had shipped the day before; this is the
fourth, and it did not close.

**Two gates, and that is the decision.** Confirming an address is self-service;
approval stays a person's. Vince's call, taken mid-build after the first half
was written against "verification replaces approval" — the site is
invitation-only and the privacy policy was still unwritten, so a stranger who
finds the form should reach a queue rather than an account. `is_active` is
approval and `email_confirmed_at` is confirmation, kept as separate fields so
that opening the doors later is a change of policy rather than of design.

**S1 therefore stays impossible**, on one point instead of four, and its verdict
now says which. Its done-means asks for a usable workspace *without waiting for
a human*, and approval is a human. What closed is the complaint underneath: the
applicant is told what happened, told which of the two waits they are in, and
can recover a lost confirmation email themselves — without which the failure is
unrecoverable, because the username is taken, the account cannot log in and the
address is spoken for.

The token is stateless, so no model: §4 asks a concept to earn one by having a
life cycle, and "valid until used" has none. It signs `email_confirmed_at`
rather than `is_active`, which is what makes a link single-use — signing
approval would leave it live through the whole review window, exactly when it
is most likely to be sitting unread in an inbox.

**The terms and the privacy policy were written to be checkable rather than
reassuring.** Every claim was verified against the source, and the checking
changed the text twice: the daily digest defaults to `True`, so it is described
as on-by-default rather than opt-in, and the deletion window came from
`ACCOUNT_DELETION_GRACE` instead of memory. Twelve tests hold the claims with a
mechanical counterpart, so the code cannot drift away from a published promise
silently. Where something is not done, they say so — deleting an account does
not reach data already at Sentry or Resend, which is an open item, so the policy
states it and offers to do it by hand.

Owned by Vinclarice, LLC; hosted in DigitalOcean's New York region, which is
**the one claim on that page no test can hold** and is marked as such at the
paragraph. Not lawyer-reviewed, with the trigger named: broader beta testing.

### The deployment

`DEPLOYED-2026-08-19/0111`, carrying migration `0015_user_email_confirmed_at`.
The bird was held for the planning-assistant release. The approval email below
shipped after it and is **not yet deployed**.

### What it taught

- **The product promised an email nothing sent, for a day, in production.**
  `activation_confirmed.html`, the confirmation email and the login form all
  said "we'll write to you once yours is open"; no signal, no hook, no
  function. It is the same defect the flow was built to remove, moved one step
  later — and it was found while auditing whether the *planning documents* were
  current, which is not where anybody would look for it. Copy is a claim about
  behaviour and nothing was checking this one.
- **A browser found what the whole suite could not.** `signup_pending.html`
  rendered the signed-in app bar — username and a Log out button — to somebody
  with no session, because the view passed `{"user": user}` and that name
  belongs to the context processor; `AbstractBaseUser.is_authenticated` is True
  on any real instance, so the bar had no way to tell. Every assertion passed
  throughout, because they all read the copy they expected rather than the
  chrome around it.
- **A test passed for the wrong reason and hid it well.** `test_email_identity`
  drove `mail_admins` *through signup*. When that notice moved to confirmation,
  two of its three assertions failed correctly and the third passed — reading
  the activation email instead, and asserting the right thing about the wrong
  message. All three now drive the lockout notice, the only caller left.
- **Watching a state instead of a transition emails forever.** `is_active` is
  True for the rest of an account's life and `last_login` is written on every
  sign-in, so the first approval hook would have sent on every login. The
  second version still re-sent on a second save of the same instance, because
  it never refreshed what it had loaded.
- **The shared test database interrupted this three times**, and the fix was
  already written down from August 16 — a private test database via a settings
  shim. Waiting for another session to finish was the wrong answer twice
  before the note got read, and one of those waits produced a spurious error in
  an unrelated migration test that did not reproduce in isolation.

## Navigation and identity — August 18, 2026

**Three navigations that disagreed, three visual identities, and a home page
that was the login form.** "Review" named the weekly review *and* the knowledge
core's pending queue. "Today" resolved to two different destinations depending
on which nav you clicked. `/mind/` was a one-way door: both other navs linked
into it and its own had no link out. Designed in
[`navigation-and-identity-plan.md`](navigation-and-identity-plan.md), which is
now a stub; the design itself is in `landing-mockup.html` and
`shell-mockup.html`, kept for the same reason the other comps are.

**One bar, server-rendered, on all three surfaces.** It had to be Django rather
than React because `/mind/` carries no JavaScript at all and a React bar would
either not reach that core or cost it the instant load that is its whole point.
Below it a per-core sub-nav; beside that a rail demoted to *contents*, which is
what it was always best at and could never say plainly while it also held
navigation. The knowledge core's Review became Pending, and Things became
Concepts — which is what its view, URL and template had always called it.

**The palette was measured rather than chosen by eye, and two values moved
because of it.** Slate "released" sat at 4.35:1 on paper, under AA. The hairline
was 1.30:1, fine for a border nobody looks at and not for a design where ruled
lines are the whole visual language. `--color-border-strong` exists because one
token was doing two jobs and WCAG 1.4.11 asks 3:1 of the second.

**The area dots had been invisible and nobody had checked.** All eight measured
1.11:1 to 1.77:1 against the light background — not weak labels, unreadable
ones — under a comment asserting one palette could serve both themes. True
before this work; the paper ground only made it obvious.

**`--font-sans` named Inter and nothing loaded it.** One declaration in the
tree, no `@font-face`, no link tag, so every page had rendered in the system
fallback while the stack claimed otherwise. Archivo, Spectral and IBM Plex Mono
are self-hosted now, and the split is a rule rather than a palette: sans is
machinery, serif is the record, mono is anything that has to add up.

**The signed-out page stopped being a login form**, which is
[`product-stories.md`](product-stories.md) S1's fourth requires. Its hero is a
real week — eight commitments chosen, five kept, one released, two open — with
the arithmetic done in front of the reader. And a brand-new account now gets one
thing to do on the Day page instead of three empty boxes it cannot act on.

### The deployment

Two events, both recorded. `DEPLOYED-2026-08-18/2230` shipped the work and
`DEPLOYED-2026-08-18/2244` shipped the CSS fix below; `LIVE` moved from
`a0fc6f1` to the second. **The bird codename was deliberately held** — Vince's
call — to ship with the planning-assistant work rather than being spent here.

### What it taught

- **The page about honest numbers divided by the wrong denominator.** The first
  draft of the landing mockup read 5/8, counting the released commitment as a
  failure three inches under a note saying it is not — and `review/reads.py`
  is explicit that `set_aside` is outside the denominator entirely. It was
  caught by checking the page's claims against the code rather than against the
  design document, which is the only check that could have found it. Every other
  claim on that page survived the same audit; two were understated.
- **A production defect that no suite could see, and it was older than the work
  that revealed it.** The Dockerfile's frontend stage copied `frontend/` and
  nothing else, so tailwind.css's `@source` globs reaching `../../../src/`
  matched an empty directory and every Django-only utility was silently dropped
  from the built CSS. It had been true since the Tailwind migration; nothing
  noticed because `base.html`'s classes are all *also* used in some `.tsx` file.
  `text-kept` and `text-released` were simply the first two that nothing else
  used. **Every suite builds in this tree, which has always had the templates —
  which is exactly why none of them could fail.** Found by looking at
  production.
- **Three tests would have gone on passing while testing nothing.** Archive moved
  into an always-visible sub-nav, and two smoke tests plus a Vitest one asserted
  its visibility through a disclosure. Their own comments had already named that
  hazard about a different Archive link on the same page. Re-pointed at an area,
  which is genuinely behind the drawer.
- **A fixture described a state the database cannot produce.** Twenty DayRoute
  tests went red on a correct check, because their day payload carried action
  items with no areas — and an `Item` belongs to a `List`. The fixture was
  wrong, not the gate, and the temptation was to loosen the gate.
- **A comment saying "if one moves, the other has to" is a hope.** The rail's
  collapse was declared at 760px in CSS and 761px in JavaScript, two hand-picked
  numbers agreeing with nothing but each other. Both are Tailwind's `md` now and
  a test fails if they drift — watched failing first, reporting the 132px band
  where the rail is collapsed and the disclosure cannot be opened, which is B0
  with a smaller viewport.
- **Naming a typeface you do not serve is worse than naming none.** It reads as
  a decision in review and is a no-op in the browser.

## Production defects — Part 1, opened August 12 and closed August 15, 2026

Ten defects found by the commercial audit. All closed; `commercial-blueprint.md`
Part 1 is four lines now, because a defect list with nothing on it is a document
outliving its work.

| # | Defect | Closed by |
|---|---|---|
| 1 | CI had failed 17 consecutive runs | `fd4a8d7` — and it needed three fixes, not one: the `mind` suite was not in CI at all, `postgres:18` carries no pgvector, and the browser job could no longer use SQLite |
| 2 | Token-authenticated writes recorded the wrong day | `6da41c8`, at `_resolve_scoped_token` — the seam both token paths share, rather than at the six endpoints that each forgot |
| 3, 4 | Two dropped Tailwind styles | `2986ed6` — **already shipped on August 12**; the list said otherwise for two days |
| 5 | A white screen on any render exception | `0428efb` |
| 6 | Tags dropped on one of two promotion routes | Declined August 14; moot August 15 when Heron deleted both routes |
| 7 | The Android capture queue had no lock | A process-wide lock on the companion object — not `@Synchronized`, which would have passed a shared-queue test and protected nothing |
| 8 | The queue was included in Android backups | Excluded in *both* `backup_rules.xml` and `backup_rules_legacy.xml` |
| 9 | Nothing would tell you the site was down at 3am | `/healthz` (`fd896c6`), `restart_policy: unless-stopped` (`b2e16b2`), and UptimeRobot polling it from August 15 |
| 10 | Sentry could ship private note text | `bbfc38d` — `include_local_variables` defaults to `True` and is independent of `send_default_pii=False` |

**Three lessons cost a session each and outlive the defects.**

- **A signal that is always red carries no information.** CI failed seventeen
  times and stopped being read; the same shape appeared twice more that week —
  certbot failing on a deleted staging certificate, and a defect list nobody
  trusted.
- **A fix does not repair what the defect already wrote.** Defect 2 filed real
  `RoutineOccurrence` rows against the wrong date for as long as it existed, and
  nothing recorded which auth path created a row, so a repair would have to
  guess at a durable record — which `principles.md` refuses. Left alone
  deliberately, recorded so it is a decision rather than an oversight.
- **The list twice described finished work as open**, which cost more than the
  defects did: a session of re-investigation on the Android pair, two days on
  the Tailwind pair. If a list like this exists again, check the code before
  believing it.

## The mail transport — August 18, 2026, `jackdaw`

**No mail had left this droplet for at least three days and nothing said so.**
DigitalOcean blocks outbound 25, 465 and 587 on every Droplet, so the digest,
password resets, deletion warnings and every contact-form message went into a
SYN blackhole that took four and a half minutes to give up. Three Sentry reports
read as a flaky relay. Only three arrived because the digest skips users with
nothing due and the contact form is rarely used — not because it usually worked.

**The diagnosis is the part worth keeping.** `smtp.resend.com` resolves to two
IPv4 addresses, and `socket.create_connection` walks them until the kernel
exhausts its SYN retries at ~127s each: 2 × ~135s is the 271 seconds the August
16 breadcrumbs span, with `raise exceptions[0]` firing because both failed.
Resend itself answered an ordinary network in 0.15s throughout.

Sending moved to Resend's HTTPS API — reachable from that host, where an
unauthenticated POST returns 401 rather than hanging. Refused along the way: a
support ticket to unblock, which leaves the application one policy decision from
this again; a queue, which is right at a scale this does not have; and an HTTP
dependency, when `requirements.txt` has ten entries and this is one POST.

**What the backend refuses to do is most of its design.** Only a 2xx counts as
sent and Resend's own message is carried into the error, because B4 exists
precisely because a provider returned success for a message it had discarded. It
refuses attachments and HTML rather than delivering something diminished,
honours `fail_silently`, bounds the request with `EMAIL_TIMEOUT`, and keys an
idempotency header on the whole payload so an hourly digest retry cannot
double-send.

**Mail failures stopped taking pages with them.** The contact form keeps the
visitor's text and offers an address that does not depend on what just failed;
`signup` no longer leaves a real account behind a 500; and the password reset
stays deliberately indistinguishable between "no such account" and "the send
failed" — the page that says otherwise is the page that discloses which
addresses are registered.

### What it taught

- **Two defects were findable only by deploying, and both were mine.** The image
  build broke because making `resend` the default *and* requiring its key at boot
  together demanded a variable the Dockerfile does not set. Then the first send
  failed `403 error code: 1010` — Cloudflare, not Resend, refusing
  `Python-urllib` by signature. Every test in `test_mail.py` injects a transport
  or patches `urlopen` so the suite stays offline, which is correct and is
  exactly why neither could surface there. Both have tests now that would.
- **A verification that cannot distinguish "we fixed it" from "it started
  working" is not a verification.** The drill kept deliberately: SMTP is *still*
  blocked from that host, checked after the deploy, so HTTPS is demonstrably
  what carries the mail.
- **Three incidents in three days were all already fixed and undeployed.** The
  August 18 digest crash was D2, closed twelve days of commits earlier. Work
  sitting in `main` protects nobody.

## Operational gaps — August 18, 2026

The four the review named, closed together. Each turned out to have something its
one-line summary did not carry.

- **A rollback path.** The image is tagged by commit and four are kept, so a bad
  deploy has something to go back to. The identifier is a bare SHA rather than
  the `git describe` already registered — that resolves to the nearest
  *annotated* tag, and this repository's own `DEPLOYED-<date>/<time>` convention
  is full of slashes Docker tags forbid. **Documented with its limit**: rolling
  the image back does not roll the database back.
- **Scheduled-job visibility.** `/healthz/scheduled`, watching *outcomes* rather
  than heartbeats — which catches the job running and failing, or running and
  skipping somebody, both of which ping identically to a healthy run. No new
  model, because every signal already existed. Separate from `/healthz` because a
  late cron job is not the site being down.
- **The backup check that had never run.** Scheduled in CI, not on the droplet:
  it needs `doctl` authenticated, and that is a decision about where a
  DigitalOcean token lives rather than a cron line. Run against production while
  wiring it — backups were 16 hours old and current, which nothing had
  established either.
- **The restore drill.** It compared row counts and `django_migrations`, which
  are both *data*; every guarantee the schema makes is DDL. A restore missing all
  of it passed. The new step checks behaviour where it can — proved by disabling
  the append-only trigger and watching the catalogue check report `ok` while the
  UPDATE it exists to refuse was accepted.

## Code review findings — closed from August 18, 2026, `ibis`

**The codename was attached on August 26, 2026**, by the guard described at the
end of this file: this entry is `ibis`'s narrative and had never said so, so
nothing could get from the tag to the story. Sixteen findings, D1 through D17,
plus three production incidents that arrived while the work was in flight and
two defects those incidents exposed.

Findings from [`code-review-2026-08-16.md`](code-review-2026-08-16.md), taken in
the order that review ranked them. **The review itself gets no status lines** —
it is a record of one review at one commit, and annotating it with what happened
afterwards is the drift [`README.md`](README.md)'s rule exists to stop. What
happened to its findings lives here instead.

`commercial-blueprint.md` Part 1 stays closed and empty throughout. None of these
was ever promoted to it, so there is no defect-list entry to close, and promoting
a finding remains a separate decision.

| # | Finding | Closed by |
|---|---|---|
| D1 | CRITICAL — unsaved edits destroyed by a background refetch, in three routes | `4bf8bc9` |
| D2 | HIGH — one nullable column, four broken surfaces | `4e89675` |
| D3 | HIGH — Sentry shipped raw request bodies despite `send_default_pii=False` | `dedc23d` |
| D4 | HIGH — `/api/v1/login` unthrottled at every layer | `9eb9eea` |
| D5 | HIGH — `open_question` filtered on `dormant_thread`'s name | `c9ac698` |
| D6, D11 | HIGH / MEDIUM — three scheduled loops where one account blocked the rest | `70f27b1` |
| D7 | HIGH — note text in the nginx access log and in Sentry's `query_string` | `faf55dd` |
| D8 | MEDIUM — area deletion destroyed completed and archived work with no count | `23a47e1` |
| D9 | MEDIUM — routine progress was an unlocked read-modify-write | `c9be0ec` |
| D10 | MEDIUM — a deletion could be scheduled with its warning never sent | `4d4a225` |
| — | A production incident, and what guarding these loops had cost | `0a87f91` |
| D12 | MEDIUM — the export dropped every tag association and three models | `79d2816` |
| D16 | LOW-MED — corrected the false hourly-cap claim (behaviour unchanged) | `0476bb3` |
| D13 | MEDIUM — side-nav counts went stale on every task write | `9631e32` |
| D14 | MEDIUM — search truncated by recency, silently, beside a miss button | `6e280ba` |
| — | Two more production incidents, and the mail paths they exposed | `0cf8803` |
| D15 | MEDIUM — dead `/capture/` links in the Agenda sidebar | `2e6cd1c` |
| D17 | MEDIUM — commitment parser fires on prose; **gate deferred**, recorded | `1d09220` |

### D1 — the refetch clobber

`TaskDetailRoute`, `AreaRoute` and `ProjectRoute` each seeded form state from
inside the `queryFn`, so the setters re-ran on every settle of the query. With
`refetchOnWindowFocus` on and `staleTime` at 0, alt-tabbing away from a
half-written note and back restored the server's value over it. It broke the
product's own core promise, and it was the **third** time the project had fixed
this bug — `PreferencesRoute` and `DayRoute` already carried the guard.

**It was never only the alt-tab, which the review did not say.** Four of
`ProjectRoute`'s own mutations call `refresh()`, which invalidates the very query
that seeds the title; `AreaRoute` reaches it through `projectMutation`'s direct
`refetch()`. Renaming a project and then adding an area to it lost the rename,
with the area's success message beside it — no window focus involved. That is
the path a person actually walks, and the review missed it by reasoning from the
mechanism rather than from the page.

**Moving a side effect out of a render path opens a gap.** With the setters in an
effect, one render has `data` and no seeded state; `TaskDetailRoute` guarded on
`!task || !areaRef` and would have flashed `RouteFailure` over a request that had
just succeeded. `!data` is a failure, `!task` is a load, and they are not the
same guard.

### D2 — the half-introduced nullable column

`Item.list` went nullable on August 14 (`0857835`). That commit fixed five sites
and drew the rule in its own message — *"a nullable column is only
half-introduced until both directions are covered"* — then did not touch
`src/review/` or `android/`. Four surfaces still read the column as non-null,
every one of them one tap from `/mind/`'s `confirm_actionable`.

`/api/v1/review` **500d permanently**, because Ninja validates responses and
`CompletedTaskOut.area_id` was `int`. There was no way out from inside the
product: `completed_in_week` filters on `completed_at` alone, so archiving the
task does not clear it and only setting an Area by hand ever did. The digest
**crashed rather than degraded**, and its loop orders by username, so one
affected account starved every recipient sorting after it. Both Android read tabs
**blanked**, because the payload-level catch discards the whole response.

**The near-miss is the finding.**
`test_a_task_without_an_area_is_readable.py` already constructed exactly the
state that 500s the week — `archive_item(complete_item(self.unfiled))` — and
asserted only `/api/v1/archive`. One more line would have caught this the day it
shipped.

### D3 — the same trap, one option over

`send_default_pii=False` gates **cookies**. In `_wsgi_common.extract_into_event`,
`should_send_default_pii()` guards the cookie line while `request_info["data"]`
is set unconditionally; the only thing between a request body and Sentry is
`max_request_body_size`, never passed, defaulting to `"medium"` — ten kilobytes.
Every captured thought, every day's intentions and every task note is far under
that, so a 500 on a capture or day write sent the writing itself.

**This is defect 10 a second time.** That fix's comment drew the rule — *"the
default belongs to a dependency: silence here is a decision made by whoever last
released the SDK"* — and the option beside it was left silent. Two comments and a
test docstring asserted the opposite of the truth in between, which is what let
the second one sit unnoticed after the first was found.

### D4 — the rule that was written down twice and never applied

`POST /api/v1/login` trades a password for a 90-day all-scopes token, is
`auth=None` by design, and matched nothing but the catch-all `location /`.
Both the nginx template's header and `settings.py` state that nginx throttling
is the first line of defence and django-axes the second; neither was true for
the one route where it mattered most. `architecture-trajectory.md` §6 records
closing this identical hole for `/` on August 3, and the API login shipped three
days later without a matching rule.

**The only one of these findings `roadmap.md` already carried as open**, and now
the only one whose fix is not yet live: an nginx template changes nothing until
the playbook runs.

**What replaces it is a test, not a rule.** The rule closes this route; the test
reads the template and the API together and fails on any operation with an
explicit `auth=None` that has no throttled exact-match block. `auth_param` is
the discriminator Ninja already keeps — `NOT_SET` for an operation inheriting
`django_auth`, `None` for one opting out. Two more tests keep it from passing
vacuously, because an introspection that quietly returned an empty set would
pass while covering nothing.

**Proved by running it.** There is no staging, so a template test that says a
rule exists is not the same as knowing nginx accepts it. The template was
rendered with the playbook's own variables and served by nginx 1.31.3 in a
container: eight POSTs to the login gave four 200s then four 429s, the reset
gave six then two, and eight GETs to `/api/v1/agenda` all returned 200 — the
half that matters second, since a rate limit that reached the authenticated API
would be a worse defect than the one being fixed.

### D5 — a workaround that hid the defect it worked around

`open_question` imported `_previously_proposed_ids` from `dormant_thread`, and
Python binds a function's globals to its *defining* module — so the filter
queried `detector="dormant_thread"`. Its own `DETECTOR` sat one line below the
import, consulted by nothing. A dismissed answer came back every night forever,
and every pair `dormant_thread` had already proposed was permanently invisible
to it — the directional finding this detector exists for, unreachable on exactly
the pairs most likely to have one.

**`semantic_echo` and `shared_referent` had each already worked around it**, by
keeping an identical private copy of the body. That is what kept it hidden: with
two of three detectors carrying their own, the one that did not looked like the
pattern rather than the exception. A fourth copy would have left the trap for the
fifth detector, so the fix passes the detector as an argument and there is one
body again.

**The refactor proved itself mid-change.** Between changing the signature and
changing the body, `shared_referent`'s own dismissal tests failed — evidence
both that the collapsed function is the one all four use, and that those tests
reach the filter rather than the fingerprint constraint that would mask it.

### D6 and D11 — three loops, one shape

Taken together because they are one defect in three files. Every scheduled
command that loops over accounts ended its run on the first failure.

**The digest was the worst of them.** The loop orders by username, so an
unguarded raise did not *delay* everyone sorting after the failing recipient —
it never delivered to them, and the write-off path stamped `last_digest_date`
anyway, recording the day as decided. Daily, and leaving no trace in the data.
`purge_deleted_accounts` held every remaining erasure open on one bad address;
`run_mind_maintenance` lost the pass *and the marker* for every owner after a
failure, which `/numbers/` then reports as never maintained — true, and silent
about why.

**The digest already guarded the other instance of this exact class**, two lines
above the one that was missed: `resolve_time_zone(...) or ZoneInfo(...)` exists
so one bad time zone cannot stop the run. The class was recognised and the
likelier case left open.

**A failed iteration is deliberately not marked done.** The digest does not stamp
a day it did not decide, so the next hourly run retries and the existing
`until_hour` write-off still closes it out; maintenance writes no marker for a
corpus it did not finish. Catching an exception must not turn into recording
success.

**One narrower instance is left open on purpose.** `run_detectors` catches only
`Unavailable` per node, so a single malformed note still costs one owner their
pass. Its blast radius is now one owner, reported and exiting non-zero, instead
of everybody after them.

### D7 — the words were in the URL by design

`manifest.json` declares the share target `"method": "GET"`, which is what lets a
share work with no service worker, so a shared passage reaches `/mind/share/` as
`?text=`. `/mind/search/` takes `?q=`. That is a good design decision and it put
somebody's own words in the request line, where two separate things wrote them
down.

**The disk half was unconditional and is the larger one.** No `access_log`
anywhere in the template and the playbook never templates `nginx.conf`, so the
distro default applied — `combined`, whose `$request` is the verbatim request
line. Every search and every share, on every request, in plaintext, for as long
as rotation keeps it. The fix logs `$uri` instead, keeping every other field, so
the log holds its operational value and not the query. The port-80 block needed
it too: it only redirects, but `return 301 https://$host$request_uri` carries the
query onto that hop.

**The Sentry half is narrower, and the review was right to separate them.**
`query_string` is set unconditionally and the default `EventScrubber` never
touches it — but with no `traces_sample_rate` there are no transaction events, so
it travels only when an error is captured. On error, not on every request. No
option covers it, so it takes a `before_send`; `request.url` is left alone
because `get_request_url` excludes the query already.

**Observed, not reasoned.** nginx 1.31.3 was run against the rendered template
before and after: `"GET /mind/search/?q=therapy%20notes%20about%20my%20marriage"`
became `"GET /mind/search/"`. The template tests that now guard it were written
afterwards and passed immediately — regression guards, and said to be.

### D8 — the finding was the disclosure, not the behaviour

The first of these that turned out to be a product decision rather than a defect,
and the verifier who narrowed it was right. Deleting an Area does hard-delete
completed and archived tasks, and `completed_in_week` has no snapshot so they
leave past weeks retroactively — but the UI already warned, and `reads.py`
already documents the consequence by name, calling it the reason §8 has a
completed review stamp its figure. A reasoned trade, not a missed case.

**So the fix is disclosure and the behaviour stands** — Vince's call, asked
rather than assumed. The dialog now names the counts, archived separately
because `area_detail` sends `archived_count` rather than including those tasks in
`items`: they are not in the list the person is looking at, which is why they are
easiest to forget.

**Detaching had become newly possible in the meantime, and was not taken.** D2's
nullable `Item.list` made an unfiled task first-class, so `SET_NULL` would work
now where it would not have when this was designed. Recorded because the option
changed without anyone deciding it had.

**Both halves of the consequence are stated.** Weeks never reviewed change; weeks
whose review was completed keep their stamped figures. Saying only the alarming
half would be its own kind of wrong, and the breakdown is shown only where it
says something — "0 completed, 0 archived" is the padding that teaches people to
dismiss the dialog.

### D9 — the count that cannot be reconstructed

`log_progress` read `progress`, added in Python and saved: no
`select_for_update`, no `F()`. Two taps read the same number and wrote the same
number. It matters more here than the shape suggests because **the log is the
count** — nothing else records the increment, so if the loss is what makes a
period miss its target, `habits_met` is wrong for that week and no record
disagrees. `lists/services.py` opens every mutation with a lock; this module
opened none.

**Proved with two threads on two connections.** A test inside one transaction
cannot see this and would pass against the broken version. Before the fix,
`2 != 3`; after, `3`, five runs running. The occurrence is created and committed
before the threads start, or both race `get_or_create`'s INSERT instead — which
Postgres serialises on the unique index, a different mechanism that would mask
the one under test.

**The sweep found three more and one of them bit back.** `call_it_enough` is the
same defect on the same row; `pause_routine` and `resume_routine` are the same
shape on `Routine`, costing a duplicated `RoutinePause`. Rebinding `routine` to
the locked row stopped those functions mutating the instance the caller handed
them — so a test that paused a routine and then logged against that object found
`is_active` still true. **A concurrency fix quietly reopened the hole pausing
exists to close**, and three existing tests caught it. Locked and refreshed in
place instead.

Only `log_progress` has a concurrency test; the other three carry the idiom and
their behavioural tests. Said here rather than left to look like full coverage.

### D10 — the guard was right and its precondition was not

`request_deletion` wrote the timestamp, committed, then sent the email. A failed
send left the account scheduled with nobody told — and the idempotency guard made
that **permanent**, because the retry took the early return. The guard is
correct: a doubled click is not a second decision. What nothing enforced was its
precondition, that the message went out when the timestamp was written.

**`purge_account` already had this right, twenty lines below**, and says so in
its own comment: *"a receipt for an erasure that did not happen is worse than no
receipt."* Reasoned once, in the same file, and not applied to its neighbour.

**`EMAIL_TIMEOUT` is part of the fix, not beside it.** Sending inside the atomic
block puts an SMTP round trip between BEGIN and COMMIT; unset, smtplib inherits
the global default socket timeout — also unset — so a hung relay would hold that
transaction open unboundedly, on one worker with four threads.

**The rollback was not enough, and the test caught why.** A transaction undoes
the row and cannot undo an attribute on the caller's instance, so the user object
kept claiming a timestamp the database no longer had — and the guard took the
early return again. *The defect, reintroduced by its own fix.* The same
divergence bit `pause_routine` during D9, one finding earlier.

**`cancel_deletion` is deliberately asymmetric and now says so.** Rolling a
cancellation back because its receipt bounced would leave an account scheduled
for erasure after the person asked to keep it — trading a missing email for the
outcome the email was about.

### The August 16 SMTP timeout — the fix that would have hidden the next one

Not a review finding. A real Sentry report, arriving mid-series: a connection
timeout at `send_due_digest`'s `send_mail`, 13:00 UTC on August 16 — D6 in
production, on the deployed code, before any of this landed.

**It confirmed two committed fixes and broke a third.** The breadcrumbs run
13:00:03 to 13:04:35: four and a half minutes inside `socket.create_connection`,
Linux retrying SYNs across both of the relay's addresses with no timeout set.
D10's `EMAIL_TIMEOUT` bounds exactly that, and Django's SMTP backend does read it
through to `create_connection`. And the failure was the *relay being
unreachable*, not one rejected recipient — so it failed identically for
everybody, and unguarded it cost every user that hour rather than the ones
sorting after a bad address.

**The third is the one worth keeping.** The only reason anybody knew about this
is that the exception propagated and Sentry caught it. Guarding the loop took
that away: `BaseCommand.run_from_argv` catches the `CommandError` the guard
raises, writes it to stderr and exits, so it never propagates — and cron has no
`MAILTO` and the host no MTA, so stderr reaches nobody. **The fix for D6 would
have made the next outage completely silent, which is worse than the crash it
replaced.** All three guarded loops now `logger.exception` the caught error;
sentry-sdk installs `LoggingIntegration` at event level ERROR by default, so that
is an event without any command importing the SDK.

Generalise it: **a guarded loop reports through logging or it reports nowhere.**
Catching an exception moves the decision about who hears about it from the
runtime to you, and the default answer becomes nobody.

### D12 — a promise nothing could check

`_rows` iterates `_meta.concrete_fields`, which excludes many-to-many by
definition, so tags left as a list of names with nothing saying which tag was on
which task. Three models were never queried: `HypothesisMember` — the span
citations that are a hypothesis's whole evidence — plus `Attachment` and
`SentenceEmbedding`. The module docstring promised *"every row of every owned
model across both cores"*.

**The stakes are what make it more than untidy.** This file is what stands
between somebody and irreversible erasure. Export, then delete, and an
association missing here is not missing — it is destroyed, with no other copy.
`product-stories.md` scores leaving with your data as one of only three journeys
that work.

**The promise was not checkable, so it was not true.** `EXPORT_KEYS` now exists
to be checked rather than read: a test walks every concrete model in the six
owning apps and fails if one has no export line. A model added later is caught by
the suite instead of by somebody who has already deleted their account.

**The guard passed by coincidence, and the probe is the only reason that is
known.** Walking the payload recursively descended into `ActivityEvent`'s JSON,
so a key appearing in somebody's activity data counted as proof a model was
exported — it reported the export complete with `Attachment` removed. It reads
the payload's own two levels now and fails on that same mutation.

### D13, D14 and D16 — re-verified before being touched

Three findings the review itself was least sure of, checked against the tree
before any of them was fixed. **All three mechanisms held**, and three details
did not.

**D13 was understated.** The right pattern is in *seven* files, not four —
`AgendaWorkspace`, `AreaRoute`, `PreferencesRoute`, `ProjectRoute`,
`ProjectsIndexRoute`, `ReviewRoute` and `DeletionBanner`. Seven right and three
wrong reads as oversight rather than unsettled convention. Fixed by invalidating
after *every* write path in the three, not the ones whose counts obviously move:
picking is how it happened, and a rule re-derived per handler gets missed again.

**D14 held, including its own self-correction.** No `SearchRank` anywhere; a
`.distinct()[:30]` over a `-captured_at` order with no count in the template. Run
directly: 35 matches, 30 returned, 5 silently dropped. And searching a term the
person *deleted* in a revision returns the note while the page renders text
without it. `retirement_gate` really is about absorbing the task core's domains,
so inflated misses hold it shut — the review was right to invert its own claim.

**D16 held, and I had made it worse.** Its honest framing is that the defect is a
false statement, and D4 rewrote that exact comment block while preserving the
sentence — *"caps how many messages actually leave per hour"* — the review had
already identified as untrue. The counter is `LocMemCache` in one gunicorn worker
recycling every ~500 requests, and whitenoise serves every static asset through
that worker, so ordinary browsing resets it. Corrected in both places that
claimed it; the behaviour fix needs a shared cache, which is infrastructure
nobody has decided to add.

### D14 — the truncation that fed the instrument measuring it

`SearchRank` appeared nowhere, so search took the first thirty of a
`-captured_at` ordering: the newest matches rather than the best, with no count
and no pagination to make the cut visible. Run against the tree: 35 matches, 30
returned, 5 dropped in silence.

**The button underneath is what turns this from untidy into corrupting.** "I know
I wrote this and can't find it" sits directly below the results, so the person
whose note was number thirty-one presses it and a *truncation* is recorded as a
retrieval failure — in the one signal the product has where the right answer is
already known.

**Fixed by ranking and by saying the number**, and the number only when it says
something: "showing 3 of 3" on every search is noise, and noise above a button
about failure is how the button stops being read.

**A match in superseded text is labelled, not removed.** Searching a word
somebody edited out returned the note and rendered a body without that word —
baffling, but the match is right: `original_content` is never mutated precisely
so what was first said survives. The missing part was the sentence explaining it.

### The mail outages — three incidents, two more defects

August 16 through 18, and every one of them arrived from production rather than
from the review. The August 18 pair mattered most: the nullable-Area
`AttributeError` in `send_due_digest` was **D2 exactly**, already fixed and
undeployed; and an SMTP connect timeout on `POST /contact/` was a defect nobody
had found.

**The contact form had no guard and no model.** Its docstring says the message
*"only exists in the support inbox it was sent to"* — a deliberate choice — so a
failed send meant the message existed nowhere, and the visitor got a 500 with
their own text inside it. A stranger with a question is the person least able to
recover from that. It now keeps their text, says the message has not arrived, and
offers an address that does not depend on what just failed.

**The sweep found the same shape one function away.** `signup` sends the admin
notification *after* `form.save()`, so the same outage left a real account behind
a 500: no "pending approval" page, no way to know it worked, and a retry failing
on a duplicate username. Caught and deliberately **not** rolled back — the
asymmetry `request_deletion` settled two days earlier, from the other side.

**`roadmap.md`'s "a real production 500 reaching Sentry" closed here**, having
been narrowed two days before to the web half specifically. A management command
reaches Sentry through the excepthook; a view reaches it through the WSGI
integration. This was the view.

### D15 and D17 — a dead link, and a decision left open

D15 was two hardcoded `/capture/` links Heron 4b orphaned, in a block no test
looked at. **Its tests failed the first time for the wrong reason** — a fixture
string borrowed from the Android suite — so the green run afterwards proved
nothing until the dead link was put back and they failed on the assertion.

D17 is the first finding closed **without a fix, on purpose.** The parser proposes
a commitment for prose that names a day, including one ten months out. But the
false positives are structurally identical to the true ones, a past-tense rule
reaches three of five while silencing a real commitment, and `cold-start.md` says
these thresholds get set by accept-rate data rather than guessed at. The five
strings are a strict `xfail`: the expectation is recorded, the suite stays green,
and the day something makes one pass, it says so.

### What these have in common

- **A fix applied only where the bug was reported is not a fix.** D1 was guarded
  in two of five stateful routes; D2 in five of nine sites; D3 was the option
  beside the one defect 10 had just fixed. All three survived a fully green suite
  because the unguarded places were the untested ones.
- **The idiom was always already present.** `PreferencesRoute`'s `seeded` ref for
  D1; `optIntOrNull("project_id")` one line below `getInt("area_id")` for D2;
  defect 10's own "pass it explicitly" comment for D3. None needed a design
  decision, only a sweep.

- **A comment that is wrong hides the next defect.** D3 sat behind three
  assertions that `send_default_pii` covered request bodies — in the module, in a
  test comment and in a test docstring. The first fix read them and stopped.
- **A regression guard that passes on its first run has to be probed.** The
  seeding ref is keyed on the record id rather than a boolean; degrading it to a
  boolean kills that test and only it, which is what makes it worth keeping.
- **The type check earns its place at a schema change.** Regenerating the
  contract after D2 named `ReviewRoute`'s hand-written mirror type immediately —
  the same way `0857835` found seven.

- **A stated architecture is not an implemented one.** D4's rule was written
  down in two files and applied in neither, for the route that needed it most.
  Where a guarantee spans two languages or two tools, the only thing that holds
  it is a test that reads both — which is what D2's and D4's fixes each left
  behind.

- **A local workaround hides the defect it works around.** Two detectors kept a
  private copy of D5's filter rather than fixing why the shared one was wrong,
  and that made the broken caller look like the ordinary case. Copying to avoid
  a bug is a decision worth writing down, because the next person reads the
  copies as the pattern.

- **Guarding one instance of a class is where the class stops being looked
  for.** D6 sat two lines below a guard against the same failure, D3 one option
  below a fix for the same trap, and D5 one import from two detectors that had
  already worked around it. Each time the near-miss was written down and the
  neighbour was not checked. The sweep is the cheap part; remembering to run it
  is the whole discipline.

- **A fix is a change, and changes have their own blast radius.** D9's sweep
  reintroduced a defect while removing one, because rebinding a variable
  silently dropped an in-place mutation three tests depended on. D10's fix
  reintroduced *its own* defect, because a rollback cannot reach an attribute
  on the caller's instance. Twice in two findings, both times the divergence
  between a row and the object holding it, both times caught by a test. The
  sweep these lessons keep asking for is not free; the tests are what make it
  affordable.

- **Not fixing is a result, if it is written down where the next person looks.**
  D17 closed with no behaviour change and a strict `xfail` carrying the evidence,
  because the gate needs data nobody has yet. A deferred decision with its
  reasoning attached is a different object from an unnoticed defect, and only one
  of them rots.

- **An instrument fed by a broken path measures the path, not the thing.** D14's
  truncation manufactured retrieval misses, and retrieval misses are what the
  product uses to judge retrieval. A measurement is only as trustworthy as the
  road its data travelled, and that road is worth checking before the number is
  believed.

- **Editing around a known untruth preserves it.** D16's false comment survived
  a rewrite of the very lines it sat in, because the edit was about rate limits
  and the sentence was about something else. A finding that says "this comment is
  wrong" is a finding about a file, and touching that file is the moment to act
  on it.

- **A test written after the fix has to be attacked before it is trusted.** D12's
  coverage guard passed on its first run and was worthless: it descended into a
  JSON blob and found the key it was looking for by accident. Two of these
  regression guards have now been probed by breaking the code they guard, and
  one of them failed that check. The first run proves nothing; the mutation is
  the test of the test.

- **Symmetry is not a reason.** D10's two halves look identical and must behave
  differently: the request rolls back because the email *is* the protection, the
  cancellation must not because rolling back would schedule an erasure the
  person just declined. Written down at the function, because the next person to
  notice the asymmetry will otherwise fix it.

- **Not every finding is a defect, and the difference is who decides.** D8's
  mechanism was real and its framing was not: the behaviour was a documented
  trade and only the disclosure was missing. A review can establish that
  something happens; whether it should is the product's question, and the fix
  that changes behaviour needs an answer rather than an assumption.

- **Three of these were about what leaves the server, and only one had a
  setting.** Defect 10 had `include_local_variables`, D3 had
  `max_request_body_size`, D7 had nothing and needed a hook. A dependency's
  options are a list of what it thought to make configurable, not a list of what
  it sends — so the question to ask of a monitoring SDK is what the payload
  contains, not which switches are off.

D1b — `AddRoutine` clearing before its request resolves, and expired-session 401s
handled on reads but not writes — is D1's class and is **not** fixed.

## Account deletion and data export — August 16, 2026

The first piece of the commercial substrate, and the one that did not wait on
`commercial-blueprint.md` Part 9's unanswered first question — *is Clarice a
business, a product with users, or a personal tool* — because the answer is the
same either way: the blueprint calls the pair a legal blocker rather than a
feature gap, and Sentry and Resend already process other people's data.

**Deletion was not unbuilt, it was impossible.** `ActivityEvent` is append-only
by a `BEFORE UPDATE OR DELETE` trigger and `ActivityEvent.owner` was
`on_delete=CASCADE`, so `User.delete()` raised. The model had reasoned exactly
this through for its *node* reference — "CASCADE, SET_NULL and SET_DEFAULT are
each a *mutation* of the log, which the append-only trigger refuses" — and made
that one non-constraining; the owner reference never got the same treatment,
because nothing had ever deleted an account.

**The line taken: append-only means history cannot be rewritten within a live
account.** It was never a promise to outlive the account's own erasure, and
could not be, because the log is not content-free — concept events carry the
labels somebody typed, on real material including other people's names, and
every event carries the username as `actor`. The exemption is narrow on purpose:
`DELETE` only, naming **one owner id**, read from a **transaction-local**
setting. A boolean would have passed the "erases my log" test and failed the
"does not touch anybody else's" one; `SET LOCAL` matters because connections are
reused across requests.

**A thirty-day grace period, and `is_active` deliberately untouched** — that flag
already means "pending admin approval", and one flag for two unrelated states is
indistinguishable everywhere it is read. The account stays fully usable while
leaving, which is what keeps *cancel* reachable without inventing a signed-link
email flow for a window that is the person's own to close.

**Two things were found by reading rather than by asserting.** A fixture claimed
to cover every owned model and missed four, caught by the "another account is
untouched" test failing — a neighbour with no rows cannot have them preserved;
there is now a test that the fixture populates what it claims. And an export for
an account with no areas produced a `tasks.md` containing the word "Tasks" and
nothing else, indistinguishable from a broken export at the exact moment you
most need to trust the file.

**Four more came from Vince reading the copy rather than the code**, which is the
review the tests could not do — every one passed against wording that was not
good enough.

* **It never said "permanent".** *Erased after 30 days* implies irreversibility
  rather than stating it. It now says permanently deleted and cannot be
  recovered — section, banner and email — and tests assert those words.
* **There was no acknowledgement.** Password re-entry guards the wrong mistake:
  it stops a passer-by at an unlocked screen and does nothing about somebody who
  has misread what the button does. Two gates now, and the tests say which
  mistake each one guards.
* **Nothing was emailed.** The thirty-day window only protects somebody who
  finds out inside it, and a banner cannot guarantee that. Three messages now —
  scheduled, cancelled, and a receipt sent immediately before the rows go, which
  reads the address *before* the delete, because a receipt depending on the
  record whose destruction it confirms never sends.
* **The banner was built to be global and wasn't.** `deletion_purge_at` went on
  the nav payload specifically so it could render on every route, then was wired
  only into Preferences. `DeletionBanner` now lives in `AppLayout` and carries
  the stop button itself, because "go and find the page where you did it" is
  harder than starting it was.

**One nav entry went with it.** "Settings" sat beside "Preferences" and linked to
`/accounts/settings/`, a two-line view redirecting to `/preferences` — one page
with two doors. The URL stays, since it is bookmarkable and `change_password`
redirects to it; the duplicate door is gone.

Verified by 911 Django, 616 pytest, 277 frontend and 32 browser tests, including
a browser test that downloads the archive and opens it. The secrets exclusion was
checked by emptying it and confirming the password and token hash then appear —
the test would have caught its removal, which is not the same as the test having
been watched fail.

## Heron — the crossover, August 15, 2026

**Tagged `heron` on `04e7c71`.** All five steps built, deployed and verified in
production in one day: 1–4a at 1200, then 4b and 5 together at 2030 — held to
one deploy on Vince's call, so the crossover was never half-live. The plan is
[`one-capture-surface-plan.md`](one-capture-surface-plan.md).

**Steps 1 and 2** wired a typed tag to a confirmed concept and carried a node's
concepts onto the task made from it, on almost no new machinery:
`ConceptCandidate` already had `label`, `confirmed_at` and `reason`, and
`propose_mention` with an explicit origin already self-confirmed. The trade it
settled was real, though — the Inbox modelled tags as first-class rows and the
knowledge core deliberately models none. The reconciliation is that **the
gravity gate exists to filter the system's guesses**: three mentions across a
day is what an *extracted* candidate pays because extraction over-generates on
purpose, and a person typing a tag is not a guess.

**Step 3** moved 34 captures and 2 ideas into the graph carrying their original
timestamps, 22 archived on the way in as discards. The corpus is the binding
constraint on the whole knowledge core, so this was not cleanup that preserved
data — it was the step that gave the detectors something to work on.

### 4a, and the check that came back the other way round

Step 4 said to check first that nothing on the phone still used the task-core
capture scope, believing `Backends.kt` already routed capture to the knowledge
core. **It does not, and never has on any shipped build.** `secondMindBaseUrl`
defaults to `""`, so `isSplit` is false and `capture` is literally the same
object as `workspace`: every thought typed on the phone posts to the task core's
`/api/v1/capture`, and deleting it as planned would have drained the encrypted
offline queue into 404s. The plan had also miscounted the surfaces at two — the
SPA Day page's quick-capture box posts to the same endpoint on session auth.

So the step became: keep the URL, the bearer token and the `capture:write`
scope, change what they write. `/api/v1/capture` writes a `Node` through
`services.capture_idempotent`, shared with `/mind/api/v1/capture` so the two
cannot drift, and the router moved from `capture/api_v1.py` to `mind/api_v1.py`
— which is what turned 4b from a migration into a deletion. No APK rebuild,
nobody logged in twice, one `/api/v1/` for one application.

**A fix that had shipped to the wrong endpoint.** Android sends `captured_at`
from both call sites — `CaptureViewModel.deliver` and `QueueDrainer.drain` — so
a thought that waited hours in the queue arrives with the time it was written;
the live endpoint's schema was `text` and `tags` only, so Ninja dropped the
field in silence. It had been found and fixed once, on the
August 14 device pass, on `/mind/api/v1/capture` — which nothing calls. The
defect stayed live on the real path for a day, and the 22 device-test captures
now in the graph carry delivery times rather than writing times as a result.

**The lesson, and it is the third time in two days** — after `/healthz` that
nothing polled and detectors that were built, green and never invoked. **Code
that exists is not code that runs, and a test that walks the wrong endpoint
proves the wrong thing**: `test_journeys.py` was posting to
`/mind/api/v1/capture` with a `mind.ApiToken`, and now walks the real route with
the real credential.

Deployed at noon as `DEPLOYED-2026-08-15/1200` (`99d48a2`), which `LIVE` points
at. Verified by 974 Django, 686 pytest, 271 frontend, 30 browser and a clean
build, then in production: the live OpenAPI schema carries `captured_at` and
returns `{public_id, captured_at}`, and an offline capture was walked from the
phone through the queue to `/mind/`. A last capture reached the Inbox after the
migration and before the deploy — "Barry tv show" — which is the gap the re-run
of `migrate_inbox` exists to close. The graph stands at 41 nodes, 19 visible to
the detectors.

### 4b — the deletion, and three things it did not cause

`/capture/`'s pages, forms, services, admin and tests are gone, with `Capture`,
`Idea` and `migrate_inbox`. Inbox and Ideas left both navs — the SPA's `SideNav`
and the Django `base.html` — and `inbox_count`, `inbox_url` and `ideas_url` left
the `/nav` payload. **`inbox_count` was the only number in that nav measuring a
backlog**, and nothing replaces it; a test now asserts that no nav key ends in
`_count` except `archived_count`, because a bare entry invites somebody to add
one and the attention policy exists to refuse exactly that.

Three things broke, and none of them were about capture:

- **`base.html` reversed `capture_inbox` and `ideas`.** Every Django-rendered
  page 500'd; the suite caught it in the first run.
- **The generated migration would not reverse.** `idea_owner_status_idx` covers
  `owner`, and unapplying `DeleteModel` runs before unapplying `RemoveField`, so
  a rewind rebuilt the table and then tried to index a column it had not
  re-added. Nothing in production would ever have reached it; the
  migration-rewind tests did. Fixed with a `RemoveIndex` first, because a
  migration nobody can back out of is worst at the moment they want to.
- **Four migration-rewind tests only rolled their own app forward** in teardown.
  Harmless for as long as every table had a live model, because the inter-test
  flush truncates by model — and fatal the instant a table had none, surfacing
  as `cannot truncate a table referenced in a foreign key constraint` in a test
  about checklist steps. They now roll the whole graph forward, which is what
  their own comment already claimed and what `accounts` had always done.

The pattern in all three: **deleting a model is a schema change, and what it
breaks is whatever quietly depended on the schema being wider than it needed.**
None was found by reading the diff.

872 Django, 672 pytest, 270 frontend, 30 browser, clean build. Deployed with
step 5 at 2030 as `DEPLOYED-2026-08-15/2030`. The pre-flight ran against
production while the models still existed, because `0008` has no reverse and
after it there is nothing left to check against: every `Capture` and `Idea` row
accounted for by a `Node` with an `inbox:` import key. Confirmed afterwards with
`showmigrations capture` — `[X] 0008_delete_idea_capture` — because that
migration runs in its own container and could fail without the play visibly
failing. `/capture/` and `/capture/ideas/` now answer 404 where they used to
redirect to a login, and the live `/nav` payload carries none of the three keys:
the two observable facts that say 4b landed.

### 5 — the URL that did not move

Step 5 was written as *move `/mind/` to the URL 4b frees*, and asking the
question directly reversed it. **`/mind/` is permanent — Vince's call**, for the
reasons `CLAUDE.md` now carries: nine routes under `/mind/` and only one is
capture, so `/capture/` would name the smallest thing in the room, against a
live PWA shortcut and every bookmark. **"Temporary" was a reason to reconsider
the name once the collision was gone, not an obligation to move.** The change
was therefore subtraction — the word came out of `clarice/urls.py`,
`mind/urls.py`, both navs and their tests, replaced by the reason it is
permanent. It also answered a question the plan had listed as beyond it: the
knowledge core's other pages stay together, under a different root from the task
core's `/app/` — two cores, two homes, one login, one nav reaching both.

### The leftovers, cleared the same day

**`/mind/api/v1/` and `mind.ApiToken`.** The knowledge core arrived with its own
`NinjaAPI` and its own `sm_`-prefixed bearer token table, so the Android app
could point at a separate Second Mind server by setting one build property.
**No shipped build ever set it, and the `/mind/` pages carry no JavaScript at
all**, so nothing had ever called it from either direction. Dropping the table
took the same pre-flight 4b took — a row would have meant a device this silently
disconnects. Production returned **0**.

**The `capture` app**, which 4b had to leave in `INSTALLED_APPS` because Django
needs an app installed for its migrations to run. With `0008` applied in
production the shell went too; no other app's migrations depended on it, checked
first because it would have been the blocker. `django_migrations` keeps eight
inert rows, deliberately — editing production's bookkeeping to tidy something
Django ignores is the worse trade.

**One test was rewritten rather than deleted, and it is the point of the whole
exercise.** `test_capture_time_zones.py` asserted that a token capture reads
"tomorrow" in the *owner's* zone — the twin of defect 2, found by asking whether
the task core's bug had a counterpart here — and it ran through
`/mind/api/v1/capture`. Deleting that endpoint would have removed the only
coverage of a behaviour that is still live; it now runs through
`/api/v1/capture` on a `PersonalAccessToken`, where `_resolve_scoped_token`
makes the same `activate_for` call. **The seam moved; the defect did not.**

One test was genuinely lost: `test_ownerless_list_removal`'s third case, that an
`Idea` survives losing the task it pointed at. It needed `Idea` in a historical
migration state, and there is no longer one — not a re-evaluated risk, a
scenario that stopped existing.

### And the rule Heron finally killed

The task core had been in maintenance since the merger was planned. **The freeze
is lifted — Vince's call, the same day.** The rule's history is the useful part:
it had been rewritten twice to survive — "until the merger", then "until the
crossover ends", on the narrower ground that `Capture` and `Idea` were retiring.
Heron deleted both. **Each rewrite found a narrower justification for a
conclusion already held**, which is the shape of motivated reasoning, and a
third would have been cargo. What replaced it is a priority rather than a
prohibition, and it lives in `CLAUDE.md`.

## The Second Mind merger — August 15, 2026, `godwit`

**Written into this file on August 26, 2026**, from its tag, by the guard at the
end of this file. It had no entry at all — the largest single piece of work this
project has done, and the record held its name nowhere. What follows is the tag
and no more; the merger's *standing consequences* are `CLAUDE.md`'s
*The shape of the application*, which is current and is not restated here.

**All five steps of Second Mind's `two-cores.md`, from separate project to one
application.** The knowledge core at `src/mind/` behind this site's own login,
its corpus moved and re-pointed, facets landing with **the actionable one as the
sole exception to soft-apply** — and a deploy on the **existing playbook,
unchanged**, which is the clearest evidence available that it was a merge rather
than a co-location.

**What the merger turned out to require, and did not set out to do.** A task can
stand on its own: `Item.list` became nullable and `Item.owner` had to exist,
because ownership had been running through the `Area` at some twenty call sites.
And a **deterministic** commitment parser reads a date out of a capture and
offers it below the box, one tap to accept, **no filing question asked** — which
is the rule the deleted `Capture → Idea → Task` pipeline broke.

**Nine of the ten defects in `commercial-blueprint.md` Part 1 closed with it**:
CI green across five jobs after four days red, token requests using the owner's
time zone rather than the server's, `/healthz` with `restart_policy`, private
note text no longer reaching Sentry, migrate-before-recreate in the deploy, an
error boundary in place of a white screen, and both Android queue defects. **The
tenth is closed as won't-fix, deliberately.**

**Verified**: 979 Django tests, 573 pytest, 269 frontend, 30 browser, 309
Android; CI green on `main`; and in production `/healthz` answering ok, the
deployed OpenAPI schema carrying the nullable `area_id` that proves the agenda
fix is live, and the deployed bundle byte-identical to the local build.

## After Dunlin — Release F and six unlettered lines of work, August 6–12, 2026

Six of these seven shipped outside the release structure entirely, which is the
honest reason the letters stopped carrying information; the window was tagged
**Fulmar** belatedly on August 15, with an annotation saying so. **In-app login,
the optional unlock gate and release signing** shipped on August 6 alongside
capture tags and were folded into Dunlin rather than promoted; see *Capture tags
— folded into Dunlin* below.

### Release F — opened August 7, closed August 13

Opened with the second-mind discovery pass, **Vince's call, ahead of the pain
that would otherwise have forced it**: `architecture-trajectory.md` §5 named two
candidates, this and the staging environment, and neither had fired its stated
trigger, so this was recorded as a deliberate exception rather than a trigger
pretended to have fired.

**Discovery done and the first slice shipped in full, August 10.** Reading the
models against the charter found most of the idea/reference/project/task/routine
boundary already settled by releases that were not about this at all:
`Idea.status` had already made idea/reference one model, and Dunlin and Crane 0
had settled task/project/area and routine/task. The slice was `Idea.tags`
reusing `lists.Tag`, tag carry-forward through promotion, and a plain
`related_ideas` link with no `kind` field. 856 backend tests green throughout.
Two of the brief's own assumptions did not survive contact with the code and
were corrected in the document rather than built around: `capture.Idea` had no
Ninja API at all, and `Idea` had no detail page for chips to live on, so they
render inline on the shared list.

**Closed August 13, 2026, with its subject moved out of the project.** The
second mind became its own repository, which Clarice is absorbed into rather
than the reverse. The shipped slice stays deployed; it is simply the last of
that line, since `Idea` does not survive the merger.

### The project workspace redesign — August 10

Trigger: a real navigation dead end — opening a project from the side nav only
ever routed to its parent Area, because `Project` had never had a page of its
own. [`project-workspace-plan.md`](project-workspace-plan.md) inverted the
containment, so a Project became a standalone workspace holding one or more
Areas rather than living inside exactly one. Eight slices, each its own commit,
model through browser smoke pass. 858 backend, 231 frontend, 28 browser
journeys. One gap the plan missed — nowhere to create a *new* project once
`ProjectsPanel.tsx` was gone — surfaced only while writing the browser journey.

**Two follow-ups the same day, both from using the shipped feature rather than
from planning:** a `/projects` index page, and letting a Project create a
brand-new Area rather than only reassign one. The second forced a standing-rule
change — **an Area no longer needs a first task to exist.** The follow-up's own
browser journey caught a real bug neither plan anticipated: the sidebar going
stale after completing or deleting a project. 865 / 239 / 30.

### The Bootstrap → Tailwind arc — three components, August 10–11

**Task list** (`a12a310`, `DEPLOYED-2026-08-10/1928`). Trigger: `TaskWorkspace.tsx`
flagged as "simply a mess" mid-review of the Projects redesign. The migration
plus additions approved against a reviewed mockup — due-date sort, select-mode
bulk complete/archive, removable tag pills, pill dedup. 254 / 867. Pre-existing
`ProjectJourneyTest` failures were ruled out by bisecting against `main` first.

**Agenda** (`94a6c4f`, `DEPLOYED-2026-08-10/2100`). The last Bootstrap-era
component and the app's highest-traffic page. Two real functional gaps were
found by reading the code rather than guessing: no text search anywhere on the
page, and no staleness signal, because `age_in_days` lived on Daily's and the
review's own item types rather than the shared `Task` type. Shipped with the
migration, the touch-target fix, a unified area/tag filter row replacing three
separate surfaces, search, and the staleness label; bulk actions and manual
reordering were deliberately left out as editing-shaped work belonging to the
Area page. 263 / 867. Live verification against the built bundle caught a layout
bug nothing else did — a search field collapsing to 30px for want of a
`flex-shrink:0` guard.

**Archive** (`1cf9147`, `85154a8`). The last component on `site.css`. The
migration, the same touch-target fix, and the row date switched from
`created_at` to `archived_at`, confirmed against the model's own
`CheckConstraint` rather than assumed. Because it was the last dependent,
**`site.css` and `workspace.module.css` were retired from the app entirely**,
source deleted rather than left unreferenced. 264 / 867.

**The finding worth keeping, because it was not confined to one page.** The
Archive delete dialog's buttons measured 32px against a ≥44px claim. `Button`'s
size variants top out at 36px, and no component test measures rendered layout.
Checking the other two found every `<Button size="sm">` composer and dialog
button in all three at 28–36px, despite each brief claiming ≥44px and each live
verification reporting it confirmed. Fixed in all three with an explicit height
override. **Three consecutive verifications reported a measurement none of them
had taken.**

### Android as a full client — slices 1 and 2, August 10–11

Trigger: a request for a "more comprehensive overhaul" after a design pass on
the app's previously nonexistent visual theme.
[`android-full-client-plan.md`](android-full-client-plan.md) checked the gap
first and got half of it wrong: `lists`, `daily`, `review` and `routines` expose
the same *routes* the SPA consumes but not the same *auth* — only `/api/v1/me`
and `/api/v1/capture` took the Bearer token Android carries.

**Slice 1 (Daily, read-only)** installed clean on both devices and then did not
load: the stored token authenticated Settings and got 401 from `/api/v1/day`.
Asked directly rather than patched around, the call was to design a scoped token
tier before opting more routers into `TokenAuth` — see
[`token-scopes-plan.md`](token-scopes-plan.md). 899 backend tests, deployed the
same day and verified live, with the older device's pre-existing token still
working — the migration's grandfathering.

**Slice 2 (Agenda, read *and* write)** turned out bigger than the read half.
Complete/reopen, reschedule and quick-add live on `lists/api.py`'s hand-rolled
pre-Ninja endpoints with no token concept, sitting behind Django's *real*
`CsrfViewMiddleware` that every Ninja route is structurally exempt from.
`token-scopes-plan.md` §7 traces the mechanism Ninja actually uses and ports it
by hand as a `token_or_session_required` decorator, with a field-level guard so
`agenda:write` can complete or reschedule a task but never delete one or touch
its text, tags, notes or recurrence. 918 backend, 260 Android.

**Slice 1 extended to writable** the same day: focus pin/unpin, the day's own
text, and all six routine actions, behind `day:write` and `routines:write`.
Every endpoint was already Ninja, so no CSRF porting was needed. 933 / 285.

Both verified live on the SM-S928U1 against production. **One operational
lesson: a scope-adding deploy needs a fresh login on each device**, because an
existing connection predates the new scopes. Also found and fixed: a long
action-item title left the "Pinned" badge a few pixels wide, wrapping it letter
by letter.

### The staging environment — designed August 11, deferred August 12

Next in line on the infrastructure track per `architecture-trajectory.md` §6,
and decided directly rather than guessed: a second DigitalOcean droplet, not a
second process on production's already memory-tight host, with its own database
on the existing Postgres cluster — see
[`staging-environment-plan.md`](staging-environment-plan.md).

**Designing it found a real gap before it could reach production.**
`settings.py`'s `DEBUG` had only two states and neither fit `"staging"` safely;
the decision was pulled into a tested `clarice/deployment.py::is_debug()`, the
same "a function with a test, not a branch in a config file" pattern
`monitoring.py` already used. 937 backend tests.

**Deferred the next day, before provisioning** — see that plan's §8. Nothing in
flight touched the deploy mechanism and there was no real user data to protect
from an untested migration, so the recurring droplet cost had nothing to offset.
The decisions and the `is_debug()` fix stand; the droplet waits for a trigger.

Alongside it, §6's other two "now" items closed: **local development moved onto
Postgres**, closing the gap where SQLite silently omitted a constraint
production enforces, and the droplet-swap item — done back on August 3 — was
found never to have been marked complete.

## Production verification markers, per release

The practice these record is worth more than the markers themselves: **verify
with a marker the change actually introduced, not one that merely looks
plausible.** Bittern nearly confirmed a deploy that had not happened by checking
for `Something went wrong.`, a string that predated the change.

**Bittern.** The deployed bundle carried `RequestFailed`, the class B2.1
introduced. No unapplied migrations. Sentry active with `DEBUG` false. B1's
spawned occurrence rendering with its children and no refresh. Android capture
reaching the Inbox exactly once across every network condition. Per-user time
zones discriminating between accounts at 07:00 WITA.

**Crane.** The review routes answered 401 while a made-up route answered 404;
the POST-only `/review/{day}/complete` and `/routines/{id}/enough` answered 405
to a GET; the served bundle carried "Recent weeks", "Save the review" and "Call
it enough"; `/app/review` rendered on the real account. `lists/0023` linked both
existing repeating tasks.

**Dunlin.** `/api/v1/projects` and `/api/v1/areas/1` answered 401 while a
made-up route answered 404; `/api/v1/lists/1` was gone at 404; `/lists/1/`
redirected to `/areas/1/`; the login page said "areas" and never "lists"; the
served bundle carried "No projects in this area yet." and "stay open if you
complete this" with none of the old vocabulary. `app-shell.js` on production was
byte-identical to the build the tests ran against. All six migrations applied;
`0026` converted six subtasks; ownerless areas numbered zero.

## C2 — the interface failure, and the reason it was not an interface problem

C2 was an observation task rather than work: *reassess information architecture
after B0*, on the theory that "I can't tell where things are" might dissolve
once the navigation actually rendered. **Its evidence arrived from B1's own
verification on August 2, 2026.** Setting
up one recurring parent with three children took three attempts, and each
failure was the interface rather than the person:

- A task's **Repeat** (a select, parent-only) sat directly above each subtask's
  **Repeats** (a checkbox, child-only). Near-identical words, one screen,
  opposite meanings — and setting the first to None silently hid every instance
  of the second, so the control being reached for disappeared as a side effect
  of the mistake.
- A subtask row carried two checkboxes with no visual distinction: the leading
  one completed the task, a later one governed recurrence. Having used the
  first, the row read as done with.
- Neither failure produced an error. Both looked like success.

The verdict from that session was recorded as given: the web UI needed a
complete overhaul, not adjustment.

**Closed by Dunlin, August 3, 2026 — and the verdict was only half right.** Both
defects are gone. The first dissolved *by construction* when a Checklist Step
lost its recurrence field: the interface was never redesigned to fix it, which
is the strongest evidence the thesis behind that release was right. The second
became a checkbox and a switch. **The model was the larger problem, and fixing
it removed a defect no amount of interface work would have.** The evidence above
is left as recorded rather than rewritten, because what it observed is why the
release took the shape it did.

## Capture tags — folded into Dunlin rather than promoted

**Decided August 3, 2026.** Merged onto `main` the same day, deployed August 6
in `DEPLOYED-2026-08-06/2248`. Optional tags on a capture, typed on the Android
compose screen and displayed as pills in the web Inbox. It reused `lists.Tag`
rather than a parallel model (`_resolve_tags` became public `resolve_tags` so
`capture.services` could call it), added `Capture.tags` additively, and the
Android queue carried tags through offline capture the same way it already
carried text. Triage gained no tags field, and a capture's tags did not carry
forward onto the task or idea it became — both deliberate non-goals, not
oversights. The second was closed later by Release F's first slice.

The same decision covered the rest of what the Android device-testing branch
carried in: in-app login, the optional unlock gate, and release signing wired
into the build. None of it earned a release of its own, **which is why the
letter sequence skips E.**

## Dunlin — shipped August 3, 2026

`dunlin` (`82fd591`) was tagged after production was verified. Two deploys
carried it: 00:27 EDT (`e76c200`, `DEPLOYED-2026-08-03/0027`), which took slices
1 to 8 and all six migrations in one run, and 02:03 EDT
(`DEPLOYED-2026-08-03/0203`), which took the UI brief, the carries-forward
switch, and the playbook fix below. It closed with work outstanding by decision
rather than omission, listed at the end.

### What shipped

- **Slices 1–4 — the parent–child redesign, end to end.** A subtask is a
  **Checklist Step**: its own model, no due date, no tags, cannot recur, dies
  with its parent, promotable into a real task. `lists/0025` added the table,
  `0026` converted every existing subtask — deleting the `Item` each came from,
  or auto-promoting it when it carried a due date, tags, notes or a recurrence
  the new model could not hold — and `0027` retired `Item.parent`,
  `always_recurs` and `archive_group` outright rather than leaving them dead.
- **Slice 5 — the Area vocabulary.** A `List` is an **Area** everywhere a person
  reads one: copy, `aria-label`s, JSON field and schema names, and URL paths.
  The `List` model and the `lists` app keep their names, per
  `architecture-trajectory.md` §7. The old `/lists/` paths redirect rather than
  404. No migration.
- **Slice 6 — `List.owner` non-null.** `0028` deleted the anonymous-era
  ownerless areas, irreversibly; `0029` made the column required. Charter rule 1
  — owned at birth — now holds for every model without an exception.
- **Slices 7–8 — `Project`.** Work that completes, inside an Area that never
  does. `Project.area` is required, `Item.project` additive and nullable, so a
  task keeps its Area and may *additionally* join a project. Projects are
  created and finished on the Area page; a task joins one from its own detail
  page.
- **Slice 9 — the interface brief**, plus the single fix in it that had evidence
  behind it: a checklist step's carries-forward control is a `Switch`, so the
  two questions on a step row are told apart by control type rather than by
  their labels alone.

**What it closed.** C2's recorded interface failure, both defects — see *C2*
above, which records how and why.

### What it taught

- **A word in a plan document hid a defect for two slices.** `release-d-plan.md`
  §4 predicted the two-checkbox row would be mechanical "once `is_done` is the
  only boolean on the row." It was not — `carries_forward` stayed on the row as
  a second checkbox. Slice 3's own entry called it a "toggle", and because the
  plan then read as though the problem were solved, nobody checked. **Check a
  plan's predictions against the shipped interface before writing the next plan
  on top of them.**
- **A migration that prints its evidence is worthless if the deploy discards
  it.** `0026` and `0028` printed counts precisely so that running them against
  production would be the evidence no local database could supply. The playbook
  ran migrations through `docker_container_exec`, which captures stdout into an
  unregistered Ansible result, so it went nowhere and `docker logs` never had it
  either. `0026`'s figure was recoverable by counting rows; `0028`'s is gone
  permanently. Fixed the same night in `a6550e4`, and exercised on the second
  deploy while the stakes were a no-op.
- **The nullable-to-required cost is asymmetric, and one slice's experience
  reversed the next slice's design.** Slice 6 spent an entire slice paying it on
  `List.owner`: an audit, a destructive migration, sixteen tests. Slice 7 then
  had to choose for `Project.area`, and `release-d-plan.md` §3 had recommended
  nullable on reversibility grounds — reasoning that inverts once the direction
  is named, since required→nullable is a bare `AlterField` with no data work.
  **The permissive default is the expensive one to undo.**
- **The local database was not evidence, exactly as the plan said.** Local
  development held three lists and zero ownerless rows; production held nine
  areas. Both migrations were written for the general case rather than the
  observed one, and that was right for reasons only visible afterwards.
- **A contract rename lands wider than the plan scopes it.** Slice 4 found
  `daily` and `review` each carrying their own hand-rolled `parent` breadcrumb
  rather than reusing `lists.serializers.serialize_item`; slice 5 found the same
  split for `area_id`. `daily` got the rename for free; `review` needed it
  applied separately. **That difference is the whole argument for the shared
  serializer.**
- **A feature can be write-only if you only build the surfaces that create it.**
  Slice 8 shipped project assignment, and `project` reaches exactly three
  frontend files — not the Agenda, which already renders an area pill and has
  room for a second, nor the Daily Page, the review, or the Archive. Someone can
  put a task in a project and never see that fact again. Found while writing
  slice 9's brief.

### Closed with work outstanding

- **Two migration counts are lost**, per the second lesson above.
- **`ui-second-pass-plan.md` steps 2 to 4 were blocked on evidence, not effort**
  — a project is invisible everywhere a task is worked, and Projects have no
  place in navigation, but both findings came from reading source where C2's
  came from a person failing a real task, and production held zero projects. An
  observational sitting on August 3 confirmed them; F1–F5 all shipped by
  August 6.
- **The vocabulary half of Crane 0** was still deferred at Dunlin's close. It
  had been blocked on knowing what a subtask is, which Dunlin answered.

## Crane — shipped August 2, 2026

`crane` (`e0acf05`) was deployed at 20:05 EDT and marked by
`DEPLOYED-2026-08-02/2005`. Two deploys carried it: 17:54 EDT, which took Crane
0a, 1 and 2 in one run of ten migrations, and the last one, which took Crane 3's
four. The tag went on after production was verified rather than alongside the
deploy, which is the correction Bittern's own record asks for. It closed with
work outstanding by decision rather than omission: the remainder of Bittern's
carried-in checklist, most of which this deploy finally unblocked.

### What shipped

- **Crane 0 and 0a — the repetition domain.** A design brief settling routines,
  targets and occurrences, plus the one half built immediately:
  `RecurringCommitment` and `Item.commitment`, so a recurring task's occurrences
  form a series rather than a chain of rows whose only connection was a matching
  text string. Its backfill linked both repeating tasks in production. The
  vocabulary half — moving `text` and `recurrence` onto a real template — went
  to release D with the parent–child redesign it depends on.
- **Crane 1 — the Daily Page**, in seven slices: a written day, the agenda
  embedded rather than copied, capture, a durable Daily Focus whose
  `released_at` distinguishes a decommitment from an unfinished commitment, the
  Personal Compass, the home surface with a preference to opt back out, and a
  phone-viewport pass.
- **Crane 2 — routines and task age**, in five slices: `Routine` and
  `RoutineOccurrence` with lazily created periods and snapshotted targets,
  correction and skip as distinct statements, routines on the day, pausing that
  keeps what already happened, and how long a task has been waiting said without
  reproach.
- **Crane 3 — the weekly review**, in ten slices: what a week finished, planned
  and made of it, its own words and what is still waiting, a dated review record
  that stamps the figure it concluded from, one explicit decision at a time with
  no bulk reschedule anywhere on the surface, habit performance over the periods
  a week actually asked of, a paused week that says so, a satisfied-but-partial
  close that is not a skip, four weeks of context, and a phone pass.

### What it taught

- **A slice list hides a missing surface unless you look for one.** It had
  happened twice — the Daily Page reachable only by typing its URL until slice
  6, routine creation with no surface at all until Crane 2 slice 3 — so Crane
  3's list was read back for that specific failure before any code was written.
  It found three: the navigation entry, the way to reach the week *before* this
  one, and a control for the new partial close. Reading the list for a known
  failure mode is cheaper than a slice discovering it.
- **A test can be wrong about the world rather than about the code.** Four times
  in this release: an assertion that the week of July 27 was not the current
  one, made on a Sunday inside it; a British date order asserted against a
  locale-following formatter; an unanchored `/all/` matching "Call the bank";
  and a straight apostrophe asserted against the typographic one the application
  renders. Each looked like a defect for as long as it took to read it.
  `principles.md` says to diagnose before editing either side; the corollary is
  that the test is a suspect too.
- **The schema could not answer a question the plan asked.** Slice 9 needed
  "before the account existed" and `accounts.User` carries no creation timestamp
  at all — no `date_joined`, no `created_at` — which a test found by asserting
  against one that was not there. Adding the field would have meant defaulting
  three real accounts to today and marking their whole history prehistoric, so
  the line was drawn at the owner's first trace instead: earliest day written,
  task made, routine kept, thought captured. The better question, arrived at by
  being unable to ask the worse one.
- **A rule emerged that no single slice set out to make.** Released pins,
  skipped periods and periods closed as enough all leave a denominator — three
  decisions taken a slice apart that turned out to be one: *a deliberate
  decision leaves the denominator; only what merely elapsed stays in it.* It is
  written that way in the code rather than as three subtractions, so the next
  decision-shaped outcome inherits it.
- **A guard that has never been seen red is a claim, not a check.** Three passed
  on their first run this release — that nothing in the review mutates a task,
  that the pause backfill seeds what it should, and that the page does not
  scroll sideways at 375px. Each was made to fail on purpose before being left
  alone.
- **Running the tests does not migrate the development database.** The first
  browser check of the review record failed with `no such table` on a suite
  green for an hour, because tests build their own database and `migrate` had
  never been run against the dev one. The page said "Couldn't reach Clarice"
  with a retry rather than rendering blank — B2.1's fix doing precisely what it
  was built for, an unplanned confirmation of an earlier release from a mistake
  in this one.

## Bittern — shipped August 2, 2026

`bittern` (`359a7e3`) was deployed at 00:35 EDT and marked by
`DEPLOYED-2026-08-02/0035`. Three deploys carried the release: 11:56 EDT on
August 1 (`fed210b`), 21:51 EDT that evening, and the last one, which was the
only one to carry B2.1 and B2.2 — their commits landed after the second deploy,
and an earlier claim that Bittern was already live rested on `/contact/`
returning 200, which proved B3 and nothing else.

It closed with work outstanding by decision rather than omission: five
after-deploy checks never run, three infrastructure confirmations owed, and
several Android gaps. All were carried into Crane.

### What shipped

- **A native Android capture client** (`android/`, M1–M5). Personal access token
  authentication, capture online or offline, a durable encrypted queue drained
  in the background, a share target, and idempotent writes that cannot duplicate
  a thought. 143 JVM tests and 16 instrumentation tests.
- **Per-user time zones.** Left the deferred list the day both halves of its
  trigger fired: a second active user in Indonesia, and a digest delivering at
  03:00 Eastern.
- **Web session and state gaps closed** — B1's spawned recurring subtasks, B2's
  SPA logout, B2.1's failure states, B2.2's browser smoke coverage.
- **Branded email and a contact path** (B3), and **production error monitoring**
  (B4).
- **B0** — the missing side navigation, diagnosed and fixed; see below.

### What it taught

- **A phone was the first thing to discover a production contract gap.** The
  Android client's first real connection failed because the bearer-auth
  `/api/v1/me` endpoint was still only on `main`. The token was always valid.
  Check the deployed OpenAPI schema before pointing a client at an endpoint, not
  after. B0.1 exists because of this.
- **Verification tooling can lie.** The script written to prove production's
  duplicate protection matched `"id":[0-9]*` against an API that renders
  `"id": 2`, extracted nothing from either response, compared the two nothings,
  and announced that production was broken — over evidence in its own output
  showing it working. Assert on values you have proven you can parse.
- **Rebuilding a state object silently drops fields.** Twice in one evening: a
  pending count left standing over an emptied queue, and a keyboard preference
  reverting on every capture. Neither would ever be reported as a bug; people
  would just quietly stop trusting the app.
- **Some defects only exist on hardware.** Background delivery worked on its
  first real attempt, and the count on screen did not update, because a screen
  cannot see a background drain. Every unit test asserting that count was
  correct.
- **A marker has to be something the change introduced.** Checking whether B2.1
  was deployed, `Something went wrong.` was found in the served bundle and
  nearly taken as proof — it predates B2.1 by months. `RequestFailed`, which
  B2.1 actually added, was absent. The weaker check would have confirmed a
  deploy that never happened, and the same instinct produced a premature
  "Bittern is live" in these documents an hour earlier.
- **`state: latest` on an infrastructure package** means a routine deploy is
  willing to upgrade — and so restart — the thing running the application. The
  "Install docker" task looked hung on three separate deploys and was cancelled
  each time; it was never hung, just resolving upgrade candidates on every run.
  Fixed in `fed210b` with `state: present` and `cache_valid_time: 3600`, and the
  commands to check before cancelling an apt task are in `CLAUDE.md`.
- **Isolating one half of a store's identity is isolating neither.** The
  instrumentation tests parameterised the Keystore alias but not the preference
  file, so running them deleted a live token off a real phone.

## Albatross — shipped July 31, 2026

`albatross` (`f5ddb85`) was deployed at 22:24 EDT and marked by
`DEPLOYED-2026-07-31/2224`. It carried seven migrations, taking the schema from
53 to 60 without changing existing rows.

### Platform and production work

- Replaced the task UI with a React Router/TanStack Query SPA backed by a Django
  Ninja `/api/v1/` contract and generated TypeScript types.
- Moved production from bind-mounted SQLite to managed Postgres.
- Added GitHub Actions: Django tests against Postgres, frontend tests and builds
  on every push and pull request.
- Restricted the application to a dedicated Postgres database user, proved the
  backup/restore path against a cloned managed database, and closed the database
  firewall to the application droplet. Grants are not ownership; Django
  migrations required correcting table ownership.
- Added the daily-digest cron job, verified by dry run. Its first unattended
  fire was 07:00 on August 1, 2026; "runs as root from cron on a schedule" has a
  failure mode that "prints to stdout when I run it" does not, so it was not
  proven until that run was checked.
- Added self-service password reset, including live validation of lockout
  behaviour, and production-ready static asset handling through Docker,
  Gunicorn, WhiteNoise, nginx and Ansible.
- Added an adversarial per-user isolation suite, including id-based task/list
  and subtask cases.

### Task and agenda work

- Added archive/restore state handling and snooze presets.
- Added notes as plain text on task detail.
- Added one-level subtasks with duplicate protection, ordering, ownership
  isolation, archive/restore, completion, recurrence, and undo behavior.
- Added `always_recurs` to decide which subtasks return with a recurring parent,
  plus the follow-up fix that prevents completed children from being orphaned
  when their recurring parent archives.
- Added persistent SPA navigation in source. Its absence in production was
  Bittern B0 — the deployed bundle was never the problem. Direct Inbox and Ideas
  links on the Agenda workspace mitigated it only once the current bundle was
  deployed; they did not replace B0's diagnosis.

### Capture and account work

- Added Capture: a zero-friction, owner-scoped inbox for untriaged thoughts, and
  triage into a task, an Idea, or a discarded record, with undo. The planned
  two-week usage checkpoint was dropped as a release gate — the triage model had
  enough direct product conviction to ship.
- Added Ideas with exploring/reference states, notes, edit/delete, and promotion
  to a task.
- Added personal access tokens and `POST /api/v1/capture` for non-browser
  capture clients, plus account themes and daily-digest preferences.

Track A (infrastructure and public-readiness, A0–A6) and Track A Next (the
task-model queue) both closed here. Track A Next's one deliberately unscoped
consequence — a spawned recurring task not serializing its copied subtasks, so
they appeared only after a refresh — was closed as Bittern B1 on August 1, 2026.

## Bittern B0 — the missing side navigation, diagnosed August 1, 2026

B0 existed to decide between two causes: a stale or mispackaged frontend bundle,
or a current bundle failing at runtime.

**The artifact was never the problem**, and the stale-artifact branch was closed
on read-only evidence gathered before any redeploy. The served
`app-shell.b94af7d63d1b.js` was what the deployed `staticfiles.json` mapped
`app-shell.js` to, so it was what `app_shell.html` referenced, and its
`Last-Modified` was the `DEPLOYED-2026-07-31/2224` deploy; it carried
every navigation string and, correctly, no `Log out`, since B2 was unbuilt; the
served `app.css` was byte-identical to a local build; and `AppLayout`, `SideNav`
and `sidenav.module.css` were unchanged between `f5ddb85` and `main`.

**The cause.** `AppLayout` wrapped `SideNav` in a `<details>` that nothing ever
opened, while `sidenav.module.css` hid its `<summary>` unconditionally. Above
the breakpoint the nav was sealed inside a closed disclosure with no handle to
open it — the source comment asserted "above it the nav is always open," but no
code implemented that. A closed `<details>` has its contents skipped, so the
element collapsed to zero height. Measured on the live page:

```text
detailsBox: 210x0     <- the empty gutter the user could see
navBox:     210x306   <- a skipped subtree keeps its geometry
shellCols:  210px 1814px
```

Firefox does not paint skipped content, so the column was simply empty. Chromium
148 still paints it, which is why the same page looked correct in Edge and on a
Chromium phone, and why the defect shipped.

**Why no test caught it.** `SideNav.test.tsx` renders the component directly,
never inside the `<details>`, and jsdom has no paint model in any case — the
condition is invisible to unit tests by construction. `AppLayout.test.tsx` now
asserts the invariant that was violated: above the breakpoint the disclosure is
open, and stays open across navigation. Proving what a person actually sees
needed B2.2's browser-level coverage.

**The fix, and its verification.** The layout holds the disclosure open above
the breakpoint via `matchMedia` rather than depending on how an engine treats a
closed one, and only closes on navigation when narrow; with the patch the
disclosure's own box goes from `210x0` to `210x145`, matching its content.
Deployed at 11:56 EDT on August 1; the served bundle rotated to
`app-shell.98590f71d7af.js`, byte-identical to a local build of the same source
and carrying the fix's own `min-width: 761px` breakpoint. An authenticated visit
confirmed the nav down the left above the cutoff, collapsing into the ☰ menu
below it. B0 closed.

**A false trail worth keeping.** The first reproduction reported the nav as
"visible" in every browser, which discarded the correct hypothesis for most of
the investigation. The instrument was wrong: it tested
`getBoundingClientRect().width > 0 && height > 0`. **A layout box is not paint.**
Content skipped by a closed disclosure keeps its geometry, so the probe answered
"visible" for something invisible on screen, and the user's own report was
trusted less than a faulty measurement. The signal that finally settled it was a
container measuring `210x0` while its child measured `210x306` — a contradiction
that can only mean skipped content.

## Decisions and lessons retained from the work

### Product decisions

- Capture never forces categorization at entry time; triage decides whether a
  thought becomes a task, an Idea, or nothing worth keeping.
- An Idea is not a task without a due date. It has a distinct lifecycle and can
  later promote into a task, carrying its notes with it.
- The task UI is now SPA-only. Capture and account surfaces can remain
  Django-rendered where that is the better fit.
- The agenda is a date-based cross-list view; lists are navigation targets, not
  agenda filters in the persistent navigation.

### Engineering lessons

The ones that are not already stated in a release section above:

- A deployment task is not proven until it has run against production.
- Test against the same database family and relevant version as production.
- A clean hard refresh does not prove the deployed frontend image contains
  current source. Inspect the served bundle when UI source and production
  disagree.
- Markup must not depend on how an engine renders a closed `<details>`. Engines
  differ and are still converging; a layout that only works in the browser it
  was built in will look correct to whoever built it.
- Every id-taking surface requires direct per-user isolation tests, not just
  trust in a general ownership convention.

## Release conventions

Releases use alphabetic bird names. What each tag means is in `CLAUDE.md`; the
letter sequence, which bird holds which letter, and **which deploys earn a bird
at all** are in `roadmap.md` under *Release practice*. None of it is restated
here. A letter is never reused: a follow-up production release receives the next
bird name, even if it immediately corrects the last.

**A codename with no entry here fails a test.**
`clarice/tests/test_every_release_is_in_the_record.py` reads the annotated tags
and this file, and fails when a release has a name and no narrative. It found
`godwit` and `ibis` on the day it was written — the merger and the code review's
defect list, both with entries that never said which bird they were — after an
audit had already found `osprey` and `petrel` with no entries at all. **A guard
rather than an inventory**: an inventory would list the four, and the guard
notices the fifth. It selects on the tag being **annotated**, which is the rule
`CLAUDE.md` already states, so a lightweight working marker is invisible to it
without needing an exception list.

~~a release receives three tags — `LIVE`, `DEPLOYED-<date>/<HHMM>` and the bird
codename — after it is verified in production.~~ **Struck August 26, 2026**,
because it said every verified deploy is a release and the practice never was.
**Fourteen of thirty-six deploys carry a bird**, so the selection was real from
the beginning and only the criterion was missing — which is how three deploys
came to be absent from this file at once. The criterion now exists and lives in
`roadmap.md`.
