from calendar import monthrange
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from lists.models import (
    ChecklistStep,
    Item,
    List,
    Project,
    RecurringCommitment,
    Tag,
)


EMPTY_ITEM_ERROR = "You can't have an empty list item"
DUPLICATE_ITEM_ERROR = "You've already got this in your list"
ARCHIVED_DELETE_ERROR = "Only archived tasks can be permanently deleted"
CHECKLIST_STEP_ARCHIVED_ERROR = "Restore this task before editing its checklist"


class TaskServiceError(Exception):
    pass


class TaskConflict(TaskServiceError):
    pass


class InvalidTaskTransition(TaskServiceError):
    pass


def normalize_task_text(text):
    normalized = (text or "").strip()
    if not normalized:
        raise TaskConflict(EMPTY_ITEM_ERROR)
    return normalized


def _duplicate_exists(for_list, text, excluding=None):
    duplicates = for_list.item_set.exclude(status=Item.Status.ARCHIVED).filter(
        text=text,
    )
    if excluding is not None:
        duplicates = duplicates.exclude(pk=excluding.pk)
    return duplicates.exists()


@transaction.atomic
def create_list_with_item(owner, title, text):
    normalized_text = normalize_task_text(text)
    normalized_title = (title or "").strip() or normalized_text[:100]
    new_list = List.objects.create(owner=owner, title=normalized_title)
    Item.objects.create(list=new_list, text=normalized_text)
    return new_list


def _next_position(for_list):
    highest = for_list.item_set.exclude(
        status=Item.Status.ARCHIVED,
    ).aggregate(Max("position"))["position__max"]
    return 0 if highest is None else highest + 1


def _clean_tag_names(tag_names):
    cleaned = []
    seen = set()
    for raw in tag_names or []:
        name = (raw or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        cleaned.append(name)
    return cleaned


def _resolve_tags(owner, tag_names):
    return [
        Tag.objects.get_or_create(owner=owner, name=name)[0]
        for name in _clean_tag_names(tag_names)
    ]


def _anchor_commitment(item):
    """Give a repeating task the series identity it belongs to.

    Called on every path that can leave a root task repeating. Reuses an
    existing commitment rather than starting a second series, so a task that
    was paused and resumed stays one commitment with a gap in it.

    Always returns a commitment. It used to return None when the list had
    no owner, for anonymous-era rows; release D slice 6 made `List.owner`
    required and deleted those rows, so that branch became unreachable and
    went with them, exactly as this docstring used to promise it would.
    """
    if item.commitment_id is not None:
        commitment = item.commitment
        if commitment.ended_at is not None:
            commitment.ended_at = None
            commitment.save(update_fields=["ended_at"])
        return commitment
    # Seeded from the item at birth, not left empty. A commitment adopted at
    # completion (the legacy path, for rows predating this key) would
    # otherwise reach its first spawn with a blank template and produce a
    # blank task.
    commitment = RecurringCommitment.objects.create(
        owner=item.list.owner,
        text=item.text,
        list=item.list,
        cadence=item.recurrence,
        notes=item.notes,
    )
    item.commitment = commitment
    commitment.tags.set(item.tags.all())
    return commitment


def _end_commitment(item):
    """Stop a series accepting new occurrences, without disowning the old ones."""
    if item.commitment_id is None:
        return
    commitment = item.commitment
    if commitment.ended_at is None:
        commitment.ended_at = timezone.now()
        commitment.save(update_fields=["ended_at"])



def _write_through_to_commitment(item, **fields):
    """Editing an occurrence edits its commitment -- "this and future".

    Decided August 3, 2026; see recurring-commitment-vocabulary-plan.md 4.
    Renaming a recurring task means renaming the commitment, so the next
    occurrence carries the new name. Occurrences already completed keep their
    own text, notes and tags -- they are the snapshot of what actually ran,
    and nothing here touches them.

    A no-op for the ordinary one-off task, which has no commitment. That is
    the load-bearing part: inventing one here would turn every edited task
    into a series.
    """
    if item.commitment_id is None:
        return
    commitment = item.commitment
    tags = fields.pop("tags", None)
    if fields:
        for name, value in fields.items():
            setattr(commitment, name, value)
        commitment.save(update_fields=tuple(fields))
    if tags is not None:
        commitment.tags.set(tags)


@transaction.atomic
def create_item(for_list, text, due_date=None, tags=None, recurrence=None):
    normalized = normalize_task_text(text)
    if _duplicate_exists(for_list, normalized):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)
    if recurrence and recurrence not in Item.Recurrence.values:
        raise TaskConflict("Choose a valid recurrence.")
    try:
        item = Item.objects.create(
            list=for_list,
            text=normalized,
            due_date=due_date,
            position=_next_position(for_list),
            recurrence=recurrence or Item.Recurrence.NONE,
        )
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    if item.recurrence != Item.Recurrence.NONE:
        _anchor_commitment(item)
        item.save(update_fields=["commitment"])
    if tags:
        item.tags.set(_resolve_tags(for_list.owner, tags))
    return item


@transaction.atomic
def edit_item(item, text):
    item = Item.objects.select_for_update().select_related("list").get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")

    normalized = normalize_task_text(text)
    if _duplicate_exists(item.list, normalized, excluding=item):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)

    item.text = normalized
    try:
        item.save()
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    _write_through_to_commitment(item, text=normalized)
    return item


@transaction.atomic
def reorder_items(for_list, ordered_ids):
    # Set equality against the list's open tasks is what stops an id
    # belonging to another list from being smuggled in.
    items = list(
        Item.objects.select_for_update()
        .filter(list=for_list)
        .exclude(status=Item.Status.ARCHIVED)
    )
    by_id = {item.id: item for item in items}
    if set(ordered_ids) != set(by_id):
        raise TaskConflict(
            "This list changed since you last loaded it. Refresh and try again."
        )
    for position, item_id in enumerate(ordered_ids):
        item = by_id[item_id]
        if item.position != position:
            item.position = position
            item.save(update_fields=["position"])
    return [by_id[item_id] for item_id in ordered_ids]


@transaction.atomic
def set_item_tags(item, tag_names):
    item = Item.objects.select_for_update().select_related("list").get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    resolved = _resolve_tags(item.list.owner, tag_names)
    item.tags.set(resolved)
    _write_through_to_commitment(item, tags=resolved)
    return item


@transaction.atomic
def set_due_date(item, due_date):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    item.due_date = due_date or None
    item.save()
    return item


@transaction.atomic
def set_recurrence(item, recurrence):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    if recurrence not in Item.Recurrence.values:
        raise TaskConflict("Choose a valid recurrence.")
    item.recurrence = recurrence
    if recurrence == Item.Recurrence.NONE:
        # The link stays. This task really was an occurrence of that series,
        # and clearing the key would rewrite history to say it never was --
        # only the series stops accepting new ones.
        _end_commitment(item)
    else:
        _anchor_commitment(item)
    item.save()
    # The cadence is the commitment's rule; `item.recurrence` above is this
    # occurrence's snapshot of it. Writing both keeps an *active* occurrence
    # in step with its series, which is why the API can keep reading the
    # item's own value -- see the plan file, slice 3.
    #
    # Deliberately also written when the cadence is NONE: a commitment that
    # was stopped should say so rather than keep advertising the rule it no
    # longer follows.
    _write_through_to_commitment(item, cadence=recurrence)
    return item


@transaction.atomic
def set_item_notes(item, notes):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    # Normalised to "" rather than None so callers never have to handle both;
    # clearing notes and never having written any are the same state.
    item.notes = (notes or "").strip()
    item.save()
    _write_through_to_commitment(item, notes=item.notes)
    return item


def _next_step_position(task):
    highest = task.checklist_steps.aggregate(Max("position"))["position__max"]
    return 0 if highest is None else highest + 1


def _duplicate_step_exists(task, text, excluding=None):
    # Mirrors unique_open_checklist_step_text: open-scoped, not task-wide, so
    # a done step's text is free to reuse -- see design/release-d-plan.md 2.
    duplicates = task.checklist_steps.filter(is_done=False, text=text)
    if excluding is not None:
        duplicates = duplicates.exclude(pk=excluding.pk)
    return duplicates.exists()


@transaction.atomic
def add_checklist_step(task, text, carries_forward=None):
    task = Item.objects.select_for_update().select_related("list").get(pk=task.pk)
    if task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    normalized = normalize_task_text(text)
    if _duplicate_step_exists(task, normalized):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)
    try:
        step = ChecklistStep.objects.create(
            owner=task.list.owner,
            task=task,
            text=normalized,
            position=_next_step_position(task),
            carries_forward=True if carries_forward is None else carries_forward,
        )
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    return step


@transaction.atomic
def set_checklist_step_done(step, is_done):
    step = ChecklistStep.objects.select_for_update().select_related("task").get(pk=step.pk)
    if step.task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    step.is_done = bool(is_done)
    step.completed_at = timezone.now() if step.is_done else None
    step.save()
    return step


@transaction.atomic
def set_checklist_step_carries_forward(step, value):
    step = ChecklistStep.objects.select_for_update().select_related("task").get(pk=step.pk)
    if step.task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    step.carries_forward = bool(value)
    step.save()
    return step


@transaction.atomic
def edit_checklist_step_text(step, text):
    step = ChecklistStep.objects.select_for_update().select_related("task").get(pk=step.pk)
    if step.task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    normalized = normalize_task_text(text)
    if _duplicate_step_exists(step.task, normalized, excluding=step):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)
    step.text = normalized
    try:
        step.save()
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    return step


@transaction.atomic
def delete_checklist_step(step):
    step = ChecklistStep.objects.select_for_update().select_related("task").get(pk=step.pk)
    if step.task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    step.delete()


@transaction.atomic
def reorder_checklist_steps(task, ordered_ids):
    steps = list(ChecklistStep.objects.select_for_update().filter(task=task))
    by_id = {step.id: step for step in steps}
    if set(ordered_ids) != set(by_id):
        raise TaskConflict(
            "This checklist changed since you last loaded it. Refresh and try again."
        )
    for position, step_id in enumerate(ordered_ids):
        step = by_id[step_id]
        if step.position != position:
            step.position = position
            step.save(update_fields=["position"])
    return [by_id[step_id] for step_id in ordered_ids]


@transaction.atomic
def promote_checklist_step(step):
    """Turn a Checklist Step into its own Task -- design/release-d-plan.md 2.

    A state transition, not a copy: the step ceases to exist, so there is
    exactly one live record of the work either way. No due date, no tags, no
    recurrence -- the owner does whatever they were going to do with a new
    task next. Demotion (the reverse) is deliberately not built; see that
    document for why.
    """
    step = (
        ChecklistStep.objects.select_for_update()
        .select_related("task", "task__list")
        .get(pk=step.pk)
    )
    if step.task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    task_list = step.task.list
    if _duplicate_exists(task_list, step.text):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)
    try:
        promoted = Item.objects.create(
            list=task_list,
            text=step.text,
            position=_next_position(task_list),
        )
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    step.delete()
    return promoted


def _advance_due_date(due_date, recurrence):
    base = due_date or timezone.localdate()
    if recurrence == Item.Recurrence.DAILY:
        return base + timedelta(days=1)
    if recurrence == Item.Recurrence.WEEKLY:
        return base + timedelta(days=7)
    if recurrence == Item.Recurrence.MONTHLY:
        month = base.month % 12 + 1
        year = base.year + (base.month // 12)
        day = min(base.day, monthrange(year, month)[1])
        return base.replace(year=year, month=month, day=day)
    return None


def _spawn_next_occurrence(completed_item, carry_forward_steps=()):
    # Anchored here as well as on the paths that set a cadence, because rows
    # predating this key reach completion without one. Their earlier
    # occurrences can't be recovered -- that history is gone -- but adopting
    # the pair here means no path leaves the series unlinked from now on.
    was_linked = completed_item.commitment_id is not None
    commitment = _anchor_commitment(completed_item)
    if not was_linked:
        completed_item.save(update_fields=["commitment"])
    # Built from the template, not copied from the occurrence that just
    # finished. That is the whole point of the pair: the commitment says what
    # the next one starts as, and the completed row keeps what *it* was, so
    # renaming a commitment in September leaves June reading "Pay rent".
    #
    # `due_date` is the exception and always was -- computed per occurrence by
    # _advance_due_date rather than seeded, because it advances from the one
    # that just finished rather than being a property of the series.
    #
    # The template is the sole source now. It carried `or` fallbacks to the
    # completed occurrence through one deploy, as the compatibility window
    # for 0031's backfill; that window closed on August 3, 2026 when the
    # migration reported empty=0 against production -- every commitment has a
    # template, so there is nothing left for a fallback to cover.
    #
    # The cadence is not merely a label: it decides how far the next due date
    # moves, so reading the wrong one schedules the next occurrence on the
    # wrong day rather than just describing it wrongly.
    next_item = Item.objects.create(
        list=commitment.list,
        text=commitment.text,
        due_date=_advance_due_date(completed_item.due_date, commitment.cadence),
        recurrence=commitment.cadence,
        position=_next_position(commitment.list),
        commitment=commitment,
        notes=commitment.notes,
    )
    next_item.tags.set(commitment.tags.all())

    # Fresh copies, not carried state: a step that was already ticked off
    # this cycle starts the next one unchecked, the same way the parent
    # itself starts active rather than completed.
    for step in carry_forward_steps:
        ChecklistStep.objects.create(
            owner=step.owner,
            task=next_item,
            text=step.text,
            position=step.position,
            carries_forward=step.carries_forward,
        )
    return next_item


def _checklist_steps_to_carry_forward(item):
    """Every checklist step flagged carries_forward -- what clones onto the
    next occurrence. A step has no independent archived state to exclude: it
    dies with its task (release-d-plan.md 2) rather than being separately
    removed, so there's nothing else to filter here.
    """
    return list(
        item.checklist_steps.filter(carries_forward=True).order_by("position", "id")
    )


@transaction.atomic
def complete_item(item):
    item = Item.objects.select_for_update().select_related("list").get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Archived tasks must be restored first")
    if item.status != Item.Status.COMPLETED:
        now = timezone.now()
        is_recurring = item.recurrence != Item.Recurrence.NONE
        # Read before the item moves: a recurring task archives itself below,
        # and reading this after would see its own steps as belonging to an
        # already-archived task rather than change what they answer.
        carry_forward_steps = (
            _checklist_steps_to_carry_forward(item) if is_recurring else []
        )
        item.status = Item.Status.COMPLETED
        item.completed_at = now
        item.archived_at = None
        if is_recurring:
            # Recurring tasks skip the "completed" resting state: archive
            # immediately (freeing up its text for the next occurrence,
            # which would otherwise collide with the unique-active-text
            # constraint) and spawn the next one right away.
            item.status = Item.Status.ARCHIVED
            item.archived_at = now
        item.save()
        if is_recurring:
            item._spawned = _spawn_next_occurrence(
                item, carry_forward_steps=carry_forward_steps,
            )
    return item


@transaction.atomic
def reopen_item(item):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Archived tasks must be restored first")
    if item.status != Item.Status.ACTIVE:
        item.status = Item.Status.ACTIVE
        item.completed_at = None
        item.archived_at = None
        item.save()
    return item


@transaction.atomic
def archive_item(item):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status != Item.Status.ARCHIVED:
        item.status = Item.Status.ARCHIVED
        item.archived_at = timezone.now()
        item.save()
    return item


def _restore_status_for(item):
    # A null completed_at means the task was active when it was archived, so
    # that is where it goes back to; anything else was genuinely completed.
    if item.completed_at is None:
        return Item.Status.ACTIVE
    return Item.Status.COMPLETED


@transaction.atomic
def restore_item(item):
    item = Item.objects.select_for_update().select_related("list").get(pk=item.pk)
    if item.status != Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Only archived tasks can be restored")
    if _duplicate_exists(item.list, item.text, excluding=item):
        raise TaskConflict(
            "That task already exists in its original list, so it was not restored."
        )

    item.status = _restore_status_for(item)
    item.archived_at = None
    try:
        item.save()
    except IntegrityError as error:
        raise TaskConflict(
            "That task already exists in its original list, so it was not restored."
        ) from error
    return item


@transaction.atomic
def delete_archived_item(item):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status != Item.Status.ARCHIVED:
        raise InvalidTaskTransition(ARCHIVED_DELETE_ERROR)
    item.delete()


@transaction.atomic
def delete_list(list_):
    list_ = List.objects.select_for_update().get(pk=list_.pk)
    list_.delete()


EMPTY_PROJECT_TITLE_ERROR = "Give the project a name"
FOREIGN_PROJECT_ERROR = "That project isn't yours"
CROSS_AREA_PROJECT_ERROR = "A task can only join a project in its own area"


@transaction.atomic
def create_project(area, title, due_date=None):
    """A new project inside an area, owned by whoever owns the area.

    The owner is derived rather than passed: `List.owner` is required as of
    slice 6, so there is exactly one right answer and asking a caller for it
    only creates the chance of a wrong one.
    """
    normalized = (title or "").strip()
    if not normalized:
        raise TaskConflict(EMPTY_PROJECT_TITLE_ERROR)
    return Project.objects.create(
        owner=area.owner, area=area, title=normalized, due_date=due_date,
    )


@transaction.atomic
def complete_project(project):
    """Mark a project done, without touching a single one of its tasks.

    Charter rule 5 -- a project references its tasks, it does not own their
    status. Someone finishing a project has said the *grouping* is done; if
    tasks are still open underneath, that is information worth seeing rather
    than something to tidy away silently. principles.md: automations propose,
    people decide.

    Completing an already-completed project keeps the original stamp, so a
    double-click cannot rewrite when the work actually finished.
    """
    project = Project.objects.select_for_update().get(pk=project.pk)
    if project.is_completed:
        return project
    project.is_completed = True
    project.completed_at = timezone.now()
    project.save(update_fields=("is_completed", "completed_at"))
    return project


@transaction.atomic
def reopen_project(project):
    project = Project.objects.select_for_update().get(pk=project.pk)
    project.is_completed = False
    project.completed_at = None
    project.save(update_fields=("is_completed", "completed_at"))
    return project


@transaction.atomic
def set_task_project(task, project):
    """Put a task into a project, or take it out again with None.

    Both guards live here rather than only at the API, because the API is one
    caller and the invariant belongs to the model. principles.md: guards fail
    closed.
    """
    task = Item.objects.select_for_update().select_related("list").get(pk=task.pk)
    if project is not None:
        if project.owner_id != task.list.owner_id:
            raise TaskConflict(FOREIGN_PROJECT_ERROR)
        # A project groups work inside one area. Slice 8 renders a project's
        # tasks from the area page, so a task from elsewhere would appear
        # under a heading it does not belong to.
        if project.area_id != task.list_id:
            raise TaskConflict(CROSS_AREA_PROJECT_ERROR)
    task.project = project
    task.save(update_fields=("project", "updated_at"))
    return task


def delete_project(project):
    """Hard delete -- charter rule 6, stated in the model too.

    Its tasks survive: `Item.project` is SET_NULL, so deleting a project says
    the grouping was wrong, not that the work is gone. No tombstone, because
    rule 2 does not apply -- nothing creates or holds a Project offline.
    """
    project.delete()
