"""Ninja router registered onto clarice.api's /api/v1/ contract.

Item mutations (create/complete/reorder/tags/due-date) stay on the
hand-rolled lists.api endpoints -- they already work and are tested, so
a route's migration PR only moves what doesn't already have a JSON
path. List rename/delete never had one (the Django views redirect on
success, which doesn't suit a fetch-based caller), so those are genuinely
new here rather than moved.
"""
from typing import Literal

from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from lists import agenda as agenda_reader
from lists import services
from lists.forms import ListTitleForm
from lists.models import Item, List
from lists.serializers import (
    archive_workspace_data_for,
    list_ref_for,
    list_workspace_data_for,
    task_detail_data_for,
)

router = Router()

TaskStatus = Literal["active", "completed", "archived"]
TaskRecurrence = Literal["none", "daily", "weekly", "monthly"]
BucketKey = Literal["overdue", "today", "week", "later", "someday"]
ListColorKey = Literal[
    "sky", "sage", "amber", "lilac", "coral", "azure", "blush", "straw"
]


class TaskOut(Schema):
    id: int
    text: str
    status: TaskStatus
    created_at: str
    updated_at: str
    completed_at: str | None
    archived_at: str | None
    due_date: str | None
    position: int
    tags: list[str]
    recurrence: TaskRecurrence
    list_id: int
    url: str
    edit_url: str


class AgendaBucketOut(Schema):
    key: BucketKey
    label: str
    collapsed: bool


class AgendaListSummaryOut(Schema):
    id: int
    title: str
    url: str
    create_item_url: str
    open_count: int
    overdue_count: int
    color_key: ListColorKey


class AgendaOut(Schema):
    today: str
    username: str
    archive_url: str
    archived_count: int
    new_list_url: str
    settings_url: str
    daily_digest: bool
    buckets: list[AgendaBucketOut]
    items: list[TaskOut]
    completed_today: list[TaskOut]
    lists: list[AgendaListSummaryOut]


class ListRefOut(Schema):
    id: int
    title: str
    create_item_url: str
    reorder_url: str


class ListDetailOut(Schema):
    list: ListRefOut
    items: list[TaskOut]
    archived_count: int
    archive_url: str


class ListRenameIn(Schema):
    title: str


class TaskListSummaryOut(Schema):
    id: int
    title: str
    url: str


class ArchiveOut(Schema):
    items: list[TaskOut]
    lists: list[TaskListSummaryOut]


class TaskDetailOut(Schema):
    task: TaskOut
    list: TaskListSummaryOut


@router.get("/agenda", response=AgendaOut)
def agenda(request):
    user = request.user
    today = timezone.localdate()
    all_open = agenda_reader.annotate_for_display(
        list(agenda_reader.open_items_for(user)), today
    )
    completed_today = agenda_reader.annotate_for_display(
        list(agenda_reader.completed_today_for(user, today)), today
    )
    lists = agenda_reader.list_summaries(user)
    archived_count = Item.objects.filter(
        list__owner=user,
        status=Item.Status.ARCHIVED,
    ).count()

    return agenda_reader.workspace_data_for(
        user,
        today=today,
        all_open=all_open,
        completed_today=completed_today,
        lists=lists,
        archived_count=archived_count,
    )


def _owned_list(request, list_id):
    return get_object_or_404(List, id=list_id, owner=request.user)


@router.get("/lists/{list_id}", response=ListDetailOut)
def list_detail(request, list_id: int):
    our_list = _owned_list(request, list_id)
    items = list(
        our_list.item_set.exclude(status=Item.Status.ARCHIVED)
        .select_related("list")
        .prefetch_related("tags")
    )
    return {
        **list_workspace_data_for(our_list, items),
        "archived_count": our_list.item_set.filter(
            status=Item.Status.ARCHIVED,
        ).count(),
        "archive_url": reverse("archive"),
    }


@router.patch("/lists/{list_id}", response=ListRefOut)
def rename_list(request, list_id: int, payload: ListRenameIn):
    our_list = _owned_list(request, list_id)
    # Reuses ListTitleForm's own validation (strip, required, max_length)
    # rather than re-implementing it, so the two entry points to the same
    # rule can't quietly drift.
    form = ListTitleForm(data={"title": payload.title}, instance=our_list)
    if not form.is_valid():
        raise HttpError(400, form.errors["title"][0])
    form.save()
    return list_ref_for(our_list)


@router.delete("/lists/{list_id}")
def delete_list(request, list_id: int):
    our_list = _owned_list(request, list_id)
    services.delete_list(our_list)
    return {"deleted": list_id}


@router.get("/tasks/{item_id}", response=TaskDetailOut)
def task_detail(request, item_id: int):
    # Matches edit_item's queryset exactly: archived tasks are managed
    # from the Archive route (restore/delete), not edited here.
    item = get_object_or_404(
        Item.objects.select_related("list").prefetch_related("tags"),
        id=item_id,
        list__owner=request.user,
        status__in=(Item.Status.ACTIVE, Item.Status.COMPLETED),
    )
    return task_detail_data_for(item)


@router.get("/archive", response=ArchiveOut)
def archive(request):
    user = request.user
    archived_items = list(
        Item.objects.filter(list__owner=user, status=Item.Status.ARCHIVED)
        .select_related("list")
        .prefetch_related("tags")
        .order_by("-archived_at", "-id")
    )
    return archive_workspace_data_for(user, archived_items)
