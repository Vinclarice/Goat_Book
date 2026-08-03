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
    # Additive, alongside `list` rather than replacing it -- see
    # release-d-plan.md 3. Letting `list` point at either an Area or a
    # Project would touch the FK that unique_active_item and every agenda
    # query already key off. A task belongs to an Area exactly as it always
    # has, and may *additionally* belong to a Project.
    #
    # SET_NULL, not CASCADE: a project groups tasks, it does not own them, so
    # deleting one says the grouping was wrong rather than that the work is
    # gone. Same shape as DailyFocus.task.
    project = models.ForeignKey(
        "Project",
        related_name="tasks",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
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
            models.UniqueConstraint(
                fields=("list", "text"),
                condition=~Q(status="archived"),
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

    def get_absolute_url(self):
        return reverse("view_list", args=[self.id])


class Project(models.Model):
    """Work that completes, inside an Area that never does.

    release-d-plan.md 3, and the charter test in architecture-trajectory.md 4
    names this exact pair: a Project earns its own model against a List
    because it has a different life cycle, not a different name.

    Charter compliance, stated once here rather than rediscovered later:

    - **Rule 1, owned at birth.** A direct non-null `owner`, not one reached
      through `area`. A two-hop owner makes every isolation test a two-hop
      assertion.
    - **Rule 2, public identifier.** Not needed. No client creates a Project
      offline -- this is a web/API-only surface, the same reasoning
      ChecklistStep and RecurringCommitment already used.
    - **Rule 3, snapshot.** Does not apply. A Project is a live record of
      intent, not a record of what happened during a period; there is nothing
      whose meaning could be rewritten underneath it.
    - **Rule 5, reference never copy.** Completing a Project does not touch
      any task's status, and `Item.project` is SET_NULL: a project groups
      tasks, it does not own them.
    - **Rule 6, deletion.** Hard delete. Its tasks survive, unparented. No
      tombstone, since rule 2 does not apply.
    - **Rule 8, repetition.** Does not apply -- a Project does not recur, and
      whether it ever should is left open by release-d-plan.md 3.
    """

    owner = models.ForeignKey(
        "accounts.User", related_name="projects", on_delete=models.CASCADE,
    )
    # Required, against release-d-plan.md 3's own nullable recommendation.
    # Slice 6 had just spent a whole slice paying the nullable-to-required
    # cost on List.owner; required-to-nullable is a bare AlterField with no
    # data work, so the permissive option was the expensive one to undo.
    #
    # CASCADE follows from that: deleting an Area already deletes the tasks
    # inside it, and a project in a deleted area has nowhere left to be.
    area = models.ForeignKey(
        "List", related_name="projects", on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=100)
    due_date = models.DateField(blank=True, null=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
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
