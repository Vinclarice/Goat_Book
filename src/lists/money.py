"""The money module's reads -- what is due, what went out, what it came to.

**Was `bills.py` until August 27, 2026**, renamed when Vince widened the surface
from Bills to Money: *"if I need to check on financial information, I know
exactly where to go."* Bills did not become Money -- **bills became part of
it**, and income is the sibling this file is now named to hold.

**`MoneyLine` keeps its name**, deliberately. A bill is one kind of money thing and
income is another; a model named after the module would have to be both, which
is the collapse `architecture-trajectory.md` §4 exists to catch. The rename is
the module and the namespace, not the noun.

Original docstring follows.

What is due this month, and what it comes to.

A read, not a model. A bill is a task with a `MoneyLine` sidecar -- see that model
for why §4 said no to a primitive -- so everything here is a question about
rows that already exist.

Its own module beside `agenda.py` and `projects.py`, because it is a read with
its own vocabulary and putting it in the agenda would make the agenda answer a
question about money.
"""

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
import datetime
from datetime import timedelta
from decimal import Decimal

from django.db.models import Q

from lists.models import Account, Direction, Item, MoneyLine


@dataclass(frozen=True)
class BillRow:
    task: Item
    bill: MoneyLine

    @property
    def paid(self):
        """Whether this one is settled.

        **`completed_at`, not a status**, and the difference is not pedantry:
        a completed *recurring* task is `ARCHIVED` rather than `COMPLETED` --
        `complete_item` says so, because `unique_active_arealess_item` would
        otherwise refuse the successor it spawns in the same breath. Reading the
        status would therefore have hidden every paid rent, which is the bill
        this page most exists for.

        **There is still no second definition of paid**: `completed_at` is the
        one the day and the agenda read, and it is cleared by `reopen_item`, so
        un-paying works without anything here knowing about it.
        """
        return self.task.completed_at is not None

    def overdue_on(self, today):
        """Unpaid, and the day it was due has gone.

        **Against the owner's own today**, not the month being looked at: an
        unpaid July bill read in September is late, and reading it in July is
        not what makes it so. `clarice.clocks.today_for` is the rule, and a
        date worked out in a browser would be a second opinion on whose day it
        is -- which is the defect D16 found in the note-to-day join.

        A paid bill is never late, whenever it was paid. *Paid, eventually* is
        a fact about the past and this is a state about now.
        """
        if self.paid or self.task.due_date is None:
            return False
        return self.task.due_date < today


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


def bills_for(owner, day):
    """Every bill in the month containing ``day``, soonest first, paid or not.

    **Paid ones are included, and used not to be.** The filter said open only,
    on the reasoning that *a paid bill is not still due, which is the agenda's
    own definition of open rather than a second one* -- true of an agenda, and
    wrong here. **Not due and not this month's are different facts**, and this
    page is asked both *what do I owe* and *what did this month cost*; the old
    read could answer only the first while appearing to answer both.

    Archived bills stay out. That is not a filter on paid-ness -- it is the
    task core's own "this is put away" and it means the same thing here.

    Any day of the month asks about the same month, the courtesy
    `intention_for` and `month_for` already give a week and a month.
    """
    first = day.replace(day=1)
    last = first.replace(day=monthrange(first.year, first.month)[1])

    rows = [
        BillRow(task=bill.item, bill=bill)
        for bill in MoneyLine.objects.filter(
            item__owner=owner,
            # Open ones, plus anything ever paid -- including the paid
            # recurring occurrences that are `ARCHIVED` rather than
            # `COMPLETED`. A task archived *without* being completed is
            # genuinely put away and stays out.
            item__due_date__gte=first,
            item__due_date__lte=last,
        )
        .filter(Q(item__status=Item.Status.ACTIVE) | Q(item__completed_at__isnull=False))
        .select_related("item", "item__list")
        .order_by("item__due_date", "item__id")
    ]

    due = defaultdict(Decimal)
    paid = defaultdict(Decimal)
    expected_in = defaultdict(Decimal)
    received = defaultdict(Decimal)
    unpriced = 0
    for row in rows:
        if row.bill.amount is None:
            # Counted whether or not it is paid: "the water bill, whatever it
            # came to" is as unpriced after paying it as before.
            unpriced += 1
            continue
        # **Four buckets, not two**, because a salary in the *still to pay*
        # column would make every month look catastrophic. Direction decides
        # which pair, settlement decides which of the pair.
        incoming = row.bill.direction == Direction.IN
        if row.paid:
            # What actually moved, not what was expected -- they differ the
            # moment somebody pays extra or a bonus lands. Falls back to the
            # expected figure for rows settled before `paid_amount` existed.
            settled = (
                row.bill.paid_amount
                if row.bill.paid_amount is not None
                else row.bill.amount
            )
            (received if incoming else paid)[row.bill.currency] += settled
        else:
            (expected_in if incoming else due)[row.bill.currency] += row.bill.amount
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
    Item.Recurrence.WEEKLY: 52,
    # 26, not 12. A fortnightly figure counted monthly understates the year by
    # a sixth, which is the sort of error a yearly total exists to avoid.
    Item.Recurrence.FORTNIGHTLY: 26,
    Item.Recurrence.MONTHLY: 12,
    Item.Recurrence.QUARTERLY: 4,
    Item.Recurrence.ANNUAL: 1,
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


def landing_for(owner, *, today):
    """Everything the landing page says, in one pass.

    ``today`` is injected rather than read from the clock -- `principles.md`,
    *pass dates and times into domain logic* -- which is also what lets this be
    tested at a month boundary without freezing time.
    """
    rows = [
        BillRow(task=line.item, bill=line)
        for line in MoneyLine.objects.filter(
            item__owner=owner, direction=Direction.OUT
        ).select_related("item")
    ]
    open_rows = [row for row in rows if not row.paid and row.task.due_date]

    overdue = sorted(
        (row for row in open_rows if row.task.due_date < today),
        key=lambda row: row.task.due_date,
    )
    due_soon = sorted(
        (
            row
            for row in open_rows
            if today <= row.task.due_date <= today + SOON
        ),
        key=lambda row: row.task.due_date,
    )
    # Inside its lead time and not already in the two lists above: saying a
    # thing twice on one screen is how a page stops being read.
    already = {row.task.pk for row in overdue} | {row.task.pk for row in due_soon}
    renewing = sorted(
        (
            row
            for row in open_rows
            if row.task.pk not in already
            and row.task.lead_days
            and row.task.due_date <= today + timedelta(days=row.task.lead_days)
        ),
        key=lambda row: row.task.due_date,
    )

    yearly = defaultdict(Decimal)
    for row in rows:
        times = TIMES_A_YEAR.get(row.task.recurrence)
        if times is None or row.bill.amount is None:
            continue
        yearly[row.bill.currency] += row.bill.amount * times

    owed, held, owed_change, held_change, unread = _balances(owner, today)
    return MoneyLanding(
        overdue=overdue,
        due_soon=due_soon,
        renewing_soon=renewing,
        yearly_totals=dict(yearly),
        owed_totals=dict(owed),
        held_totals=dict(held),
        owed_change=dict(owed_change),
        held_change=dict(held_change),
        unread_accounts=unread,
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
    for account in Account.objects.filter(owner=owner).prefetch_related("readings"):
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
