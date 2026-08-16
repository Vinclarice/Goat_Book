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

from accounts.auth import SessionAuthIfLoggedIn, TokenAuth
from accounts.models import SCOPE_AGENDA_READ
from lists import agenda as agenda_reader
from lists import projects as project_reader
from lists import services
from lists.forms import ListTitleForm
from lists.models import CadenceMode, Item, List
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
    # Nullable since August 14, 2026 -- a task may stand on its own, so this is
    # the boundary admitting a state the database already allowed. Ninja
    # validates responses, so leaving it `int` turned every unfiled task into a
    # 500 that no amount of care in the serializer could avoid.
    area_id: int | None
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
    # Singular and optional -- an Area belongs to at most one Project.
    project: AgendaProjectSummaryOut | None
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
    # Whether a repeating task is fixed to the calendar or counts from when it
    # was last done -- see lists.models.CadenceMode. Null when it does not
    # repeat, which is the honest answer rather than a default nobody chose.
    cadence_mode: CadenceMode | None
    # Optional since August 14, 2026: a task may stand on its own. Declared
    # nullable here rather than only handled in the serializer, because Ninja
    # validates the response -- a non-optional schema turns an unfiled task
    # into a 500 no matter how carefully the dict was built.
    area: TaskAreaSummaryOut | None
    checklist_steps: list[ChecklistStepOut]
    create_checklist_step_url: str
    reorder_checklist_steps_url: str


class NavAreaOut(Schema):
    id: int
    title: str
    open_count: int
    overdue_count: int
    color_key: AreaColorKey


class NavProjectOut(Schema):
    id: int
    title: str
    open_task_count: int


class NavOut(Schema):
    areas: list[NavAreaOut]
    # ui-second-pass-plan.md F3, Vince's call: a top-level group, flat
    # across areas, the same weight as `areas` rather than nested under it.
    # Completed projects are left out -- this group is ongoing work, the
    # same reason the Agenda excludes completed tasks, and unlike an Area a
    # project actually has a completion state to filter on.
    projects: list[NavProjectOut]
    archived_count: int
    settings_url: str
    # The knowledge core, and since Heron 4b the only place a thought lives.
    # `inbox_count`, `inbox_url` and `ideas_url` sat beside this until the Inbox
    # was deleted; the count was the one number here that measured a backlog,
    # and it went with the thing that had one.
    #
    # Served rather than written into the client. That was originally because
    # the prefix was temporary; step 5 made `/mind/` permanent, and it is still
    # served -- the server owns its own URLs, and a route spelled out in two
    # languages is one that can disagree with itself.
    mind_url: str
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
        "projects": [
            {
                "id": each.id,
                "title": each.title,
                "open_task_count": each.open_task_count,
            }
            for each in project_reader.projects_for(user).filter(is_completed=False)
        ],
        "archived_count": Item.objects.filter(
            owner=user, status=Item.Status.ARCHIVED
        ).count(),
        "settings_url": reverse("account_settings"),
        # Django pages, not SPA routes: these links leave the app shell.
        "mind_url": reverse("capture"),
        "landing_surface": user.landing_surface,
    }


@router.get(
    "/agenda",
    response=AgendaOut,
    # Token auth as well as session -- android-full-client-plan.md's slice
    # 2. Read-only: the write actions the Agenda page performs live on the
    # hand-rolled lists.api views, which get their own token support via
    # token_or_session_required (see accounts/auth.py and
    # token-scopes-plan.md §7) since they were never on this Ninja router.
    auth=[TokenAuth(SCOPE_AGENDA_READ), SessionAuthIfLoggedIn()],
)
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
        owner=user,
        status=Item.Status.ARCHIVED,
    ).count()
    projects = project_reader.projects_for(user)

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
        Item.objects.select_related("list", "commitment").prefetch_related("tags"),
        id=item_id,
        owner=request.user,
        status__in=(Item.Status.ACTIVE, Item.Status.COMPLETED),
    )
    return task_detail_data_for(item)


class ProjectOut(Schema):
    id: int
    title: str
    due_date: str | None
    is_completed: bool
    completed_at: str | None
    created_at: str
    open_task_count: int
    areas: list["ProjectAreaOut"]
    is_overdue: bool


class ProjectAreaOut(Schema):
    id: int
    title: str
    open_count: int
    overdue_count: int
    color_key: AreaColorKey


class ProjectCreateIn(Schema):
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


class AreaProjectIn(Schema):
    # null clears it -- explicit rather than a separate DELETE route, since
    # "move to another project" and "remove from any project" are the same
    # write from the Area's point of view.
    project_id: int | None


def _areas_by_project(user):
    """This owner's areas, grouped by which project (if any) they're in.

    Computed once per request rather than once per project inside
    _project_out -- reuses list_summaries's own open/overdue annotation, one
    authoritative definition of "an area's open count," not two.
    """
    grouped = {}
    for each in agenda_reader.list_summaries(user):
        if each.project_id is not None:
            grouped.setdefault(each.project_id, []).append(each)
    return grouped


def _project_out(project, areas=None):
    if areas is None:
        areas = _areas_by_project(project.owner).get(project.id, [])
    return {
        "id": project.id,
        "title": project.title,
        "due_date": project.due_date.isoformat() if project.due_date else None,
        # A finished project is never overdue regardless of due_date -- the
        # same rule tasks and areas already apply, extended here rather than
        # left for the client to reinvent with its own idea of "today".
        "is_overdue": (
            not project.is_completed
            and project.due_date is not None
            and project.due_date < timezone.localdate()
        ),
        "is_completed": project.is_completed,
        "completed_at": (
            project.completed_at.isoformat() if project.completed_at else None
        ),
        "created_at": project.created_at.isoformat(),
        # Annotated by projects_for; a freshly created project has not been
        # through that read, so it falls back rather than raising.
        "open_task_count": getattr(project, "open_task_count", 0),
        "areas": [
            {
                "id": each.id,
                "title": each.title,
                "open_count": each.open_count,
                "overdue_count": each.overdue_count,
                "color_key": each.color_key,
            }
            for each in areas
        ],
    }


@router.get("/projects", response=list[ProjectOut])
def projects(request):
    by_project = _areas_by_project(request.user)
    return [
        _project_out(each, areas=by_project.get(each.id, []))
        for each in project_reader.projects_for(request.user)
    ]


@router.get("/projects/{project_id}", response=ProjectOut)
def project_detail(request, project_id: int):
    project = project_reader.project_for(request.user, project_id)
    if project is None:
        raise HttpError(404, "Project not found.")
    return _project_out(project)


@router.post("/projects", response=ProjectOut)
def create_project(request, payload: ProjectCreateIn):
    try:
        project = services.create_project(
            request.user, payload.title, due_date=_parse_date(payload.due_date),
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


@router.patch("/areas/{area_id}/project", response=AreaRefOut)
def assign_area_project(request, area_id: int, payload: AreaProjectIn):
    """Put an Area into a Project, move it, or take it out again.

    A dedicated route rather than folding into AreaRenameIn: that schema's
    one field is always required, and project_id is optional/tri-state --
    bolting the two together would mean the always-required half inheriting
    exclude_unset semantics it doesn't need.
    """
    our_list = _owned_area(request, area_id)
    if payload.project_id is None:
        services.remove_area_from_project(our_list)
    else:
        project = project_reader.project_for(request.user, payload.project_id)
        if project is None:
            raise HttpError(404, "Project not found.")
        try:
            services.add_area_to_project(our_list, project)
        except services.TaskConflict as error:
            raise HttpError(409, str(error))
    return area_ref_for(our_list)


class AreaCreateIn(Schema):
    title: str


@router.post("/projects/{project_id}/areas", response=AreaRefOut)
def create_area_in_project(request, project_id: int, payload: AreaCreateIn):
    """A new, empty Area, already inside this Project.

    No first task required, unlike the Agenda sidebar's own "+ New area" --
    Vince's call, August 10, 2026: the predominant use case for a project
    is areas that don't exist yet, not reassigning ones that do.
    """
    project = project_reader.project_for(request.user, project_id)
    if project is None:
        raise HttpError(404, "Project not found.")
    area = services.create_area(request.user, payload.title, project=project)
    return area_ref_for(area)


@router.get("/archive", response=ArchiveOut)
def archive(request):
    user = request.user
    archived_items = list(
        Item.objects.filter(owner=user, status=Item.Status.ARCHIVED)
        .select_related("list")
        .prefetch_related("tags")
        .order_by("-archived_at", "-id")
    )
    return archive_workspace_data_for(user, archived_items)
