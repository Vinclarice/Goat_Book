"""Writing bills — the service module for `Bill` and `BillSeries`.

Increment 4 of `design/bill-as-a-model-plan.md`. `money.py` is the read module
and this is its pair, which is `architecture-trajectory.md` §4 rule 4: *a read
module and a service module, from the first slice.*

**Its own module rather than more of `services.py`**, which is the task core's
and is 1,500 lines. A bill stops being a task in this increment; its writes
stopping being task writes is the same statement made in the file layout.

**Everything here is dark until the surfaces switch**, which happens in the
same commit that deletes `create_bill`, `pay_bill`, `update_bill` and
`delete_bill` from `services.py`. Reads and writes move together — increment 3
records why the alternative, a fifteen-site mirror, was not worth building.

**What this does not carry over from the task versions**, each because the
concept goes with `Item`:

- **No archive.** A bill is outstanding or settled; *put away* was a task
  state, and a bill you neither pay nor delete is simply owed.
- **No status reconciliation.** `pay_bill` had to know that completing a
  recurring task archives it; `paid_at` has no such trap.
- **No two-record correction.** `update_bill`'s docstring says the four fields
  a bill has *"do not live in one place"* — amount, payee and currency on the
  sidecar, the due date on the task — and that one service existed so a caller
  could not leave a bill half-corrected. They live in one place now.
"""
from django.db import transaction
from django.utils import timezone

from lists.models import Bill, BillSeries, CadenceMode, Direction, Item
from lists.services import TaskConflict, _advance_due_date, normalize_task_text


#: Sentinel for *leave this alone*, so `None` can mean *clear it* — the same
#: contract `services.update_bill` uses and for the same reason.
_KEEP = object()


@transaction.atomic
# DARK: no production caller. Trigger: the money endpoints stop calling `services.create_bill` --
# increment 4 of design/bill-as-a-model-plan.md, which switches the
# reads and the writes in one commit.
def record(
    owner,
    *,
    payee,
    amount=None,
    currency="USD",
    due_date,
    repeats=True,
    recurrence=None,
    lead_days=0,
    direction=Direction.OUT,
    category=None,
    account=None,
):
    """A bill, and the standing rule behind it when it repeats.

    **Named `record` rather than `create`**, which is not taste: this module is
    full of `Bill.objects.create(...)`, so a service called `create` is
    ambiguous to a reader and indistinguishable to
    `test_dark_services_declare_their_deferral`, which found it dark and could
    not tell. A name that collides with the ORM's is a name that hides.

    **The series and the occurrence in one transaction**, which is
    `modules.md`'s rule that a module links to work through its own create path
    or not at all: membership cannot be forgotten because this is the only path
    that makes either row.

    `recurrence` names the cadence when it is not monthly; `repeats=False` is
    the one-off and is the same thing as `recurrence=NONE`.
    """
    payee = (payee or "").strip()
    if not payee:
        raise TaskConflict("A bill needs a payee.")
    if amount is not None and amount < 0:
        raise TaskConflict("A bill is something owed, so it cannot be negative.")

    if recurrence is None:
        recurrence = Item.Recurrence.MONTHLY if repeats else Item.Recurrence.NONE
    if recurrence not in Item.Recurrence.values:
        raise TaskConflict("Choose a valid cadence.")

    series = None
    if recurrence != Item.Recurrence.NONE:
        series = BillSeries.objects.create(
            owner=owner,
            payee=payee,
            amount=amount,
            currency=currency,
            direction=direction,
            category=category,
            account=account,
            cadence=recurrence,
            lead_days=lead_days,
        )

    return Bill.objects.create(
        owner=owner,
        series=series,
        due_date=due_date,
        payee=payee,
        amount=amount,
        currency=currency,
        direction=direction,
        category=category,
        account=account,
        lead_days=lead_days,
    )


@transaction.atomic
# DARK: no production caller. Trigger: the pay endpoint stops calling `services.pay_bill` --
# increment 4 of design/bill-as-a-model-plan.md, which switches the
# reads and the writes in one commit.
def settle(bill, *, amount=None, today=None):
    """Record that it was paid — or received — and produce the next one.

    **`amount` defaults to what was expected**, so the ordinary case is one
    click and the number is still recorded rather than inferred later. Passing
    a different one is the case that decided the design: paying extra must not
    overwrite what the bill was *supposed* to be, or the month loses the
    difference and *"this has been creeping up"* stops being answerable.

    **An unpriced bill settles with no figure**, and that is a real state
    rather than a gap — see `Bill.paid_at`. It is also the row that disproved
    this model's first constraint.
    """
    bill = Bill.objects.select_for_update().get(pk=bill.pk)
    if bill.paid_at is not None:
        raise TaskConflict("That bill is already settled.")
    if amount is not None and amount < 0:
        raise TaskConflict("A payment cannot be negative.")

    bill.paid_amount = bill.amount if amount is None else amount
    bill.paid_at = timezone.now()
    bill.save(update_fields=["paid_amount", "paid_at", "updated_at"])
    spawn_next(bill, today=today)
    return bill


def spawn_next(bill, *, today=None):
    """The next occurrence of a repeating bill, or None.

    **The payee and the currency carry; the amount does not.** What a bill
    comes to is a fact about *this* occurrence — last quarter's was 500 and
    this one is 525 — so carrying the number forward would state something
    nobody has been told. What lands is an unpriced bill from a known payee,
    which the month counts rather than totals.

    **The cadence arithmetic is borrowed, not rewritten.**
    `services._advance_due_date` is a pure function of dates and modes, and it
    carries a month of argument about the `>` boundary that a second copy would
    lose. Sharing it is the one place a bill still leans on the task core, and
    it leans on a calculation rather than on a record.
    """
    series = bill.series
    if series is None or series.ended_at is not None:
        return None
    if series.cadence == Item.Recurrence.NONE:
        return None
    return Bill.objects.create(
        owner=bill.owner,
        series=series,
        due_date=_advance_due_date(
            bill.due_date, series.cadence, today=today, mode=series.cadence_mode
        ),
        payee=series.payee,
        amount=None,
        currency=series.currency,
        direction=series.direction,
        category=series.category,
        account=series.account,
        lead_days=series.lead_days,
    )


@transaction.atomic
# DARK: no production caller. Trigger: the edit endpoint stops calling `services.update_bill` --
# increment 4 of design/bill-as-a-model-plan.md, which switches the
# reads and the writes in one commit.
def update(
    bill,
    *,
    payee=_KEEP,
    amount=_KEEP,
    currency=_KEEP,
    due_date=_KEEP,
    lead_days=_KEEP,
    category=_KEEP,
    account=_KEEP,
    clear_amount=False,
):
    """Correct a bill.

    **Absent is not empty.** A field left out keeps its stored value, the same
    partial-write contract the day and the review already have. Clearing an
    amount back to unpriced is an explicit act — `clear_amount=True` — because
    *"the water bill, whatever it comes to"* is a state somebody chooses rather
    than a field they forgot.

    **This occurrence, not the series.** Editing August's rent says something
    about August; the standing rule is `revise_series`. That split is what the
    old two-record version could not express at all, because the sidecar had no
    template to be distinguished from.
    """
    bill = Bill.objects.select_for_update().get(pk=bill.pk)
    if payee is not _KEEP:
        cleaned = (payee or "").strip()
        if not cleaned:
            raise TaskConflict("A bill needs a payee.")
        bill.payee = cleaned
    if clear_amount:
        bill.amount = None
    elif amount is not _KEEP:
        if amount is not None and amount < 0:
            raise TaskConflict("A bill is something owed, so it cannot be negative.")
        bill.amount = amount
    if currency is not _KEEP:
        bill.currency = (currency or "USD")[:3].upper()
    if due_date is not _KEEP:
        if due_date is None:
            raise TaskConflict("A bill needs a date it is due.")
        bill.due_date = due_date
    if lead_days is not _KEEP:
        bill.lead_days = lead_days
    if category is not _KEEP:
        bill.category = category
    if account is not _KEEP:
        bill.account = account
    bill.save()
    return bill


@transaction.atomic
# DARK: no production caller. Trigger: the delete endpoint stops calling `services.delete_bill` --
# increment 4 of design/bill-as-a-model-plan.md, which switches the
# reads and the writes in one commit.
def remove(bill, *, whole_series=False):
    """Delete a bill, and say which one is meant when it repeats.

    **`whole_series=False` means this one and not the habit.** What somebody
    means by deleting August's rent is *not this one*; they would have said so
    if they meant stop paying rent — so the successor is created first, exactly
    as the task version does.

    **`whole_series=True` ends the series rather than deleting it**, and then
    removes the occurrences that are still owed. What was actually paid stays:
    those rows are a record of money that moved, and `BillSeries` is
    `SET_NULL` on the occurrence precisely so ending a rule does not erase its
    history.
    """
    series = bill.series
    if whole_series and series is not None:
        series.ended_at = timezone.now()
        series.save(update_fields=["ended_at"])
        Bill.objects.filter(series=series, paid_at__isnull=True).delete()
        return
    if series is not None and series.ended_at is None:
        spawn_next(bill)
    bill.delete()


@transaction.atomic
# DARK: no production caller. Trigger: a surface offers editing the standing rule rather than one month --
# increment 4 of design/bill-as-a-model-plan.md, which switches the
# reads and the writes in one commit.
def revise_series(series, *, payee=_KEEP, amount=_KEEP, lead_days=_KEEP, cadence=_KEEP,
                  cadence_mode=_KEEP, category=_KEEP, account=_KEEP):
    """Change the standing rule, which takes effect on what it produces next.

    **It does not rewrite what already happened**, which is the whole reason
    occurrences snapshot rather than read through — §4 rule 3. Renaming a payee
    in March leaves January saying what January said.
    """
    if payee is not _KEEP:
        cleaned = (payee or "").strip()
        if not cleaned:
            raise TaskConflict("A bill needs a payee.")
        series.payee = cleaned
    if amount is not _KEEP:
        series.amount = amount
    if lead_days is not _KEEP:
        series.lead_days = lead_days
    if cadence is not _KEEP:
        if cadence not in Item.Recurrence.values:
            raise TaskConflict("Choose a valid cadence.")
        series.cadence = cadence
    if cadence_mode is not _KEEP:
        if cadence_mode not in CadenceMode.values:
            raise TaskConflict("Choose a valid schedule mode.")
        series.cadence_mode = cadence_mode
    if category is not _KEEP:
        series.category = category
    if account is not _KEEP:
        series.account = account
    series.save()
    return series
