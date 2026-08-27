# Bills, as a place rather than a report — focused spec

Vince · focused spec · written August 27, 2026 · **status is the strikes below**

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

1. **The read learns about paid.** `bills_for` returns the whole month with a
   paid flag and two totals; the page shows both and marks what is paid. No
   write path yet. **The failing test is the month that cost 1264.99 reporting
   64.99.**
2. **Adding, on the page.** One form — payee, amount, currency, due date,
   repeats — behind a service that writes the `Item` and the `Bill` in one
   transaction. The empty state stops being a dead end.
3. **Editing in place**, the same fields against an existing bill.
4. **Deleting**, with the recurring question asked once.

**1 is worth doing whatever happens to the rest**, and it is the one that fixes
a wrong number rather than a missing button.

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
