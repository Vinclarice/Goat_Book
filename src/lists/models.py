from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from django.db.models import Q
from django.urls import reverse


class Recurrence(models.TextChoices):
    """How often a commitment repeats.

    Module level rather than nested in `Item` because RecurringCommitment is
    declared above `Item` and needs the same choices -- the cadence is the
    commitment's rule, and an occurrence's copy is a snapshot of what it ran
    under. `Item.Recurrence` remains an alias below, so nothing that already
    says `Item.Recurrence.WEEKLY` has to change.
    """

    NONE = "none", "Doesn't repeat"
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    #: Added August 27, 2026, because a salary every two weeks is ordinary and
    #: this had no word for it. Not a special case: `_nth_occurrence_after`
    #: already advances weekly by whole weeks, so a fortnight is two of them.
    FORTNIGHTLY = "fortnightly", "Every two weeks"
    MONTHLY = "monthly", "Monthly"
    # Added August 20, 2026 for the commitments that come round least often
    # and are hardest to hold in your head -- a property tax bill due 5
    # October could not be expressed at all. Both are the monthly arithmetic
    # with a multiplier rather than new branches, so they inherit its
    # anchor-and-clamp behaviour instead of restating it.
    QUARTERLY = "quarterly", "Quarterly"
    ANNUAL = "annual", "Annually"

class CadenceMode(models.TextChoices):
    """Whether a repeating commitment is fixed to the calendar or to the last
    time it was actually done.

    `design-concept.md` calls this distinction load-bearing, and it is: the two
    modes disagree by months on a commitment done late, and each is plainly
    wrong for the other's cases.

    ANCHORED is the default, and the asymmetry is deliberate. A mortgage that
    quietly drifts off the 1st is a missed payment; a furnace filter changed six
    days early is nothing. Somebody who never discovers this setting keeps the
    behaviour that cannot hurt them.
    """

    #: The calendar rule is the truth. Due the 1st whether or not last month's
    #: was paid on time. Missed periods are skipped, never replayed.
    ANCHORED = "anchored", "On a fixed schedule"
    #: The elapsed interval is the truth. A filter lasts a month from when it
    #: was changed, not from when it was notionally due.
    FLOATING = "floating", "A set time after it is done"


class Priority(models.TextChoices):
    """How pressing a commitment is, relative to the rest.

    Module level for the same reason `Recurrence` is: `RecurringCommitment` is
    declared below and carries it too, because priority belongs to the series
    rather than to one occurrence. `Item.Priority` is an alias further down.

    **There is deliberately no "medium".** Priority marks a *departure* from
    ordinary, so an unmarked task already means medium; offering both invites
    the distinction every to-do app collapses into, where everything is medium
    and the field says nothing. `NONE` is the absence of the signal rather than
    another value of it.
    """

    NONE = "none", "No priority"
    HIGH = "high", "Pressing"
    LOW = "low", "Whenever"


class RecurringCommitment(models.Model):
    """The durable identity of a repeating commitment, across its occurrences.

    A template, as of the vocabulary half -- see
    design/recurring-commitment-vocabulary-plan.md. It was deliberately thin
    until then, holding only identity, because copying `text` and `cadence`
    here while `Item` was the sole authority would have been drift.

    It is not drift now, because the two answer different questions. The
    template says what the *next* occurrence starts as; each `Item` keeps its
    own copy as the record of what *that* occurrence actually ran under, so
    renaming a commitment does not rewrite what June was called. Routine and
    RoutineOccurrence already ship this exact pair for `target_quantity`, and
    charter rules 3 and 8 in architecture-trajectory.md are the convention it
    follows.

    crane-plan.md 3 described this as moving the fields off the occurrence.
    Its own acceptance example contradicts that -- it requires the earlier
    occurrences to keep the old title -- and the example is the better
    statement of intent. The plan file records that correction.

    Owner is direct rather than reached through `List`, whose own owner is
    still nullable for anonymous-era reasons. Nothing here inherits that.

    Never deleted: `Item.commitment` is PROTECT, so a series with history
    cannot be dropped. `ended_at` is how a commitment stops, and a resumed one
    clears it rather than starting a second series -- a pause and a resume are
    one commitment with a gap, and the gap is visible in the occurrences.
    """

    owner = models.ForeignKey(
        "accounts.User",
        related_name="recurring_commitments",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # The template half. Every field below seeds the next occurrence and is
    # deliberately optional: slice 1 adds them inert, and a commitment
    # created before the backfill ran carries empty values rather than
    # blocking on them.
    text = models.TextField(blank=True, default="")
    # Nullable where Item.list is not: an Item must live somewhere, but a
    # commitment whose area was deleted should end rather than vanish, and
    # SET_NULL keeps the series and its history intact.
    list = models.ForeignKey(
        "List",
        related_name="commitments",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    cadence = models.CharField(
        max_length=12, choices=Recurrence.choices, default=Recurrence.NONE,
    )
    # On the commitment rather than the occurrence, because it is a property of
    # the *rule* -- `Item.recurrence` is a snapshot of what an occurrence ran
    # under, and this is not something an occurrence has.
    cadence_mode = models.CharField(
        max_length=10, choices=CadenceMode.choices, default=CadenceMode.ANCHORED
    )
    notes = models.TextField(blank=True, default="")
    # Carried by the series, like text, notes, tags and the Area. A priority
    # that reset every occurrence would be the one attribute somebody had to
    # set again forever.
    priority = models.CharField(
        max_length=6, choices=Priority.choices, default=Priority.NONE
    )
    # Carried by the series like priority above it: a lead time that came back
    # zero next month would be the one attribute somebody had to set again
    # forever. See `Item.lead_days` for what it means.
    lead_days = models.PositiveSmallIntegerField(default=0)
    tags = models.ManyToManyField("Tag", related_name="commitments", blank=True)

    def __str__(self):
        return f"commitment {self.pk}"


# Create your models here.
class Item(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Open"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"

    Recurrence = Recurrence
    Priority = Priority

    text = models.TextField(default="")
    # Nullable since August 14, 2026. A task no longer needs an Area to exist.
    #
    # Three independent findings in product-stories.md converge on this -- a
    # stranger's first four minutes, a task made from an external source, and a
    # someday state that currently has to masquerade as an Idea -- which made it
    # the most-supported single change in either planning document. The merger
    # then made it urgent rather than merely right: a thought that becomes a
    # commitment has no Area to be filed in, and demanding one at that moment
    # asks a filing question exactly where this design refuses to.
    #
    # Widening only. Every existing row keeps its Area and every creation path
    # that supplies one is unchanged; what is new is that a task may stand on
    # its own.
    list = models.ForeignKey(
        'List', default=None, null=True, blank=True, on_delete=models.CASCADE
    )
    # The other half of that change, and the half without which it is a defect.
    #
    # Ownership ran through the Area -- `Item.objects.filter(list__owner=user)`
    # at about twenty call sites -- so making `list` nullable created rows that
    # belonged to nobody and were returned by no query anybody makes. Not lost
    # exactly, but unreachable, which for somebody who wrote down an appointment
    # is the same thing.
    #
    # Derived, not a second opinion: `save()` forces this to the Area's owner
    # whenever there is an Area, so the two cannot disagree. It is authoritative
    # only for a task standing on its own. Django has no composite foreign key
    # to make the database say that instead, and a trigger for a field one
    # method already keeps correct is more machinery than the risk earns.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="items",
    )
    # `project` retired -- project-workspace-plan.md 2. A task's project is
    # derived through its Area (item.list.project) rather than stored here;
    # it belongs to a project only by belonging to an Area that's inside it.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    completed_at = models.DateTimeField(blank=True, null=True)
    archived_at = models.DateTimeField(blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    position = models.PositiveIntegerField(default=0)
    tags = models.ManyToManyField('Tag', blank=True, related_name='items')
    recurrence = models.CharField(
        # 12 rather than 10 since August 27, 2026: "fortnightly" is eleven
        # characters. The shorter "biweekly" would have fitted and is
        # ambiguous in English -- twice a week, or every two? -- and a stored
        # value should say what it means rather than save two bytes.
        max_length=12,
        choices=Recurrence.choices,
        default=Recurrence.NONE,
    )
    priority = models.CharField(
        max_length=6, choices=Priority.choices, default=Priority.NONE
    )
    #: How many days before its due date this should be mentioned. Zero is
    #: off, not "the day itself" -- otherwise every dated task in the product
    #: would join the advance reminder.
    #:
    #: On the task rather than on `MoneyLine`, because a lead time is not a
    #: property of costing money: "remind me before the MOT" is the same
    #: sentence. And it changes nothing about when a thing is *due* --
    #: `bucket_for` is untouched, which also keeps this out of the three
    #: languages that mirror it.
    lead_days = models.PositiveSmallIntegerField(default=0)
    # Plain text, deliberately not Markdown: a renderer plus an XSS surface
    # is a poor trade at two users. blank=True and no null -- "no notes" is
    # the empty string, so nothing has to handle both.
    notes = models.TextField(blank=True, default="")
    # Which repeating commitment this task is an occurrence of. Null means an
    # ordinary one-off task, which is what most rows will always mean.
    #
    # RESTRICT rather than SET_NULL, because nulling these on delete would
    # silently turn a series back into unrelated one-offs, which is the
    # precise failure this key exists to fix -- and rather than PROTECT,
    # which was the first choice and was wrong. PROTECT refuses even when the
    # referring task is being deleted in the same cascade, so deleting an
    # account raised ProtectedError instead of removing it: the owner's
    # commitments and their tasks both go, but PROTECT does not care that the
    # referrer is on its way out. RESTRICT allows exactly that case and still
    # refuses a bare commitment delete. Covered by test_commitment_deletion.
    commitment = models.ForeignKey(
        RecurringCommitment,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="occurrences",
    )
    # Generated, so it cannot drift from its source -- the same argument
    # `mind.Node.search_original` makes, and the same mechanism, because
    # search-plan.md's rule is that this core inherits that one rather than
    # starting a second way of doing it.
    #
    # `text` outranks `notes` because a task's text is its name and its notes
    # are its body, and a query matching the name is almost always the better
    # hit. Weighting *within* one model is safe in a way that ranking across
    # two models is not -- see search-plan.md on why the cross-core list is
    # sectioned rather than merged.
    #
    # The two-argument `to_tsvector` that `config=` produces is immutable,
    # which is what makes it legal in a generated column; the one-argument
    # form is only stable and is rejected.
    search_document = models.GeneratedField(
        expression=(
            SearchVector("text", weight="A", config="english")
            + SearchVector("notes", weight="B", config="english")
        ),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("list", "text"),
                condition=~Q(status="archived"),
                name="unique_active_item",
            ),
            # The same protection for a task with no Area, which the one above
            # stops giving the moment `list` is NULL -- NULLs are distinct, so
            # it matches nothing and every duplicate passes. A phone retrying a
            # share would have written the note twice.
            #
            # Keyed on owner, and scoped to `list IS NULL` so it says only what
            # the other cannot: two people may each have "Buy milk", and one
            # person may have it both filed and unfiled, because those are
            # different places rather than the same task twice.
            models.UniqueConstraint(
                fields=("owner", "text"),
                condition=Q(list__isnull=True) & ~Q(status="archived"),
                name="unique_active_arealess_item",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="active",
                        completed_at__isnull=True,
                        archived_at__isnull=True,
                    )
                    | Q(
                        status="completed",
                        completed_at__isnull=False,
                        archived_at__isnull=True,
                    )
                    | Q(
                        status="archived",
                        archived_at__isnull=False,
                    )
                ),
                name="valid_item_status_timestamps",
            ),
        ]
        indexes = [
            # GinIndex, not models.Index, and the distinction is not stylistic.
            # `mind/models.py:113` records what a btree on a tsvector costs: it
            # cannot serve `@@` at all, so every search falls back to a
            # sequential scan -- and its 2704-byte entry cap means a row with a
            # few hundred distinct lexemes fails to INSERT. A long task note
            # would stop being savable. Inherited as a decision, not rediscovered;
            # test_search.py holds the write path open.
            GinIndex(fields=["search_document"], name="item_search_document"),
            # Covers list_summaries()'s open/overdue counts per list, and
            # (extended with due_date) open_items_for()'s per-list bucket
            # ordering without a separate lookup.
            models.Index(
                fields=("list", "status", "due_date"),
                name="item_list_state_idx",
            ),
            # Backs open_items_for()'s global "every open task, ordered
            # by due date" query, which isn't scoped to one list.
            models.Index(
                fields=("status", "due_date"),
                name="item_status_due_idx",
            ),
            # Backs completed_today_for()'s per-user range scan over
            # completed_at now that it isn't hidden behind a __date cast.
            models.Index(
                fields=("list", "status", "completed_at"),
                name="item_list_state_completed_idx",
            ),
            # Backs "every occurrence of this commitment, oldest first", which
            # is the series read every trend and streak in release F runs.
            # Nothing queries it yet -- charter rule 7 asks for the index the
            # feature will actually run, and it costs a line now.
            models.Index(
                fields=("commitment", "created_at"),
                name="item_commitment_seq_idx",
            ),
        ]

    def _derive_owner(self):
        """An Area's owner wins whenever there is an Area.

        That is what makes a mismatch unreachable rather than merely rejected --
        a task whose two owners disagreed would show up in one person's queries
        and another person's Area at the same time.
        """
        if self.list_id is not None:
            self.owner_id = self.list.owner_id

    def full_clean(self, *args, **kwargs):
        """Derive before validating, not after.

        `Model.clean()` would be the natural home, but `full_clean` runs
        `clean_fields()` first -- so a task built with an Area and validated
        before saving failed as ownerless, which is a task that is perfectly
        well-formed being called invalid. Found by two existing model tests.
        """
        self._derive_owner()
        return super().full_clean(*args, **kwargs)

    def save(self, *args, **kwargs):
        """Keep `owner` derived on the way to the database.

        `update_fields` is widened rather than obeyed: a caller saving only
        `list` is also changing who owns the row, and quietly not writing that
        is precisely the drift this exists to prevent.
        """
        self._derive_owner()
        fields = kwargs.get("update_fields")
        if fields is not None and "list" in fields and "owner" not in fields:
            kwargs["update_fields"] = list(fields) + ["owner"]
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.text

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
    `MoneyLine` on exactly that: a bill is an expected movement on a date that
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

    **No link to the bill that pays it, and that is deliberate.** `paid_by` was
    written on August 27, 2026 and removed the same day, having been set by
    nothing and read by nothing through two screens that were each supposed to
    give it a purpose. The seam rule this project applies everywhere else --
    *built and dark gets a declared trigger or a deletion* -- was being applied
    to the codebase and not to the new code, so this is it applied evenly. It
    comes back the day a surface actually wants it, which is a cheap migration
    and an honest one.

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

    class Meta:
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
    to read. The same argument that gave `MoneyLine.paid_amount` its own column
    instead of overwriting `amount`.

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
    case. `services.SEED_CATEGORIES` holds the starting set.

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


class MoneyLine(models.Model):
    """What a task is worth, when the task is money moving.

    **Was `MoneyLine` until August 27, 2026**, renamed when income arrived. The name
    was accurate while every row was something owed and became actively
    misleading the moment half of them were salary -- and unlike `List`/Area or
    `Item`/task, this is not one concept under two words. It is a concept that
    genuinely widened, which is the case `architecture-trajectory.md` §7's
    refusal of cosmetic renames does not cover.

    **A sidecar, not a primitive**, and `architecture-trajectory.md` §4 is why:
    a bill's life cycle -- arrives, is due, is paid, comes round again -- *is* a
    recurring task's, and `daily-operating-system-vision.md` says so by
    example, with "pay rent every month" as its canonical recurring task. A
    `MoneyLine` model of its own would contradict the product's own statement and
    re-implement recurrence, due dates, completion and snapshotting beside the
    thing that already does them.

    So this adds attributes without claiming a life cycle. One-to-one rather
    than fields on `Item`, which keeps a decimal column that is null for almost
    every row off the most-queried model in the application -- and makes "is
    this a bill" a row's existence rather than a nullable flag.

    **Not a `Facet` either.** That table carries inferred capabilities with a
    confirmation flow; a number somebody typed is a fact, and putting it there
    would muddy both.
    """

    item = models.OneToOneField(
        "Item", related_name="money_line", on_delete=models.CASCADE
    )
    #: What kind of thing this is. Null is **Uncategorised**, which is a real
    #: state rather than a missing one: a bill added in a hurry should not have
    #: to answer a filing question, the same reason it has no Area. SET_NULL,
    #: because deleting a category is losing a label and not losing the bill.
    category = models.ForeignKey(
        "MoneyCategory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lines",
    )
    #: Which way it goes. Out is the default because bills came first, and
    #: because most rows will always be money leaving: a person has one salary
    #: and a dozen subscriptions.
    direction = models.CharField(
        max_length=3, choices=Direction.choices, default=Direction.OUT
    )
    #: What it is **expected** to come to. Optional, because "the water bill,
    #: whatever it comes to" is a real bill, and so is a bonus nobody can
    #: predict. The *row* is what marks a task as money.
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    #: What **actually moved**, recorded when it is settled -- paid, for a
    #: bill; received, for income. Null until then.
    #:
    #: **A second number rather than overwriting the first**, because they
    #: answer different questions and stop being equal the moment somebody pays
    #: extra -- Vince, August 27, 2026, and it is the ordinary case for a
    #: variable bill rather than an edge one. Keeping both is what lets the
    #: month say *still to pay* from expectations and *already paid* from
    #: facts, and what makes "the electricity bill has been creeping up"
    #: answerable at all: a field that gets overwritten has no history to read.
    #:
    #: **Not its own model.** §4's test is a different life cycle, and this has
    #: the same one as the amount beside it -- set once, about this occurrence,
    #: gone when the bill is. A `Payment` table would be a second answer to
    #: "what did this cost" with nothing extra to say.
    paid_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    #: Per bill rather than per account, so somebody paying rent in one
    #: currency and a subscription in another is not a migration later. Three
    #: characters and no lookup table: this is a label on a number, not an
    #: exchange-rate system, and it does not become one by having a table.
    currency = models.CharField(max_length=3, default="USD")
    payee = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        constraints = [
            # A bill is something owed. A negative one is a refund, which is a
            # different thing and not this -- refused in the database as well
            # as at the boundary, because the boundary is not the only writer.
            models.CheckConstraint(
                condition=Q(amount__isnull=True) | Q(amount__gte=0),
                name="money_line_amount_not_negative",
            ),
        ]

    def __str__(self):
        return f"bill for {self.item_id}"


class BillSeries(models.Model):
    """The durable identity of a repeating bill, across its occurrences.

    **Increment 1 of `bill-as-a-model-plan.md`, and deliberately dark**: nothing
    reads or writes this yet. `principles.md` permits exactly one form of that —
    a deferral with a declared trigger — and the trigger is that plan's
    increment 3, which moves the Money surfaces onto these tables. If the plan
    is abandoned at its own section 7, these two tables are dropped rather than
    left standing.

    **Why a template at all**, when `MoneyLine` needed none:
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
    #: whatever it comes to"* — the same reason `MoneyLine.amount` is nullable.
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
        choices=Item.Recurrence.choices,
        default=Item.Recurrence.MONTHLY,
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
    actually moved, which is the same argument `MoneyLine.paid_amount` makes
    for being a second column rather than an overwrite.

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
    #: unanswerable from a field with no history. Inherited wholesale from
    #: `MoneyLine.paid_amount`, whose reasoning survives the move.
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
        indexes = [
            # §4 rule 7, and these are the reads `lists/money.py` already runs
            # against `MoneyLine` + `Item`, named before they are moved.
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
        ]

    def __str__(self):
        return f"{self.payee} due {self.due_date}"


class ChecklistStep(models.Model):
    """A step inside a task's checklist -- release-d-plan.md 2.

    Deliberately not a subtask: no due date, no tags, cannot recur, and has
    no life apart from its task. Where a Task's status cycles through
    active/completed/archived, a step has exactly one boolean, `is_done`,
    because it never appears on the agenda on its own and never needs the
    independent archive/restore cycle a Task's own history requires. A step
    can be promoted into a full Task (see services.promote_checklist_step);
    nothing here converts an existing Task into a step.
    """

    # Charter rule 1 (architecture-trajectory.md 4): a direct, non-null
    # owner rather than reaching one through `task` alone, so an isolation
    # test on this model is a one-hop assertion.
    owner = models.ForeignKey(
        "accounts.User",
        related_name="checklist_steps",
        on_delete=models.CASCADE,
    )
    # CASCADE: a step has no existence apart from its task -- "dies with its
    # parent" is the whole point of this model over the old self-FK subtask.
    task = models.ForeignKey(
        "Item",
        related_name="checklist_steps",
        on_delete=models.CASCADE,
    )
    text = models.TextField(default="")
    position = models.PositiveIntegerField(default=0)
    is_done = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    # Whether this step reappears when its task's next recurring occurrence
    # is spawned. Only meaningful when `task` recurs -- the same question
    # Item.always_recurs answered for subtasks, carried over under a name
    # that can never collide with a task's own Repeat control, because a
    # step has no recurrence control of its own to collide with.
    carries_forward = models.BooleanField(default=True)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("task", "text"),
                condition=Q(is_done=False),
                name="unique_open_checklist_step_text",
            ),
        ]
        indexes = [
            # Backs "this task's open steps", the only query this model runs.
            models.Index(fields=("task", "is_done"), name="step_task_done_idx"),
        ]

    def __str__(self):
        return self.text


class List(models.Model):
    # An Area at the boundary; still `List` here, per
    # architecture-trajectory.md 7's refusal to rename the model.
    #
    # Required since release D slice 6. It was nullable for anonymous-era
    # reasons that outlived the anonymous era by three releases, and the
    # exception cost two later migrations an explicit skip-clause each. Now
    # charter rule 1 -- owned at birth -- holds for every model without one.
    owner = models.ForeignKey(
        "accounts.User",
        related_name="lists",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=100, default="Untitled list")
    updated_at = models.DateTimeField(auto_now=True)
    # The inverse of Project.area -- project-workspace-plan.md 2. Optional:
    # most Areas aren't part of a dedicated project workspace. SET_NULL, not
    # CASCADE: a Project groups Areas, it does not own them, the same
    # reasoning Item.project already carried one level down.
    project = models.ForeignKey(
        "Project", related_name="areas", null=True, blank=True,
        on_delete=models.SET_NULL,
    )

    def get_absolute_url(self):
        return reverse("view_list", args=[self.id])


class Project(models.Model):
    """A standalone workspace that can hold one or more Areas.

    project-workspace-plan.md inverts the original release-d-plan.md 3
    shape (a Project living inside one Area) into this one. The charter
    test in architecture-trajectory.md 4 -- a concept earns its own model
    when it has a different life cycle, not a different name -- still
    settles Project's existence against List/Area exactly as it did before;
    what changed is which one contains the other.

    Charter compliance, stated once here rather than rediscovered later:

    - **Rule 1, owned at birth.** A direct non-null `owner` -- the only
      ownership path now that Project has no parent record to borrow one
      from at all.
    - **Rule 2, public identifier.** Not needed. No client creates a Project
      offline -- this is a web/API-only surface, the same reasoning
      ChecklistStep and RecurringCommitment already used.
    - **Rule 3, snapshot.** Does not apply. A Project is a live record of
      intent, not a record of what happened during a period; there is nothing
      whose meaning could be rewritten underneath it.
    - **Rule 5, reference never copy.** Completing a Project does not touch
      any task's status. Stronger than before: a task's project is now pure
      computation (`item.list.project`), nothing stored to keep in sync.
    - **Rule 6, deletion.** Hard delete. Its Areas survive, unparented
      (`List.project` is `SET_NULL`) -- deleting a project says the grouping
      was wrong, not that the work is gone. No tombstone, since rule 2 does
      not apply.
    - **Rule 8, repetition.** Does not apply -- a Project does not recur, and
      whether it ever should is left open by release-d-plan.md 3.
    """

    owner = models.ForeignKey(
        "accounts.User", related_name="projects", on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=100)
    # What the project is *for*, in the person's own words. The first of
    # product-stories.md S10's three (purpose, notes, abandonment condition),
    # and here before the other two because planning-assistant-plan.md
    # increment 4 needs something to anchor retrieval against: a project
    # carrying only a title gives a matcher nothing, which is why S16's
    # "opening a project surfaces what you learned last time" is currently
    # impossible for want of a field rather than for want of a mechanic.
    #
    # Blank rather than null, exactly as DailyEntry's three text fields are:
    # "wrote nothing" and "cleared it" are the same state, so nothing
    # downstream has to handle both, and no client has to coerce a None into
    # a text area. Plain text, per roadmap.md's settled boundary.
    #
    # Optional, and staying optional. Requiring it would put a writing task
    # in front of somebody who wants to group three areas -- the same toll
    # confirm_actionable refuses to charge for filing. Increment 4 simply has
    # nothing to say about a project nobody gave a purpose.
    #
    # TextField rather than a capped CharField: "short" is guidance to the
    # person, not an invariant worth a validation error mid-thought.
    purpose = models.TextField(blank=True, default="")
    # What *done* would look like, beside what the project is for --
    # planning-assistant-v2-plan.md increment 3. Purpose answers *why*; this
    # answers *what would be true when it is finished*, and they are different
    # enough that somebody asked for both in one box writes only one.
    #
    # It also earns its keep in retrieval. `brief_for` anchors on the project's
    # own words, and an outcome supplies the concrete nouns a purpose usually
    # does not -- "the booking form is live" against "stop enquiries going to
    # email" -- which is the kind of term the rare-term gate behind
    # `material_bearing_on` can actually select on.
    #
    # Blank rather than null and optional, for `purpose`'s reasons exactly.
    #
    # **Not S10's abandonment condition**, which is still unbuilt and whose
    # relationship to this field is D4 in that plan. Both describe how a
    # project ends; deciding them apart risks two text areas nobody fills, and
    # that decision is not made here.
    desired_outcome = models.TextField(blank=True, default="")
    #: What would tell him it went wrong -- S10, and **D4's answer: this is not
    #: `desired_outcome`.**
    #:
    #: D4 asked whether they are one field, since both describe how a project
    #: ends and *deciding them apart risks two text areas nobody fills*. They
    #: are two, and the deciding argument is not aesthetic: **a tripwire you
    #: cannot tell from an ambition can never be checked.** Merged, nothing can
    #: ever ask *has the abandonment condition been met?* because nothing can
    #: tell which half of the text is the condition -- which removes the only
    #: thing the field is for.
    #:
    #: They also have different readers. `desired_outcome` answers *are we
    #: there?*; this answers *should we stop?*, which is the question v3's
    #: *first question* release is built around.
    #:
    #: D4's real risk is answered by optionality rather than by merging, the
    #: way `purpose` already answers it: two empty boxes cost nothing, and one
    #: confused box costs the story.
    abandon_if = models.TextField(blank=True, default="")
    #: S10's other missing third. Not in the story's done-means, which turns on
    #: the abandonment condition -- named in its requires, and the same shape.
    #: What he would do differently — **S12's fourth clause**.
    #:
    #: **A field rather than a `Retrospective` model**, by
    #: `architecture-trajectory.md` §4's test: *a concept earns its own model
    #: when it has a different life cycle, not when it has a different name.*
    #: This is written once when a project closes and edited afterwards, which
    #: is exactly `purpose`, `desired_outcome` and `abandon_if`'s life cycle. It
    #: does not propose, confirm or retire; nothing schedules it; nothing else
    #: points at it.
    #:
    #: **The rest of the retrospective is derived and this is not**, which is
    #: the whole reason it needs storing: planned-versus-met, what was set
    #: aside, the notes and the decisions are all reads over rows that already
    #: exist, and *what I would do differently* is the one thing no row can
    #: answer. Part 1's *facts, not derivations* cuts the other way here — a
    #: judgement a person makes is a fact, and there is nowhere else to put it.
    learned = models.TextField(blank=True, default="")

    notes = models.TextField(blank=True, default="")
    due_date = models.DateField(blank=True, null=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    # Parked: not finished, and not being worked on either. A todo application
    # that can only say "open" makes a deliberately shelved project look like
    # neglect, and a weekly check-in that has to *ask* which projects are
    # active is asking for something the system could know.
    #
    # **A nullable timestamp rather than a status enum**, following
    # `DailyFocus.released_at` and `completed_at` above: when a state began is
    # strictly more than the fact that it holds, it is additive against
    # `valid_project_completion` rather than a rewrite of it, and it leaves
    # room for a `ProjectPause` model later without touching what is here --
    # the charter's asymmetry argument. §4's test says a paused project has a
    # project's life cycle, so this is a field and not a model.
    #
    # Completed wins over paused: `complete_project` clears this, so no row is
    # ever both and no reader has to decide which state to believe.
    paused_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Open projects first, then most recently created. The read module
        # relies on this rather than re-sorting.
        ordering = ("is_completed", "-created_at", "id")
        constraints = [
            # The same guarantee Item's valid_item_status_timestamps gives,
            # for the same reason: a flag and its timestamp that can disagree
            # will eventually disagree. Free on a new table, a data migration
            # later -- the charter's asymmetry argument exactly.
            models.CheckConstraint(
                condition=(
                    Q(is_completed=False, completed_at__isnull=True)
                    | Q(is_completed=True, completed_at__isnull=False)
                ),
                name="valid_project_completion",
            ),
        ]
        indexes = [
            # Rule 7: backs "this owner's projects, open first", which is the
            # only query this model runs today.
            models.Index(
                fields=("owner", "is_completed"), name="project_owner_state_idx",
            ),
        ]

    def __str__(self):
        return self.title


class Tag(models.Model):
    owner = models.ForeignKey(
        "accounts.User",
        related_name="tags",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=40)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("owner", "name"),
                name="unique_owner_tag_name",
            ),
        ]

    def __str__(self):
        return self.name
