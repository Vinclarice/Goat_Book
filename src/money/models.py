"""The Money module's models.

**Moved from `lists/models.py` on September 2, 2026**, step 4 of giving Money
its own app. What moved is the Python; **no table moved and no row moved.**
Every model below pins `db_table` to the name it already had, and the migrations
that record the move are state-only — they change Django's idea of who owns
these models and emit no SQL at all.

**Why the tables keep saying `lists_`.** They hold somebody's financial history,
and renaming them buys consistency in `psql` and nothing else. `0057` deleted
rows and `0059` dropped a table in the same week; a third physical migration for
a cosmetic gain is not a trade worth making. If it is ever worth it, it is its
own decision on its own day — and this docstring is the note saying it was
declined rather than missed.

**Nothing here points at a task and nothing about a task points here.** The only
foreign keys that leave this file go to `accounts.User`, which every app has.
That was not true before increment 4 — `MoneyLine` hung off `Item` — and it is
what makes this move a state change rather than a schema one.

The vocabulary these share with the task core is
[`clarice.recurrence`](../clarice/recurrence.py): both a task and a bill recur,
and the calendar belongs to neither.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from clarice.recurrence import CadenceMode, Recurrence


class AccountKind(models.TextChoices):
    """What sort of thing carries a balance.

    Open by design, the way `FacetKind` is: new kinds are new values, because
    the set is expected to grow and a migration per kind would make adding one
    a decision rather than a note.
    """

    CARD = "card", "Credit card"
    LOAN = "loan", "Loan"
    SAVINGS = "savings", "Savings"
    INVESTMENT = "investment", "Investment"


class Account(models.Model):
    """A thing with a balance -- a card, a loan, a savings pot, an investment.

    **It earns its own model, and `architecture-trajectory.md` §4 is why.** Its
    test is a different life cycle, not a different name, and this fails to be a
    `Bill` on exactly that: a bill is an expected movement on a date that
    **settles once**; an account is a value that is **re-read forever** and
    never settles. A card's balance belongs to the card, not to this month's
    payment.

    **The same model serves debt and investment**, which is the payoff rather
    than a coincidence. Vince wanted balances for loans and cards, and
    investments separately; both are *a thing whose value changes, re-read
    periodically*, differing in sign. One model, one update ritual, one trend.

    **`owes` rather than a negative balance.** A credit card at 4,200 and an ISA
    at 4,200 are both *four thousand two hundred*, and storing one as negative
    makes every read carry a sign convention nobody wrote down. This says which
    direction the number points, once, where it belongs.

    **The link to the bill that pays it lives on `Bill.account`**, and this
    paragraph is the history of how it got there rather than a rule.

    `Account.paid_by` was written on August 27, 2026 and removed the same day,
    having been set by nothing and read by nothing through two screens that
    were each supposed to give it a purpose -- the seam rule this project
    applies everywhere else, *built and dark gets a declared trigger or a
    deletion*, applied evenly to new code for once. That commit said it would
    come back *"the day a surface actually wants it"*, and it did, on
    September 1, 2026: `bill-as-a-model-plan.md` increment 7.

    **Pointed the other way, and both halves shipped together.** It is a
    property of the bill rather than of the account, so the standing
    arrangement lives on `BillSeries.account` and each occurrence snapshots it
    -- §4 rule 3. The balances screen reads it back as `next_payment`, which is
    the surface the first version never got.

    **Charter compliance** (architecture-trajectory.md §4):

    - Rule 1, owned at birth: `owner` is non-null in the first migration.
    - Rule 2, public identifier: none. Nothing addresses an account offline.
    - Rule 3, snapshot: nothing to copy. A reading carries its own figure and
      its own date; the account carries no derived state at all.
    - Rule 5, reference never copy: the linked commitment's own fields are read
      live wherever they are shown.
    - Rule 6, deletion: **hard delete, with the readings.** An account you
      closed and removed is not history you are keeping -- unlike a week you
      reviewed, its existence answers nothing about whether a practice
      happened. `PlanningSession` keeps its row for that reason and this does
      not qualify.
    - Rule 7, index the query: the constraint below covers "this owner's
      accounts, by name", which is the only read.
    - Rule 8, template and occurrences: does not apply.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="accounts"
    )
    name = models.CharField(max_length=120)
    kind = models.CharField(
        max_length=12, choices=AccountKind.choices, default=AccountKind.CARD
    )
    #: Per account rather than per reading: a card is denominated in one
    #: currency and a balance that changed currency would be a different
    #: account.
    currency = models.CharField(max_length=3, default="USD")
    #: Whether the number is money you owe or money you have. Named rather than
    #: signed, so no read has to remember a convention.
    owes = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    #: When somebody stopped using this, or null while they still are.
    #:
    #: **`ended_at` spelled for accounts**, and the parallel is deliberate:
    #: ending a `BillSeries` keeps what it produced because *"those rows are a
    #: record of money that moved"*, and an account's readings are the same kind
    #: of row. Twelve months proving a card was paid off is the one thing the
    #: history page exists to show.
    #:
    #: **Closing and deleting are different acts**, which is the whole reason
    #: this column exists. `close_account` says *I stopped using this*: out of
    #: the monthly balance pass, out of what is owed, still in the history.
    #: `delete_account` says *this should never have existed* and takes the
    #: readings with it — §4 rule 6 asks for the deletion decision to be stated,
    #: not for it to be hard, and this states both.
    #:
    #: Added September 3, 2026, discharging `close_account`'s declared
    #: deferral — *"a card somebody stops using stays in the monthly balance
    #: pass forever asking for a figure"*.
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        #: **The table does not move.** It was created as `lists_account`
        #: and every row in it is somebody\'s financial history; renaming
        #: it would be a physical migration bought for cosmetic
        #: consistency. The app label changed on September 2, 2026 and
        #: the table deliberately did not.
        db_table = "lists_account"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("owner", "name"),
                name="unique_account_name_per_owner",
            ),
        ]

    def __str__(self):
        return self.name


class BalanceReading(models.Model):
    """What an account came to on a date.

    **Its own row rather than a field on the account**, and the reason is the
    whole point of the feature: *is this loan actually going down* is a question
    about a series, and a field that gets overwritten each month keeps no series
    to read. The same argument that gave `Bill.paid_amount` its own column
    instead of overwriting `amount` — made first for `MoneyLine`, the sidecar
    that preceded it, and inherited when that was deleted.

    **One per account per month**, enforced rather than assumed -- the ritual is
    a monthly pass, and saving it twice should correct the figure rather than
    grow a second one.

    **`on_date` is the first of the month it describes.** A balance is *what it
    came to in August*, not *what it came to at 14:32 on the 31st*; storing the
    instant would make two readings a day apart look like different months.
    """

    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="readings"
    )
    on_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    recorded_at = models.DateTimeField(auto_now=True)

    class Meta:
        #: **The table does not move.** It was created as `lists_balancereading`
        #: and every row in it is somebody\'s financial history; renaming
        #: it would be a physical migration bought for cosmetic
        #: consistency. The app label changed on September 2, 2026 and
        #: the table deliberately did not.
        db_table = "lists_balancereading"
        ordering = ("-on_date",)
        constraints = [
            models.UniqueConstraint(
                fields=("account", "on_date"),
                name="one_reading_per_account_per_month",
            ),
        ]

    def __str__(self):
        return f"{self.account.name} {self.on_date}: {self.amount}"


class MoneyCategory(models.Model):
    """What kind of thing a bill is — Housing, Utilities, and whatever else.

    **A table rather than a `TextChoices`, and the reason is one clause of
    Vince's.** He asked for a fixed list *"however add a setting that lets the
    user manually edit the list"* — and a list somebody edits is created,
    renamed and deleted on its own schedule, which is `architecture-trajectory.md`
    §4's life-cycle test met rather than argued around. `FacetKind` is the
    counter-example and stays values: nobody edits that.

    **Seeded on first use, with ordinary rows.** A person opening the module
    finds a usable list rather than an empty one and a form — and because the
    seeds are rows like any other, renaming or deleting one needs no special
    case. `bills.SEED_CATEGORIES` holds the starting set.

    **A label, not a container.** The bill points here and the reference is
    `SET_NULL`: deleting *Housing* must not delete the rent. That is the
    difference between filing something and putting it in a box.

    **Charter compliance** (architecture-trajectory.md §4):

    - Rule 1, owned at birth: `owner` is non-null in the first migration.
    - Rule 2, public identifier: none. Nothing addresses a category offline.
    - Rule 3, snapshot: nothing to copy — a category has one field that means
      anything, and a bill showing a renamed category should show the new name.
    - Rule 6, deletion: **hard delete, with the bills kept.** A category's
      existence answers nothing about whether anything happened; the bills it
      labelled are the history and they survive it.
    - Rule 7, index the query: the constraint below covers "this owner's
      categories, by name", which is the only read.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="money_categories",
    )
    name = models.CharField(max_length=60)
    #: Where it sits in the list, so a person can put the ones they look at
    #: first, first. Ties break on name, which keeps the order total.
    position = models.PositiveIntegerField(default=0)

    class Meta:
        #: **The table does not move.** It was created as `lists_moneycategory`
        #: and every row in it is somebody\'s financial history; renaming
        #: it would be a physical migration bought for cosmetic
        #: consistency. The app label changed on September 2, 2026 and
        #: the table deliberately did not.
        db_table = "lists_moneycategory"
        ordering = ("position", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("owner", "name"),
                name="unique_money_category_per_owner",
            ),
        ]

    def __str__(self):
        return self.name


class Direction(models.TextChoices):
    """Which way the money goes.

    **One model with a direction, not two models**, and
    `architecture-trajectory.md` §4 decides it: *a concept earns its own model
    when it has a different life cycle, not when it has a different name.*
    Income recurs, has a date, has an amount, gets settled and can be late --
    a bill's life cycle in every respect. What differs is the sign, and whether
    the person acts or observes.
    """

    OUT = "out", "Money out"
    IN = "in", "Money in"


class BillSeries(models.Model):
    """The durable identity of a repeating bill, across its occurrences.

    **Increment 1 of `bill-as-a-model-plan.md`, and deliberately dark**: nothing
    reads or writes this yet. `principles.md` permits exactly one form of that —
    a deferral with a declared trigger — and the trigger is that plan's
    increment 3, which moves the Money surfaces onto these tables. If the plan
    is abandoned at its own section 7, these two tables are dropped rather than
    left standing.

    **Why a template at all**, when the sidecar it replaced needed none:
    `architecture-trajectory.md` §4 rule 8 — anything that happens more than
    once splits into a durable template holding the rule and dated occurrence
    rows holding what actually happened. Its cost note is the argument for
    doing it in the first migration rather than the fourth: *one foreign key
    now*, against *the history exists but cannot be assembled, and no migration
    can invent links after the fact*.

    **Not `RecurringCommitment`.** That is the task core's template and holds
    task-shaped fields — text, list, priority, tags. Pointing a bill at it would
    re-couple the two vocabularies this plan exists to separate, and it carries
    no payee, amount, currency or account.
    """

    #: §4 rule 1, owned at birth. Cascade because a series is nothing without
    #: the person; the account it points at is not, hence SET_NULL below.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bill_series",
    )
    payee = models.CharField(max_length=200)
    #: What it is **expected** to come to, and null for *"the water bill,
    #: whatever it comes to"* — the reason the sidecar's amount was nullable too.
    #: Each occurrence snapshots this rather than reading through, per rule 3.
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="USD")
    direction = models.CharField(
        max_length=3, choices=Direction.choices, default=Direction.OUT
    )
    #: Null is **Uncategorised**, a real state rather than a missing one.
    #: SET_NULL because deleting a category loses a label, not the series.
    category = models.ForeignKey(
        "MoneyCategory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bill_series",
    )
    #: **The link this whole plan started from** — Vince, August 31, 2026:
    #: *"it should be tied to the payments."* This is `Account.paid_by`
    #: returning, pointed the other way and living on the template rather than
    #: the occurrence, because it is the *standing* bill that pays a card.
    #:
    #: **Still dark in increment 1**; increment 7 is the surface that reads it.
    #: SET_NULL: closing an account does not erase what was paid to it.
    account = models.ForeignKey(
        "Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bill_series",
    )
    cadence = models.CharField(
        max_length=20,
        choices=Recurrence.choices,
        default=Recurrence.MONTHLY,
    )
    #: Anchored or floating, mirroring `RecurringCommitment.cadence_mode`.
    #: A bill is the canonical anchored case -- rent keeps its date however
    #: late it is paid -- and the default says so.
    cadence_mode = models.CharField(
        max_length=20, choices=CadenceMode.choices, default=CadenceMode.ANCHORED
    )
    #: How many days before the due date this should be mentioned. Zero is off.
    lead_days = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    #: When the series stopped, rather than deleting it -- the occurrences it
    #: already produced are a record of money that moved, and
    #: `RecurringCommitment.ended_at` makes the same call for the same reason.
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        #: **The table does not move.** It was created as `lists_billseries`
        #: and every row in it is somebody\'s financial history; renaming
        #: it would be a physical migration bought for cosmetic
        #: consistency. The app label changed on September 2, 2026 and
        #: the table deliberately did not.
        db_table = "lists_billseries"
        verbose_name_plural = "bill series"
        indexes = [
            # §4 rule 7. The only query this table will run: this person's
            # standing bills, newest first, for the module's own list.
            models.Index(fields=["owner", "-created_at"], name="bill_series_owner"),
        ]

    def __str__(self):
        return f"{self.payee} ({self.get_cadence_display()})"


class Bill(models.Model):
    """One dated bill — what was expected, and what actually moved.

    **The occurrence half of §4 rule 8**, in the shape that rule names: owner, a
    foreign key to the template, the date covered, a snapshot of what was
    expected, an outcome, and when that outcome was decided.

    **Why this is a model and not an `Item` with a sidecar.** §4's test is a
    different life cycle, and `bill-as-a-model-plan.md` §2 has the one that
    qualifies: **a missed period is gone for a task and still owed for a bill.**
    The same event demands opposite outcomes, which is not something one
    `status` field on one model can hold. `money-module-plan.md` refused this
    on August 27 and the evidence was written on August 28; the refusal was
    right about names and was made a day early.

    **Dark in increment 1.** Nothing reads or writes it; the trigger is
    increment 3 of that plan.

    **Deletion, §4 rule 6.** Hard, and cascading from the owner. There is no
    soft-delete because there is no undo surface to want one, and no tombstone
    because rule 2 does not apply — see below. A series being deleted does
    *not* take its occurrences: `SET_NULL` keeps the record of money that
    actually moved, which is the same argument `paid_amount` below makes for
    being a second column rather than an overwrite.

    **§4 rule 2 does not apply.** A public identifier is for records a client
    may create offline, and no client creates a bill offline: `android/` has no
    money surface at all, and the phone's only durable queue is capture. If one
    ever gains one, this needs a `public_id` and a tombstone before it ships,
    not after.
    """

    #: §4 rule 1. Denormalised from the series rather than read through it,
    #: exactly as `Item.owner` is, because every query here is *this person's*
    #: and a one-off bill has no series to read through.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bills"
    )
    #: Null for a one-off -- *"the plumber, once"* -- which is the same shape
    #: `Item.commitment` uses for a task that does not repeat.
    series = models.ForeignKey(
        BillSeries,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="occurrences",
    )
    #: The period this occurrence covers, and the date every read sorts by.
    due_date = models.DateField()

    # -- Snapshots of what was expected, §4 rule 3 -----------------------
    #
    # Copied at creation rather than read through `series`, so renaming a payee
    # or changing an amount in March does not silently rewrite what January
    # said. A one-off has no series to read through in any case.
    payee = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="USD")
    direction = models.CharField(
        max_length=3, choices=Direction.choices, default=Direction.OUT
    )

    category = models.ForeignKey(
        "MoneyCategory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bills",
    )
    account = models.ForeignKey(
        "Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bills",
    )

    # -- The outcome, and when it was decided ----------------------------
    #
    #: What **actually moved**. A second number rather than an overwrite of
    #: `amount`, because they stop being equal the moment somebody pays extra,
    #: and because *"the electricity bill has been creeping up"* is
    #: unanswerable from a field with no history. Inherited wholesale from the
    #: sidecar this replaced, whose reasoning survived the move and outlived it.
    paid_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    #: When it settled, and **null with a figure beside it is refused while
    #: null without one is not** -- see the constraint below.
    #:
    #: When it settled. **This replaces `Item.Status`**, and the replacement is
    #: the point: a bill is outstanding or settled, where a task is active,
    #: completed or archived. Null means still owed -- including for a period
    #: long past, which is the asymmetry this model exists for.
    paid_at = models.DateTimeField(null=True, blank=True)

    #: How many days before the due date this should be mentioned. Zero is off.
    #:
    #: **A snapshot like `payee` and `amount`, not a read through the series**
    #: -- and it was missed in increment 1, found by increment 4 porting the
    #: landing read: `renewing_soon` needs a lead time *per bill*, and a
    #: one-off has no series to read one from. `set_lead_days` works on any
    #: task today, so a one-off with a lead time is a real row rather than a
    #: hypothetical.
    lead_days = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        #: **The table does not move.** It was created as `lists_bill`
        #: and every row in it is somebody\'s financial history; renaming
        #: it would be a physical migration bought for cosmetic
        #: consistency. The app label changed on September 2, 2026 and
        #: the table deliberately did not.
        db_table = "lists_bill"
        indexes = [
            # §4 rule 7. These were named before the reads moved, when
            # the money reads still ran them against a sidecar joined to its
            # task; they are the same three reads and they run here now.
            #
            # The month, overdue-across-every-month, and due-soon-across-a-
            # boundary all sort this person's bills by date.
            models.Index(fields=["owner", "due_date"], name="bill_owner_due"),
            # "What is still owed" -- the landing page's first question, and
            # the one the missed-period work in increment 6 will lean on.
            models.Index(fields=["owner", "paid_at"], name="bill_owner_paid_at"),
            # One series' history, which is what makes a trend readable at all.
            models.Index(fields=["series", "due_date"], name="bill_series_due"),
        ]
        constraints = [
            # **A figure requires a settlement; a settlement does not require a
            # figure.** This was symmetric for a day and was wrong in one
            # direction, and increment 2 found out from the data rather than by
            # argument: `services.pay_bill` defaults the amount to what was
            # expected, so an *unpriced* bill -- "the water bill, whatever it
            # comes to" -- paid without an explicit number settles with
            # `paid_amount` still null. One of five development rows was in
            # exactly that state and the migration would have refused it.
            #
            # *Paid, amount unrecorded* is a real answer. Fabricating a zero is
            # what `principles.md` calls inventing, and dropping `paid_at` to
            # satisfy the constraint would throw away the fact that it was paid.
            # The other direction stays refused: a number against a bill nobody
            # settled is a claim about money that did not move.
            models.CheckConstraint(
                condition=(
                    models.Q(paid_amount__isnull=True)
                    | models.Q(paid_at__isnull=False)
                ),
                name="bill_paid_at_and_amount_agree",
            ),
            # **One occurrence per period, and the guarantee is the database's.**
            # `bills.catch_up` runs on a schedule and is idempotent by design --
            # it asks for the latest occurrence and builds forward from it -- but
            # `principles.md` is explicit that retry-safety is bought with a
            # constraint rather than with care, and two passes overlapping would
            # otherwise double somebody's rent.
            #
            # **Scoped to the series, so one-offs are unaffected**: they carry no
            # series and nulls do not collide, which is exactly right. Two
            # invoices from one supplier on one day are two records, and the
            # refusal that used to prevent that was an artifact the split removed
            # -- see `test_bill_writes.WhatABillRefusesTest`. What cannot happen
            # is one *schedule* claiming the same date twice, because a schedule
            # is a rule about periods and a period happens once.
            models.UniqueConstraint(
                fields=["series", "due_date"],
                name="bill_one_occurrence_per_period",
            ),
            # **Inherited from the sidecar this replaced**, and nearly lost with
            # it. `MoneyLine` carried `money_line_amount_not_negative` -- *a bill
            # is something owed; a negative one is a refund, which is a different
            # thing* -- refused in the database *"as well as at the boundary,
            # because the boundary is not the only writer"*. `Bill` was built
            # without it, so for one day the only thing refusing a negative bill
            # was Python in `bills.record` and `bills.update`.
            #
            # Increment 8 deletes that model. Carrying the guarantee across
            # rather than letting it go is `principles.md`'s rule that a
            # guarantee is bought with a constraint and not with care.
            #
            # **`paid_amount` joins it**, which the original did not cover: it is
            # what actually moved, and money moving backwards is the same refund
            # the other column already refuses. Null stays legal in both --
            # unpriced, and unsettled, are real states.
            models.CheckConstraint(
                condition=(
                    (models.Q(amount__isnull=True) | models.Q(amount__gte=0))
                    & (
                        models.Q(paid_amount__isnull=True)
                        | models.Q(paid_amount__gte=0)
                    )
                ),
                name="bill_amount_not_negative",
            ),
        ]

    @property
    def paid(self):
        """Settled, whichever direction the money went.

        **`paid_at`, and there is nothing else to consult.** The read this
        replaced had to explain that a paid *recurring* task is `ARCHIVED`
        rather than `COMPLETED`, so settlement could never be taken from the
        status -- a paragraph of reconciliation that has no equivalent here.
        Kept as a property rather than left to callers so that "settled" has
        one spelling.
        """
        return self.paid_at is not None

    def overdue_on(self, today):
        """Still owed, and its date has passed.

        `today` is injected rather than read from the clock, for the reason
        every date rule here is: the day boundary belongs to the owner's zone,
        and `clarice.clocks` is the authority. A browser computing this would
        be a second opinion.

        **Income can be overdue too**, and deliberately: a salary that has not
        arrived is exactly the thing worth saying out loud.
        """
        return self.paid_at is None and self.due_date < today

    def __str__(self):
        return f"{self.payee} due {self.due_date}"
