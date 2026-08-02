from django.db import models


class WeeklyReview(models.Model):
    """What somebody concluded about one week, and what they meant to do next.

    The review app's only stored record. Everything else it serves is
    derived from tables that already existed -- charter rule 5, reference
    rather than copy -- because a week is a lens over durable records and
    not a second place to keep them. What cannot be derived is the part a
    person writes.

    **Why the counts are here at all**, which looks like the rule-5
    violation it is not. `DailyFocus` snapshots `task_text`, so the planned
    denominator survives a task being permanently deleted from the archive;
    that is the number `daily-operating-system-vision.md` says "cannot be
    reconstructed after the fact". The numerator has no such protection --
    it is read through `DailyFocus.task`, which `delete_archived_item`
    leaves NULL -- so a live recount of a reviewed week can quietly fall
    afterwards. A completed review is a record of what somebody concluded
    on a day, and it carries its own copy of the figure they concluded it
    from. That is charter rule 3, snapshot what a record's meaning depends
    on, applied to a conclusion rather than to a target.

    They are null until the review is completed, and null again if it is
    reopened, because an unfinished review has concluded nothing.

    **Charter compliance** (architecture-trajectory.md §4):

    - Rule 1: `owner` is direct and non-null in this first migration.
    - Rule 2: no UUID. Nothing writes a review offline -- the Android
      client captures and nothing else -- so there is no identity to
      reconcile.
    - Rule 3: the recorded counts above.
    - Rule 6: no delete path, deliberately, and for the same reason a day
      has none. A review emptied of text stays as a row: "I reviewed that
      week and had little to say" and "I never reviewed that week" are
      different facts, and a product that could not tell them apart would
      be unable to say whether the practice is happening at all. Deleting
      an account still cascades.
    - Rule 7: the unique constraint below is the index. Every read is
      "this owner, this week", which it covers exactly.
    - Rule 8: does not apply. A week recurs in the calendar sense but has
      no template holding a rule, and inventing one would be the overload
      that rule exists to prevent -- the same call `DailyEntry` made.
    """

    owner = models.ForeignKey(
        "accounts.User",
        related_name="weekly_reviews",
        on_delete=models.CASCADE,
    )
    # The Monday the week starts on, always from
    # routines.periods.period_start_for. Any date in the week addresses the
    # same record, so two links to one week cannot make two rows -- see
    # crane-plan.md §6 on why a second definition of "this week" would be
    # wrong in a way nobody would see.
    week_start = models.DateField()
    # Plain text, blank rather than null, exactly as the day's three fields
    # are: "wrote nothing" and "cleared it" are the same state, so nothing
    # downstream has to handle both.
    reflections = models.TextField(blank=True, default="")
    # What the coming week is for. Deliberately a person's sentence rather
    # than a list of tasks the system would then own -- the vision document
    # asks for "a short planning area", and anything that scheduled work
    # from here would be the automatic rescheduling it forbids.
    plan = models.TextField(blank=True, default="")
    # When the week was reviewed. Null means still open, which is not the
    # same as never started -- the row exists because something was written.
    completed_at = models.DateTimeField(null=True, blank=True)
    recorded_planned_total = models.PositiveIntegerField(null=True, blank=True)
    recorded_planned_met = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Most recent first, like the day: the weeks worth reopening are
        # the recent ones.
        ordering = ("-week_start",)
        constraints = [
            # One week, one review, one person. Enforced here rather than
            # by a service remembering to check, because two rows for one
            # week would surface as a plan that silently vanished.
            models.UniqueConstraint(
                fields=("owner", "week_start"),
                name="unique_weekly_review_per_owner_week",
            ),
        ]

    def __str__(self):
        return f"{self.owner}: week of {self.week_start}"
