# Crane — forward plan

Vince · plan for the next release · drafted August 2, 2026

## 1. Purpose and scope

Crane is the release that makes the Daily Page Clarice's home surface. This
document is the forward plan for it: the work Bittern closed with rather than
finished, a settled design for the repetition domain the vision document
requires before any of it is built — routines and targets, plus the recurring
commitments the brief widened to cover on August 2, 2026 — an ordered slice
sequence for the Daily Page foundation itself, what is deliberately not part of
this release, and the decisions it deferred to Vince — all of which were
answered on August 2, 2026 and are kept in §6 as a record. It does not
restate `daily-operating-system-vision.md`'s product direction or
`principles.md`'s delivery practices — both are read alongside this, not
duplicated into it.

## 2. Carried in from Bittern

Bittern closed on August 2, 2026 with this work outstanding by decision, not
omission. None of it blocks Crane 0's design work; none of it should be
allowed to quietly drop off either. Most items are a single production check,
not a design or implementation task. **Sequencing settled August 2, 2026:
clear them at the next deploy, in one pass.** Nine of the fourteen cannot be
done without one — every production verification, every infrastructure
confirmation and the digest — so doing them beforehand was never actually
available. The five Android gaps need a phone rather than a deploy and are
independent of it. Reasoning in §6.

### Production verifications never run

Each is already deployed and covered by a test; nobody has watched it happen
in production.

**Four of the five were cleared on August 2, 2026**, in the session that
deployed Crane 0a, 1 and 2 — which is the sequencing §6 predicted, since a
deploy is the only thing that makes them possible. The fifth is still open
and is still blocked on the same thing it was always blocked on: setting up
a recurring parent with an opted-out subtask takes three attempts through
the interface C2 found, and that is the UI overhaul's problem rather than
this checklist's.

- [x] Log out at desktop and narrow widths, then confirm protected API calls
  fail afterwards. (B2) — August 2, 2026.
- [x] Hard-refresh `/app/agenda` and confirm navigation content and counts
  render. (B0) — August 2, 2026.
- [x] Visit a deliberately broken route, `/app/task/999999`, and confirm it
  says what went wrong and offers a way out rather than rendering blank.
  (B2.1) — August 2, 2026.
- [x] Send an Android capture after the redeploy and confirm the client still
  reaches production. — August 2, 2026.
- [ ] Confirm B1's opt-out rule in production: a subtask with `always_recurs`
  false does not clone onto the parent's next occurrence. Three attempts
  to set this up by hand failed on the interface, not the rule — expect
  the same friction and route around it rather than reopening C2's
  finding here.

### Infrastructure confirmations owed

All three share Bittern's recurring failure mode: they look like success
until somebody checks.

- [ ] A forwarded contact message arrives in the inbox rather than spam, now
  that DMARC enforces.
- [ ] DMARC aggregate reports begin arriving at `dmarc@vinclarice.com`.
- [ ] A real production 500 reaches Sentry, not only the controlled probe.

### The New York morning digest

Separate from the two groups above because half of it is already proven: the
Makassar account's digest fired at its own 07:00 on August 2 while the
`America/New_York` accounts stayed on the previous day, which is the evidence
that the job discriminates by user. What has not been seen is the other
side of the same day.

- [ ] Confirm both `America/New_York` accounts received their digest at
  07:00–12:00 EDT on a day where the Makassar account's window has
  already closed, completing the pair of observations B started on
  August 2.

### Android gaps

Recorded in `bittern-plan.md`; none block Crane, all are real gaps in what
has been exercised.

- [ ] Run the app in an emulator at least once.
- [ ] Exercise the forced-retry path on a physical device (only network
  interruption has been tested there so far).
- [ ] Test a plain-text share on hardware.
- [ ] Test an offline share on hardware.
- [ ] Set up release signing — without it the APK cannot be given to anyone
  but the person who built it.

One item is not on this checklist because it is a deliberate deferral, not an
owed confirmation: there is still no way to discard a rejected capture from
the client. That was a conscious call while the app is a prototype and stays
parked unless Crane's own work touches that flow.

## 3. Crane 0 — the repetition domain

This is a design brief. It settles the shape of the domain so Crane 2 can
implement it later; it produces no migration. The model sketch below is
illustrative of the shape, not final code to merge.

Its scope widened on August 2, 2026, from routines alone to repetition
generally, and was then **settled narrower than it was proposed** — see "The
recurring-commitment half" below and the decision recorded in §6. The three
cases named in `daily-operating-system-vision.md` — a lesson target, a daily
exercise target, a weekly practice target — are what the routine half has to
survive; the commitment half carries its own acceptance example.

### The five settle points

**Routine template shape.** A `Routine` belongs to one owner, has a title,
an active/paused flag (paused rather than deleted — the person intends to
come back to it), a cadence, a target quantity, and an optional human unit
("lessons", "sessions"; blank means the target is a plain yes/no for the
period). Cadence starts at exactly two values, daily and weekly — the two the
vision doc's cases require. Monthly is not modeled yet; adding a third
`TextChoices` value later is additive, the same shape of decision
`Item.Recurrence` already made when monthly joined daily and weekly.

**`RoutineOccurrence` record.** One row per routine per period (a day, for
daily cadence; a week, for weekly), holding its own copy of `target_quantity`
and `unit` at creation time, plus `progress` and an outcome of
open/completed/skipped. The copy matters: if a lesson routine's target
changes from 5 to 3 next month, last month's occurrences must go on reading
"4 of 5," not be silently recalculated against the routine's current
setting. This is `principles.md`'s durable-history rule applied directly —
the same reasoning that keeps a completed task's history from being rewritten
when its list or recurrence changes later.

**Cadence, logging, correction, and skip semantics.** Occurrences are created
lazily — on first log or first view of a period, not by a nightly job that
pre-creates a row for every routine every day. That is a smaller, more
reversible piece of infrastructure than a scheduled job, and Crane 0 does not
need to commit to one before real use says a "you haven't logged anything
today" prompt is worth building.

Logging is an explicit action that adds an amount (default 1) to the current
period's `progress`, creating the occurrence if it doesn't exist yet.
Reaching `target_quantity` sets outcome to completed automatically; there is
no separate "mark done" tap once the count is there. Correction is the same
write path with a different amount — the owner can log after the fact or fix
a mis-tap by adjusting `progress` directly, and if a correction drops
`progress` back under target, outcome reverts from completed to open rather
than staying stuck at a count that's no longer true. Skip is a distinct
action, not silence: setting outcome to skipped is how "I chose not to
today" gets recorded as different from "I meant to and didn't." An
occurrence whose period ends with neither target reached nor a skip
recorded simply stays open — that is a fact about what happened, not an
automatic "missed" verdict the system asserts on the person's behalf. That
follows `principles.md`'s "Automations propose; people decide" and
`daily-operating-system-vision.md`'s design principle to "let history be
useful without making missed work feel like punishment": Crane 3's weekly
review is where an elapsed-open occurrence gets described, not where it gets
silently relabeled.

**Per-user time-zone requirements.** This is inherited, not new work. Any
session-authenticated request already runs with the requesting user's zone
activated (`per-user-time-zones-plan.md`), so a daily occurrence's period is
just `timezone.localdate()` read once at the log/view boundary, the same
inject-the-clock pattern the agenda already uses. The one boundary carried
over unchanged: a future token-authenticated logging endpoint (if routines
are ever logged from the Android client) would have to activate the owner's
zone itself, exactly as that plan already flags for capture.

**The boundary with recurring tasks.** Restated concretely: a routine
measures repeated practice toward a quantity over a period; a recurring task
represents one discrete commitment whose completion creates the next
occurrence. A `Routine` never spawns an `Item`, and completing an `Item`
never creates a `RoutineOccurrence` — they are peer domains with their own
life cycles, not a hierarchy or a shared table. Five daily lesson sessions
are a `Routine`, not five `Item`s and not `Item.Recurrence.DAILY` on one task
standing in for a count it was never designed to hold.

### Data model sketch

```python
# routines/models.py

class Routine(models.Model):
    class Cadence(models.TextChoices):
        DAILY = "daily", "Every day"
        WEEKLY = "weekly", "Every week"

    owner = models.ForeignKey(
        "accounts.User", related_name="routines", on_delete=models.CASCADE
    )
    title = models.CharField(max_length=200)
    cadence = models.CharField(max_length=10, choices=Cadence.choices)
    # Integer, not decimal: every named case (lessons, a yes/no move-today,
    # weekly sessions) is a count. Add a duration/decimal unit later only if
    # a real routine needs one -- see design/principles.md on not optimizing
    # an imagined workflow.
    target_quantity = models.PositiveIntegerField(default=1)
    # Blank means the target is a plain yes/no for the period, not a count
    # of something -- the daily-exercise case.
    unit = models.CharField(max_length=40, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class RoutineOccurrence(models.Model):
    class Outcome(models.TextChoices):
        OPEN = "open", "Open"
        COMPLETED = "completed", "Completed"
        SKIPPED = "skipped", "Skipped"

    routine = models.ForeignKey(
        Routine, related_name="occurrences", on_delete=models.CASCADE
    )
    # The local date a daily occurrence covers, or the Monday that starts
    # the week a weekly occurrence covers -- see the open question below.
    period_start = models.DateField()
    # Copied from the routine at creation time and never re-read from it,
    # so a later change to the routine's target cannot rewrite a past
    # occurrence's meaning. See "Preserve durable records" in principles.md.
    target_quantity = models.PositiveIntegerField()
    unit = models.CharField(max_length=40, blank=True, default="")
    progress = models.PositiveIntegerField(default=0)
    outcome = models.CharField(
        max_length=10, choices=Outcome.choices, default=Outcome.OPEN
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("routine", "period_start"),
                name="unique_routine_occurrence_period",
            ),
        ]
```

### Acceptance examples

**A lesson target.** `Routine(title="Practice Spanish", cadence=DAILY, target_quantity=5, unit="lessons")`. On August 3rd local time, the owner logs
2 lessons in the morning and 3 more that evening; the occurrence for
`period_start=2026-08-03` reaches `progress=5`, and its outcome flips to
completed with `decided_at` stamped, without a separate "mark done" action.
August 4th starts its own occurrence at `progress=0` — logging that day never
touches the 3rd's row. If the owner later realizes they only actually did 4,
correcting the 3rd's progress down to 4 reverts its outcome from completed to
open.

**A daily exercise target.** `Routine(title="Move today", cadence=DAILY, target_quantity=1, unit="")`. There is nothing to count, so one log call
(amount defaults to 1) both creates the day's occurrence and completes it.
The blank unit is what distinguishes this from a count-based routine at the
domain level; how that difference should render (a toggle versus a running
number) is a Crane 2 UI decision, not settled here.

**A weekly practice target.** `Routine(title="Guitar practice", cadence=WEEKLY, target_quantity=3, unit="sessions")`. The owner logs one
session Monday and one Wednesday of the week starting August 3rd; that
occurrence sits at `progress=2`, outcome open, all week — there is no
sub-weekly partial state. If they explicitly decide not to practice at all
that week, skipping sets the whole occurrence to skipped regardless of the
partial progress already logged, which is different from Sunday night
arriving with `progress=2` and nobody having skipped: that occurrence simply
stays open, a fact the weekly review can report ("2 of 3") without asserting
the week was a failure. The following Monday begins a new occurrence at
`progress=0` independent of how the previous one ended.

### The recurring-commitment half

Crane 0 was originally scoped as routine design alone. Widening it to cover
recurring commitments was proposed here, and on August 2, 2026 it was accepted
in a narrowed form: the identity problem is solved now, the vocabulary problem
stays at release D. The decision and its reasoning are in "What was decided"
below. The argument for widening at all is that the shape settled above is
exactly the shape recurring tasks are missing.

`lists/services.py`'s `_spawn_next_occurrence` creates a recurring task's next
occurrence with `Item.objects.create(list=..., text=..., due_date=..., recurrence=..., position=...)`, then copies the tag set and clones the
carried-forward children with their own notes, position and `always_recurs`.
What it never writes is a reference back to the item it came from. Content
carries forward; identity does not. The only thing marking occurrence five of
"Pay rent" as the same commitment as occurrence four is a shared text string in
one list — rename the task and the series splits silently in two, change its
cadence and nothing records that it was ever weekly.

**What breaks, stated precisely.** Not Crane 3's whole weekly review. Its
specified gathering — "completed work and recurring commitments from the
preceding week" — is a one-week query over completion timestamps, and today's
schema answers it. What today's schema cannot do is assemble occurrences into a
series across weeks, which is every trend, streak and completion rate the
vision document asks for immediately afterwards, and the reason that document
insists habit metrics "must not infer a habit from a recurring task's current
state after history has changed." Routines will be able to answer those
questions on the day Crane 2 ships. Recurring commitments will not, for the
same questions, unless this is designed now.

**What was originally proposed.** A recurring commitment becomes a durable
template — owner, text, list, cadence, tags, notes, and whatever a subtask
template turns out to be — and each occurrence becomes a task pointing back at
it through a nullable foreign key. That is the full shape, and it is still the
destination. It is not what ships in Crane.

**What was decided, August 2, 2026.** The proposal bundled two changes that
have different costs and different deadlines, and it is taken apart here.

- **The identity half — accepted, and built now.** A `RecurringCommitment`
  record that holds nothing but owner and lifespan, plus a nullable
  `Item.commitment` foreign key that `_spawn_next_occurrence` writes. Purely
  additive: no field leaves `Item`, no API contract changes, no client work.
  It buys series identity, which is the whole of the analytical argument.
- **The vocabulary half — deferred to release D.** Moving `text`, `list`,
  `cadence`, `tags` and `notes` off the occurrence and onto the template. That
  buys model cleanliness rather than answerable history, and it collides
  head-on with the parent–child redesign already scheduled for D — a
  commitment template has to say what a subtask template is, and D is where
  what a subtask *is* gets decided. Doing it in Crane would mean answering
  that question twice.

**Why the identity half could not wait.** Not because the loss is infinite —
it isn't. Every occurrence spawned after the key exists is linked, so the
unrecoverable history is exactly what accrues between now and the day it
ships. That is a clock, not a deadline, and today the hand is barely moving:
three users and a two-week-old migration history. What changes it is Crane
itself. Crane 1 through 3 is the work that turns Clarice into a daily
practice, and Crane 3 is the first feature that reads the history back. Ship
the Daily Page first and the busiest stretch of recurring history is also the
unlinked stretch — the accrual rate rises at precisely the moment the record
starts mattering. Cheaper to spend a day now than to explain a gap later.

**Why the "designing it twice" argument did not carry the decision.** It was
the headline case for widening and it is weaker than it reads. The two halves
share no table and no base class — §4 rule 8 of
`architecture-trajectory.md` explicitly prefers "a documented convention rather
than an abstract base class" — and that convention is *already written down* in
rule 8. Designing the commitment half at release D would be applying a recorded
rule, not rediscovering a shape. What justified acting now was the accrual
clock above, not the duplication.

**The thin template is deliberate, and is a partial application of rule 8.**
Rule 8 asks for a template that holds the rule and occurrences that hold what
happened. Here the template holds only identity; the rule stays on `Item` until
D. Recorded as a conscious partial application rather than an oversight,
because the alternative — copying `text` and `cadence` onto the template while
`Item` still carries them — would create exactly the two-sources-of-truth drift
that `principles.md` forbids. One authority, and it stays where it is until the
whole vocabulary moves at once.

**What stays separate.** A routine and a recurring commitment share a shape,
not a table. A routine accumulates progress toward a target across a period and
can be partially met; a commitment is discrete and either done or not. They are
siblings under one pattern — a template holds the rule, a dated occurrence holds
what happened, and the occurrence snapshots what was expected of it — which is
what lets one review layer read both. Merging them into a single "repeating
thing" model would rebuild the overload this is escaping.

**What is deliberately not settled here.** Nothing leaves `Item` — that was
true of the original proposal for everything except recurrence, and under the
narrowing it is true of recurrence too. What a subtask *is* stays with the
parent–child design cycle named in §5; archival and the ordinary task fields
are untouched. The routine half of this section remains a brief and produces
no migration; the identity slice below is the one exception, and it is small
enough to be specified here rather than deferred to a document of its own.

**Acceptance example.** "Pay rent" is monthly. It is completed in June, July
and August; in September its title is edited to "Pay rent — new landlord" and
completed again. A query for the series returns four occurrences in order, the
September one carrying the new text and the earlier three carrying the old,
because every one of them points at a single template rather than matching on a
string. Today that same query returns a series of three and a series of one,
with nothing to indicate they were ever the same commitment.

**Noted while writing this, and separable from it — since fixed.** The spawn
copied each child's `notes` explicitly and never the parent's own, so a
recurring task with notes lost them on every cycle. That was a bug with a
regression test rather than a design question, and it was fixed as one on
August 2, 2026 without waiting on the widening: `_spawn_next_occurrence` now
passes `notes` for the parent too, and
`RecurringParentTest.test_a_recurring_task_keeps_its_own_notes_on_the_next_occurrence`
holds both halves of the symmetry.

### Crane 0a — the identity slice

**Shipped August 2, 2026** — migrations `0022`–`0024`, deployed to
production at 17:54 EDT the same day, where `0023` backfilled both existing
repeating tasks and every series gained an identity. The accrual this slice
was justified by stops running from there. The one piece of Crane 0 that
produces a migration, and it
ran ahead of Crane 1 for the accrual reason above: cheap that day, and more
expensive every week the Daily Page drives real use. It was never a Daily Page
slice and never belonged in §4's ordering.

**The model.** `RecurringCommitment` — a non-null `owner` (charter rule 1;
note it does *not* reach its owner through `List`, whose own `owner` is still
nullable), `created_at`, and a nullable `ended_at`. Nothing else. It is an
identity anchor, not a template, per the note above.

**The link.** `Item.commitment`, a nullable foreign key with `related_name="occurrences"`. Null means an ordinary one-off task, which is
what the overwhelming majority of rows will keep meaning. `on_delete=RESTRICT`:
`SET_NULL` would silently turn a series back into unrelated one-offs, which is
the exact failure being fixed, and `CASCADE` would let deleting one record take
years of tasks with it.

**`PROTECT` was the first choice and it was wrong**, recorded here because the
distinction is not obvious and the next person will reach for it too. `PROTECT`
refuses the delete even when the referring task is going in the same cascade,
so deleting an account raised `ProtectedError` instead of removing it — an
owner's commitments and their tasks both go, and `PROTECT` does not care that
the referrer is on its way out. Account deletion is a roadmap item, so this
would have surfaced later as a feature that could not be built. `RESTRICT`
permits exactly that case and still refuses a bare commitment delete. Nothing
in the suite caught it because nothing deleted a user; `test_commitment_deletion`
now does.

**Where the link gets written.**

- `create_item` with a non-`NONE` recurrence on a root creates the commitment
  and links the task.
- `set_recurrence` from `NONE` to a real cadence creates and links it.
- `set_recurrence` back to `NONE` stamps `ended_at` and **keeps the link** —
  the past occurrences are still members of that series, and clearing the key
  would rewrite history to say they never were.
- Setting a cadence again on a task that already has a commitment clears
  `ended_at` and reuses it rather than starting a second series. A pause and a
  resume are one commitment with a gap, and the gap is already visible in the
  occurrences' due dates.
- `_spawn_next_occurrence` copies the completed occurrence's commitment onto
  the new one.

**Legacy rows, and the honest limit.** Recurring tasks that already exist have
no commitment and cannot be given a shared one retroactively — that is the
irrecoverable part, and it stays irrecoverable. Two consequences are handled
rather than ignored. A data migration gives every existing recurring root its
own commitment, so series begin accumulating from today instead of from each
task's next completion. And `_spawn_next_occurrence` creates one on demand if
a completed recurring task somehow still lacks it, linking both the completed
task and its new occurrence, so no path leaves the accrual running.

**Deliberately not attempted:** reconstructing past series by matching on
`(list, text, recurrence)`. At twenty-four rows it would mostly work, which is
what makes it tempting. It would also silently merge two genuinely distinct
tasks that share a title, and silently split any series whose text was ever
edited — inventing history that reads exactly like the real thing. A gap that
is visibly empty is worth more than a reconstruction nobody can audit.

**Charter compliance, stated rather than assumed.** Rule 1: satisfied, direct
non-null owner. Rule 2: no UUID — commitments are never created offline by a
client, and Android captures only. Rule 3: satisfied without new fields, since
each occurrence is already its own snapshot of the text, due date and cadence
it ran under. Rule 4: mutations go through `services.py`; no read module yet,
because nothing reads a series until Crane 3. Rule 6: a bare hard delete is
refused by `RESTRICT` while an account deletion still cascades cleanly, and
there is no offline client to strand. Rule 7: an
explicit `(commitment, created_at)` index, which is the series-ordered read
release F will run. Rule 8: partially, by design — see above.

**Acceptance — met.** The "Pay rent" example above, asserted end to end in
`test_recurring_commitments.py`: four monthly occurrences, the fourth renamed,
all four returned in order by one query against a single commitment. Before
this slice that same query returned a series of three and a series of
one, with nothing connecting them.

### Open questions this design leaves for Crane 2

- ~~**Which weekday a weekly occurrence starts on.**~~ **Settled: Monday**,
  and this entry's premise was wrong. `lists/agenda.py` already resolves the
  snooze menu's "Next week" to the coming Monday, so the product has been
  saying a week starts there since Albatross. The observation about
  `Item`'s rolling seven days stands and is not a counter-example — that is
  recurrence arithmetic, not a claim about when a week begins. Full
  reasoning in §6.
- ~~**Whether progress needs an entry-level audit trail.**~~ **Settled: no,
  with a trigger.** A single mutable integer answers every question the
  vision document and `architecture-trajectory.md` §4 currently ask of
  routines, and an entry-level log is additive whenever one of them changes
  — unlike the missing foreign key, which could not be invented after the
  fact. §6 records the reconsideration trigger.
- **What a paused routine's gap means for review.** Pausing an active
  routine stops new occurrences from being created; it does not touch
  occurrences that already exist. What Crane 3's weekly review says about a
  paused week — silence, or an explicit "paused" note distinct from an
  elapsed-open occurrence — is not decided here.
- **A satisfied-but-partial close.** The model gives exactly two ways an
  occurrence leaves open: reaching `target_quantity` (automatic) or an
  explicit skip. There is no path for "I did some of it and I'm satisfied,
  close it as-is" — neither a full completion nor a skip, but a common real
  case. Whether that needs a third outcome, or is better handled as a skip
  with progress already logged (the weekly example above already reads that
  way informally), is not settled here.

## 4. Crane 1 — Daily Page foundation

**All seven slices shipped August 2, 2026**, in order, each with its
acceptance condition verified in a real browser rather than only in tests,
and **deployed to production at 17:54 EDT the same day** — see §7 for the
deploy's own verification.

Two things worth carrying forward. Slice 6 found that slices 1–5 had built a
surface reachable only by typing its URL, which is why the side nav now
carries Today; a home surface with no way in is the kind of gap a slice
sequence can hide from itself. And slice 7's phone pass found the page sound
at 375px but the application's touch targets well under the 44px guideline —
older than Crane, owned by the UI overhaul, and recorded with measurements in
`roadmap.md`'s mobile web entry.

Ordered as the thinnest usable path first, per `principles.md`'s vertical-
slice practice: each slice below is something a person can actually do,
not a layer of the stack finished in isolation. Later slices depend on
earlier ones existing; none depends on Crane 0's routine work, which is why
routines are Crane 2. None depended on Crane 0a either — that slice ran first
for the accrual reason given in §3, not because anything here needed it.

1. **Write today.** An owner-scoped, date-unique Daily Entry record with
   plain-text intentions, gratitude, and happenings fields, reachable at a
   dated route. *Acceptance:* a person writes an intention and a gratitude
   line, reloads the page, and both are still there; a second user viewing
   the same calendar date sees their own entry, never the first user's.
2. **See today's work without leaving the page.** Embed the existing agenda
   query as the Daily Page's Action Items, reusing `agenda.py` rather than
   copying task state onto the entry. *Acceptance:* completing a task from
   the ordinary Agenda view is reflected in the Daily Page's Action Items on
   next load, because both read the same task, not a duplicate.
3. **Capture from today.** Add the same capture affordance already proven
   elsewhere directly to the Daily Page. *Acceptance:* a thought typed on
   the Daily Page appears in Inbox triage, indistinguishable in the triage
   flow from one typed on the Inbox's own form.
4. **Pin work to today.** A Daily Focus join between a Daily Entry and an
   existing task — "pin this to today" — with its own order and selection
   timestamp, rendered above the broader Action Items so the day's
   deliberate choices are visually distinct from the full agenda.
   *Acceptance:* pinning a task changes none of the task's own due date,
   status, or ownership; removing a pin keeps enough of the record that a
   later review can tell an intentional unpin from a task that was simply
   never finished.
5. **See the compass, not just the day.** A rarely edited, user-level
   Personal Compass (purpose statement and guiding question), displayed on
   the Daily Page but stored and edited once, not copied into each day's
   entry. *Acceptance:* editing the Compass changes what every day's page
   shows going forward, including past dates viewed again, without writing
   anything into those days' own records.
6. **Make it the front door, and let people close it.** Route an
   authenticated session to the Daily Page by default on login, while
   Agenda, Inbox, Ideas, lists, and archive remain directly reachable from
   navigation exactly as before — **and add a landing-surface preference so
   anyone who prefers the Agenda can have it back.** Decided August 2, 2026;
   see §6. That makes this slice a User field alongside `daily_digest` and
   `time_zone`, a control on the existing account settings page, and a
   default the login redirect reads — not a hard-coded route change. The
   default is the Daily Page, so the product still states a preference
   rather than shrugging.
   *Acceptance:* a fresh login lands on today's Daily Page; setting the
   preference to Agenda makes the next login land there instead; navigating
   directly to `/app/agenda` still works unchanged for anyone who prefers it.
7. **Prove it on a phone — done, and it measures rather than eyeballs.**
   Six tests at 375×812 against the built bundle: horizontal overflow
   asserted as a number (and naming the offenders when it is not zero), no
   control past the right edge, every section present, the day writable and
   savable, a thought capturable, and Today reachable from behind the phone
   disclosure. All passed on the first run, so the overflow assertion was
   deliberately made to fail once — a 900px element injected, caught as
   "scrolls 525px sideways" — rather than trusted.
   A browser-smoke pass at a phone viewport against
   the built bundle, covering the assembled page from slices 1–6 rather than
   any one field in isolation — each slice above is built mobile-aware as it
   lands, per the vision doc's instruction not to retrofit this surface, but
   this is the first point there is a whole page worth measuring against a
   narrow width. *Acceptance:* Compass, Focus, Action Items, the Daily
   Entry fields, and capture all render usably (no horizontal scroll, no
   clipped control) at the layout's mobile breakpoint, using the same
   built-bundle smoke suite Bittern's B2.2 established.

## 5. Explicitly out of scope for Crane

Two design cycles were named while verifying B1 in production on August 2,
2026, and neither is Crane's foundation work:

**The parent–child domain redesign.** What a subtask actually *is* — a
step, a dependent task, a checklist item — was never decided; its current
rules (recurrence only on parents, `always_recurs` only on children,
inconsistent archive cascades) were each added defensibly on their own and
don't add up to a model anyone could predict. Crane 1's slices touch task
and agenda code — embedding Action Items, pinning a task to Daily Focus —
and it will be tempting to "just fix" a parent/child inconsistency noticed
along the way. Don't: that redesign needs its own decision about what a
subtask is before any more of its behavior changes, and folding it into
Crane's daily-surface work would mean neither gets the vertical slice and
acceptance condition it deserves.

**The web UI overhaul, second pass.** C2's evidence — a Repeat select that
silently hides its own child control, two visually identical checkboxes on
a subtask row meaning different things — is a language-and-interaction
problem in the existing task UI, not a styling one, and it wants its own
brief the same way the first Tailwind/shadcn pass got one. The Daily Page is
new surface, not a place to quietly relabel or restructure the surfaces it
embeds; if Crane 1's agenda embedding surfaces a similar confusion, name it
for that redesign rather than patching it in place.

## 6. Open questions for Vince

**All six are answered as of August 2, 2026.** Kept struck through rather
than deleted: what a decision replaced is often the useful part of it, and
two of these turned out to rest on a premise that was wrong rather than a
preference that needed stating. This section is now a record.

Two questions Crane 2 still has to answer are in §3 rather than here — what
a paused routine's gap means for a weekly review, and whether an occurrence
needs a satisfied-but-partial close. Neither blocks anything before Crane 2
starts.

- ~~**Crane 0's widened scope.**~~ **Answered August 2, 2026: widened, then
  narrowed.** The identity half — a thin commitment record and the foreign key
  `_spawn_next_occurrence` never wrote — was accepted and shipped ahead of
  Crane 1 as §3's Crane 0a. The vocabulary half, moving text and cadence off the
  occurrence onto a real template, goes to release D with the parent–child
  redesign it depends on. What decided it was not the "designing the same shape
  twice" argument, which turned out to be weak once §4 rule 8 was noticed to
  have recorded the convention already; it was that the unlinkable history
  accrues fastest exactly when Crane makes the product a daily practice. The
  full reasoning is in §3.
- ~~**Weekly occurrence anchor.**~~ **Answered August 2, 2026: Monday — and
  the question was less open than it was written.** This entry claimed
  nothing in the codebase set the precedent. It does. `lists/agenda.py`
  defines `MONDAY = 0` and resolves the snooze menu's "Next week" to
  `next_weekday(today, MONDAY)`, with a docstring spelling out that on a
  Monday it means the Monday *after* this one. So the product already tells
  people, in a control they use on ordinary tasks, that a week begins on a
  Monday. A routine that disagreed would be the same word meaning two things
  on two screens, which is the C2 failure in a new place.

  That settles it on evidence rather than taste, and it binds one more
  thing: Crane 3's weekly review has to use the same boundary. Two
  definitions of "this week" between a routine and the review that reports
  on it would make the report wrong in a way nobody would see.

  What genuinely remains a preference is only whether *this* person's week
  starts on a Monday, and the snooze menu has been answering yes since
  Albatross without complaint.
- ~~**Progress correction history.**~~ **Answered August 2, 2026: the single
  mutable count is enough, with a named trigger for revisiting.** Nothing
  currently asked of routines needs to know *when inside a period* a unit
  was logged. Go through the list in `architecture-trajectory.md` §4 —
  streaks and recovery time, cadence drift, completion rate by list, load
  against closure, time-to-close, abandonment — and every one is answerable
  from an occurrence's period, target, progress and outcome. So is the
  vision document's own example, "4 of 5 planned lesson targets met".

  The retrofit argument that carried Crane 0a does not apply here, and the
  difference is worth being precise about rather than assuming the same
  answer twice. A missing foreign key could not be invented later because
  the relationships it would have recorded were gone. An entry-level log is
  additive whenever it is wanted: add the table, keep `progress` as the
  denormalised count, and lose only the detail from before that day —
  detail no stated question needs.

  **Reconsider when** a question arrives that needs time-of-day or
  order-of-logging — "am I front-loading the week", a correction somebody
  disputes, or a client that logs offline and needs to reconcile. Until one
  does, `principles.md`'s instruction to measure behaviour before optimising
  it applies squarely.
- ~~**Home-surface reversibility.**~~ **Answered August 2, 2026: default to
  the Daily Page, with a preference to go back to Agenda.** Not a hard
  switch. The product still takes a position — the Daily Page is the
  default, and a fresh account gets it without choosing — but the surface a
  person opens all day is not somewhere to be told they are wrong. It also
  fits what `principles.md` says about automations proposing rather than
  deciding, and it makes slice 6 reversible in the sense that section means:
  if the Daily Page turns out not to earn the front door, the evidence is a
  preference people actually flipped, not a complaint. Slice 6 in §4 now
  carries the extra field and control this implies.
- ~~**Sequencing the carried-in checklist.**~~ **Answered August 2, 2026 by
  events, and worth recording as a decision rather than leaving as a
  drift.** Crane 1 shipped first and the checklist is untouched. That was
  the right way round — none of it blocked the design work, exactly as §2
  said — but the reason it stays untouched now is narrower and should be
  named: **nine of the fourteen items cannot be done without a deploy.**
  All five production verifications, all three infrastructure confirmations
  and the New York digest need production to be running the code. Only the
  five Android gaps are independent, and those need a phone rather than a
  deploy.

  So the sequencing answer is: **clear them at the next deploy, in one
  pass.** The deploy puts most of them in front of you anyway — a session
  that has just watched the play recap is already logged in, already looking
  at production, and already the cheapest moment to check a logout, a hard
  refresh and a broken route. Doing them piecemeal beforehand was never
  available; doing them long afterwards is how Bittern's list got written in
  the first place.
- ~~**Crane's own shipping cadence.**~~ **Answered August 2, 2026: deploy
  often, tag once — and the question contained a false choice.** "Ship once
  or in stages" reads as one decision and is two, because this project's own
  release practice already separates them. `roadmap.md` defines
  `DEPLOYED-<date>/<HHMM>` as a permanent deployment-event tag, `LIVE` as a
  moving one, and the bird codename as a release tag applied only after
  production is verified. Deploying five times and tagging `crane` once is
  not a compromise between the options; it is what those three tags were
  designed to express.

  So: deploy each phase when it is green and useful, because Crane 1's whole
  point is removing clerical work from a day and it cannot do that from
  `main`. Tag `crane` when 0a through 3 are all in production and verified.

  **Bittern's mess is worth diagnosing correctly**, because this question
  half-assumes staged deploys caused it. They did not. Bittern's difficulty
  was that the tag went on while B2.1 and B2.2 were still catching up, and
  that five after-deploy checks were never run — a verification failure, not
  a cadence one. `roadmap.md` already draws the right lesson in one line:
  tag only after production is verified. Staged deploys are how a person
  gets value early; an early tag is how a release claims something that is
  not true yet.

## 7. Crane 2 — daily planning and routines

**All five slices shipped August 2, 2026**, each acceptance verified
against a running server rather than only the test client, and **deployed
to production at 17:54 EDT the same day** alongside Crane 0a and Crane 1 —
ten migrations in one run, `failed=0`.

Verified with markers the change actually added, per the lesson Bittern
learned when a weaker one nearly confirmed a deploy that had not happened:
`/api/v1/day` and `/api/v1/routines` answer 401 while a made-up route
answers 404, so the routes exist rather than the shell swallowing
everything, and the served bundle carries "Keep a routine", "Personal
compass" and "Nothing pinned yet". `showmigrations` reports nothing
unapplied.

**And `lists/0023` did real work for the first time.** It was a no-op
locally because the dev database has no repeating tasks; production had
two, and both came back linked — `repeating roots: 2 | linked: 2 |
commitments: 2`. Every series that existed now has an identity, and the
accrual argument that justified Crane 0a stops running from here.

Three things the sequence taught, worth carrying into Crane 3. The slice
list again omitted a surface — routine *creation* had none, the same shape
of gap Crane 1 slice 6 found when the Daily Page was reachable only by
typing its URL; slice 3 absorbed it. Pausing had to be enforced in the
service rather than by hiding a button, and the endpoint answering 409 was
a defect a test caught before a person could. And slice 5 turned out to be
about `created_at` rather than `due_date`: overdue was already visible, and
age is the half a moved due date hides.

Numbered §7 rather than inserted after §4 so that §5 and §6 keep the numbers
other documents already cite. §5's fences apply to this release too: the
parent–child redesign and the UI overhaul are still release D's, and routines
touching neither is part of what keeps them there.

Crane 0 settled the domain and answered its own open questions in §3 and §6;
this is where it gets built. The charter gaps
`architecture-trajectory.md` §4 named against that sketch are closed here
rather than inherited: `RoutineOccurrence` gets a direct non-null owner
instead of a two-hop one, reads and services are split from the first slice,
and the deletion and public-identifier decisions are stated in the models
rather than left to be inferred.

Its own app, `routines`, as §3's sketch assumed. A routine is a peer of a
task and of a day, not a part of either — that boundary is the single most
load-bearing thing in the whole design, and an app boundary is the cheapest
way to keep somebody from quietly making a routine a kind of `Item` later.

1. **Keep a routine, and log against it.** `Routine` and
   `RoutineOccurrence`, occurrences created lazily on first log or view,
   logging that adds an amount and completes the period automatically when
   the target is reached. Both cadences, because the period is one function
   and a weekly routine that had to wait would be a second implementation.
   **Domain and API only** — this said "end to end" when it was drafted,
   which was wrong: slice 3 is where routines reach a screen, so there is no
   surface for this one to end at. What it delivers is the contract slice 3
   consumes, and a `/api/v1/routines` that serves *standings* rather than
   occurrence rows, because a period nobody has logged has no row and a GET
   that wrote one to describe itself would be a page view inventing history.
   *Acceptance:* §3's own examples. "Practice Spanish, 5 lessons
   daily" logged 2 in the morning and 3 in the evening reads 5 of 5 and
   completed, with `decided_at` stamped and no separate "mark done" action;
   the next day starts at 0 and logging it never touches the first. "Guitar
   practice, 3 sessions weekly" logged Monday and Wednesday sits at 2 of 3,
   open, all week, and the following Monday starts a new period — anchored
   to Monday on the evidence in §6.
2. **Correct a mis-tap, and skip a day on purpose.** Correction is the same
   write path with a different amount. *Acceptance:* correcting a completed
   day from 5 down to 4 reverts its outcome to open rather than leaving a
   count that is no longer true; an explicit skip is stored distinctly from
   a period that merely elapsed with nothing logged, because "I chose not
   to" and "I meant to and didn't" are different facts and Crane 3 reports
   them differently.
3. **Routines on the Daily Page.** Today's routines rendered with their
   progress and loggable in place. *Acceptance:* a unit logged from the
   Daily Page is the same occurrence as one logged anywhere else, and a
   routine never appears in Action Items — the agenda is tasks, and a
   routine is not one.

   **This slice absorbed a gap in the list above**, found the same way slice
   6 found the Daily Page had no navigation link: nowhere in these five
   slices did routine *creation* get a surface, so a routine could be logged
   against and never made. It lives here rather than in Preferences, where
   the compass went, because a routine is content rather than a setting.

   **Two decisions §3 deferred, settled here.** A blank unit with a target
   of one reads "Done" / "Not yet" rather than "1 of 1" — §3 named the
   toggle-versus-count question as a Crane 2 UI decision and this is it. And
   routines *are* shown on a past day, read-only, where Action Items cannot
   be: a task holds no record of what it looked like then, but an occurrence
   is a dated record, so reading one back is history rather than inference.
   Back-logging into that day is legitimate per §3 and is deliberately not
   built — the acceptance does not need it and a date-taking log endpoint is
   a wider surface than it has earned.
4. **Pause without losing what happened.** *Acceptance:* pausing an active
   routine stops new occurrences being created and leaves every existing one
   untouched; resuming does not backfill the gap, because the gap is a fact
   about the person's month rather than missing data.
5. **Task age, and overdue without reproach.** The other half of Crane 2 in
   `daily-operating-system-vision.md`: show how long a carried-forward task
   has been open so the carry-forward is visible rather than silent.
   *Acceptance:* an old task says how long it has been waiting, in wording
   that reports rather than scolds — the vision document's "let history be
   useful without making missed work feel like punishment" is the test, and
   a red "12 days late!" badge fails it.

**What Crane 2 is not.** No streaks, no trend views, no weekly summary:
those read routine history and belong to Crane 3, which is the point of
recording occurrences properly now. No monthly cadence — §3 leaves it
additive on purpose. And no routine logging from the Android client, which
would need the token-authenticated zone activation
`per-user-time-zones-plan.md` already flags and has no product trigger yet.
