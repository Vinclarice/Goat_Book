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
        max_length=10,
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
    #: On the task rather than on `Bill`, because a lead time is not a
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

class Bill(models.Model):
    """What a task costs, when the task is a bill.

    **A sidecar, not a primitive**, and `architecture-trajectory.md` §4 is why:
    a bill's life cycle -- arrives, is due, is paid, comes round again -- *is* a
    recurring task's, and `daily-operating-system-vision.md` says so by
    example, with "pay rent every month" as its canonical recurring task. A
    `Bill` model of its own would contradict the product's own statement and
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
        "Item", related_name="bill", on_delete=models.CASCADE
    )
    #: Optional, because "the water bill, whatever it comes to" is a real
    #: bill. The *row* is what marks a task as one.
    amount = models.DecimalField(
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
                name="bill_amount_not_negative",
            ),
        ]

    def __str__(self):
        return f"bill for {self.item_id}"


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
