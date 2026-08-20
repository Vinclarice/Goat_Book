"""What is due this month, and what it comes to.

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

from lists.models import Bill, Item


@dataclass(frozen=True)
class BillRow:
    task: Item
    bill: Bill


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
    totals: dict
    #: How many of them have no amount. Counted and not totalled, because "the
    #: water bill, whatever it comes to" is a real bill and a total that
    #: silently omitted it would be a number somebody plans against.
    unpriced: int


def bills_for(owner, day):
    """The bills due in the month containing ``day``, soonest first.

    Open ones only -- a paid bill is not still due, which is the agenda's own
    definition of open rather than a second one. Any day of the month asks
    about the same month, the courtesy `intention_for` and `month_for` already
    give a week and a month.
    """
    first = day.replace(day=1)
    last = first.replace(day=monthrange(first.year, first.month)[1])

    rows = [
        BillRow(task=bill.item, bill=bill)
        for bill in Bill.objects.filter(
            item__owner=owner,
            item__status=Item.Status.ACTIVE,
            item__due_date__gte=first,
            item__due_date__lte=last,
        )
        .select_related("item", "item__list")
        .order_by("item__due_date", "item__id")
    ]

    totals = defaultdict(Decimal)
    unpriced = 0
    for row in rows:
        if row.bill.amount is None:
            unpriced += 1
            continue
        totals[row.bill.currency] += row.bill.amount
    return MonthOfBills(bills=rows, totals=dict(totals), unpriced=unpriced)
