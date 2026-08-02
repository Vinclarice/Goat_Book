from django.db import models
from django.db.models import Q
from django.urls import reverse

class RecurringCommitment(models.Model):
    """The durable identity of a repeating commitment, across its occurrences.

    Deliberately thin: an owner and a lifespan, and nothing else. It is an
    identity anchor rather than a template -- `text`, `list`, `recurrence`,
    tags and notes stay on `Item`, where each occurrence is already its own
    snapshot of what it ran under. Copying them here while `Item` still
    carries them would create exactly the two-sources-of-truth drift the
    design is meant to prevent; the whole vocabulary moves at once at release
    D, or not at all. See design/crane-plan.md 3.

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

    def __str__(self):
        return f"commitment {self.pk}"


# Create your models here.
class Item(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Open"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"

    class Recurrence(models.TextChoices):
        NONE = "none", "Doesn't repeat"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    text = models.TextField(default="")
    list = models.ForeignKey('List', default=None, on_delete=models.CASCADE)
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
    # Plain text, deliberately not Markdown: a renderer plus an XSS surface
    # is a poor trade at two users. blank=True and no null -- "no notes" is
    # the empty string, so nothing has to handle both.
    notes = models.TextField(blank=True, default="")
    # One level only: a subtask cannot itself have subtasks, enforced in
    # services rather than the schema (SQL can't express depth). CASCADE
    # because a deleted parent's children have nothing left to belong to.
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="subtasks",
    )
    # Whether this subtask reappears on the parent's next occurrence. Only
    # meaningful when parent_id is set, and defaulted to True because a
    # subtask is assumed part of the recurring routine unless said otherwise.
    # It exists because "what must be cascaded" and "what comes back next
    # time" are different questions -- see design/recurring-subtasks-addendum.md.
    always_recurs = models.BooleanField(default=True)
    # Stamped on every archive, single or cascade, so restore can regroup
    # exactly what one action archived. An explicit marker rather than
    # matching on archived_at: same-instant timestamps would be a timestamp
    # doing a marker's job, and a child archived separately then re-archived
    # with its parent makes that ambiguous.
    archive_group = models.UUIDField(null=True, blank=True, editable=False)
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

    class Meta:
        ordering = ("position", "id")
        constraints = [
            # Postgres 15+ only: nulls_distinct=False is what lets one
            # constraint cover both root tasks (parent IS NULL) and subtasks.
            # Without it SQL treats every NULL parent as distinct, so this
            # would stop preventing duplicate top-level tasks entirely --
            # see design/subtasks-plan.md 6a.
            models.UniqueConstraint(
                fields=("list", "parent", "text"),
                condition=~Q(status="archived"),
                nulls_distinct=False,
                name="unique_active_item",
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
            # Backs "the open children of this parent", which every list
            # render and every cascade walks.
            models.Index(
                fields=("parent", "status"),
                name="item_parent_state_idx",
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

    def __str__(self):
        return self.text

class List(models.Model):
    owner = models.ForeignKey(
        "accounts.User",
        related_name="lists",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=100, default="Untitled list")
    updated_at = models.DateTimeField(auto_now=True)

    def get_absolute_url(self):
        return reverse("view_list", args=[self.id])


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
