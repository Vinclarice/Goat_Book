"""Writing bills — the service module for `Bill` and `BillSeries`.

Increment 4 of `design/bill-as-a-model-plan.md`. `money.py` is the read module
and this is its pair, which is `architecture-trajectory.md` §4 rule 4: *a read
module and a service module, from the first slice.*

**Its own module rather than more of `services.py`**, which is the task core's
and is 1,500 lines. A bill stops being a task in this increment; its writes
stopping being task writes is the same statement made in the file layout.

~~**Everything here is dark until the surfaces switch**~~ — that happened on
September 1, 2026, in the commit that deleted `create_bill`, `pay_bill`,
`update_bill` and `delete_bill` from `services.py`. Reads and writes moved
together; increment 3 records why the alternative, a fifteen-site mirror, was
not worth building.

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

**What it still imports from `lists` is its own models**, and only until they
move with it -- step 3 of the extraction. Everything else it needs from outside
now comes from `clarice.recurrence` and `clarice.errors`, which belong to
neither core.

**And one thing that goes the other way: `catch_up` has no task equivalent, and
must not acquire one.** *Missed periods are skipped, not replayed* is right for
a task and wrong for a bill, which is the entire argument
`architecture-trajectory.md` §4 was satisfied by — see
`bill-as-a-model-plan.md` §2. The two doctrines now live in two modules, which
is what having two models is for.
"""
import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from clarice.errors import Conflict
from clarice.recurrence import CadenceMode, Recurrence, advance_due_date
from money.models import (
    Account,
    AccountKind,
    BalanceReading,
    Bill,
    BillSeries,
    Direction,
    MoneyCategory,
)


class BillConflict(Conflict):
    """A money write refused because the domain says no.

    **Its own class since September 2, 2026.** This module raised
    `TaskConflict` until then -- it worked, because the boundary caught it by
    name, and it said a bill refusing a write was a task conflict. A bill has
    not been a task since increment 4.

    A `clarice.errors.Conflict`, so a handler catching the base still gets it.
    """


logger = logging.getLogger(__name__)


#: Sentinel for *leave this alone*, so `None` can mean *clear it* — the same
#: contract `services.update_bill` uses and for the same reason.
_KEEP = object()


@transaction.atomic
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
        raise BillConflict("A bill needs a payee.")
    if amount is not None and amount < 0:
        raise BillConflict("A bill is something owed, so it cannot be negative.")

    if recurrence is None:
        recurrence = Recurrence.MONTHLY if repeats else Recurrence.NONE
    if recurrence not in Recurrence.values:
        raise BillConflict("Choose a valid cadence.")

    series = None
    if recurrence != Recurrence.NONE:
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
        raise BillConflict("That bill is already settled.")
    if amount is not None and amount < 0:
        raise BillConflict("A payment cannot be negative.")

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

    **The cadence arithmetic is shared, not rewritten.**
    `clarice.recurrence.advance_due_date` is a pure function of dates and modes
    carrying a month of argument about its `>` boundary that a second copy would
    lose. ~~The one place a bill still leans on the task core.~~ **It leans on
    neither core since September 2, 2026**: this imported the private
    `lists.services._advance_due_date` until then, which worked and said a
    bill's schedule belonged to tasks. A calendar belongs to neither.

    **One period on, and never past today — the asymmetry §2 is built on.**
    That function advances until it clears *today*, because five missed bin
    rounds are five things that did not happen and inventing them is fabricated
    history. A payment you did not make is still owed, so paying June's rent in
    August must produce **July's**, not September's. Passing `bill.due_date` as
    `today` asks the shared calculation for exactly one interval and leaves its
    own doctrine, and the tasks that depend on it, untouched.

    The `today` argument survives for `CadenceMode.FLOATING`, which ignores the
    old due date entirely and counts from when the work was done — there is no
    period to miss, so there is nothing here to correct.

    What is still owed *between* the successor and today is
    `catch_up`'s: this makes one, and that makes the rest.
    """
    series = bill.series
    if series is None or series.ended_at is not None:
        return None
    if series.cadence == Recurrence.NONE:
        return None
    return Bill.objects.create(
        owner=bill.owner,
        series=series,
        due_date=advance_due_date(
            bill.due_date,
            series.cadence,
            today=today if series.cadence_mode == CadenceMode.FLOATING
            else bill.due_date,
            mode=series.cadence_mode,
        ),
        payee=series.payee,
        amount=None,
        currency=series.currency,
        direction=series.direction,
        category=series.category,
        account=series.account,
        lead_days=series.lead_days,
    )


#: A runaway guard, not a policy. A series can produce at most one occurrence
#: per period since it was created, so real data is bounded by how long somebody
#: has used the module -- a weekly bill untouched for two years is a hundred, and
#: that is a true hundred. What this catches is a corrupt cadence or a due date
#: seeded far in the past, where the honest response is to stop and say so
#: rather than to write five thousand rows quietly.
REPLAY_LIMIT = 400


@transaction.atomic
def catch_up(owner=None, today=None):
    """Create every occurrence a live series has come to owe, up to today.

    **This is the increment the model was argued for.**
    `architecture-trajectory.md` §4 grants a model for a different life cycle,
    and `bill-as-a-model-plan.md` §2 names it: the same event -- a period
    elapsing unfinished -- has opposite meanings. A missed bin round did not
    happen. A missed payment is still owed.

    **Measured before it was written**, September 1, 2026. Nothing created an
    occurrence except settling or deleting one, so a series nobody touched never
    grew: a monthly card bill due August 20 and unpaid had exactly one row and
    would have had one in 2027. **The further behind you were, the less the
    module said** -- which is the doctrine's cost, not a bug in any one
    function.

    **Nobody is asked to confirm anything.** `modules.md`'s input ratio counts a
    prompt about a skipped period as feeding, and `principles.md` sanctions this
    outright: routine generation is an automation that may act because the act
    is visible and undoable -- a replayed bill is a row on a page with a delete
    button.

    **Nothing after today.** A bill not yet due is not owed, and creating it
    would put a forecast in the same column as a debt.

    **Anchored only.** Floating counts from when the work was done, so by
    construction no period elapses unnoticed -- that argument is
    `_advance_due_date`'s and it needs no second version here.

    **Idempotent, and guaranteed so by the database.** It runs on a schedule and
    a second pass within a day must not double somebody's rent;
    `bill_one_occurrence_per_period` is the constraint that makes that a promise
    rather than an intention, per `principles.md`'s rule that retry-safety is
    bought with a constraint and not with care.

    Returns how many it created, because a scheduled job whose output is silence
    is a job nobody can tell has stopped.
    """
    today = today or timezone.localdate()
    series = BillSeries.objects.filter(
        ended_at__isnull=True, cadence_mode=CadenceMode.ANCHORED
    ).exclude(cadence=Recurrence.NONE)
    if owner is not None:
        series = series.filter(owner=owner)

    created = 0
    for rule in series.select_related("category", "account"):
        latest = (
            Bill.objects.filter(series=rule)
            .order_by("-due_date")
            .values_list("due_date", flat=True)
            .first()
        )
        if latest is None:
            # A series with no occurrence at all cannot be replayed: its schedule
            # says how far apart they fall and nothing says where they started.
            # `record` makes both together, so this is unreachable by any path
            # here -- and skipped rather than guessed at if one is ever found.
            continue
        for _ in range(REPLAY_LIMIT):
            following = advance_due_date(
                latest, rule.cadence, today=latest, mode=rule.cadence_mode
            )
            if following is None or following > today:
                break
            Bill.objects.create(
                owner=rule.owner,
                series=rule,
                due_date=following,
                payee=rule.payee,
                # Unpriced, which is `spawn_next`'s rule and for its reason:
                # what a bill comes to is a fact about *this* occurrence.
                amount=None,
                currency=rule.currency,
                direction=rule.direction,
                category=rule.category,
                account=rule.account,
                lead_days=rule.lead_days,
            )
            created += 1
            latest = following
        else:
            logger.warning(
                "catch_up stopped at the replay limit for series %s (%s, %s); "
                "its due date or cadence is probably wrong.",
                rule.pk,
                rule.payee,
                rule.cadence,
            )
    return created


@transaction.atomic
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
            raise BillConflict("A bill needs a payee.")
        bill.payee = cleaned
    if clear_amount:
        bill.amount = None
    elif amount is not _KEEP:
        if amount is not None and amount < 0:
            raise BillConflict("A bill is something owed, so it cannot be negative.")
        bill.amount = amount
    if currency is not _KEEP:
        bill.currency = (currency or "USD")[:3].upper()
    if due_date is not _KEEP:
        if due_date is None:
            raise BillConflict("A bill needs a date it is due.")
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
def set_cadence(bill, recurrence):
    """Change whether a bill repeats, and how often.

    **A series-level act reached from one occurrence**, which is a distinction
    the old model could not make: `Item.recurrence` sat on the occurrence, so
    *does this repeat* and *what does the standing rule say* were one field.
    Here they are two, which is what makes *stop paying rent* a different act
    from *delete August's rent*.

    Three cases, and each is a different verb underneath. Starting to repeat
    creates the series **from this occurrence**, because a rule with no payee
    and no figure would spawn a bill for nobody. Changing the cadence revises
    the rule. Stopping ends it rather than deleting it -- the occurrences it
    already produced are a record of money that moved -- and leaves this one
    standing, since it is still owed.
    """
    if recurrence not in Recurrence.values:
        raise BillConflict("Choose a valid cadence.")
    series = bill.series
    current = series.cadence if series is not None else Recurrence.NONE
    if recurrence == current:
        return bill
    if recurrence == Recurrence.NONE:
        if series is not None:
            series.ended_at = timezone.now()
            series.save(update_fields=["ended_at"])
        bill.series = None
        bill.save(update_fields=["series", "updated_at"])
        return bill
    if series is None:
        bill.series = BillSeries.objects.create(
            owner=bill.owner,
            payee=bill.payee,
            amount=bill.amount,
            currency=bill.currency,
            direction=bill.direction,
            category=bill.category,
            account=bill.account,
            cadence=recurrence,
            lead_days=bill.lead_days,
        )
        bill.save(update_fields=["series", "updated_at"])
        return bill
    revise_series(series, cadence=recurrence)
    return bill


@transaction.atomic
def remove(bill, *, whole_series=False, today=None):
    """Delete a bill, and say which one is meant when it repeats.

    **`today` is injected, like `settle`'s**, and for a reason a test found on
    September 1, 2026: the successor's date depends on it, because
    `_advance_due_date` will not produce one already overdue. Without a way to
    pass it in, this function reads the wall clock and every test of it passes
    or fails depending on the day it runs.

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
        spawn_next(bill, today=today)
    bill.delete()


@transaction.atomic
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
            raise BillConflict("A bill needs a payee.")
        series.payee = cleaned
    if amount is not _KEEP:
        series.amount = amount
    if lead_days is not _KEEP:
        series.lead_days = lead_days
    if cadence is not _KEEP:
        if cadence not in Recurrence.values:
            raise BillConflict("Choose a valid cadence.")
        series.cadence = cadence
    if cadence_mode is not _KEEP:
        if cadence_mode not in CadenceMode.values:
            raise BillConflict("Choose a valid schedule mode.")
        series.cadence_mode = cadence_mode
    if category is not _KEEP:
        series.category = category
    if account is not _KEEP:
        series.account = account
    series.save()
    return series


# ---------------------------------------------------------------------------
# Accounts and categories
#
# **Moved from `lists/services.py` on September 2, 2026**, the last thing the
# app extraction left behind: their models had already gone and these had not,
# so money's writes were still being made by the task core's service module.
#
# They kept `TaskConflict` while they lived there and raise `BillConflict` here,
# for the reason every other write in this file does — a duplicate account name
# is not a task conflict, and it has not been since the name was accurate.
# ---------------------------------------------------------------------------

#: What a fresh module starts with. Ordinary rows once written, so any of them
#: can be renamed or deleted -- these are a starting point, not a schema.
#:
#: Chosen to cover the bills a person actually has rather than to be complete:
#: an accountant's chart would be exhaustive and useless at eight entries.
SEED_CATEGORIES = (
    "Housing",
    "Utilities",
    "Subscriptions",
    "Insurance",
    "Debt",
    "Transport",
    "Health",
)


def categories_for(owner):
    """This owner's categories, seeded on first ask.

    **Seeding here rather than at signup** so that accounts predating the
    feature get their list the first time they look, and nothing has to
    backfill. `get_or_create` per name makes a second call a no-op rather than
    a duplicate — and a person who has deleted *Transport* does not find it
    back next time, because the seeding only runs when they have none at all.
    """
    existing = MoneyCategory.objects.filter(owner=owner)
    if not existing.exists():
        MoneyCategory.objects.bulk_create(
            [
                MoneyCategory(owner=owner, name=name, position=index)
                for index, name in enumerate(SEED_CATEGORIES)
            ]
        )
    return MoneyCategory.objects.filter(owner=owner)


@transaction.atomic
def add_category(owner, *, name):
    """One more, at the end of the list."""
    name = (name or "").strip()
    if not name:
        raise BillConflict("A category needs a name.")
    last = (
        MoneyCategory.objects.filter(owner=owner)
        .order_by("-position")
        .values_list("position", flat=True)
        .first()
    )
    try:
        return MoneyCategory.objects.create(
            owner=owner, name=name, position=(last or 0) + 1
        )
    except IntegrityError as error:
        raise BillConflict(f"There is already a category called {name}.") from error


@transaction.atomic
def rename_category(category, name):
    name = (name or "").strip()
    if not name:
        raise BillConflict("A category needs a name.")
    category.name = name
    try:
        category.save(update_fields=["name"])
    except IntegrityError as error:
        raise BillConflict(f"There is already a category called {name}.") from error
    return category


@transaction.atomic
def delete_category(category):
    """Remove a label. **The bills it labelled are untouched** -- the reference
    is `SET_NULL`, so they become uncategorised rather than disappearing with
    it. A category is a label and not a container."""
    category.delete()


@transaction.atomic
def create_account(owner, *, name, kind=None, currency="USD", owes=None):
    """Open something that carries a balance.

    **`owes` defaults from the kind**, because a card and a loan are money you
    owe and an investment or savings pot is money you have -- and making a
    person answer that for every account would be asking them to restate what
    they already said by choosing the kind.
    """
    name = (name or "").strip()
    if not name:
        raise BillConflict("An account needs a name.")
    kind = kind or AccountKind.CARD
    if kind not in AccountKind.values:
        raise BillConflict("Choose a valid kind of account.")
    if owes is None:
        owes = kind in (AccountKind.CARD, AccountKind.LOAN)
    try:
        return Account.objects.create(
            owner=owner,
            name=name,
            kind=kind,
            currency=currency,
            owes=owes,
        )
    except IntegrityError as error:
        raise BillConflict(
            f"There is already an account called {name}."
        ) from error


@transaction.atomic
def record_balance(account, *, on_date, amount):
    """What this account came to, in the month ``on_date`` falls in.

    **Snapped to the first of the month**, because a balance is *what it came to
    in August* rather than what it read at 14:32 on the 31st -- and two readings
    a day apart would otherwise look like two months.

    **Saving a month twice corrects it.** The ritual is a monthly pass; somebody
    who mistypes and saves again means *that figure was wrong*, not *here is a
    second August*. `update_or_create` under the unique constraint, so two
    browser tabs cannot produce two rows either.
    """
    if amount is None:
        raise BillConflict("A balance needs a figure.")
    if amount < 0:
        # Direction is `Account.owes`, not the sign of the number: a card at
        # 4,200 and an ISA at 4,200 are both four thousand two hundred.
        raise BillConflict(
            "Enter the balance as a positive figure -- whether it is owed or "
            "held is the account's own setting."
        )
    reading, _ = BalanceReading.objects.update_or_create(
        account=account,
        on_date=on_date.replace(day=1),
        defaults={"amount": amount},
    )
    return reading


@transaction.atomic
# DARK: no production caller. Nothing on the balances screen closes an account,
# so a card somebody stops using stays in the monthly pass forever, asking for a
# figure that no longer exists. Trigger: a control for removing an account,
# which the balances screen is the obvious home for and was not part of what
# Vince asked for. Declared rather than deleted because the gap is real and
# one-sided -- accounts can be created and not removed, which is a worse end
# state than an uncalled function.
# Two things about where and how this is written, both learned by getting them
# wrong. It sits *below* the decorator because the guard reads the comment lines
# immediately preceding `def`, and a declaration above `@transaction.atomic` is
# invisible to it -- the same decorator-and-def adjacency CLAUDE.md records
# costing a lost `@transaction.atomic` once already. And it has no blank comment
# lines, because a bare `#` does not match `^# .*` and silently ends the block,
# so only the paragraph after it is read.
def close_account(account):
    """Remove an account and the readings that belong to it.

    Hard delete, per §4 rule 6: unlike a week somebody reviewed, an account's
    existence answers nothing about whether a practice happened, so there is
    nothing here that keeping the row would preserve.
    """
    account.delete()
