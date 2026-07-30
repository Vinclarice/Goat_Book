"""Ninja router registered onto clarice.api's /api/v1/ contract.

Read-only for now -- create/update/delete stay on the hand-rolled
lists.api endpoints until a route's own migration PR (see the UI
overhaul plan's Step 4) moves them over.
"""
from typing import Literal

from django.utils import timezone
from ninja import Router, Schema

from lists import agenda as agenda_reader
from lists.models import Item

router = Router()

TaskStatus = Literal["active", "completed", "archived"]
TaskRecurrence = Literal["none", "daily", "weekly", "monthly"]
BucketKey = Literal["overdue", "today", "week", "later", "someday"]


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
