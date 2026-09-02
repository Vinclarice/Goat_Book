# A bill earns its own model

**Shipped August 31 – September 2, 2026. Nine increments, six migrations, and
not yet deployed** — the deploy carries `0055`–`0060`, one of which deletes rows
and one of which drops a table. From Vince, after using the repaired Money
module: *"there's a disconnect. Like it should be tied to the payments. So I
really think we need to separate bills from a task."*

This is a stub. What shipped, the reversal condition that was met and declined,
the four things the increments found that the plan had not, and the two mistakes
worth keeping are in [`roadmap-history.md`](roadmap-history.md) under *A bill
earns its own model*.

## The sections code cites, and where each argument now lives

Fifty files cite this plan, and eight of them by section rather than by name —
which is why this stub is longer than most. `admin-mfa-plan.md` is the
precedent: a reader arriving from a migration on *increment 4* should not have
to guess where the reasoning went.

**§2 — why a bill earns a model** (`money.py`, `models.py`, `services.py`,
`bills.py`). `architecture-trajectory.md` §4 grants a model for a **different
life cycle, not a different name**, and it is met rather than waived: the same
event — a period elapsing unfinished — must produce opposite outcomes. A missed
bin round did not happen; a missed payment is still owed. Two behaviours that
cannot share one `status` field is what §4 asks for. The full argument is in the
history entry; the code that depends on it states its own rule and cites this as
provenance.

**Decision 4 — bills stay on the daily surfaces** (`agenda.py`, `daily/reads.py`,
`DayRoute.tsx`, `AgendaWorkspace.tsx`). Paying is a real thing to do on a day, so
a bill that stops being an `Item` arrives in a `bills` array rather than leaving
the page. **This was the plan's own reversal condition, and it triggered** — it
cost two shapes on one screen — and Vince's call on August 31 was to pay it.

**The increments**, each struck in the commit that shipped it, now one line each:

1. `Bill` and `BillSeries` created dark, with the trigger that switches them on.
2. `0055` copies every `MoneyLine` and its `Item` across, refusing two states it
   cannot represent rather than guessing.
3. The `Bill` reads written and proven against the old ones — half of it moved
   into 4 on purpose, because a mirror across two models was a worse bug surface
   than the thing it de-risked.
4. **The point of no return**: reads and writes switch together, and `0057`
   deletes the task copies `0055` left behind.
5. Decision 4's cost, paid — the `bills` array on the agenda and the day.
6. **Missed periods are replayed** — `bills.catch_up`, hourly from the playbook.
   The life-cycle difference in §2, demonstrated rather than argued.
7. **`Account.paid_by` returns as `Bill.account`** — the disconnect Vince
   reported. Written and deleted in one evening on August 27 for having no
   reader; it came back with both halves, which was the condition `d50d6eb` set.
8. `MoneyLine` deleted — and its not-negative CHECK carried onto `Bill`, which
   had never been given one.
9. The key stops calling itself `task_id`.

## What is still open

**Whether replaying missed periods produces a wall of arrears.** Measured at six
further unpaid rows by March 2027 on one untouched series. It is
[`roadmap.md`](roadmap.md)'s own entry now rather than a paragraph in here — the
signal to watch is the agenda, and the cheapest answer if it arrives is a
per-series cap on unpaid occurrences surfaced, not a retreat from the model.

Reduced to a stub on September 2, 2026. See [`README.md`](README.md).
