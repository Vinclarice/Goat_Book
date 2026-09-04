from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models


class DailyEntry(models.Model):
    """What one person wrote about one day.

    The durable half of the Daily Page. It holds only what belongs to this
    day for this person -- intentions, gratitude, what actually happened --
    and deliberately references no task. Action Items are read from the
    agenda at display time (Crane 1 slice 2), because a day page that owned
    its own copy of a task's state would be a second source of truth for
    whether something is done. See daily-operating-system-vision.md, "No
    duplicate task copies."

    **Charter compliance** (architecture-trajectory.md §4), stated rather
    than assumed, since this is the first table written under it:

    - Rule 1, owned at birth: `owner` is non-null in this first migration.
    - Rule 2, public identifier: none. No client creates a day offline --
      the Android app captures and nothing else -- so there is no identity
      to reconcile. Revisit if a mobile client ever writes a day.
    - Rule 3, snapshot what a record's meaning depends on: nothing to
      snapshot. The text is its own meaning and depends on no other row.
    - Rule 6, deletion decision: there is no delete path, by design. A day
      emptied of text stays as a row -- "I wrote nothing on the 3rd" and "I
      have never opened the 3rd" are different facts, and a review that
      cannot tell them apart is the kind of thing the vision document means
      by history that is useful without being punishing. Deleting an
      account still cascades.
    - Rule 7, index the query: the unique constraint below is the index for
      the read this table was built for -- "this owner, this date", covered
      exactly. **A second read arrived on August 20, 2026** and needed its
      own: search over the three text fields, which no btree can serve. The
      `GinIndex` beside the constraint is that one.
    - Rule 8, template and occurrences: does not apply. A day recurs in the
      calendar sense but has no template holding a rule, and inventing one
      would be the overload that rule exists to prevent.
    """

    owner = models.ForeignKey(
        "accounts.User",
        related_name="daily_entries",
        on_delete=models.CASCADE,
    )
    # The owner's local date, decided at the request boundary from their own
    # time zone -- never read from the clock in here. See principles.md,
    # "Inject the clock; do not freeze it".
    date = models.DateField()
    # Plain text on all three, and blank rather than null: "wrote nothing"
    # and "cleared it" are the same state, so nothing downstream has to
    # handle both. No Markdown, per the settled boundary in roadmap.md.
    intentions = models.TextField(blank=True, default="")
    gratitude = models.TextField(blank=True, default="")
    happenings = models.TextField(blank=True, default="")
    #: When the first act of execution drew the line under the day's list --
    #: `superlists-2.0-plan.md` rules 3, 4 and 11.
    #:
    #: **Null means the line was never drawn**, and that is a fact rather than
    #: a missing value: rule 11 refuses to write a midnight row into a day
    #: nobody executed on, because *a day nobody answered closes unclosed,
    #: which is itself a record* -- S5's own insistence, and the reason this
    #: table has no delete path either. The freeze on a past day is derived
    #: from the date, never from this column.
    #:
    #: **It is not a status and it does not move.** Reopening a task cannot
    #: clear it: what it records is that the day's work began, not that
    #: anything is finished. `daily/tests/test_the_line.py` holds both.
    #:
    #: Above or below the line is not a field on `DailyFocus`; it is
    #: `selected_at` compared against this -- see `daily.reads.above_the_line`.
    list_closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # search-plan.md slice 1, and the half its trigger actually fired on: a day
    # was reachable only by knowing its date, and there is no date picker.
    #
    # All three fields as peers, with no weights, because none of them is the
    # day's title -- `Item` weights its text over its notes for exactly the
    # reason that does not apply here.
    #
    # Generated rather than maintained, so it cannot drift from its source;
    # the same mechanism as `mind.Node.search_original`, inherited rather than
    # reinvented.
    search_document = models.GeneratedField(
        expression=SearchVector(
            "intentions", "gratitude", "happenings", config="english"
        ),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    class Meta:
        # Most recent first: the pages worth reopening are the recent ones.
        ordering = ("-date",)
        constraints = [
            # One day, one entry, one person. Enforced here rather than by
            # the service remembering to check, because two rows for one
            # date would surface as a paragraph that silently vanished.
            models.UniqueConstraint(
                fields=("owner", "date"),
                name="unique_daily_entry_per_owner_date",
            ),
        ]
        indexes = [
            # GinIndex, not models.Index. A btree on a tsvector cannot serve
            # `@@` and caps entries at 2704 bytes -- on a journal entry, which
            # is long and lexically varied, that is a failure to INSERT rather
            # than a slow read. `mind/models.py:113` is where that was paid for.
            GinIndex(fields=["search_document"], name="daily_entry_search"),
        ]

    def __str__(self):
        return f"{self.owner}: {self.date}"


class DailyFocus(models.Model):
    """"I chose this task, on this day" -- and, if released, that I unchose it.

    The deliberate half of the Daily Page. Action Items are whatever the
    agenda says is due; a Focus is what the person actually committed to,
    which is a different claim and the only one a finish rate can honestly
    divide by. `daily-operating-system-vision.md` is explicit that the
    planned denominator "cannot be reconstructed after the fact from a
    mutable due date", so it is recorded at the moment of choosing.

    **Unpinning releases rather than deletes**, which is the whole design.
    Deciding on Tuesday morning that something is not for today, and simply
    never getting to it, are different facts about a week. A row that
    vanished would make them identical, and a review would then report a
    number that looks authoritative and is not.

    **Charter compliance** (architecture-trajectory.md §4):

    - Rule 1: `owner` is direct and non-null, rather than reached through
      `entry`. That document's own critique of the RoutineOccurrence sketch
      is that a two-hop owner makes every isolation test a two-hop
      assertion; this avoids inheriting it.
    - Rule 3: `task_text` is snapshotted at selection time, because an
      archived task can be permanently deleted (`delete_archived_item`) and
      the record of having planned it has to outlive it. Without that the
      denominator shrinks silently, which is worse than losing it loudly.
    - Rule 5: nothing about the task's *state* is copied -- not status, not
      due date, not completion. Whether the pinned work got done is still
      the task's own answer, read live, so this can never drift from it.
    - Rule 6: no hard delete. `released_at` is how a pin ends. The task FK
      is SET_NULL for the same reason: deleting a task must not take the
      history of having chosen it along.
    - Rule 7: the unique constraint below indexes (entry, task), which is
      the lookup every pin and unpin does.
    """

    owner = models.ForeignKey(
        "accounts.User",
        related_name="daily_focus",
        on_delete=models.CASCADE,
    )
    entry = models.ForeignKey(
        DailyEntry,
        related_name="focus",
        on_delete=models.CASCADE,
    )
    # Nullable because the task may be permanently deleted later; the choice
    # to work on it that day happened regardless.
    task = models.ForeignKey(
        "lists.Item",
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )
    # What was chosen, as it read when it was chosen. Only load-bearing once
    # `task` is null -- until then the live task is the better answer, and
    # this is deliberately not used for display.
    task_text = models.TextField()
    position = models.PositiveIntegerField(default=0)
    selected_at = models.DateTimeField(auto_now_add=True)
    # Set when the pin is deliberately removed. Null means "still chosen",
    # which is not the same as "finished" -- that question belongs to the
    # task.
    released_at = models.DateTimeField(null=True, blank=True)
    # Whether this pin came from accepting the day's draft rather than being
    # composed by hand.
    #
    # **The measurement that makes the automation checkable.** Without it,
    # rubber-stamping a good draft and genuinely agreeing with it are the same
    # row, and the finish rate quietly stops measuring commitment kept and
    # starts measuring how good the draft was -- two numbers wearing one name,
    # and not separable afterwards. The same instinct as `typical_day_for`
    # refusing to let a day be its own evidence.
    accepted_from_draft = models.BooleanField(default=False)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            # One pin per task per day. A released pin keeps its row, so
            # repinning finds it and clears released_at rather than starting
            # a second, which would make one decision look like two.
            #
            # A deleted task leaves task NULL, and ordinary SQL NULL
            # semantics keep those rows from colliding with each other.
            models.UniqueConstraint(
                fields=("entry", "task"),
                name="unique_daily_focus_per_entry_task",
            ),
        ]
        verbose_name_plural = "daily focus"

    def __str__(self):
        return f"{self.entry.date}: {self.task_text}"
