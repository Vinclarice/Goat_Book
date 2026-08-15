from calendar import monthrange
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from lists.models import (
    CadenceMode,
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


def _duplicate_exists(for_list, text, excluding=None, owner=None):
    # An unfiled task is deduplicated against its owner's other unfiled tasks,
    # which reverses what this said an hour earlier. The argument then was that
    # unfiled tasks are not a list, so two thoughts sharing wording should both
    # be allowed through. What changed it is the retry: a phone re-sending a
    # share is the common case and a second identical commitment is the common
    # cost, while the thought itself is never at stake -- the node stays in the
    # knowledge core either way, and only the duplicate task is refused.
    if for_list is None:
        if owner is None:
            return False
        duplicates = Item.objects.filter(
            owner=owner, list__isnull=True, text=text
        ).exclude(status=Item.Status.ARCHIVED)
    else:
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


def create_area(owner, title, project=None):
    """An Area with no task in it -- Vince's call, August 10, 2026.

    create_list_with_item's first-task requirement was never a domain rule;
    it was the only creation path that existed before a Project needed its
    own way to grow an Area from nothing. The Agenda sidebar's "+ New area"
    form is unchanged and still asks for a first task -- this is a second,
    additive path, not a replacement.
    """
    normalized_title = (title or "").strip() or "Untitled list"
    if project is not None and project.owner_id != owner.id:
        raise TaskConflict(FOREIGN_PROJECT_ERROR)
    return List.objects.create(owner=owner, title=normalized_title, project=project)


def _next_position(for_list, owner=None):
    # Position orders a task within its Area. An unfiled task is ordered by the
    # agenda's own rules instead, so any value is unused -- but they still get
    # distinct ones, because a column full of zeroes makes a stable sort
    # impossible the day something does want to arrange them.
    if for_list is None:
        if owner is None:
            return 0
        highest = (
            Item.objects.filter(owner=owner, list__isnull=True)
            .exclude(status=Item.Status.ARCHIVED)
            .aggregate(Max("position"))["position__max"]
        )
        return 0 if highest is None else highest + 1
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


def resolve_tags(owner, tag_names):
    """Public: capture.services reuses this rather than a second
    definition of what a tag is, per lists.Tag being the one owner-scoped
    tag vocabulary in the app.
    """
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
        owner=item.owner,
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
def create_item(for_list, text, due_date=None, tags=None, recurrence=None, owner=None):
    """A task, in an Area or standing on its own.

    `owner` is only needed when `for_list` is None; with an Area, the Area's
    owner is the answer and passing a different one would be inventing a second
    opinion. Callers that already pass an Area are unchanged, which is what
    makes this a widening rather than a migration of every call site.
    """
    if for_list is None and owner is None:
        raise TaskConflict("A task with no Area still has to belong to somebody")
    owner = for_list.owner if for_list is not None else owner

    normalized = normalize_task_text(text)
    if _duplicate_exists(for_list, normalized, owner=owner):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)
    if recurrence and recurrence not in Item.Recurrence.values:
        raise TaskConflict("Choose a valid recurrence.")
    try:
        item = Item.objects.create(
            list=for_list,
            owner=owner,
            text=normalized,
            due_date=due_date,
            position=_next_position(for_list, owner=owner),
            recurrence=recurrence or Item.Recurrence.NONE,
        )
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    if item.recurrence != Item.Recurrence.NONE:
        _anchor_commitment(item)
        item.save(update_fields=["commitment"])
    if tags:
        item.tags.set(resolve_tags(owner, tags))
    return item


@transaction.atomic
def edit_item(item, text):
    item = Item.objects.select_for_update(of=("self",)).select_related("list").get(pk=item.pk)
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
    item = Item.objects.select_for_update(of=("self",)).select_related("list").get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    resolved = resolve_tags(item.owner, tag_names)
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
def set_recurrence(item, recurrence, cadence_mode=None):
    """Set how often this repeats, and optionally whether it is anchored.

    `cadence_mode=None` means "leave it as it is", not "reset to the default".
    Editing a cadence must not silently undo a mode somebody chose -- that is
    how a setting gets quietly reverted by an unrelated edit.
    """
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    if recurrence not in Item.Recurrence.values:
        raise TaskConflict("Choose a valid recurrence.")
    if cadence_mode is not None and cadence_mode not in CadenceMode.values:
        raise TaskConflict("Choose a valid schedule mode.")
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
    if cadence_mode is not None:
        _write_through_to_commitment(item, cadence_mode=cadence_mode)
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
    task = Item.objects.select_for_update(of=("self",)).select_related("list").get(pk=task.pk)
    if task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    normalized = normalize_task_text(text)
    if _duplicate_step_exists(task, normalized):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)
    try:
        step = ChecklistStep.objects.create(
            owner=task.owner,
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
        ChecklistStep.objects.select_for_update(of=("self",))
        .select_related("task", "task__list")
        .get(pk=step.pk)
    )
    if step.task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    task_list = step.task.list
    # From the task, not from its Area, which may not exist -- the same
    # correction as in _spawn_next_occurrence, and the same mistake: relying on
    # save() to derive an owner works for every filed task and leaves an
    # unfiled one violating NOT NULL. Passing it here also restores the
    # duplicate check, which followed the Area and so did nothing without one.
    owner = step.task.owner
    if _duplicate_exists(task_list, step.text, owner=owner):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)
    try:
        promoted = Item.objects.create(
            list=task_list,
            owner=owner,
            text=step.text,
            position=_next_position(task_list, owner=owner),
        )
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    step.delete()
    return promoted


def _nth_occurrence_after(base, recurrence, n):
    """The nth scheduled date after `base`, counting in calendar units.

    Computed from the anchor each time rather than by stepping one interval
    off the last result, which matters for monthly: the 31st advanced through
    February and then carried forward would spend the rest of the year on the
    28th. Here February is the only month that clamps, and March is the 31st
    again.
    """
    if recurrence == Item.Recurrence.DAILY:
        return base + timedelta(days=n)
    if recurrence == Item.Recurrence.WEEKLY:
        return base + timedelta(weeks=n)
    if recurrence == Item.Recurrence.MONTHLY:
        month_index = base.month - 1 + n
        year = base.year + month_index // 12
        month = month_index % 12 + 1
        return base.replace(
            year=year, month=month, day=min(base.day, monthrange(year, month)[1])
        )
    return None


def _advance_due_date(due_date, recurrence, today=None, mode=CadenceMode.ANCHORED):
    """The next occurrence's due date, which is never already in the past.

    It used to be one interval past the *previous due date*, full stop. A
    monthly commitment due July 4 and completed August 10 therefore produced a
    successor due August 4 -- overdue at the instant it was created, on a task
    the person had just finished. `roadmap.md` carried this as "one defect to
    fix on the way in rather than port"; the way in happened and it was not.

    **Missed periods are skipped, not replayed.** The schedule keeps its anchor
    and moves forward until it clears today, so a filter changed on the 4th is
    still on the 4th afterwards, and five missed weeks produce one task rather
    than five. Occurrences that did not happen are not invented -- a fabricated
    history is worse than an absent one, and `principles.md` refuses it.

    All of that describes **anchored**, which is the default and was the only
    mode until August 15, 2026. **Floating** counts from the completion instead
    -- a furnace filter lasts a month from when it was changed, not from a date
    nobody acted on -- and needs no skipping, because it starts from today by
    construction.

    See `CadenceMode` for why anchored is the default rather than a coin toss.
    """
    if today is None:
        today = timezone.localdate()
    if mode == CadenceMode.FLOATING:
        # The old due date is deliberately ignored, including a future one:
        # floating means the clock restarts when the work is actually done.
        return _nth_occurrence_after(today, recurrence, 1)

    base = due_date or today

    # Bounded rather than `while True`: a corrupt cadence or a due date far in
    # the past should not spin. Two thousand steps clears five years of daily.
    for n in range(1, 2001):
        candidate = _nth_occurrence_after(base, recurrence, n)
        if candidate is None:
            return None
        if candidate > today:
            return candidate
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
        # From the series, not from the Area. `Item.save()` derives owner from
        # `list`, which works for every filed task and leaves an unfiled one
        # with nothing to derive from -- so this insert violated NOT NULL and
        # completing the task raised. The commitment is the durable identity
        # here and it knows whose it is, whether or not it has a place.
        owner=commitment.owner,
        text=commitment.text,
        due_date=_advance_due_date(
            completed_item.due_date,
            commitment.cadence,
            today=timezone.localdate(),
            mode=commitment.cadence_mode,
        ),
        recurrence=commitment.cadence,
        position=_next_position(commitment.list, owner=commitment.owner),
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
# `of=("self",)` on every lock that also selects the Area.
#
# Item.list became nullable on August 14, 2026, which turned select_related("list")
# from an inner join into an outer one -- and Postgres refuses "FOR UPDATE cannot
# be applied to the nullable side of an outer join". Locking only the base row is
# what was meant anyway: nothing here mutates the Area, and locking it would take
# a lock on every task in it.
#
# Found by the suite rather than by reading: 95 errors from one column changing
# nullability, none of them in code that mentions the column.


def complete_item(item):
    item = Item.objects.select_for_update(of=("self",)).select_related("list").get(pk=item.pk)
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
    item = Item.objects.select_for_update(of=("self",)).select_related("list").get(pk=item.pk)
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


@transaction.atomic
def create_project(owner, title, due_date=None):
    """A new, standalone project -- project-workspace-plan.md 2.

    Owner is passed directly rather than derived: a Project has no parent
    record left to borrow it from, the same shape create_list_with_item
    already uses.
    """
    normalized = (title or "").strip()
    if not normalized:
        raise TaskConflict(EMPTY_PROJECT_TITLE_ERROR)
    return Project.objects.create(owner=owner, title=normalized, due_date=due_date)


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
def add_area_to_project(area, project):
    """Put an Area into a Project, or move it from one Project to another.

    project-workspace-plan.md 2. The guard below is a cross-row check a
    plain ForeignKey can't express on its own -- same "two owned records,
    guard they share an owner" shape as capture.services.link_ideas.
    Checked here rather than only at the API, so the invariant holds
    regardless of caller. principles.md: guards fail closed.
    """
    area = List.objects.select_for_update().get(pk=area.pk)
    if project.owner_id != area.owner_id:
        raise TaskConflict(FOREIGN_PROJECT_ERROR)
    area.project = project
    area.save(update_fields=("project",))
    return area


@transaction.atomic
def remove_area_from_project(area):
    """Take an Area out of its Project. A no-op if it has none."""
    area = List.objects.select_for_update().get(pk=area.pk)
    area.project = None
    area.save(update_fields=("project",))
    return area


def delete_project(project):
    """Hard delete -- charter rule 6, stated in the model too.

    Its areas survive: `List.project` is SET_NULL, so deleting a project
    says the grouping was wrong, not that the work is gone. No tombstone,
    because rule 2 does not apply -- nothing creates or holds a Project
    offline.
    """
    project.delete()
