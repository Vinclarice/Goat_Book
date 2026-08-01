from calendar import monthrange
from datetime import timedelta
from uuid import uuid4

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from lists.models import Item, List, Tag


EMPTY_ITEM_ERROR = "You can't have an empty list item"
DUPLICATE_ITEM_ERROR = "You've already got this in your list"
ARCHIVED_DELETE_ERROR = "Only archived tasks can be permanently deleted"
SUBTASK_RECURRENCE_ERROR = "Only top-level tasks can repeat"
ALWAYS_RECURS_ON_ROOT_ERROR = "Only subtasks can repeat with their parent"
NESTED_SUBTASK_ERROR = "Subtasks can't have subtasks of their own"
FOREIGN_PARENT_ERROR = "That parent task isn't in this list"


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


def _duplicate_exists(for_list, text, excluding=None, parent=None):
    # Sibling-scoped, not list-scoped: "Book flights" may appear once under
    # each of several parents, but only once within any one sibling group.
    # Mirrors the unique_active_item constraint exactly.
    duplicates = for_list.item_set.exclude(status=Item.Status.ARCHIVED).filter(
        text=text,
        parent=parent,
    )
    if excluding is not None:
        duplicates = duplicates.exclude(pk=excluding.pk)
    return duplicates.exists()


def _reject_invalid_parent(for_list, parent):
    """Guards the two ways a parent can be wrong: not in this list, or
    already a subtask itself.

    The list check is a data-integrity rule, not an authorisation one --
    callers are responsible for having resolved `parent` through an
    owner-scoped queryset first (see lists/api.py). It still catches a
    cross-user parent, because another user's task is necessarily in
    another user's list.
    """
    if parent.list_id != for_list.id:
        raise TaskConflict(FOREIGN_PARENT_ERROR)
    if parent.parent_id is not None:
        raise TaskConflict(NESTED_SUBTASK_ERROR)


@transaction.atomic
def create_list_with_item(owner, title, text):
    normalized_text = normalize_task_text(text)
    normalized_title = (title or "").strip() or normalized_text[:100]
    new_list = List.objects.create(owner=owner, title=normalized_title)
    Item.objects.create(list=new_list, text=normalized_text)
    return new_list


def _next_position(for_list, parent=None):
    # Positions run within a sibling group, so a subtask's position is
    # relative to its siblings rather than to everything in the list.
    highest = for_list.item_set.exclude(
        status=Item.Status.ARCHIVED,
    ).filter(parent=parent).aggregate(Max("position"))["position__max"]
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


@transaction.atomic
def create_item(
    for_list,
    text,
    due_date=None,
    tags=None,
    recurrence=None,
    parent=None,
    always_recurs=None,
):
    normalized = normalize_task_text(text)
    if parent is not None:
        _reject_invalid_parent(for_list, parent)
    # None means "not asked for", which is different from False: only an
    # explicit choice on a root task is an error, since the flag says nothing
    # there. Children left unspecified take the model default.
    if always_recurs is not None and parent is None:
        raise TaskConflict(ALWAYS_RECURS_ON_ROOT_ERROR)
    if _duplicate_exists(for_list, normalized, parent=parent):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)
    if recurrence and recurrence not in Item.Recurrence.values:
        raise TaskConflict("Choose a valid recurrence.")
    if parent is not None and recurrence and recurrence != Item.Recurrence.NONE:
        raise TaskConflict(SUBTASK_RECURRENCE_ERROR)
    try:
        item = Item.objects.create(
            list=for_list,
            text=normalized,
            due_date=due_date,
            position=_next_position(for_list, parent=parent),
            recurrence=recurrence or Item.Recurrence.NONE,
            parent=parent,
            always_recurs=True if always_recurs is None else always_recurs,
        )
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    if tags:
        item.tags.set(_resolve_tags(for_list.owner, tags))
    return item


@transaction.atomic
def edit_item(item, text):
    item = Item.objects.select_for_update().select_related("list").get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")

    normalized = normalize_task_text(text)
    if _duplicate_exists(
        item.list, normalized, excluding=item, parent=item.parent
    ):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)

    item.text = normalized
    try:
        item.save()
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    return item


@transaction.atomic
def reorder_items(for_list, ordered_ids, parent=None):
    # Scoped to one sibling group: a reorder names every open task under
    # `parent` (or every root task when parent is None) and nothing else.
    # Set equality against that group is what stops ids belonging to another
    # group -- or another user's list -- from being smuggled in.
    items = list(
        Item.objects.select_for_update()
        .filter(list=for_list, parent=parent)
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
    item.tags.set(_resolve_tags(item.list.owner, tag_names))
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
    # Recurrence is a parent-only feature: a repeating subtask would have to
    # spawn its next occurrence somewhere, and the only sensible parent is one
    # that may itself have moved on.
    if item.parent_id is not None and recurrence != Item.Recurrence.NONE:
        raise TaskConflict(SUBTASK_RECURRENCE_ERROR)
    item.recurrence = recurrence
    item.save()
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
    return item


@transaction.atomic
def set_always_recurs(item, value):
    """Whether this subtask comes back on its parent's next occurrence.

    Guarded the same way set_recurrence guards a subtask: the flag answers a
    question a root task cannot be asked, so setting it there is a conflict
    rather than a silent no-op.
    """
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.parent_id is None:
        raise TaskConflict(ALWAYS_RECURS_ON_ROOT_ERROR)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    item.always_recurs = bool(value)
    item.save()
    return item


@transaction.atomic
def set_parent(item, parent):
    """Promote a subtask to a root task (parent=None) or demote a root task
    under another. Moving between parents is the same operation.
    """
    item = Item.objects.select_for_update().select_related("list").get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    if parent is not None:
        if parent.pk == item.pk:
            raise TaskConflict(NESTED_SUBTASK_ERROR)
        _reject_invalid_parent(item.list, parent)
        # Demoting a task that has children would create a third level.
        if item.subtasks.exists():
            raise TaskConflict(NESTED_SUBTASK_ERROR)
        if item.recurrence != Item.Recurrence.NONE:
            raise TaskConflict(SUBTASK_RECURRENCE_ERROR)
    if _duplicate_exists(item.list, item.text, excluding=item, parent=parent):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)

    item.parent = parent
    # Position is sibling-relative, so it means nothing in the new group.
    item.position = _next_position(item.list, parent=parent)
    try:
        item.save()
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    return item


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


def _spawn_next_occurrence(completed_item, carry_forward=()):
    next_item = Item.objects.create(
        list=completed_item.list,
        text=completed_item.text,
        due_date=_advance_due_date(completed_item.due_date, completed_item.recurrence),
        recurrence=completed_item.recurrence,
        position=_next_position(completed_item.list),
    )
    next_item.tags.set(completed_item.tags.all())

    # The next occurrence gets a fresh copy of the children, reset to active.
    # Their due dates shift by the same delta the parent's did, so a subtask
    # due two days before its parent stays two days before it; undated
    # children stay undated. What gets cloned is _children_to_carry_forward's
    # answer, not the cascade's -- see that function for why they differ.
    delta = None
    if completed_item.due_date and next_item.due_date:
        delta = next_item.due_date - completed_item.due_date
    for child in carry_forward:
        clone = Item.objects.create(
            list=child.list,
            text=child.text,
            due_date=(child.due_date + delta) if (child.due_date and delta) else child.due_date,
            recurrence=Item.Recurrence.NONE,
            position=child.position,
            notes=child.notes,
            parent=next_item,
            # Carried over rather than left to the model default, so a
            # subtask marked "don't bring this back" stays that way for every
            # cycle after the one it was set in.
            always_recurs=child.always_recurs,
        )
        clone.tags.set(child.tags.all())
    return next_item


def _lock_open_children(item):
    """Children still open, locked parent-first.

    Lock ordering matters now that select_for_update() is real on Postgres:
    every cascade takes the parent's lock before its children's, so two
    cascades can't deadlock by grabbing them in opposite orders.
    """
    return list(
        Item.objects.select_for_update()
        .filter(parent=item, status=Item.Status.ACTIVE)
        .order_by("pk")
    )


def _children_to_carry_forward(item):
    """Every child flagged always_recurs that hasn't been independently
    archived -- what clones into the next occurrence, regardless of whether
    it's still active, already completed, or about to be cascaded by this
    same action.

    Deliberately not the same query as _lock_open_children: that one is about
    cascade bookkeeping ("what must be resolved because an archived or
    completed parent can't have live children"), this one is about what the
    next occurrence looks like. Sharing one answer between them is the bug
    this exists to fix -- a subtask ticked off before its parent was
    invisible to the cascade query and so never came back.

    Archived children are excluded even when flagged: archiving reads as
    "removed", not "done", so it shouldn't come back on its own.
    """
    return list(
        Item.objects.filter(parent=item, always_recurs=True)
        .exclude(status=Item.Status.ARCHIVED)
        .order_by("pk")
    )


@transaction.atomic
def complete_item(item):
    item = Item.objects.select_for_update().select_related("list").get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Archived tasks must be restored first")
    item._cascaded = []
    if item.status != Item.Status.COMPLETED:
        now = timezone.now()
        # Captured before the parent moves, and returned to the caller: the
        # server cannot reconstruct this set afterwards, because children
        # already completed before the parent was ticked are indistinguishable
        # from ones this action completed. Undo has to reopen exactly these.
        children = _lock_open_children(item)
        is_recurring = item.recurrence != Item.Recurrence.NONE
        # Read before the cascade below mutates anything. A recurring parent
        # archives its open children on the way out, so running this query
        # afterwards would find them already archived and exclude every one
        # of them from the occurrence they're supposed to reappear in.
        carry_forward = _children_to_carry_forward(item) if is_recurring else []
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
            item.archive_group = uuid4()
        item.save()

        for child in children:
            child.status = item.status
            child.completed_at = now
            child.archived_at = item.archived_at
            child.archive_group = item.archive_group
            child.save()
        item._cascaded = children

        if is_recurring:
            item._spawned = _spawn_next_occurrence(item, carry_forward=carry_forward)
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
    item._cascaded = []
    if item.status != Item.Status.ARCHIVED:
        now = timezone.now()
        group = uuid4()
        # Everything still live under this parent goes with it: an archived
        # parent cannot have live children, or the list page would show an
        # orphan whose parent is nowhere on screen.
        children = list(
            Item.objects.select_for_update()
            .filter(parent=item)
            .exclude(status=Item.Status.ARCHIVED)
            .order_by("pk")
        )
        item.status = Item.Status.ARCHIVED
        item.archived_at = now
        item.archive_group = group
        item.save()

        for child in children:
            child.status = Item.Status.ARCHIVED
            child.archived_at = now
            child.archive_group = group
            child.save()
        item._cascaded = children
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
    if _duplicate_exists(item.list, item.text, excluding=item, parent=item.parent):
        raise TaskConflict(
            "That task already exists in its original list, so it was not restored."
        )

    # Children that went down with this parent come back with it, each to
    # whichever status it held before -- which is only knowable because
    # archiving stopped fabricating completed_at (migration 0018). Grouped by
    # archive_group, so a child archived separately beforehand stays archived.
    children = []
    if item.archive_group is not None:
        children = list(
            Item.objects.select_for_update()
            .filter(
                parent=item,
                status=Item.Status.ARCHIVED,
                archive_group=item.archive_group,
            )
            .order_by("pk")
        )

    item.status = _restore_status_for(item)
    item.archived_at = None
    item.archive_group = None
    try:
        item.save()
        for child in children:
            child.status = _restore_status_for(child)
            child.archived_at = None
            child.archive_group = None
            child.save()
    except IntegrityError as error:
        raise TaskConflict(
            "That task already exists in its original list, so it was not restored."
        ) from error
    item._cascaded = children
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
