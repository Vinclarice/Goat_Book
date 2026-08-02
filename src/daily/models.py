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
    - Rule 7, index the query: the unique constraint below is the index.
      Every read is "this owner, this date", which it covers exactly.
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

    def __str__(self):
        return f"{self.owner}: {self.date}"
