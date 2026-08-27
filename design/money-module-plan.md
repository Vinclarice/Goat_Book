# Money — a place rather than a report — focused spec

Vince · focused spec · written August 27, 2026 · **status is the strikes below**

**Renamed from Bills to Money on August 27, 2026**, the same day it was written,
once Vince described what the surface is: *"a module is essentially its own sort
of landing page for relevant information... if I need to check on financial
information, I know exactly where to go."* Then: *"I think I will want to include
income and investments."*

**Bills did not become Money — bills became part of it.** The nav entry, the
route, the read module and the API namespace all moved; **`Bill` kept its name**,
because a bill is one kind of money thing and income will be another, and a
record named after the module would have to be both. That is
`architecture-trajectory.md` §4's collapse, avoided by not renaming the noun.

**The old address still works and keeps its month.** `/bills/2026-08` lands on
`/money/2026-08` rather than on today: a redirect that dropped the month would
be worse than a dead link, because it looks like it worked. `/capture/` is the
precedent for what a moved prefix costs once anything points at it.

## What this is

**The Bills page is a report on a thing you cannot make, edit, or delete, and it
hides half of what it is about.** Vince's own words: *"Why does it exist? I
can't actually do anything on that page."* This makes it the one place bills are
entered, maintained, changed and deleted.

**It is the first repair aimed at a feeling rather than a journey** —
*"everything is still sort of in silos"* — and it was picked because it is the
sharpest instance, not because it is the biggest.

## What is actually wrong, measured

Checked live at `previewuser`, August 27, 2026:

1. **No write path exists at all.** `BillsRoute.tsx` is 138 lines with zero
   mutations, and `/api/v1/bills/{day}` is a lone `GET`. `set_bill` and
   `clear_bill` are exposed only on `TaskDetailRoute`.
2. **So adding a bill means not saying "bill"**: create a *task* somewhere else,
   open its detail page, fill in amount and payee.
3. **A paid bill disappears.** `bills_for` filters `status=ACTIVE`. Rent, 1200
   USD, paid on the 1st, is absent from the month on the 2nd.
4. **The total is mislabelled.** The page shows `64.99 USD` for a month that
   cost `1264.99`. It is a remainder presented as a total.
5. **The empty state is a dead end.** *"No bills due this month."* and two links,
   both to other months.

**Nothing here is a missing capability.** `create_item` takes a `due_date`, a
`recurrence` and a standing `owner` with no Area; `Item.Recurrence.MONTHLY`
exists; `set_bill` exists. **Every part was built and none was joined to this
surface**, which is the general diagnosis in one page.

## The cause, and what is not being reopened

**`architecture-trajectory.md` §4 decided a bill is a sidecar on `Item`, not a
model, because its life cycle *is* a recurring task's. That is right and stays.**

**What leaked is the interface.** Because a bill is a task underneath, the page
made the person think in tasks — and item 3 above is the same leak in the read:
*"the agenda's own definition of open"* is correct for an agenda and wrong here.
A bills page answers *what do I owe* **and** *what did this month cost*, and only
the first survives that filter.

**So the rule this slice follows: the page owns the concept, and the model stays
where it is.** The word *task* does not appear on it.

## Decided August 27, 2026 — Vince's, in one pass

1. **Show the whole month, two totals per currency** — still due, and already
   paid. A number labelled *total* never means *remainder* again.
2. **Delete removes the whole thing.** From the person's side there is no task.
   If it recurs, ask once: this month, or the standing bill and everything after.
3. **Repeats is part of adding**, monthly and on by default. Rent is set up once.
4. **Bills stay ordinary tasks elsewhere** — day, agenda, lists. Paying is a real
   thing to do on a day, and the day is where it gets noticed.

## Increments, in order

1. ~~**The read learns about paid.**~~ **Done August 27, 2026.** The month holds
   every bill, paid ones marked, and two figures per currency. `totals` was
   **renamed rather than added to**, so every caller had to say which question
   it was asking — the defect expressed as a field name.
2. ~~**Adding, on the page.**~~ **Done August 27, 2026.** `create_bill` writes
   the `Item` and the `Bill` in one transaction, `POST /api/v1/bills` serves it,
   and the form asks payee, amount, currency, due date, repeats. **No title
   box** — the name comes from the payee, and a test asserts the form never
   grows one. The empty state offers the form instead of two links to other
   empty months.

   **It turned up a defect that would have sunk the increment.**
   `_spawn_next_occurrence` never touched `Bill`, so paying a repeating bill
   produced a plain task next month and **rent silently stopped being a bill**.
   *Repeats monthly*, on by default, would have shipped a page that emptied
   itself one payment at a time. Payee and currency now carry and the amount
   does not, which is `set_bill`'s own rule — what lands is an unpriced bill
   from a known payee, exactly what `unpriced` was built to count.

   **Nothing was going to catch it.** `set_bill`, `_spawn_next_occurrence` and
   `bills_for` are each correct; the defect lived in the space between them —
   the second of that shape in one day, after the miss-review surface in
   `search-plan.md`.
3. ~~**Editing in place**, the same fields against an existing bill.~~ **Done
   August 27, 2026.** `update_bill` corrects all four fields across both records
   they live in — amount, payee and currency on the sidecar, the due date on the
   task — so the page never has to know which is which. Absent keeps its value,
   and **clearing an amount is explicit**, because *whatever it comes to* is a
   state somebody chooses.

   **It does not rename the task**, recorded as a decision rather than an
   omission: the name came from the payee at creation, and
   `RecurringCommitment.text` is what a series with history is called.

   **The write routes are `/bills/entry/{id}`**, because `/bills/{day}` already
   takes a date in that position and two routes differing only by the type of
   one segment is a collision waiting for the first numeric-looking date.
4. ~~**Deleting**, with the recurring question asked once.~~ **Done August 27,
   2026.** The narrow act is the default and the wide one has to be chosen:
   removing August's rent means *not this one*, and only *stop paying rent*
   cannot be undone by adding a bill back. A one-off bill is deleted without
   any question, because there is only one thing it could mean.

   **It had the same trap as increment 2 and nearly shipped with it.** A series
   continues only because completing an occurrence spawns the next one, so
   deleting this month would have ended the series *silently* -- no next month,
   nothing to notice until a bill failed to arrive. The successor is created
   before the occupant is removed.

   **And it exposed a real defect in increment 1.** A completed *recurring*
   task is `ARCHIVED`, not `COMPLETED` — `complete_item` says why, since
   `unique_active_arealess_item` will not have a successor beside a live
   predecessor. So the first version of the month read filtered on status and
   **would have hidden every paid rent**, while passing every test, because no
   fixture repeated. Keyed on `completed_at` now, which survives that archive,
   and the case has its own test rather than staying found-by-accident.

## The second half — August 27, 2026, after use

Vince's, on reading increments 1–4: **the module is Money, not Bills**, and the
thing it is for is **recurring expenses — especially an annual subscription
about to renew.** *"When I sign up for an annual subscription, when it's about
to expire."*

**Bank transactions are refused, by preference rather than by cost.** *"I never
really liked that and found it too difficult to really use."* So no aggregator,
no ledger, no reconciliation — which also spares this project the business
entity, the per-connection fee and the question of what leaves the machine.
**What is left is most of the value for one person who is already typing bills
in by hand**: what is due, what is late, what recurs, what it actually cost.

5. ~~**Paying, with what actually went out.**~~ **Done August 27, 2026.** `Bill.amount` currently means both
   *what it costs* and *what it cost*, which works only while those are equal.
   A nullable `paid_amount`, set when paid and defaulting to the expected
   figure, so the common case stays one click. **The two totals get sharper**:
   *still to pay* from expected amounts, *already paid* from real ones. And it
   makes *"the electricity bill has been creeping up"* answerable, which a field
   that gets overwritten never can be.
6. ~~**Late is a state.**~~ **Done August 27, 2026**, decided on the server
   against the owner's clock — a browser working out *late* would be a second
   opinion on whose day it is, which is the defect D16 found in the note-to-day
   join. Measured against today rather than the month on screen: an unpaid July
   bill read in September is late, and a paid bill never is.
   ~~Late is a state.~~ An unpaid bill past its due date reads exactly like one
   due next week. The agenda has overdue logic; this page has none, which for a
   bills page is the most important state there is.
7. ~~**Every cadence, and a warning before it lands.**~~ **Done August 27,
   2026, and it needed no new machinery at all** — which is the finding, not an
   aside. `Item.lead_days` already meant *how many days before its due date this
   should be mentioned*, `agenda.py` already surfaced anything inside its lead
   time, and `_spawn_next_occurrence` already carried it. **Nothing let a person
   set it.** So an annual subscription now warns on Bills *and* on the agenda,
   set once, carried into next year.
   ~~Every cadence, and a warning before it lands.~~ The model has weekly,
   monthly, quarterly and annual; the form offers a checkbox. And
   **`Item.lead_days` already does the whole warning job** — `agenda.py` reads
   it, `_spawn_next_occurrence` carries it, and its own comment says why it
   belongs on the task rather than the bill. **Nothing lets a person set it
   from here**, which is the fourth *the parts exist and nobody joined them* in
   one evening.

**7 is the one that answers what this is for**, and it needs no new machinery
at all.

**1 is worth doing whatever happens to the rest**, and it is the one that fixes
a wrong number rather than a missing button.

## Income — August 27, 2026

**Done the same day**, after *"I think I will want to include income and
investments."*

**One model, not two.** §4's test is a different life cycle, and income has a
bill's exactly: it recurs, has a date, has an amount, gets settled, can be late.
What differs is the sign and whether you act or observe, neither of which is a
life cycle. So `Bill` became `MoneyLine` with a `direction` — **a rename that
`makemigrations` wanted to do as a `CreateModel` plus a `DeleteModel`**, which
would have dropped the table and every bill in it under a filename reading like
a rename. Hand-written as `RenameModel` and verified against real rows.

**But income is not a task, and that is the difference that shows.** You do not
tick off being paid, so it is excluded from the day and the agenda — one clause
at `agenda.open_items_for`, the single selection point both use. It lives on
Money alone, where it can still be called late.

**The month now answers four questions**: still to pay, already paid, expected
in, already received. *Did this month balance* is the one that needed the other
three.

**Two open lines from one payee collide**, because the name is derived from the
payee and `unique_active_arealess_item` is `(owner, text)` over everything
unfiled and unarchived. **Accepted rather than designed around** — putting a
number into every name to serve the rarer case makes *Pay Landlord* worse for
the common one. Vince's improvement: **the refusal suggests a way through**
rather than only refusing, and *"Amazon (Prime)"* is a better row than *"Amazon"*
twice would have been. The constraint pushes toward the clearer name.

**And the form was throwing those sentences away.** Every 409 on this router is
worded for a person and the page substituted *"could not be added"* for all of
them. It now reads the server's `detail` and falls back to the status only when
there is nothing to say, because an unworded failure should not pretend to be
advice.

## Balances — August 27, 2026

Vince: *"for those with balances (like loans and credit cards), I'd like to have
the ability to add the current monthly balance -- typically at the end of the
month I'll do a review and update all the balances."*

**A different animal, and §4 says so properly this time.** A `MoneyLine` is an
expected movement on a date that settles once; an `Account` is a value re-read
forever that never settles. A card's balance belongs to the card, not to this
month's payment. Both new models carry their charter compliance at the class.

**And investments came free**, which is why the model was worth insisting on.
Both are *a thing whose value changes, re-read periodically*, differing in sign —
so a stocks ISA is an account with `owes: false` and is already in the update
screen and the held total. One build, not two.

**`owes` is a flag, not a negative number.** A card at 4,200 and an ISA at 4,200
are both four thousand two hundred; storing debt as `-4200` makes every read
carry a sign convention nobody wrote down, and one place forgetting it produces
a net worth wrong by twice the balance.

**A reading is a row.** *Is this loan going down* is a question about a series,
and a field overwritten monthly keeps no series to answer with — the same
argument that gave `paid_amount` its own column.

**The ritual is a batch, so the endpoint is.** One transaction, so a bad figure
in the fifth box does not leave four saved and two not. An untouched box means
*skip me*, never *blank me*. And the boxes start empty with last month shown
beside them: pre-filling would make an untouched box look like a considered
answer, which is the thing a monthly review exists to prevent.

**Owed and held are never subtracted.** A net worth is a different claim from
either, and not one six typed numbers entitle this page to make.

**What the guards caught, and it is the third tonight.**
`test_every_owned_model_is_named_somewhere_in_the_export` failed on the new
models: they hold a person's financial data and were absent from the data export
that `/privacy/` promises. Its docstring anticipated exactly this — *"a model
added later without an export line fails here rather than being discovered by
somebody who has already deleted their account."* Exported as
`accounts_with_balances`, not `accounts`, because the archive already has an
`account` key for login details and two of those teaches a reader the wrong
thing.

## The second phase — a module rather than a month, August 27, 2026

**The premise was never a month view.** Vince: *"a module is essentially its own
sort of landing page for relevant information... if I need to check on financial
information, I know exactly where to go."* What `/money` shows is **August**, and
answering *how am I doing* from it means reading three lists and doing
arithmetic. A month view is not a dashboard, and that difference is the
difference between a page and a module.

8. **The landing page.** `/money` becomes what the module was described as, and
   the month moves to `/money/month/:month`. What it answers, all of it read
   rather than stored: **what is overdue right now** across every month, **what
   is due in the next fortnight** across month boundaries, **what renews soon**,
   **what is owed and held** with the change since last month, and **whether
   this month balances**.

   **This is where `paid_by` stops being a seam.** The account-to-bill link was
   written, accepted by the service and used by nothing — a fifth
   un-switched-on seam, added hours after a guard about exactly that class. An
   account listed beside the bill that pays it is what it was for.

9. **What the recurring things cost a year.** Monthly × 12, quarterly × 4,
   annual × 1. Nobody has that number and it is the one that makes a person
   cancel something. A read over data already held, and the natural companion
   to the renewal warnings.

10. **Out of the month box.** *What is due in the next fortnight* crosses month
    boundaries and nothing can answer it, because every read is keyed to a month.
    Folded into increment 8 rather than built alone: the landing page is the
    caller that needs it, and a read with no caller is the thing this project
    keeps finding.

11. **History, as a table and a graph.** The argument for `paid_amount` and for
    dated balance readings was *is the electricity creeping up* and *is the loan
    going down*. Both are being recorded and **neither is read** — data accruing
    against a promise nobody has kept.

    **The graph is hand-drawn SVG and not a charting library.** A dependency is
    a permanent cost against a handful of sparklines, and this project defers
    dependencies for size on principle — `torch` went that way on August 18.
    Twelve points on a line need no framework. **Recorded as a decision so it is
    not re-argued**, and reversible if a real chart is ever wanted.

    **Worth doing last.** A trend over two readings is not a trend; after three
    monthly passes it earns the screen.

## What is still open

**Investments.** The question is not whether to build it but whether balances
would actually get typed in — Vince abandoned Mint's bank feed because
reconciling it was work, and a stale investments tab fails the same way by a
different road. **Tracking contributions rather than balances** is the version
made of facts you already know at the moment they happen.

## What this refuses

- **A `Bill` model.** §4 settled it and nothing here needs it.
- **A second definition of "paid".** `Item.Status.COMPLETED` is it.
- **Hiding bills from the rest of the product.** Decision 4.
- **A payments integration, reminders, or anything that leaves the machine.**

## Where the facts live

What is active is [`roadmap.md`](roadmap.md); the charter is
[`architecture-trajectory.md`](architecture-trajectory.md) §4; how the product
scores is [`product-stories.md`](product-stories.md), and **this slice is not
aimed at a story** — it is aimed at a surface being unusable, which that file
cannot see. That gap is the interesting part and is noted in `roadmap.md`.
