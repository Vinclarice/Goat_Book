"""Ninja router registered onto clarice.api's /api/v1/ contract.

Item mutations (create/complete/reorder/tags/due-date) stay on the
hand-rolled lists.api endpoints -- they already work and are tested, so
a route's migration PR only moves what doesn't already have a JSON
path. Area rename/delete never had one (the Django views redirect on
success, which doesn't suit a fetch-based caller), so those are genuinely
new here rather than moved.

**Vocabulary.** This boundary says Area; the ORM says `List`. Release D
slice 5 moved the words and nothing else, per `architecture-trajectory.md`
§7's refusal to rename the model or the app for a cosmetic reason -- the
same split `Item`/"task" already lives with. Python locals below still read
`our_list`, because renaming them would be churn no client can observe.
See `lists/tests/test_area_vocabulary.py` for the guard.
"""
from datetime import date
from typing import Literal

from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from capture.models import Capture
from lists import agenda as agenda_reader
from lists import projects as project_reader
from lists import services
from lists.forms import ListTitleForm
from lists.models import Item, List
from lists.serializers import (
    archive_workspace_data_for,
    area_ref_for,
    area_workspace_data_for,
    task_detail_data_for,
)

router = Router()

TaskStatus = Literal["active", "completed", "archived"]
TaskRecurrence = Literal["none", "daily", "weekly", "monthly"]
BucketKey = Literal["overdue", "today", "week", "later", "someday"]
AreaColorKey = Literal[
    "sky", "sage", "amber", "lilac", "coral", "azure", "blush", "straw"
]


class ChecklistStepOut(Schema):
    id: int
    text: str
    position: int
    is_done: bool
    completed_at: str | None
    carries_forward: bool
    task_id: int
    url: str
    promote_url: str


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
    notes: str
    area_id: int
    project_id: int | None
    url: str
    edit_url: str


class AgendaBucketOut(Schema):
    key: BucketKey
    label: str
    collapsed: bool


class AgendaAreaSummaryOut(Schema):
    id: int
    title: str
    url: str
    create_item_url: str
    open_count: int
    overdue_count: int
    color_key: AreaColorKey


class AgendaProjectSummaryOut(Schema):
    id: int
    title: str
    # A project has no page of its own yet, so this is its area's --
    # ui-second-pass-plan.md F2/F3, the second half still open.
    url: str


class AgendaOut(Schema):
    today: str
    username: str
    archive_url: str
    archived_count: int
    new_area_url: str
    settings_url: str
    daily_digest: bool
    buckets: list[AgendaBucketOut]
    items: list[TaskOut]
    completed_today: list[TaskOut]
    areas: list[AgendaAreaSummaryOut]
    projects: list[AgendaProjectSummaryOut]


class AreaRefOut(Schema):
    id: int
    title: str
    create_item_url: str
    reorder_url: str


class AreaDetailOut(Schema):
    area: AreaRefOut
    items: list[TaskOut]
    projects: list[AgendaProjectSummaryOut]
    archived_count: int
    archive_url: str


class AreaRenameIn(Schema):
    title: str


class TaskAreaSummaryOut(Schema):
    id: int
    title: str
    url: str


class ArchiveOut(Schema):
    items: list[TaskOut]
    areas: list[TaskAreaSummaryOut]
    projects: list[AgendaProjectSummaryOut]


class TaskDetailOut(Schema):
    task: TaskOut
    area: TaskAreaSummaryOut
    checklist_steps: list[ChecklistStepOut]
    create_checklist_step_url: str
    reorder_checklist_steps_url: str


class NavAreaOut(Schema):
    id: int
    title: str
    open_count: int
    overdue_count: int
    color_key: AreaColorKey


class NavOut(Schema):
    areas: list[NavAreaOut]
    archived_count: int
    inbox_count: int
    settings_url: str
    inbox_url: str
    ideas_url: str
    # So the SPA's own index route sends /app/ where the server would send
    # a login, rather than hard-coding a second answer that could drift
    # from lists.views.dashboard's.
    landing_surface: str


@router.get("/nav", response=NavOut)
def navigation(request):
    """Everything the persistent side nav needs, on every page.

    A single endpoint rather than three payloads each growing the same
    fields: the agenda already carried area summaries, but the area page and
    archive didn't, and duplicating them into both schemas would mean three
    places to keep in step.
    """
    user = request.user
    return {
        "areas": agenda_reader.list_summaries(user),
        "archived_count": Item.objects.filter(
            list__owner=user, status=Item.Status.ARCHIVED
        ).count(),
        # A one-way read into capture. Capture stays isolated in the
        # direction that matters -- no FK, no import the other way -- but a
        # nav that can't show what's waiting is a nav nobody clicks.
        "inbox_count": Capture.objects.filter(
            owner=user, resolved_at__isnull=True
        ).count(),
        "settings_url": reverse("account_settings"),
        # Django pages, not SPA routes: these links leave the app shell.
        "inbox_url": reverse("capture_inbox"),
        "ideas_url": reverse("ideas"),
        "landing_surface": user.landing_surface,
    }


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
    # select_related("area") because each project's url comes from its
    # area -- a project has no page of its own -- and the plain loop in
    # workspace_data_for would otherwise be one query per project.
    projects = project_reader.projects_for(user).select_related("area")

    return agenda_reader.workspace_data_for(
        user,
        today=today,
        all_open=all_open,
        completed_today=completed_today,
        lists=lists,
        archived_count=archived_count,
        projects=projects,
    )


def _parse_date(value):
    """YYYY-MM-DD or nothing. The server owns date meaning, per
    principles.md -- a client sends the string it was given and this decides
    what it means.
    """
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HttpError(400, "Use a valid date (YYYY-MM-DD).")


def _owned_area(request, area_id):
    return get_object_or_404(List, id=area_id, owner=request.user)


@router.get("/areas/{area_id}", response=AreaDetailOut)
def area_detail(request, area_id: int):
    our_list = _owned_area(request, area_id)
    items = list(
        our_list.item_set.exclude(status=Item.Status.ARCHIVED)
        .select_related("list")
        .prefetch_related("tags")
    )
    return {
        **area_workspace_data_for(our_list, items),
        "archived_count": our_list.item_set.filter(
            status=Item.Status.ARCHIVED,
        ).count(),
        "archive_url": reverse("archive"),
    }


@router.patch("/areas/{area_id}", response=AreaRefOut)
def rename_area(request, area_id: int, payload: AreaRenameIn):
    our_list = _owned_area(request, area_id)
    # Reuses ListTitleForm's own validation (strip, required, max_length)
    # rather than re-implementing it, so the two entry points to the same
    # rule can't quietly drift.
    form = ListTitleForm(data={"title": payload.title}, instance=our_list)
    if not form.is_valid():
        raise HttpError(400, form.errors["title"][0])
    form.save()
    return area_ref_for(our_list)


@router.delete("/areas/{area_id}")
def delete_area(request, area_id: int):
    our_list = _owned_area(request, area_id)
    services.delete_list(our_list)
    return {"deleted": area_id}


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


class ProjectOut(Schema):
    id: int
    title: str
    area_id: int
    due_date: str | None
    is_completed: bool
    completed_at: str | None
    created_at: str
    open_task_count: int


class ProjectCreateIn(Schema):
    area_id: int
    title: str
    due_date: str | None = None


class ProjectUpdateIn(Schema):
    """Every field optional; absent means "leave it alone".

    `due_date` has to distinguish absent from explicitly null, because
    clearing a due date and not mentioning it are different requests and
    `str | None = None` cannot tell them apart on its own. The handler reads
    `exclude_unset` rather than inventing a sentinel default.
    """

    title: str | None = None
    due_date: str | None = None
    is_completed: bool | None = None


def _project_out(project):
    return {
        "id": project.id,
        "title": project.title,
        "area_id": project.area_id,
        "due_date": project.due_date.isoformat() if project.due_date else None,
        "is_completed": project.is_completed,
        "completed_at": (
            project.completed_at.isoformat() if project.completed_at else None
        ),
        "created_at": project.created_at.isoformat(),
        # Annotated by projects_for; a freshly created project has not been
        # through that read, so it falls back rather than raising.
        "open_task_count": getattr(project, "open_task_count", 0),
    }


@router.get("/projects", response=list[ProjectOut])
def projects(request, area_id: int | None = None):
    """This caller's projects, optionally narrowed to one Area.

    The filter is applied on top of the owner-scoped queryset rather than
    beside it, so an area id belonging to somebody else narrows to nothing
    instead of quietly falling back to everything -- a narrowing parameter
    that stops narrowing is the kind of bug nobody notices.
    """
    found = project_reader.projects_for(request.user)
    if area_id is not None:
        found = found.filter(area_id=area_id)
    return [_project_out(each) for each in found]


@router.post("/projects", response=ProjectOut)
def create_project(request, payload: ProjectCreateIn):
    area = _owned_area(request, payload.area_id)
    try:
        project = services.create_project(
            area, payload.title, due_date=_parse_date(payload.due_date),
        )
    except services.TaskConflict as error:
        raise HttpError(409, str(error))
    return _project_out(project)


@router.patch("/projects/{project_id}", response=ProjectOut)
def update_project(request, project_id: int, payload: ProjectUpdateIn):
    project = project_reader.project_for(request.user, project_id)
    if project is None:
        raise HttpError(404, "Project not found.")

    if payload.is_completed is not None:
        if payload.is_completed:
            services.complete_project(project)
        else:
            services.reopen_project(project)

    fields = []
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HttpError(409, services.EMPTY_PROJECT_TITLE_ERROR)
        project.title = title
        fields.append("title")
    if "due_date" in payload.dict(exclude_unset=True):
        project.due_date = _parse_date(payload.due_date)
        fields.append("due_date")
    if fields:
        project.save(update_fields=fields)

    return _project_out(project_reader.project_for(request.user, project_id))


@router.delete("/projects/{project_id}")
def delete_project(request, project_id: int):
    project = project_reader.project_for(request.user, project_id)
    if project is None:
        raise HttpError(404, "Project not found.")
    services.delete_project(project)
    return {"deleted": project_id}


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
