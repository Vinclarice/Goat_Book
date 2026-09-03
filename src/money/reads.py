"""The money module's reads -- what is due, what went out, what it came to.

**Was `bills.py` until August 27, 2026**, renamed when Vince widened the surface
from Bills to Money: *"if I need to check on financial information, I know
exactly where to go."* Bills did not become Money -- **bills became part of
it**, and income is the sibling this file is now named to hold.

**The noun is `Bill`, and it is a model of its own since August 31, 2026.** A
bill was a task with a `MoneyLine` sidecar until then -- deleted September 1 --
on the argument that §4 says no to a primitive for a concept that only has a
different *name*. What
overturned it is in `bill-as-a-model-plan.md` §2: a missed period is gone for a
task and still owed for a bill, which is a different life cycle and is exactly
what §4 asks for.

**These are reads, and the writes are `bills.py`.** Its own module beside
`agenda.py` for the reason that one is: a read with its own vocabulary, and
putting it in the agenda would make the agenda answer a question about money.
"""

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
import datetime
from datetime import timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from clarice.recurrence import Recurrence
from money.models import Account, Bill, Direction


@dataclass(frozen=True)
class MonthOfBills:
    """The month's bills, and what they add up to.

    `totals` is **per currency and never across them**: adding 500 USD to 40
    GBP produces 540 of nothing. One number would be easier to render and would
    be wrong -- the same trade sectioned search already refused once, where a
    rank across two document sets means nothing and fails silently.

    Empty rather than zero when there are no bills: "nothing is due" and
    "0.00 is due" are different, and only one of them deserves a total.
    """

    bills: list
    #: What is **still owed** this month, per currency. Named for the question
    #: it answers, which the field it replaced was not -- `totals` held exactly
    #: this and was rendered under the word *total*, so a month that cost
    #: 1264.99 reported 64.99. See `money-module-plan.md`, defect 4.
    due_totals: dict
    #: What has **already gone out** this month, per currency. Two figures
    #: rather than one, because a single number has to choose which of *what do
    #: I owe* and *what did this month cost* it is answering, and cannot say
    #: which it chose.
    paid_totals: dict
    #: What is **expected in** and has not arrived, per currency.
    expected_in_totals: dict
    #: What has **already arrived**, per currency. Kept apart from what is
    #: expected for the same reason `paid_totals` is kept apart from
    #: `due_totals`: a figure that mixes the two cannot say whether a month
    #: balanced or merely looks as though it will.
    received_totals: dict
    #: How many of them have no amount. Counted and not totalled, because "the
    #: water bill, whatever it comes to" is a real bill and a total that
    #: silently omitted it would be a number somebody plans against.
    unpriced: int


def month_from_bills(owner, day):
    """What is owed and what was settled in the month `day` falls in.

    **Three things the read this replaced had to do**, kept as a record of what
    the split bought rather than as an argument for it. It wrapped each row in
    a `BillRow` to hold a task and its sidecar together; here the row *is* the
    record. It reconciled status, because a paid *recurring* task is `ARCHIVED`
    rather than `COMPLETED`, so settlement had to be read from `completed_at`
    and never from the status; `paid_at` has no such trap. And it filtered the
    archive, because *put away* is a task state.

    **That last one is a decision rather than a simplification**: a bill you
    neither pay nor delete is now simply owed. Nothing was affected --
    development and production both held zero archived bills when the
    conversion ran -- but the concept is gone rather than carried.
    """
    first = day.replace(day=1)
    last = first.replace(day=monthrange(first.year, first.month)[1])

    rows = list(
        Bill.objects.filter(
            owner=owner, due_date__gte=first, due_date__lte=last
        ).order_by("due_date", "id")
    )

    due = defaultdict(Decimal)
    paid = defaultdict(Decimal)
    expected_in = defaultdict(Decimal)
    received = defaultdict(Decimal)
    unpriced = 0
    for row in rows:
        incoming = row.direction == Direction.IN
        if row.amount is None:
            # Counted whether or not it is settled: "the water bill, whatever
            # it came to" is as unpriced after paying it as before.
            unpriced += 1
            # **But a payment against it is still money that moved.** This
            # `continue` used to come first, so an unpriced bill settled for an
            # explicit 50 was counted as unpriced and then skipped -- and 50
            # vanished from *already paid*. Both facts are true at once: what it
            # was expected to come to is unknown, and what went out is 50.
            if row.paid_at is not None and row.paid_amount is not None:
                (received if incoming else paid)[row.currency] += row.paid_amount
            continue
        # Four buckets, not two. Direction decides which pair, settlement
        # decides which of the pair -- a salary in the *still to pay* column
        # would make every month look catastrophic.
        if row.paid_at is not None:
            # What actually moved, falling back to what was expected for rows
            # settled without a figure -- which is a real state here, see
            # `Bill.paid_at`.
            settled = row.paid_amount if row.paid_amount is not None else row.amount
            (received if incoming else paid)[row.currency] += settled
        else:
            (expected_in if incoming else due)[row.currency] += row.amount
    return MonthOfBills(
        bills=rows,
        due_totals=dict(due),
        paid_totals=dict(paid),
        expected_in_totals=dict(expected_in),
        received_totals=dict(received),
        unpriced=unpriced,
    )


# ---------------------------------------------------------------------------
# The landing read
# ---------------------------------------------------------------------------

#: How far ahead *soon* reaches. A fortnight because it is the span a person can
#: still do something about -- long enough to move money, short enough that the
#: list stays worth reading. Not configurable: a setting nobody changes is a
#: question asked once and answered forever.
SOON = timedelta(days=14)

#: How many times a year each cadence lands. `NONE` is absent rather than zero,
#: so a one-off cannot be counted as costing anything annually -- it happens
#: once, and inflating the figure a person acts on is the one failure this
#: number must not have.
TIMES_A_YEAR = {
    Recurrence.WEEKLY: 52,
    # 26, not 12. A fortnightly figure counted monthly understates the year by
    # a sixth, which is the sort of error a yearly total exists to avoid.
    Recurrence.FORTNIGHTLY: 26,
    Recurrence.MONTHLY: 12,
    Recurrence.QUARTERLY: 4,
    Recurrence.ANNUAL: 1,
}


@dataclass(frozen=True)
class MoneyLanding:
    """What the module says when you arrive at it.

    **All read, nothing stored.** No row exists because this page does, which is
    `daily-operating-system-vision.md`'s rule for the Day page and holds for the
    same reason: a lens over durable records is never out of step with them.
    """

    #: Owed and past due, every month rather than this one -- an unpaid June
    #: bill is still owed in August.
    overdue: list
    #: Due within `SOON`, **across the month boundary**, which is the thing no
    #: other read here could answer.
    due_soon: list
    #: Inside its own lead time. The reason the module exists.
    renewing_soon: list
    #: What every repeating thing costs in a year, per currency.
    yearly_totals: dict
    #: The latest balance of everything owed, and of everything held.
    owed_totals: dict
    held_totals: dict
    #: The move since the month before, per currency. Negative is down, which
    #: for something owed is the good direction and for something held is not --
    #: the page says which, this only reports the arithmetic.
    owed_change: dict
    held_change: dict
    #: Accounts with no reading in the current month. Counted rather than listed
    #: so the page can nudge without becoming a second balances screen.
    unread_accounts: int
    #: **Have you ever put anything here**, which every field above is silent
    #: about: they all read empty for somebody with nothing recorded *and* for
    #: somebody whose month is simply quiet, and those want opposite pages.
    #: Until August 31, 2026 the landing page could not tell them apart and
    #: told a person with no bills that nothing was overdue.
    #:
    #: **Two counts rather than one flag**, because the useful prompt differs:
    #: somebody with bills and no accounts is missing balances, not a start.
    #: Every money line ever, in any month and either direction.
    line_count: int
    account_count: int


def landing_from_bills(owner, *, today):
    """How the money stands today: what is late, what is near, what it costs.

    **Three joins became none.** The read this replaced walked a sidecar to its
    `Item` for the date, the lead time and the recurrence, with a `BillRow` to
    hold the pair together. Every field here is on the row.

    **`recurrence` becomes `series.cadence`, and a one-off is correctly
    absent** rather than filtered: `TIMES_A_YEAR` has no entry for *does not
    repeat*, and a bill with no series has no cadence to look up. The old read
    reached the same answer through `Recurrence.NONE` missing from the
    same table, which is the same rule said twice.
    """
    rows = list(
        Bill.objects.filter(owner=owner, direction=Direction.OUT)
        .select_related("series")
        # **Ordered because the yearly total depends on it.** That figure takes
        # the most recent priced occurrence per series, and "most recent" is not
        # a property an unordered query has -- Postgres would answer in whatever
        # order it liked, so which month's price a person saw would be
        # arbitrary and would change. Added September 2, 2026, with the fix that
        # created the dependency.
        .order_by("due_date", "id")
    )
    open_rows = [row for row in rows if row.paid_at is None and row.due_date]
    overdue = sorted(
        (row for row in open_rows if row.due_date < today),
        key=lambda row: row.due_date,
    )
    due_soon = sorted(
        (row for row in open_rows if today <= row.due_date <= today + SOON),
        key=lambda row: row.due_date,
    )
    already = {row.pk for row in overdue} | {row.pk for row in due_soon}
    renewing = sorted(
        (
            row
            for row in open_rows
            if row.pk not in already
            and row.lead_days
            and row.due_date <= today + timedelta(days=row.lead_days)
        ),
        key=lambda row: row.due_date,
    )
    # **What the standing arrangements cost a year, counted once per
    # arrangement.** This iterated every row until September 2, 2026, so a
    # monthly bill first recorded at 10 and later at 12 reported 264 a year --
    # (10 + 12) x 12 -- for one subscription. **Increment 6 made it inflate on a
    # schedule**, because `catch_up` adds an occurrence a month to every live
    # series, and this is the number a person is meant to act on when deciding
    # what to cancel.
    #
    # **The most recent priced occurrence is the evidence**, not the oldest and
    # not the series template: an occurrence is what a month actually cost, and
    # the latest one is the best available claim about what the next will be.
    # `rows` is ordered by date, so the last write per series wins.
    latest_priced = {}
    for row in rows:
        if row.series_id is None or row.amount is None:
            continue
        latest_priced[row.series_id] = row
    yearly = defaultdict(Decimal)
    for row in latest_priced.values():
        times = TIMES_A_YEAR.get(row.series.cadence)
        if times is None:
            continue
        yearly[row.currency] += row.amount * times
    owed, held, owed_change, held_change, unread = _balances(owner, today)
    return MoneyLanding(
        overdue=overdue,
        due_soon=due_soon,
        renewing_soon=renewing,
        yearly_totals=dict(yearly),
        owed_totals=owed,
        held_totals=held,
        owed_change=owed_change,
        held_change=held_change,
        unread_accounts=unread,
        line_count=Bill.objects.filter(owner=owner).count(),
        account_count=Account.objects.filter(owner=owner).count(),
    )


def open_bills_for(owner):
    """Bills still owed, in the order the agenda sorts by — the `Bill` half of
    `agenda.open_items_for`.

    **Decision 4 is what this exists for.** `money-module-plan.md`: *bills stay
    ordinary tasks elsewhere — day, agenda, lists. Paying is a real thing to do
    on a day, and the day is where it gets noticed.* A bill that is no longer
    an `Item` does not appear in a read that queries `Item`, so preserving that
    decision means every such read gains a second source. This is that source.

    **Income is excluded, exactly as `open_items_for` excludes it.** A salary
    is not something to do on a Tuesday, and it landing in the agenda would
    make the list a ledger.

    **Sorted by due date, nulls impossible.** `Bill.due_date` is not nullable,
    which is the one way this read is simpler than the task one it sits beside.
    """
    return (
        Bill.objects.filter(owner=owner, paid_at__isnull=True)
        .exclude(direction=Direction.IN)
        .select_related("series", "category", "account")
        .order_by("due_date", "id")
    )


def coming_bills_for(owner, today=None):
    """Bills inside their own lead time, soonest first — the `Bill` half of
    `agenda.coming_up_for`.

    **Advance notice is the feature bills need most**, and *"property tax, in
    seven days"* is the archetypal case for a lead time. The task version
    reads `open_items_for`, which stopped returning bills at increment 4 of
    `bill-as-a-model-plan.md`; without this the one outbound channel this
    product has would have gone quiet about the records it is most useful for,
    while every test named for a lead time kept passing, because they all use
    tasks.

    **The same three rules the task version follows**, deliberately not
    re-derived: strictly after today, so nothing is said twice in one email;
    zero lead time is off rather than *the day itself*; and the comparison is
    per row against that row's own `lead_days`, which is why it is not a plain
    `due_date__lte` bound.
    """
    today = today or timezone.localdate()
    return sorted(
        (
            bill
            for bill in open_bills_for(owner)
            if bill.lead_days
            and today < bill.due_date <= today + timedelta(days=bill.lead_days)
        ),
        key=lambda bill: (bill.due_date, bill.id),
    )


def _balances(owner, today):
    """The latest figures and the move since the month before.

    **An account with no reading contributes nothing and is counted.** Carrying
    last month's figure forward would report a balance nobody checked as though
    somebody had, which is the failure the update screen's empty boxes exist to
    prevent -- the same argument, one layer up.
    """
    this_month = today.replace(day=1)
    previous = (this_month - timedelta(days=1)).replace(day=1)
    owed, held = defaultdict(Decimal), defaultdict(Decimal)
    owed_change, held_change = defaultdict(Decimal), defaultdict(Decimal)
    unread = 0
    for account in Account.objects.filter(owner=owner, closed_at__isnull=True).prefetch_related("readings"):
        by_month = {r.on_date: r.amount for r in account.readings.all()}
        current = by_month.get(this_month)
        if current is None:
            unread += 1
            continue
        totals = owed if account.owes else held
        changes = owed_change if account.owes else held_change
        totals[account.currency] += current
        before = by_month.get(previous)
        if before is not None:
            changes[account.currency] += current - before
    return owed, held, owed_change, held_change, unread


# ---------------------------------------------------------------------------
# History, and arithmetic about it
# ---------------------------------------------------------------------------

#: Below this, no projection is offered. Two points make a line through whatever
#: noise those two months happened to contain, and that line looks exactly as
#: confident as one drawn from twelve -- so the refusal is what keeps the rest
#: worth believing.
ENOUGH_TO_PROJECT = 3

#: How far ahead. Vince asked for six months, and six is also about as far as an
#: average-of-recent-change stays honest.
PROJECT_AHEAD = 6


@dataclass(frozen=True)
class Projection:
    """Where a balance is heading, if it carries on as it has been.

    **Arithmetic, not a model.** The mean monthly change over the readings
    there are. Nothing learns, nothing is fitted, and
    `design-concept.md`'s ML policy is not engaged -- a straight line somebody
    can check in their head beats a better curve they cannot.
    """

    #: (month, figure), oldest first.
    months: list
    #: The average move a month, negative when falling.
    monthly_change: Decimal
    #: How many readings it was drawn from. Travels with the number, because a
    #: projection whose derivation is invisible is a claim rather than an
    #: estimate.
    readings_used: int
    #: For something owed, the month the line reaches zero -- *at this rate,
    #: clear in March 2027*. None when it never does, and always None for
    #: something held, where zero means nothing.
    clears_on: object


@dataclass(frozen=True)
class HistoryRow:
    account: object
    #: {month: figure or None}. **None is a gap, not a zero**: nothing recorded
    #: and nothing owed are different facts and only one is a number.
    balances: dict
    projection: object


@dataclass(frozen=True)
class BalanceHistory:
    months: list
    rows: list


def _months_back(today, count):
    """``count`` first-of-months ending with the one ``today`` falls in."""
    months = []
    year, month_number = today.year, today.month
    for _ in range(count):
        months.append(datetime.date(year, month_number, 1))
        month_number -= 1
        if month_number == 0:
            year, month_number = year - 1, 12
    return list(reversed(months))


def _add_months(start, count):
    total = start.month - 1 + count
    return datetime.date(start.year + total // 12, total % 12 + 1, 1)


def _project(readings, *, owes):
    """Carry the average monthly change forward.

    ``readings`` is (month, figure), oldest first, gaps already removed -- a
    missing month is not a zero and averaging over one would invent a fall
    nobody had.
    """
    if len(readings) < ENOUGH_TO_PROJECT:
        return None

    first_month, first = readings[0]
    last_month, last = readings[-1]
    # Months apart rather than readings apart, so a gap does not make the change
    # look steeper than it was.
    span = (last_month.year - first_month.year) * 12 + last_month.month - first_month.month
    if span == 0:
        return None
    change = (last - first) / span

    months, running = [], last
    clears_on = None
    for step in range(1, PROJECT_AHEAD + 1):
        running = running + change
        when = _add_months(last_month, step)
        if owes and running <= 0:
            # A loan does not become a negative loan; it ends. The first month
            # it reaches zero is the answer, and the rest of the line is zeroes
            # rather than a debt somebody is owed.
            running = Decimal("0.00")
            if clears_on is None:
                clears_on = when
        months.append((when, running.quantize(Decimal("0.01"))))
    return Projection(
        months=months,
        monthly_change=change.quantize(Decimal("0.01")),
        readings_used=len(readings),
        clears_on=clears_on,
    )


def history_for(owner, *, today, months=12):
    """Every account's balance over the last ``months``, and where it is going.

    ``today`` is injected rather than read from the clock -- `principles.md`,
    *pass dates and times into domain logic* -- which is what lets a table for
    August and a table for September disagree correctly.
    """
    window = _months_back(today, months)
    rows = []
    for account in Account.objects.filter(owner=owner).prefetch_related("readings"):
        by_month = {r.on_date: r.amount for r in account.readings.all()}
        balances = {each: by_month.get(each) for each in window}
        # Projected from every reading held, not only the ones on screen: a
        # twelve-month window is a display choice and should not quietly change
        # the arithmetic.
        ordered = sorted(by_month.items())
        rows.append(
            HistoryRow(
                account=account,
                balances=balances,
                projection=_project(ordered, owes=account.owes),
            )
        )
    return BalanceHistory(months=window, rows=rows)


# ---------------------------------------------------------------------------
# What the task core's surfaces are given
#
# **Narrow contracts rather than a shared query.** The Day and the Agenda show
# bills -- `bill-as-a-model-plan.md` decision 4 -- and they should not have to
# know what a `Bill` is to do it. These three are what they consume; everything
# else here is Money's own.
#
# **Moved from `lists/agenda.py` on September 2, 2026.** They lived there
# because the agenda payload was where bills first needed serializing, which is
# how a module's code ends up in a sibling: not by anybody deciding it should,
# but by the first caller being over there.
# ---------------------------------------------------------------------------


def bill_row(bill):
    """One bill, as the Day, the Agenda and the digest carry it.

    **Not a task-shaped row.** A bill has no area, tag, priority or checklist,
    so sending a `TaskOut` would mean synthesising a dozen fields it has not got
    and the SPA would offer to file it in an Area.

    `id` is the `Bill`'s. It was spelled `task_id` for two days after the flip;
    see `money/api_v1.AgendaBillOut`, which this fills.
    """
    series = bill.series
    return {
        "id": bill.id,
        "payee": bill.payee,
        "due_date": bill.due_date.isoformat(),
        "amount": str(bill.amount) if bill.amount is not None else None,
        "currency": bill.currency,
        "direction": bill.direction,
        "repeats": series is not None and series.ended_at is None,
    }


def actionable_bills_for(owner, day):
    """The bills `day` has a claim on: overdue, or due on it.

    **The Day's question, and it is not the Agenda's.** `daily.reads` puts tasks
    through `DAY_BUCKETS` -- overdue and today, nothing else -- so a task due in
    June does not appear in September. Bills arrived in an array of their own at
    increment 5 with no gating at all, and **every open bill appeared on every
    day's page**: a bill due June 2027 was on the page for September 2, 2026.
    Found by moving this read here, from a signature that had a `day` in it and
    the one it replaced did not.

    **Overdue is included and that is the asymmetry, not an oversight.** A
    missed payment is still owed, which is the whole argument `Bill` exists on;
    `daily.reads.action_items_for` includes overdue tasks for the ordinary
    version of the same reason.
    """
    return [
        bill for bill in open_bills_for(owner) if bill.due_date <= day
    ]


# ---------------------------------------------------------------------------
# What the morning email says about a bill
#
# **Moved from `send_due_digest.py` on September 2, 2026.** The command owns
# *when* somebody is written to and what a task's line says; what a *bill's*
# line says is Money's, and it was over there for the same accidental reason
# the agenda's row was -- the first caller happened to live there.
#
# `url_for` is passed in rather than imported, so Money composes the sentence
# and the delivery channel still owns its own link-building. Money decides what
# needs mentioning; notification infrastructure delivers it.
# ---------------------------------------------------------------------------

def digest_line(bill, today, url_for):
    """One owed bill, as a line of the morning email.

    **Not `_describe`.** A bill has no area to name and no `/tasks/{id}` to
    open, so borrowing the task renderer would print a task's sentence about a
    record that is not one and hand somebody a link that 404s. What it has
    instead is a figure, which is the thing worth seeing in a message read on
    a lock screen.
    """
    days = (today - bill.due_date).days
    if days > 0:
        when = "due yesterday" if days == 1 else f"{days} days overdue"
    else:
        when = "due today"
    what = f"{bill.amount} {bill.currency}, " if bill.amount is not None else ""
    return "\n".join(
        [
            f"  - {bill.payee} ({what}{when})",
            f"    {url_for(f'money/bills/{bill.id}')}",
        ]
    )


def digest_coming_line(bill, today, url_for):
    days = (bill.due_date - today).days
    when = "tomorrow" if days == 1 else f"in {days} days"
    what = f"{bill.amount} {bill.currency}, " if bill.amount is not None else ""
    return "\n".join(
        [
            f"  - {bill.payee} ({what}due {when})",
            f"    {url_for(f'money/bills/{bill.id}')}",
        ]
    )
