from django.db import models


class Routine(models.Model):
    """Repeated practice measured toward a quantity over a period.

    Deliberately not an `Item`, and deliberately not reachable from one. A
    routine accumulates progress toward a target across a period and can be
    partially met; a recurring task is one discrete commitment whose
    completion creates the next. They are peers with their own life cycles,
    and `crane-plan.md` §3 makes that boundary the load-bearing decision of
    the whole design: five daily lesson sessions are one Routine, not five
    tasks and not `Item.Recurrence.DAILY` standing in for a count it was
    never built to hold.

    A `Routine` never spawns an `Item`, and completing an `Item` never
    creates a `RoutineOccurrence`.
    """

    class Cadence(models.TextChoices):
        DAILY = "daily", "Every day"
        WEEKLY = "weekly", "Every week"

    owner = models.ForeignKey(
        "accounts.User", related_name="routines", on_delete=models.CASCADE
    )
    title = models.CharField(max_length=200)
    cadence = models.CharField(
        max_length=10, choices=Cadence.choices, default=Cadence.DAILY
    )
    # Integer, not decimal: every named case -- lessons, a yes/no move-today,
    # weekly sessions -- is a count. A duration or decimal unit waits for a
    # real routine that needs one, per principles.md on not optimising an
    # imagined workflow.
    target_quantity = models.PositiveIntegerField(default=1)
    # Blank means the target is a plain yes/no for the period rather than a
    # count of something -- the daily-exercise case.
    unit = models.CharField(max_length=40, blank=True, default="")
    # Paused rather than deleted: the person intends to come back to it, and
    # the occurrences already recorded are history either way. Pausing is
    # Crane 2 slice 4; this field exists from the first migration so that
    # slice is a behaviour change rather than a schema one.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")

    def __str__(self):
        return self.title


class RoutineOccurrence(models.Model):
    """What happened to one routine in one period.

    **Charter compliance** (architecture-trajectory.md §4), which named three
    gaps against §3's sketch. All three are closed here rather than
    inherited:

    - Rule 1: `owner` is direct and non-null. The sketch reached its owner
      through `routine`, which that document criticised for making every
      isolation test a two-hop assertion.
    - Rule 2: no UUID. Nothing creates an occurrence offline -- the Android
      client captures and nothing else -- so there is no identity to
      reconcile. Revisit if routine logging ever leaves the browser, which
      would also need the token-authenticated zone activation
      per-user-time-zones-plan.md already flags.
    - Rule 3: `target_quantity` and `unit` are copied at creation and never
      re-read from the routine. If a lesson target changes from 5 to 3 next
      month, last month must go on reading "4 of 5" rather than being
      silently recalculated.
    - Rule 6: no delete path exists. A routine ends by being paused, and an
      occurrence is a record of a period that really happened. The FK
      cascades because an occurrence has no meaning without its routine, and
      deleting a routine is not something the product offers.
    - Rule 7: the unique constraint indexes (routine, period_start), which
      is the lookup every log does; the second index covers "all my
      routines for this period", which is what the Daily Page will ask.
    - Rule 8: this *is* the occurrence half of the pattern -- a durable
      template holding the rule, dated rows holding what happened, each
      snapshotting what was expected of it.
    """

    class Outcome(models.TextChoices):
        OPEN = "open", "Open"
        COMPLETED = "completed", "Completed"
        SKIPPED = "skipped", "Skipped"

    owner = models.ForeignKey(
        "accounts.User",
        related_name="routine_occurrences",
        on_delete=models.CASCADE,
    )
    routine = models.ForeignKey(
        Routine, related_name="occurrences", on_delete=models.CASCADE
    )
    # The local date a daily occurrence covers, or the Monday that starts the
    # week a weekly one covers. Monday is settled in crane-plan.md §6, on the
    # evidence that agenda.py's snooze menu has resolved "Next week" to the
    # coming Monday since Albatross -- so the product already says a week
    # begins there, and a routine disagreeing would be one word meaning two
    # things on two screens.
    period_start = models.DateField()
    target_quantity = models.PositiveIntegerField()
    unit = models.CharField(max_length=40, blank=True, default="")
    progress = models.PositiveIntegerField(default=0)
    outcome = models.CharField(
        max_length=10, choices=Outcome.choices, default=Outcome.OPEN
    )
    # When the outcome stopped being open. Null while it still is -- which is
    # not the same as missed, and Crane 3 is where an elapsed-open period
    # gets described rather than relabelled.
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("period_start", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("routine", "period_start"),
                name="unique_routine_occurrence_period",
            ),
        ]
        indexes = [
            models.Index(
                fields=("owner", "period_start"),
                name="routine_owner_period_idx",
            ),
        ]

    def __str__(self):
        return f"{self.routine.title}: {self.period_start}"
