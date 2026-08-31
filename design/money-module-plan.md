# Money — a place rather than a report — focused spec

Vince · focused spec · written August 27, 2026 · **status is the strikes below**

**Deployed August 27, 2026 at 23:20 local** — `DEPLOYED-2026-08-27/2320`.
This is not a stub yet and the plan is not closed: Vince has used one of the
six screens. [`roadmap-history.md`](roadmap-history.md) owns the deployment
record and why the codename is held rather than refused.

**Renamed from Bills to Money on August 27, 2026**, the same day it was written,
once Vince described what the surface is: *"a module is essentially its own sort
of landing page for relevant information... if I need to check on financial
information, I know exactly where to go."* Then: *"I think I will want to include
income and investments."*

**Bills did not become Money — bills became part of it.** The nav entry, the
route, the read module and the API namespace all moved.

~~**`Bill` keeps its name**, because a bill is one kind of money thing and income
will be another, and a record named after the module would have to be both.~~
**Wrong, and the same day — August 27, 2026.** Income arrived as increment 8 and
went into the *same* record with a `direction`, so the row genuinely does have to
be both, and `Bill` was the name that could not describe it. `MoneyLine` is what
it is called now (`0048`, a hand-written `RenameModel`).

**Keep the reasoning, which was right about the wrong thing.** The fear was
`architecture-trajectory.md` §4's collapse — naming a record after its module
until the module's whole vocabulary has to fit inside one noun. That risk was
real; the mistake was thinking *not renaming* avoided it. What avoided it was the
sidecar staying a sidecar: a bill is still an `Item`, and `MoneyLine` is what
hangs off one. **The noun to protect was `Item`, not `Bill`.**

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

11. **History, as a table and a graph — and a projection.** Vince: *"a table
    with accounts listed, and balances over say a 12 month period. And I'd like
    to have a prediction for the next six months."*

    **The projection is arithmetic and says so.** The average monthly change
    over the readings there are, carried forward six months. Not a model, not a
    fit, nothing generative — `design-concept.md`'s ML policy is not engaged
    because nothing here learns, and a straight line a person can check in their
    head is worth more here than a better curve they cannot.

    **It refuses under three readings.** Two points make a line through
    whatever noise those two months happened to contain, and a projection drawn
    from them looks exactly as confident as one drawn from twelve. *Not enough
    history yet* is the honest output and the one that keeps the other
    projections trustworthy.

    **It carries its own basis.** *"From the last 4 months, averaging −250 a
    month"* travels with the number, because a projection whose derivation is
    invisible is a claim rather than an estimate.

    **And it names the crossing.** For something owed, the month the line
    reaches zero is the thing a person actually wants — *at this rate, clear in
    March 2027* — and it is the one output worth more than the six figures
    behind it. Suppressed for things held, where zero means nothing.

    **The graph is hand-drawn SVG and not a charting library.** A dependency is
    a permanent cost against a handful of sparklines, and this project defers
    dependencies for size on principle — `torch` went that way on August 18.
    Twelve points on a line need no framework. **Recorded so it is not
    re-argued**, and reversible if a real chart is ever wanted.

## The third phase — what looking at it turned up, August 27, 2026

Vince, on seeing the module for the first time: *"for income, there needs to be a
bi-weekly frequency option. And there's like no order to the bills. Like we need
to have categories to make it easier to look at."*

**Both are things no test could have told either of us**, which is the argument
for looking at a thing before building more of it.

12. **Fortnightly.** A salary every two weeks is ordinary and the model had no
    word for it. Cheap, as it turns out: `_nth_occurrence_after` already
    advances weekly by `timedelta(weeks=n)`, and **recurrence is not one of the
    rules mirrored across three languages** — the phone does not model it at
    all — so this is Python and a label in TypeScript. `TIMES_A_YEAR` gains 26.

13. **Categories, and the list belongs to the person.** Vince asked for a fixed
    list *"however add a setting that lets the user manually edit the list"*,
    and that second clause changes what this is. **A list somebody can edit is
    data, not an enum**: it is created, renamed, reordered and deleted on its
    own schedule, which is §4's life-cycle test met rather than argued around.
    So `MoneyCategory` earns a table where a `TextChoices` would not.

    **Seeded, not empty.** A person opening a fresh module should find Housing,
    Utilities, Subscriptions, Insurance, Debt, Transport and Health already
    there — an empty list plus a form is a chore handed to somebody who came to
    look at their bills. They are ordinary rows from birth, so renaming or
    deleting one needs no special case.

    **Nullable on the bill.** *Uncategorised* is a real state and the honest
    default: a bill added in a hurry should not demand a filing decision, which
    is the same reason a bill has no Area.

    **Bills only for now** — one or two income lines do not need grouping, and
    the field lives on the shared record so income can gain it the day there is
    enough income to sort.

14. **Grouped by category, due date within.** The complaint was that the list
    has no shape. Headings give the eye somewhere to land, and it makes *what do
    my subscriptions cost* answerable by looking rather than by adding up.

## What first real use found — August 31, 2026

**Four days after shipping, Vince opened `/money` and tried to use it.** The
walkthrough is the finding, so it is kept in his order rather than sorted by
severity: no useful landing page → *This month* → add a bill (fine) → *Update
balances* → **"No accounts yet. Add one on Money"** → *History* → **"No
accounts yet. Add one"** → the link → the August overview, which also cannot →
click the bill → **"Task detail / No area"**.

**The load-bearing one: `POST /api/v1/money/accounts` had no caller anywhere in
the SPA.** `Account` and `BalanceReading` passed §4, got an endpoint, got tests,
and never got a door. Two screens told somebody to add an account, neither
could, and the link between them pointed at a third that could not either.
`principles.md`'s *a slice is not closed while nothing calls it*, in the module
that had most recently been scored **works**.

**It also invalidated an inference drawn an hour earlier.** Production had zero
`Account` rows after four days, and that was read here as evidence for this
file's own open question — *whether balances would actually get typed in*. It
was not evidence about the input ratio. It was a missing button, and **the
question is still unanswered rather than answered badly**. Recorded because the
wrong reading was the more comfortable one: it agreed with a doubt this plan
already held.

- ~~**No way to create an account.**~~ **Fixed August 31, 2026.** An add form on
  `/money/balances`, where somebody wanting an account is already trying to
  record a balance. Name, kind and currency; `owes` stays null and lets the kind
  decide, which is what the endpoint has always taken two fields for.
- ~~**Both empty states named a page that could not help.**~~ **Fixed the same
  day.** Balances offers the form in place; History links to Balances.
- ~~**A bill opened as "Task detail / No area".**~~ **Fixed the same day.** The
  page says *Bill* and goes back to Money when the sidecar is present. The row
  has linked there since the Bills work; what changed on August 30 is that it
  stopped hanging on `Loading…` for ever, because a bill is a standing task with
  no Area and that page's guard required one —
  [`coherence-audit-2026-08-30.md`](coherence-audit-2026-08-30.md) F3. **Fixing
  an invisible defect is what made this one visible.**
- ~~**The landing page has no first-run state and no way in.**~~ **Fixed
  August 31, 2026.** It rendered a heading, three links, and *"Nothing is
  overdue, due soon, or about to renew"* — a tautology to somebody with no
  bills, on a front door that could not create one.

  **The read could not tell the two empties apart**, which is why the page
  could not either: every list and total is empty both for somebody with
  nothing recorded and for somebody whose month is simply quiet, and those want
  opposite pages. `MoneyLanding` carries `line_count` and `account_count` now.

  **Two counts rather than one flag**, because the useful prompt differs and
  the half-started state is the one that actually happened: a bill recorded, no
  account, and three screens mentioning balances without saying how to have
  one. That state now says so and links to the form.

**And the landing repair broke the endpoint, past a green suite.** Adding
`line_count` and `account_count` to `MoneyLandingOut` was not enough: the
endpoint hand-builds its response dict rather than dumping the dataclass, so
the two disagreed and `/api/v1/money` answered **500 for every request** while
2009 Django tests passed. **Every test on this page drove `money_reader.
landing_for` directly and none made a request** — a reader test proves the
arithmetic, and only a request proves the contract.

It was caught by opening the page, which is the argument for opening the page.
`TheLandingEndpointTest` is the argument for not needing to next time, and its
last case is the guard for the class rather than the instance: every field
`MoneyLandingOut` declares must actually appear in the response.

**And the bill page lost three task-shaped controls** — Vince, the same day:
*"they aren't needed for bills."* Priority, Area and Checklist are task
concepts, and a bill is unfiled by design, is not ranked against other work,
and has no steps.

**Hidden only when there is nothing to lose**, which is the care that made it
safe: any task can be marked a bill from that page, including one already
carrying a priority, an area or a checklist. Hiding those unconditionally
would make real records invisible while they went on existing — and a
recurring one would go on cloning its steps onto every occurrence from a page
showing none. So the control disappears for a clean bill and stays for a task
that became one, which is the only case where it was carrying anything.

**What this says about the module score.** ~~It reads **works**, with a caveat
that the verdict was taken mid-construction.~~ **Corrected the same day**:
[`module-score.md`](module-score.md) reads **not yet**, on Vince's own sentence
— *"obviously Money didn't work"*. That file owns the verdict and what it
learned from being wrong, and it is not restated here. The short version is
that the question was answered by looking **for somebody who already had
data**, and nothing in the module could make somebody into that person.

## What is still open

**Investments.** The question is not whether to build it but whether balances
would actually get typed in — Vince abandoned Mint's bank feed because
reconciling it was work, and a stale investments tab fails the same way by a
different road. **Tracking contributions rather than balances** is the version
made of facts you already know at the moment they happen.

## What this refuses

- ~~**A bill as its own model.** A bill is an `Item` with a `MoneyLine` hanging
  off it, and that did not change when the sidecar was renamed. §4 settled it.~~
  **Overturned August 31, 2026** —
  [`bill-as-a-model-plan.md`](bill-as-a-model-plan.md) owns it.

  **Not because §4 was overridden, but because its test is now met.** §4 asks
  for a different *life cycle*, and the one that qualifies was written down in
  `roadmap.md` on August 28 — a day after this refusal — and nobody put the two
  side by side: a missed period is **gone** for a task and **still owed** for a
  bill, which is the same event demanding opposite outcomes. The refusal was
  right about names and was made before the evidence existed.
  **Three models did pass §4 the same day** — `Account`, `BalanceReading` and
  `MoneyCategory` — each on a life cycle of its own rather than a name of its
  own: an account outlives every reading of it, a reading is immutable once the
  month is over, and a category is a label a person edits and reorders.
- **A second definition of "paid".** `Item.Status.COMPLETED` is it.
- **Hiding bills from the rest of the product.** Decision 4.
- **A payments integration, reminders, or anything that leaves the machine.**

## Where the facts live

What is active is [`roadmap.md`](roadmap.md); the charter is
[`architecture-trajectory.md`](architecture-trajectory.md) §4; how the product
scores is [`product-stories.md`](product-stories.md), and **this slice is not
aimed at a story** — it is aimed at a surface being unusable, which that file
cannot see. That gap is the interesting part and is noted in `roadmap.md`.
