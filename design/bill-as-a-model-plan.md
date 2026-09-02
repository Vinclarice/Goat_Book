# A bill earns its own model — focused spec

Vince · claimed August 31, 2026 · **overturns one written refusal, and does not
override §4** · increments 1–5 shipped, **the flip passed September 1, 2026**

## 1. What is wrong

Vince, after using the repaired Money module and adding the *Dell Community*
account:

> *"I've added Dell Commenity and its showing up but now there's a disconnect.
> Like it should be tied to the payments. So I really think we need to separate
> bills from a task."*

Two things are tangled in that sentence and they are separable. **The
disconnect** is that an account and the bill that pays it are unrelated
records; that is `Account.paid_by`, written and deleted on August 27 with a
commit message saying *"it comes back the day a surface actually wants it"*.
**The diagnosis** is that a bill should not be a task, which is a model
question and the subject of this file.

## 2. What this overturns, and what it does not

**Overturned:** [`money-module-plan.md`](money-module-plan.md)'s *What this
refuses* — **"A bill as its own model. A bill is an `Item` with a `MoneyLine`
hanging off it... §4 settled it."**

**Not overturned:** [`architecture-trajectory.md`](architecture-trajectory.md)
§4. It never named bills, and its test is not being waived — **it is now
satisfied, and it was not when the refusal was written.**

> **A concept earns its own model when it has a different life cycle, not when
> it has a different name.**

**The life-cycle difference was written down on August 28, 2026 and nobody
connected it to the model question.** `roadmap.md`'s open item *Should money
skip a missed period at all?*:

> *Missed periods are skipped, not replayed* is the task core's doctrine and it
> is right for tasks: five missed bin rounds are five things that did not
> happen... **A bill is not like that.** A payment you did not make is still
> owed... so the doctrine that correctly declines to invent bin rounds quietly
> declines to remind you about a bill.

**That is the test, met exactly.** The same event — a period elapsing
unfinished — must produce **opposite** outcomes: a task's occurrence is gone
and inventing it would be fabricated history; a bill's occurrence is a debt
that persists whether or not any record says so. Two behaviours that cannot
both live in one `status` field on one model is precisely what §4 asks for.

**So the refusal was not wrong when it was made.** It was made on August 27,
the missed-period asymmetry was written on August 28, and the two were never
put side by side. Recorded that way rather than as a reversal, because the
reasoning that produced the refusal is still sound about *names*.

## 3. Why now, and not later

**Production holds one `MoneyLine`, one `Account`, one `BalanceReading`**,
measured August 31, 2026. The data migration is a handful of rows today and a
year of somebody's financial history later. **This is the cheapest this change
will ever be**, and the cost curve is the argument for doing it now rather than
the enthusiasm for doing it at all.

## 4. What a `Bill` is

A root record, owned at birth (§4 rule 1), carrying what `MoneyLine` carries
plus what it currently borrows from `Item`:

| From `MoneyLine` | From `Item` | New |
|---|---|---|
| `payee`, `amount`, `paid_amount`, `currency`, `direction`, `category` | `due_date`, `lead_days`, `notes`, recurrence and its commitment | `account` — the link §1 asked for |

**`paid_at` replaces `status`.** A bill is outstanding or it is settled, and the
date it settled is the fact worth keeping; `Item.Status`'s three values plus
archive are a task's life cycle and this is the point of not sharing one.

**What it stops inheriting, deliberately**: tags, priority, area, checklist,
project — every one of which was hidden from the bill page on August 31 for the
same reason. The page that already hides them is evidence the model does not
want them.

**What it must not lose**: `MoneyLine`'s two-amount discipline (expected and
actual, kept separately so *"the electricity bill has been creeping up"* stays
answerable), and its docstring's own §4 note about why `paid_amount` is not a
`Payment` table. That reasoning survives the move.

## 5. Decision 4 is preserved, and it is the expensive part

[`money-module-plan.md`](money-module-plan.md)'s decision 4, Vince's, August 27:

> **Bills stay ordinary tasks elsewhere** — day, agenda, lists. Paying is a
> real thing to do on a day, and the day is where it gets noticed.

**Splitting the model does not invalidate that reasoning; it makes it
expensive.** A bill that is not an `Item` does not appear in a read that
queries `Item`, so the agenda, the day page and search each have to read two
kinds of record and merge them.

**Preserved rather than dropped, as the default**, because discarding a stated
product decision as a side effect of a model change is how a decision dies
without anybody choosing to kill it. **If it should go, it goes deliberately
and in writing** — and that is a real option, since a Money module that
answers *what needs paying* arguably makes the agenda's copy redundant.

**This is the largest single cost in the plan and the one to price first.**

## 6. Increments, in order

Each is shippable and leaves the product working.

1. ~~**`Bill` exists, and nothing reads it.** Model, migration, owner at birth,
   admin. `MoneyLine` untouched. Declared dark with this file as the trigger,
   which is the one form `principles.md` permits.~~ **Done August 31, 2026 —
   and it is two tables, not one.** §4 rule 8 requires a template plus dated
   occurrences for anything that repeats, and its own cost note is the argument
   for paying that in the first migration rather than the fourth: *one foreign
   key now*, against *no migration can invent links after the fact*. So
   `BillSeries` holds the rule and `Bill` holds what happened, in the shape
   rule 8 names — owner, a key to the template, the date covered, a snapshot of
   what was expected, an outcome, and when it was decided.

   **Not `RecurringCommitment` as the template**, which holds text, list,
   priority and tags: pointing a bill at it would re-couple the two
   vocabularies this plan separates.

   **Two guards fired and both were right**, which is the reason `CLAUDE.md`
   says to run `accounts` and `clarice` rather than the app you are editing.
   The export guard refused a new owned model that no export names — so a
   person's whole financial history would have gone missing from their archive
   the day increment 4 started writing it. And the restore-drill guard refused
   a new constraint that was in neither the drill nor the deliberately-not-
   drilled list; `bill_paid_at_and_amount_agree` is **drilled**, because losing
   it produces a bill claiming it settled with no figure, which makes a
   month's *already paid* total quietly short rather than visibly broken.
2. ~~**A data migration copies every `MoneyLine` + its `Item` into a `Bill`**,
   and is reversible. One row in production; several in development.~~ **Done
   August 31, 2026** as `0055_copy_money_lines_into_bills`, verified forward,
   backward and forward again against the development database: five money
   lines became five bills and one series, and the five source rows were never
   written.

   **It found that increment 1's constraint was wrong, from the data rather
   than by argument.** `bill_paid_at_and_amount_agree` demanded that `paid_at`
   and `paid_amount` both be set or both be null — and `services.pay_bill`
   defaults the figure to what was expected, so an *unpriced* bill paid without
   an explicit number settles with `paid_amount` still null. **One of five
   development rows was in exactly that state**, and the migration would have
   refused it. *Paid, amount unrecorded* is a real answer; fabricating a zero
   is inventing and dropping `paid_at` loses the fact of payment. Relaxed in
   `0054` to *a figure requires a settlement, a settlement does not require a
   figure*.

   **It refuses two states rather than guessing**, both reachable and neither
   present in development or production when it was written: a bill with no due
   date (`set_bill` can mark an undated task), and a figure with no completion
   (pay, then reopen). Skipping either would be silent data loss, so it raises
   at `migrate` with the row ids named.
3. **The Money surfaces read `Bill`.** ~~`/money`, the month, balances,
   history, categories. `MoneyLine` still exists and is still written, so this
   is provable by the two agreeing.~~ **Half done August 31, 2026, and the
   other half moved into increment 4 on purpose.**

   **What landed**: `money.month_from_bills` reads `Bill` where `bills_for`
   reads `MoneyLine` + `Item`, and `test_bill_reads_agree.py` runs both over
   the same converted data and requires the same answers — totals, buckets,
   currencies, ordering, settlement. Declared dark with increment 4 as its
   trigger, and the dark-services guard caught it within minutes of it being
   written.

   **What moved, and why the plan was wrong here.** *"`MoneyLine` still exists
   and is still written"* skipped a step: reading `Bill` while `MoneyLine`
   stays authoritative requires every money mutation to be mirrored into
   `Bill`. And a `Bill` mirrors fields owned by **two** models, so the mirror
   is roughly **fifteen** call sites — `set_bill`, `pay_bill`, `clear_bill`,
   `delete_bill`, the direction update, the spawn, plus `set_due_date`,
   `complete_item`, `reopen_item`, `restore_item`, `set_item_notes`,
   `set_recurrence`, `set_lead_days` and the two creates — against the eight
   `_write_through_to_commitment` needs. **Every missed one is silent
   divergence**, which is precisely the failure this repository keeps finding.
   A mirror that is a worse bug surface than the thing it de-risks is not worth
   building, so the reads switch on with the writes in increment 4.

   **Balances, history and categories were never in scope** and this is the
   increment that found out: they read `Account`, `BalanceReading` and
   `MoneyCategory`, none of which the split touches. Only two reads ever
   touched `MoneyLine`.

   **Three things the new read does not have to do**, which is the split paying
   for itself rather than an argument for it. There is no `BillRow` wrapper,
   because the row *is* the record. There is no status reconciliation:
   `BillRow.paid` needs a paragraph explaining that a paid *recurring* task is
   `ARCHIVED` rather than `COMPLETED`, so settlement must be read from
   `completed_at` and never from the status — `paid_at` has no such trap. And
   there is no archive filter, because a bill has no *put away* state.

   **That last one is a decision and is recorded here rather than absorbed**: a
   bill you neither pay nor delete is now simply owed. Nothing was affected —
   development and production both held zero archived bills when the conversion
   ran — but the concept is gone rather than carried.
4. ~~**The Money surfaces read *and* write `Bill`.**~~ **Done September 1,
   2026 — the point of no return, passed.** Every money endpoint writes through
   `bills.*` and reads `month_from_bills` / `landing_from_bills`;
   `services.create_bill`, `create_income`, `set_bill`, `clear_bill`,
   `pay_bill`, `update_bill` and `delete_bill` are deleted, along with
   `bills_for`, `landing_for`, `BillRow`, `test_bill_reads_agree.py` and both
   `DARK` registry entries.

   **The plan missed a whole half of this increment, and it is the destructive
   half.** `0055` *copied* rather than moved, deliberately, so the two reads
   could be compared — which leaves every converted bill existing **twice**.
   That was the point while both reads were live; the moment the writes moved
   it became a duplicate the digest, the calendar, search, the archive and the
   export would all go on showing, with a *Complete* button that would spawn a
   shadow of next month's bill. So `0057_retire_the_tasks_that_were_bills`
   deletes them, in this commit, because between the two the product is
   incoherent. **That migration is what "point of no return" actually means**,
   and nothing in this file said so until it was written.

   **Three consequences worth naming, each found by doing it:**

   - **The task core had to stop knowing what a bill is.** `PATCH /tasks/{id}
     {bill: …}` could still have marked a task as one, writing a `MoneyLine`
     that Money can no longer see — a feature silently doing nothing. So
     `TaskOut.bill`, `_set_bill`, `serialize_item`'s `bill` key and the task
     detail page's whole bill apparatus are gone. That apparatus was written on
     August 31 and every piece of it — a declared noun so fifteen strings could
     say *Bill*, three flags hiding Priority, Area and Checklist, a back-link to
     Money — was an admission that a bill was on the wrong screen. The split
     removed the possibility rather than the awkwardness.
   - **A refusal disappeared, and it was an artifact.** Two open bills from one
     payee used to raise *"there is already an open bill from Amazon"*. Nothing
     in money wanted that: it was `unique_active_item`, the task core's rule
     that one person cannot have two open tasks with the same text, reaching
     money through the derived title *Pay Amazon*. Two invoices from one
     supplier in a month is ordinary and the old model could not record it.
     Pinned as a test in `test_bill_writes.py` so it is a decision.
   - **`MonthBillOut` lost `text` and `url`.** A `Bill` has no title and no
     `/api/items/{id}`, and nothing read `url` at all. The month page showed
     `text` — *"Pay Landlord"* — beside a payee of *Landlord*; it shows the
     payee once now. **`task_id` is deliberately still spelled that way** while
     pointing at a `Bill` id: renaming server, contract, routes and SPA in the
     commit that changes what a bill *is* would put two failure modes in one
     place. The rename is increment 9.

   **And a defect the flip found rather than caused.** `POST /money/bills`
   declared `recurrence` and `lead_days`, the SPA's *Add a bill* form sent both,
   and the endpoint passed neither to `create_bill` — so choosing *annual* made
   a monthly bill and the lead days the form calls *"30 is usual"* were dropped
   on the floor. Every test of those two fields called the service directly, so
   all of them passed. Fixed here, since the call site was being rewritten
   anyway.
5. **Decision 4's cost, paid — Vince's call, August 31, 2026, and it moves
   *before* increment 4 rather than after.**

   **The ordering in this plan was wrong and the flip found it.** Increment 4
   was written as though decision 4 broke at increment 5; it breaks at 4. A
   bill created after the write switch has no `Item`, so it vanishes from the
   agenda and the day — **while the bills created before it stay**, because
   they still have theirs. That is not a clean break but an inconsistent one,
   where whether a bill appears on your day depends on when you made it. The
   `/tasks/{id}` link every month row carries breaks the same way.

   So §7's off-ramp arrived with a concrete cost rather than a hypothetical
   one, and was declined: **bills stay on the day and the agenda.**

   **The size, measured**: `agenda.open_items_for` is the single selection
   point the day, the agenda, the digest and coming-up all share — five
   production call sites — and each needs a second source. The payload gains a
   bills array rather than faking `TaskOut` rows, because a `Bill` id and an
   `Item` id would collide in one list and the SPA completes a row by calling
   `/api/v1/tasks/{id}`. That means server *and* client move together.

   ~~This is where the split is felt outside Money, and where it is abandoned
   if it is going to be.~~ It was felt, and it was not abandoned.

   - ~~The read that mirrors `open_items_for` for bills.~~ **Done August 31,
     2026** as `money.open_bills_for`, proven against the task read by
     `test_bill_reads_agree.py`. Dark, declared, waiting on the wiring.
   - ~~**The payloads and the SPA.**~~ **Done August 31, 2026**, and it was
     the largest single piece. `open_items_for` grew `include_bills=False`;
     the agenda and the day each grew a `bills` array beside `items` /
     `action_items`, both sourced from one `agenda.open_bill_rows_for` so the
     two surfaces cannot disagree about which bills exist. The SPA renders
     them through the *shared* `bucketFor` and `dueLabel`, so a bill and a
     task due the same day say the same thing about being overdue.

     **Two answers this piece produced rather than inherited.** The day's
     bills sit in a section of their own instead of among the action items:
     a bill has no area, no priority and nothing to pin, so a merged list
     would mean either showing fields it has not got or special-casing the
     ones it has — which is precisely what made the task detail page a bill
     page nobody designed. And `draft_day` stops proposing bills, which is
     not decision 4 arriving by inheritance but a harder constraint:
     `DailyFocus.task` is a foreign key to `Item`, so a bill that is not an
     `Item` **cannot be pinned at all**. Proposing one would offer a verb the
     model has taken away.

     **What is still on `open_items_for`'s bill-carrying path, and must move
     with the flip**: `coming_up_for` (the day brief's *coming* list),
     `digest_items_for`, and `daily.reads`'s calendar due-counts. All three
     have one kind of row and nothing to merge into, so they keep bills
     inline today — and all three go silently empty of bills at increment 4
     unless given the `Bill` source in the same commit. Written down here
     because *silently* is the word: no test named for bills covers them.
   - ~~**A bill's own detail surface**, since it can no longer borrow the
     task's.~~ **Done August 31, 2026.** `/money/bills/:id`, reading a new
     `GET /api/v1/money/bills/entry/{task_id}` on the key the writes already
     use. The month row links there instead of into the task core.

     **The surface moves before the model does**, which is the point: it reads
     the task-backed endpoint today and only its data source changes at the
     flip, so that commit does not have to invent a page in the same breath as
     it changes what a bill is.

     **It shows what a bill is and none of what a task is** — no tags,
     priority, area, checklist or project, not hidden but absent. The task page
     spent the morning of the same day being taught to hide all five; that
     teaching was the argument for this page, made one field at a time.
6. ~~**Missed periods are replayed for bills**~~ — **Done September 1, 2026.**
   The life-cycle difference in §2, which is the whole justification, made
   real; until this shipped the split had been argued and not demonstrated.

   **Measured first, which is what `roadmap.md`'s entry asked for**, and the
   finding was worse than the shape it predicted. That entry described *paid in
   August, schedules September, July is gone*. What this checkout actually
   held: *American Express*, monthly, due August 20, unpaid — **one occurrence,
   and there would never be another.** The only thing that created a successor
   was settling or deleting the current one, so a series nobody touches never
   grows. **The further behind you were, the less the module said.**

   **Two mechanisms, and both moved.** `spawn_next` skipped past today, so
   paying June's rent in August produced September's and July was owed by
   nobody — it now advances exactly one period and leaves
   `_advance_due_date`'s own doctrine, and every task that depends on it,
   untouched. And `bills.catch_up` replays whatever a live series has come to
   owe, up to and including today.

   **The asymmetry is asserted from both sides.**
   `test_a_missed_bill_is_still_owed.py` ends with a test that a *task* still
   skips: if that ever fails, the fix for bills has leaked into the doctrine
   that is correct for tasks.

   **The scheduled pass is the increment**, not a convenience on top of it.
   `catch_up_bills` runs hourly from the playbook, in this same commit —
   `CLAUDE.md` records three seams here that were built, tested, green and
   never switched on, the digest among them. Hourly rather than nightly because
   `catch_up` compares due dates against each owner's today and so has no
   opinion about time zones.

   **Not in a read**, which was the tempting shape: `principles.md` asks that
   reads and writes stay distinct, and `money.open_bills_for` is called by the
   agenda, the day, the digest and the calendar. Not folded into the digest
   either, or bills would stop appearing for anybody who turned email off.

   **Idempotence is a constraint, not a promise.**
   `bill_one_occurrence_per_period` — `principles.md`'s rule that retry-safety
   is bought with a database constraint rather than with care. Scoped to the
   series, so one-offs are unaffected and two invoices from one supplier on one
   day remain two records.

   **Nobody confirms anything**, per `modules.md`'s input ratio, and
   `principles.md` sanctions it outright: routine generation may act because
   the act is visible and undoable — a replayed bill is a row with a delete
   button.

   **The arrears risk that entry named is real and was not designed around.**
   Demonstrated against this checkout's own data, rolled forward and rolled
   back: at March 1, 2027 the untouched Amex series produces **six** further
   unpaid rows. That is true, and a module that hid it would be lying about
   money — but it is the thing to watch first if the page becomes unusable, and
   §7 already says so.
7. ~~**`Account.paid_by` returns, as `Bill.account`.**~~ **Done September 1,
   2026** — the disconnect Vince actually reported, closed.

   **Both halves in one commit, which is the whole point.** `d50d6eb` deleted
   the first version because it was *"set by nothing and read by nothing"*
   through two screens that were each supposed to give it a purpose, and its
   terms of return were explicit: *"it comes back the day a surface actually
   wants it."* So the picker on the add and edit forms and the balances
   screen's `next_payment` ship together; either alone would be the same
   mistake with a longer runway.

   **What the link means, decided rather than left open.** `Bill.account` is
   *the account this bill moves money against* — an outgoing bill against a
   card reduces what is owed, an incoming one against an investment increases
   what is held. **Not "paid from"**, which was the other available reading:
   which current account the money physically left is a second fact this
   product does not record, and one field that could mean either would make
   every reader guess. The original field's own docstring picked the same side.

   **On the series and on the occurrence**, because they are different facts:
   the series is what pays the card as a standing arrangement, the occurrence
   is what pays it in September. §4 rule 3, so refiling one month leaves the
   arrangement alone — and `spawn_next` and `catch_up` both carry it forward
   from the rule.

   **One thing measured rather than assumed.** The balances screen lists every
   account somebody has, so the payment lookup is one query for all of them
   rather than one each; the test asserts the cost is *unchanged* between one
   account and seven, which says the property directly and cannot drift when
   something unrelated adds a query.

   **And one defect this increment nearly repeated.** `POST /money/income`
   takes its own schema, so wiring `account_id` into `POST /money/bills` and
   not into its twin would have produced exactly what the flip found: a form
   that sends a field, an endpoint that returns 201, and a link that was never
   made. Caught by writing the income test rather than by review, and the
   symmetry is now asserted end to end.

   **Whether that shape deserves a guard was measured, not guessed**: a scan of
   all 129 Ninja input schemas found **zero** fields an endpoint never
   mentions, so a source-level test of *every declared field reaches a service*
   would start green and cost little. Not built here — it is a codebase-wide
   guard rather than part of this increment — but the measurement is recorded
   so the decision is one line of work away.
8. ~~**`MoneyLine` is deleted.**~~ **Done September 2, 2026.** Both stated
   conditions were met first: every read and write had moved, and the
   production cluster's daily backup had passed that morning.

   **Production was measured before the drop was written**, not after: one
   `MoneyLine`, one task carrying it, no undated bill and no figure without a
   completion — so neither `0055`'s refusal nor `0057`'s can fire there, and
   `0059` drops a table that `0057` has already emptied by cascade two
   migrations earlier in the same deploy.

   ~~A schema removal and a tidy-up~~ — **it was not only that, and the
   difference is a guarantee that would have gone out with the table.**
   `MoneyLine` carried `money_line_amount_not_negative`: *a bill is something
   owed, a negative one is a refund*, refused in the database *"as well as at
   the boundary, because the boundary is not the only writer"*. **`Bill` was
   built without it.** For one day the only thing refusing a negative bill was
   Python in `bills.record` and `bills.update`, and deleting the old model
   would have made that permanent silently. `0060` carries it across as
   `bill_amount_not_negative`, and widens it to `paid_amount`, which the
   original never covered — money moving backwards is the same refund in the
   column that records what actually moved.

   **And the restore drill was checking a constraint about to stop existing.**
   `check-restore-integrity.sh` names `money_line_amount_not_negative` in its
   CHECK loop; after the drop it would have queried a constraint that cannot
   exist, reported `no`, and failed — at step 5, in WSL, with a paid scratch
   cluster running. No test caught it, because
   `test_restore_integrity_covers_the_schema.py` walked *declared → script* and
   *NOT_DRILLED → declared* but never *script → declared*. That asymmetry was
   the whole gap and it is closed:
   `test_the_script_checks_nothing_that_no_longer_exists` parses the loops the
   script actually runs, and was mutation-tested against a renamed constraint
   rather than trusted.

   The tidy-up was real too: `accounts/export.py`'s `bills` key is gone — every
   bill is in `bill_occurrences` and `bill_series`, owned directly rather than
   reached through a task's owner, verified against the real archive — and
   `test_a_spawn_accounts_for_everything_on_a_task.py`'s positive control moved
   off the model it was written about onto two relations that are not going
   anywhere.
9. ~~**The key is renamed from `task_id`.**~~ **Done September 2, 2026**, and
   with it the plan. It pointed at a `Bill` and said otherwise for two days,
   held out of increment 4 on purpose: a mechanical rename across the server,
   the contract, four routes and the SPA is the wrong thing to carry into the
   commit that changes what a bill *is*.

   **`id` where a schema is a bill; `bill_id` where it is not.**
   `MonthBillOut`, `AgendaBillOut` and `LandingLineOut` each *are* a bill, so
   they take `id` — matching `TaskOut.id` beside `/tasks/{task_id}`, which is
   the shape this file already used. `AccountOut.next_payment` is nested inside
   a row that has an `id` of its own, so a bare one there would read as the
   account's; it takes `bill_id`, as do the four route parameters.

   **Renamed by hand where both kinds live together**, and that is the whole
   risk of this increment: `ChecklistStepOut.task_id`, every `/tasks/{task_id}`
   route, and `DailyFocus` all name a genuine `Item`, and both spellings are
   `int`, so a wrong rename type-checks and 404s at runtime. `MoneyRoute`,
   `BillDetailRoute` and `MoneyLandingRoute` were swept whole after asserting
   they never touch the task API; `AgendaWorkspace` and `DayRoute` were edited
   line by line, because they carry both.

   **`test_task_vocabulary.ABillDoesNotCallItsKeyATaskTest`** reads the OpenAPI
   schema rather than the Python classes — so it sees what a client sees — and
   checks the route paths too, since `entry/{task_id}` is the same claim in the
   place a person looks first. Mutation-tested by putting `task_id` back.

   **Verified against the dev database**, not only in tests: every one of the
   five payloads carries `id` or `bill_id` and none carries `task_id`, `GET`
   and `PATCH` on `entry/{id}` answer 200, and an account's `next_payment.bill_id`
   was proved to point at the right row by filing a bill against *Dell
   Community* inside a transaction and rolling it back.

## 7. What would reverse this

**Increment 5.** If reading two models in the agenda proves ugly enough that
Decision 4 gets dropped to avoid it, then the split has cost a product decision
to buy a modelling one, and that is a bad trade made visible. Stop at 4, keep
`MoneyLine`, and take increment 7 on `Item`.

**Or increment 6 turning out to be unwanted.** If replaying missed bills
produces *"a page full of arrears nobody will action"* — `roadmap.md`'s own
words — then the life-cycle difference that justified the model was
theoretical, and this file should say so rather than quietly keeping the model.

**It shipped on September 1, 2026 and this condition stays open**, because
whether it produces a wall is a question about use rather than about code.
Measured on this checkout's data: one untouched monthly series produces six
further unpaid rows by March 2027, which the month page spreads across six
months and the agenda would show together. **The signal to watch is the
agenda**, and the cheapest answer if it arrives is a per-series cap on how many
unpaid occurrences are surfaced — not a retreat from the model, which the
month, the landing page and the digest all now depend on.

## 8. Where the facts live

What is active is [`roadmap.md`](roadmap.md). The charter this satisfies is
[`architecture-trajectory.md`](architecture-trajectory.md) §4. What the module
is and what it refuses is [`money-module-plan.md`](money-module-plan.md), which
loses one refusal to this file and keeps the rest. How the module scores is
[`module-score.md`](module-score.md), which reads **not yet** and is not
touched by this until a person has used it.
