"""The money module's reads -- what is due, what went out, what it came to.

**Was `bills.py` until August 27, 2026**, renamed when Vince widened the surface
from Bills to Money: *"if I need to check on financial information, I know
exactly where to go."* Bills did not become Money -- **bills became part of
it**, and income is the sibling this file is now named to hold.

**`Bill` keeps its name**, deliberately. A bill is one kind of money thing and
income is another; a model named after the module would have to be both, which
is the collapse `architecture-trajectory.md` §4 exists to catch. The rename is
the module and the namespace, not the noun.

Original docstring follows.

What is due this month, and what it comes to.

A read, not a model. A bill is a task with a `Bill` sidecar -- see that model
for why §4 said no to a primitive -- so everything here is a question about
rows that already exist.

Its own module beside `agenda.py` and `projects.py`, because it is a read with
its own vocabulary and putting it in the agenda would make the agenda answer a
question about money.
"""

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Q

from lists.models import Bill, Item


@dataclass(frozen=True)
class BillRow:
    task: Item
    bill: Bill

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
        for bill in Bill.objects.filter(
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
    unpriced = 0
    for row in rows:
        if row.bill.amount is None:
            # Counted whether or not it is paid: "the water bill, whatever it
            # came to" is as unpriced after paying it as before.
            unpriced += 1
            continue
        if row.paid:
            # What went out, not what was expected -- they differ the moment
            # somebody pays extra, and only one of them is what the month cost.
            # Falls back to the expected figure for bills paid before
            # `paid_amount` existed.
            paid[row.bill.currency] += (
                row.bill.paid_amount
                if row.bill.paid_amount is not None
                else row.bill.amount
            )
        else:
            due[row.bill.currency] += row.bill.amount
    return MonthOfBills(
        bills=rows,
        due_totals=dict(due),
        paid_totals=dict(paid),
        unpriced=unpriced,
    )
