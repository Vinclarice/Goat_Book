# A bill earns its own model — focused spec

Vince · claimed August 31, 2026 · **overturns one written refusal, and does not
override §4**

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
4. **The Money surfaces read *and* write `Bill`.** `create_bill` stops making
   an `Item`, and the reads built in increment 3 switch on in the same step —
   see that increment for why they could not move separately. **The point of no
   return**, and the first increment that changes what a person's data looks
   like. `test_bill_reads_agree.py` and `month_from_bills`'s `DARK` declaration
   are both deleted by this increment; a comparison test kept past its subject
   is how a suite grows things nobody can remove.
5. **Decision 4's cost, paid.** Agenda, day and search read both. This is where
   the split is felt outside Money, and where it is abandoned if it is going to
   be.
6. **Missed periods are replayed for bills** — the life-cycle difference in §2,
   which is the whole justification, made real. Until this ships, the split has
   been argued and not demonstrated.
7. **`Account.paid_by` returns, as `Bill.account`.** The disconnect Vince
   actually reported. It comes last only because the model it points at should
   exist first; **if the split stalls, this is the increment to do anyway**, on
   `Item`, exactly as the deletion commit anticipated.
8. **`MoneyLine` is deleted.** Not before every read and write has moved and a
   backup has been taken.

## 7. What would reverse this

**Increment 5.** If reading two models in the agenda proves ugly enough that
Decision 4 gets dropped to avoid it, then the split has cost a product decision
to buy a modelling one, and that is a bad trade made visible. Stop at 4, keep
`MoneyLine`, and take increment 7 on `Item`.

**Or increment 6 turning out to be unwanted.** If replaying missed bills
produces *"a page full of arrears nobody will action"* — `roadmap.md`'s own
words — then the life-cycle difference that justified the model was
theoretical, and this file should say so rather than quietly keeping the model.

## 8. Where the facts live

What is active is [`roadmap.md`](roadmap.md). The charter this satisfies is
[`architecture-trajectory.md`](architecture-trajectory.md) §4. What the module
is and what it refuses is [`money-module-plan.md`](money-module-plan.md), which
loses one refusal to this file and keeps the rest. How the module scores is
[`module-score.md`](module-score.md), which reads **not yet** and is not
touched by this until a person has used it.
