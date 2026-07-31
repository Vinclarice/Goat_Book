from calendar import monthrange
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from lists.models import Item, List, Tag


EMPTY_ITEM_ERROR = "You can't have an empty list item"
DUPLICATE_ITEM_ERROR = "You've already got this in your list"
ARCHIVED_DELETE_ERROR = "Only archived tasks can be permanently deleted"


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
    return item


@transaction.atomic
def reorder_items(for_list, ordered_ids):
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
    item.recurrence = recurrence
    item.save()
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


def _spawn_next_occurrence(completed_item):
    next_item = Item.objects.create(
        list=completed_item.list,
        text=completed_item.text,
        due_date=_advance_due_date(completed_item.due_date, completed_item.recurrence),
        recurrence=completed_item.recurrence,
        position=_next_position(completed_item.list),
    )
    next_item.tags.set(completed_item.tags.all())
    return next_item


@transaction.atomic
def complete_item(item):
    item = Item.objects.select_for_update().select_related("list").get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Archived tasks must be restored first")
    if item.status != Item.Status.COMPLETED:
        now = timezone.now()
        item.status = Item.Status.COMPLETED
        item.completed_at = now
        item.archived_at = None
        is_recurring = item.recurrence != Item.Recurrence.NONE
        if is_recurring:
            # Recurring tasks skip the "completed" resting state: archive
            # immediately (freeing up its text for the next occurrence,
            # which would otherwise collide with the unique-active-text
            # constraint) and spawn the next one right away.
            item.status = Item.Status.ARCHIVED
            item.archived_at = now
        item.save()
        if is_recurring:
            item._spawned = _spawn_next_occurrence(item)
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
        now = timezone.now()
        item.status = Item.Status.ARCHIVED
        item.archived_at = now
        item.save()
    return item


@transaction.atomic
def restore_item(item):
    item = Item.objects.select_for_update().select_related("list").get(pk=item.pk)
    if item.status != Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Only archived tasks can be restored")
    if _duplicate_exists(item.list, item.text, excluding=item):
        raise TaskConflict(
            "That task already exists in its original list, so it was not restored."
        )

    # A null completed_at means the task was active when it was archived, so
    # that is where it goes back to; anything else was genuinely completed.
    if item.completed_at is None:
        item.status = Item.Status.ACTIVE
    else:
        item.status = Item.Status.COMPLETED
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
