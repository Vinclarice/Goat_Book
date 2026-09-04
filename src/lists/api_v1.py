"""Ninja router registered onto clarice.api's /api/v1/ contract.

**Item mutations live here as of August 30, 2026** --
coherence-audit-2026-08-30.md F2. They stayed on the hand-rolled `lists.api`
views for a long time on the reasoning that they already worked and were
tested, which was true of each one and wrong in aggregate: it left the noun
this application is named for as the only domain outside the generated
contract, so `tsc --noEmit` could not see a task write at all while it checked
every Money call.

**`lists.api` still exists and is not dead code.** It is the compatibility
surface for the shipped Android build, which reads `url` off each task in the
agenda payload and calls it -- see that module's docstring for what is left of
it and what retires it.

**Vocabulary.** This boundary says Area; the ORM says `List`. Release D
slice 5 moved the words and nothing else, per `architecture-trajectory.md`
§7's refusal to rename the model or the app for a cosmetic reason -- the
same split `Item`/"task" already lives with. Python locals below still read
`our_list`, because renaming them would be churn no client can observe.
See `lists/tests/test_area_vocabulary.py` for the guard.
"""
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count
from typing import Literal, get_args

from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from accounts import services as account_services
from accounts.auth import SessionAuthIfLoggedIn, TokenAuth
from accounts.models import SCOPE_AGENDA_READ, SCOPE_AGENDA_WRITE
from clarice.clocks import today_for
from lists import agenda as agenda_reader
from money import services as bills
from money import reads as money_reader
from lists import projects as project_reader
from lists import services
from lists.forms import ListTitleForm
from lists.models import (
    CadenceMode,
    ChecklistStep,
    Item,
    List,
    Priority,
)
from money.models import Account, Bill, Direction, MoneyCategory
# **The contract, not a leak.** The Agenda shows bills, so it receives them
# in the shape money defines -- `modules.md`'s integration contract rather
# than inheritance. The dependency points this way and never back.
from money import reads as money_reads
from appointments.api_v1 import AppointmentOut
from money.api_v1 import AgendaBillOut
from lists.serializers import (
    archive_workspace_data_for,
    area_ref_for,
    area_workspace_data_for,
    serialize_checklist_step,
    serialize_item,
    task_detail_data_for,
)

router = Router()

TaskStatus = Literal["active", "completed", "archived"]
#: **Hand-written, and it is a mirror of `Item.Recurrence`.** Adding a value to
#: the model does not add it here, so the endpoint refuses a cadence the service
#: accepts -- which is what happened to `fortnightly` on August 27, 2026: four
#: service tests passed while the API would have rejected every request. Ninja
#: needs a static type here, so this cannot simply read the enum; what it can do
#: is fail loudly when the two part company, which the assertion below does.
TaskRecurrence = Literal[
    "none", "daily", "weekly", "fortnightly", "monthly", "quarterly", "annual"
]

# The mirror, checked at import rather than trusted. A `Literal` cannot be built
# from a runtime value in a way Ninja will read, so the duplication is real --
# but a duplication that shouts when it drifts is a different thing from one
# that waits to be noticed by a person typing a cadence into a form.
assert set(get_args(TaskRecurrence)) == set(Item.Recurrence.values), (
    "TaskRecurrence has drifted from Item.Recurrence: "
    f"{set(Item.Recurrence.values) ^ set(get_args(TaskRecurrence))}"
)
#: No "medium": an unmarked task already means ordinary. See lists.models.Priority.
TaskPriority = Literal["none", "high", "low"]
assert set(get_args(TaskPriority)) == set(Priority.values), (
    "TaskPriority has drifted from lists.models.Priority: "
    f"{set(Priority.values) ^ set(get_args(TaskPriority))}"
)
#: Mirrored and asserted for the reason above. Added August 30, 2026 with the
#: typed task writes: `cadence_mode` used to be a bare `str` checked by hand
#: inside the endpoint, so the allowed values appeared nowhere in the schema and
#: the SPA could not be type-checked against them.
TaskCadenceMode = Literal["anchored", "floating"]
assert set(get_args(TaskCadenceMode)) == set(CadenceMode.values), (
    "TaskCadenceMode has drifted from lists.models.CadenceMode: "
    f"{set(CadenceMode.values) ^ set(get_args(TaskCadenceMode))}"
)
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
    priority: TaskPriority
    #: Days before the due date this should be mentioned. Zero is off.
    lead_days: int
    notes: str
    # Nullable since August 14, 2026 -- a task may stand on its own, so this is
    # the boundary admitting a state the database already allowed. Ninja
    # validates responses, so leaving it `int` turned every unfiled task into a
    # 500 that no amount of care in the serializer could avoid.
    area_id: int | None
    project_id: int | None
    url: str


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
    settings_url: str
    daily_digest: bool
    buckets: list[AgendaBucketOut]
    items: list[TaskOut]
    #: **Bills, kept on this screen while they stop being tasks** --
    #: bill-as-a-model-plan.md decision 4. They used to arrive in `items`
    #: because a bill was an `Item`; they arrive here because soon it will not
    #: be, and a screen that quietly dropped them would be the model change
    #: taking a product decision with it.
    bills: list[AgendaBillOut]
    completed_today: list[TaskOut]
    areas: list[AgendaAreaSummaryOut]
    projects: list[AgendaProjectSummaryOut]


#: Mirrored from `agenda.POOL_ROW_KINDS` and asserted below, for the reason
#: `TaskRecurrence` gives: Ninja needs a static type, so the duplication is
#: real, and one that shouts when it drifts is a different thing from one that
#: waits to be noticed.
PoolRowKind = Literal["appointment", "bill", "task"]
assert set(get_args(PoolRowKind)) == set(agenda_reader.POOL_ROW_KINDS), (
    "PoolRowKind has drifted from lists.agenda.POOL_ROW_KINDS: "
    f"{set(agenda_reader.POOL_ROW_KINDS) ^ set(get_args(PoolRowKind))}"
)


class PoolFixedRowOut(Schema):
    """A line with a date on it, whichever kind of record it came from.

    **A tagged row rather than two arrays**, unlike `AgendaOut`, and the
    difference is what the surface is for: the agenda groups by bucket and the
    client lays each group out, while the pool's fixed half is one sequence in
    date order with bills among the tasks -- `superlists-2.0-plan.md` increment
    1. Interleaving on the client would mean the browser deciding what a date
    means, which is the server's by `principles.md`.

    `task`, `bill` and `appointment` are mutually exclusive and `kind` says
    which. **The third arrived at increment 7 and neither of the first two
    changed**, which is what the tagged row was built for.

    `picked_for` is which of the days this page offers -- today and tomorrow --
    the line is currently chosen for, and is always empty on a bill, which
    cannot be picked at all. See `agenda.POOL_PICKABLE_DAYS`.
    """

    kind: PoolRowKind
    due_date: str
    #: Negative when it is already past. Computed here rather than in the
    #: browser for the reason `age_in_days` gives: the account's zone decides
    #: what day it is, and the machine reading the page is not necessarily in
    #: it.
    days_until: int
    task: TaskOut | None
    bill: AgendaBillOut | None
    appointment: AppointmentOut | None
    picked_for: list[str]


#: The two answers rule 8's one question takes. Mirrored and asserted like
#: every other `Literal` on this router.
StillWanted = Literal["keep", "let_go"]


class StillWantedIn(Schema):
    answer: StillWanted


class PoolFloatingRowOut(Schema):
    """A line nothing was promised about, plus how long it has been waiting.

    A wrapper rather than a field on `TaskOut`, on the standing decision in
    `agenda.age_in_days` -- age needs a `today` to measure against and
    `TaskOut` is serialised where there is not one.
    """

    task: TaskOut
    age_in_days: int
    #: Which of today and tomorrow this line is already chosen for, so a Pick
    #: button can say so rather than looking like it did nothing. Released pins
    #: are not picks -- see `agenda._picked_for`.
    picked_for: list[str]
    #: How long this has gone untouched -- written, chosen or kept, whichever
    #: was latest. Not the same number as `age_in_days`, which is how long ago
    #: it was written and never resets; this is the staleness clock.
    unpicked_for_days: int
    #: Whether the pool is asking about it -- rule 8. **The server decides**, so
    #: the threshold stays in one language: a client comparing
    #: `unpicked_for_days` against a number of its own would be D8's mirrored
    #: constant arriving by the back door.
    asks_to_be_kept: bool


class PoolOut(Schema):
    today: str
    #: Every open line, before any search narrowed the two arrays below.
    open_count: int
    fixed: list[PoolFixedRowOut]
    floating: list[PoolFloatingRowOut]


class AreaRefOut(Schema):
    id: int
    title: str
    #: **Kept for the shipped Android build and nothing else.** It reads this
    #: with `getString` and posts to it; the SPA addresses
    #: `/api/v1/areas/{area_id}/tasks` by id. `reorder_url` stood beside it
    #: until August 30, 2026 and went with the view it pointed at, because
    #: nothing outside this repository had ever read that one.
    create_item_url: str


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
    # Null unless this account is leaving. On the nav rather than only on
    # Preferences because the banner it drives has to appear on every route: a
    # scheduled erasure that is only visible on the page you asked to schedule
    # it from is one somebody can forget they started.
    deletion_purge_at: datetime | None




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
        "deletion_purge_at": account_services.purge_at(user),
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
    # Bills leave `items` and arrive in `bills` -- decision 4 kept while the
    # model splits. See `agenda.open_items_for`'s own note.
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
        open_bills=money_reads.open_bills_for(user),
    )


@router.get("/pool", response=PoolOut)
def pool(request, q: str = ""):
    """Every open line, in one list -- `superlists-2.0-plan.md` increment 1.

    **Session only.** The phone has no pool surface, and widening a bearer to
    reach one before there is anything to reach would be the un-switched-on seam
    this project keeps finding. `clarice/tests/test_api_auth_surface.py` is the
    authority on that and fails if this changes by accident.

    `q` is optional and empty means the whole pool; `pool_for` owns what
    matching means.
    """
    return agenda_reader.pool_for(request.user, timezone.localdate(), query=q)


@router.post("/pool/{task_id}/still-wanted", response=PoolOut)
def answer_the_pools_question(request, task_id: int, payload: StillWantedIn):
    """Rule 8's one question, answered -- keep it, or let it go.

    **One endpoint for both answers**, because they are two answers to one
    question and a page that had to know which URL each went to would be
    holding the question's shape twice.

    *Let go* is `clarice.leftovers.let_go`, the same function the evening's
    third move calls: archives the task, retires its facets, leaves the node.
    Rule 8 and rule 7 mean the same thing by the words, so they had better be
    the same code.

    Session only. The phone has no pool, and this archives a task.

    Answers with the whole pool, like every other write on this surface: the
    row goes away, the count moves, and one response keeps them from
    disagreeing for a frame.
    """
    from clarice import leftovers

    task = _owned_task(request, task_id)
    if payload.answer == "keep":
        services.keep(task)
    else:
        leftovers.let_go(request.user, task)
    return agenda_reader.pool_for(request.user, timezone.localdate())


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


class NewAreaIn(Schema):
    title: str = ""
    # Optional, and `None` is not the same as `""`. Omitting it means "an
    # empty area"; sending it empty means somebody submitted a blank task,
    # which is what the retired form's `required` used to catch.
    first_task: str | None = None


@router.post("/areas", response=AreaRefOut)
def create_area(request, payload: NewAreaIn):
    """A new Area, with or without its first task.

    coherence-audit-2026-08-30.md F1. **What this replaces is a page reload.**
    `lists.views.new_list` was a Django form view that both the Agenda's
    "+ New area" card and FirstRun posted to, so the one container the task
    core is built out of was the only thing you could not make without leaving
    the SPA -- while `POST /projects`, the sibling control beside it on the
    same card, had been typed since project-workspace-plan.md.
    `services.create_area` already existed and already took `project=None`;
    the split was entirely in the surface.

    **Two shapes, one endpoint**, because the two callers genuinely differ and
    neither is a special case of the other. The Agenda wants a named container
    and nothing in it. FirstRun wants both at once, on purpose -- naming a
    container is not a thing anybody wants to do, so it asks for the task and
    lets the area take its name.

    **Validation is borrowed, not restated**, exactly as `rename_area` borrows
    it: `ListTitleForm` is the one definition of what an Area may be called,
    and `normalize_task_text` inside `create_list_with_item` is the one
    definition of a task's text. An endpoint re-implementing either is an
    endpoint that can drift from the other entry point to the same rule.

    Ownership comes from the session and the payload has no owner field. This
    endpoint takes no ID, so there is nothing to check against -- see
    test_the_new_area_belongs_to_the_caller_and_not_a_named_owner.
    """
    if payload.first_task is None:
        # Nothing can name it but the title, so the title has to be real.
        # create_area would fall back to "Untitled list", which is right for
        # an area grown inside a project and useless as the only thing on a
        # card somebody just filled in.
        form = ListTitleForm(data={"title": payload.title})
        if not form.is_valid():
            raise HttpError(400, form.errors["title"][0])
        area = services.create_area(request.user, form.cleaned_data["title"])
    else:
        try:
            area = services.create_list_with_item(
                request.user, payload.title, payload.first_task
            )
        except services.TaskConflict as error:
            raise HttpError(409, str(error))
    return area_ref_for(area)


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


@router.get("/tasks/{task_id}", response=TaskDetailOut)
def task_detail(request, task_id: int):
    """Any task this person owns, in any state.

    ~~Matches edit_item's queryset exactly: archived tasks are managed from
    the Archive route (restore/delete), not edited here.~~ **Widened August 30,
    2026** — coherence-audit-2026-08-30.md F3. Excluding archived tasks meant
    the one surface that can show a task's notes, checklist and schedule
    refused to show an archived one at all: the Archive could list it and
    delete it, and nothing in the application could read it.

    **This does not let anybody edit one.** Every write service refuses an
    archived task with *"Restore this task before editing it"*, and
    `delete_archived_item` refuses anything that is not archived. The two-step
    is the protection and it is untouched; what changed is that both steps are
    now reachable from the task itself.
    """
    item = get_object_or_404(
        Item.objects.select_related("list", "commitment").prefetch_related("tags"),
        id=task_id,
        owner=request.user,
    )
    return task_detail_data_for(item)


class DeletedOut(Schema):
    """What a delete answers with.

    Declared rather than left as a bare dict: an endpoint with no `response=`
    generates as `undefined` in the client contract, so the one field it
    returns was invisible to the type checker -- which is the whole point of
    moving these here.
    """

    deleted: int


# What a connected phone may change on a task it can already reach.
#
# The narrow list is unchanged from the view this replaces; what changed is
# where the narrowness lives. `DELETE` and reorder express it in their auth
# lists by simply not accepting a token, so Ninja answers 401 before any
# handler runs. This set cannot be expressed that way -- it is about the body,
# not the route -- so it stays a check.
_TOKEN_WRITABLE_TASK_FIELDS = {"status", "due_date"}

_TASK_WRITE = [TokenAuth(SCOPE_AGENDA_WRITE), SessionAuthIfLoggedIn()]


class NewTaskIn(Schema):
    text: str
    due_date: str | None = None
    tags: list[str] | None = None
    recurrence: TaskRecurrence | None = None


class TaskPatchIn(Schema):
    """Exactly one of these per request, which is the discipline the view this
    replaces ran on and is kept deliberately.

    Two fields in one body is ambiguous about ordering and about which failure
    rolls back which change; zero is a request that means nothing. Every field
    is optional *and* nullable here because several of them mean something when
    null -- clearing a due date, unfiling a task, unmarking a bill -- so
    "absent" and "sent as null" have to stay distinguishable, which is what
    `__fields_set__` below reads.
    """

    text: str | None = None
    status: TaskStatus | None = None
    due_date: str | None = None
    tags: list[str] | None = None
    recurrence: TaskRecurrence | None = None
    cadence_mode: TaskCadenceMode | None = None
    notes: str | None = None
    #: **`area_id`, not `list`** -- the legacy endpoint's wire name for this was
    #: the ORM's column, which is half of coherence-audit-2026-08-30.md F5. A
    #: new endpoint with no existing clients is the free moment to fix it, and
    #: it now matches `TaskOut.area_id`, which has said `area_id` all along.
    #:
    #: It is also not optional here: a field literally named `list` shadows the
    #: builtin inside this class body, so pydantic cannot evaluate
    #: `list[str] | None` on `tags` two lines up. The old view had the same key
    #: and never had the problem, because it read a dict.
    area_id: int | None = None
    priority: TaskPriority | None = None
    lead_days: int | None = None


class TaskUpdateOut(Schema):
    """A task, and the successor that completing it may have produced.

    **A named result rather than the `{"data": ...}` envelope it replaces.**
    Completing a recurring task really does create a second task in the same
    request, and the Agenda shows it without refetching -- so returning a bare
    `TaskOut` would be a silent regression no type could catch. Everything else
    on this router returns its resource directly.
    """

    task: TaskOut
    #: Null except when a completion advanced a recurring commitment.
    spawned: TaskOut | None = None
    #: The steps that same completion cloned onto the successor. Always a list
    #: so a caller never branches on the field existing; empty when nothing
    #: recurred.
    spawned_checklist_steps: list[ChecklistStepOut] = []


def _owned_task(request, task_id):
    return get_object_or_404(
        Item.objects.select_related("list"), id=task_id, owner=request.user
    )


def _fresh(item):
    """Re-read through the join the serializer needs.

    A service returns the instance it wrote, which may not carry `list` or the
    tags; every one of these endpoints serialises, so the read is unconditional
    rather than remembered per branch.
    """
    return Item.objects.select_related("list").prefetch_related("tags").get(pk=item.pk)


def _task_due_date(value):
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise HttpError(400, "Use a valid date (YYYY-MM-DD).")


@router.post("/areas/{area_id}/tasks", response={201: TaskOut}, auth=_TASK_WRITE)
def create_task(request, area_id: int, payload: NewTaskIn):
    """A new task in one of your own areas.

    Scoped in the lookup rather than checked afterwards, like every other
    id-taking surface here: somebody else's area is *not found* rather than
    *forbidden*, because answering differently confirms the id exists.
    """
    our_list = List.objects.filter(id=area_id, owner=request.user).first()
    if our_list is None:
        raise HttpError(404, "Area not found.")
    try:
        item = services.create_item(
            our_list,
            payload.text,
            due_date=_task_due_date(payload.due_date),
            tags=payload.tags,
            recurrence=payload.recurrence,
        )
    except services.TaskConflict as error:
        raise HttpError(400, str(error))
    return 201, serialize_item(_fresh(item))


@router.patch("/tasks/{task_id}", response=TaskUpdateOut, auth=_TASK_WRITE)
def update_task(request, task_id: int, payload: TaskPatchIn):
    """Change exactly one thing about a task.

    **`__fields_set__` rather than a truthiness check**, because null is a real
    value for several of these: `due_date: null` clears a date and `list: null`
    unfiles a task. Treating absent and null alike would make two deliberate
    operations unreachable.

    **`bill` is gone from this endpoint.** A task could be marked as one until
    August 31, 2026, which is the route `money-module-plan.md` was written to
    replace and `bill-as-a-model-plan.md` finished off: a bill is not a task,
    so there is nothing here to mark. Bills are made at `POST /money/bills`.
    """
    item = _owned_task(request, task_id)
    changed = payload.__fields_set__ & set(TaskPatchIn.model_fields)
    if len(changed) != 1:
        raise HttpError(
            400,
            "Change exactly one of text, status, due_date, tags, recurrence, "
            "cadence_mode, notes, area_id, priority or lead_days per "
            "request.",
        )
    if (
        getattr(request, "token_authenticated", False)
        and not changed <= _TOKEN_WRITABLE_TASK_FIELDS
    ):
        raise HttpError(403, "Not available to a connected phone yet.")

    field = next(iter(changed))
    spawned = None
    try:
        if field == "text":
            item = services.edit_item(item, payload.text)
        elif field == "due_date":
            item = services.set_due_date(item, _task_due_date(payload.due_date))
        elif field == "tags":
            item = services.set_item_tags(item, payload.tags or [])
        elif field == "recurrence":
            item = services.set_recurrence(item, payload.recurrence)
        elif field == "cadence_mode":
            # No hand-rolled enum check: `TaskCadenceMode` is a Literal, so an
            # unknown value never reaches here -- pydantic answers 422 and the
            # allowed values are in the published schema. The view this
            # replaces checked by hand and returned 400, which meant the
            # generated client could not know what to send.
            #
            # The cadence itself is unchanged, only how it advances, and it is
            # routed through set_recurrence so the archived-task guard and the
            # write-through stay in one place.
            item = services.set_recurrence(
                item, item.recurrence, cadence_mode=payload.cadence_mode
            )
        elif field == "notes":
            item = services.set_item_notes(item, payload.notes or "")
        elif field == "area_id":
            destination = None
            if payload.area_id is not None:
                destination = List.objects.filter(
                    pk=payload.area_id, owner=request.user
                ).first()
                if destination is None:
                    raise HttpError(404, "Area not found.")
            item = services.move_item(item, destination)
        elif field == "priority":
            # A Literal too, for the reason cadence_mode gives above.
            item = services.set_priority(item, payload.priority)
        elif field == "lead_days":
            if payload.lead_days < 0:
                raise HttpError(400, "Send a whole number of days, 0 or more.")
            item = services.set_lead_days(item, payload.lead_days)
        else:
            item, spawned = _set_status(item, payload.status)
    except services.TaskConflict as error:
        raise HttpError(409, str(error))
    except services.InvalidTaskTransition as error:
        raise HttpError(400, str(error))

    result = {"task": serialize_item(_fresh(item)), "spawned_checklist_steps": []}
    if spawned is not None:
        spawned = _fresh(spawned)
        result["spawned"] = serialize_item(spawned)
        result["spawned_checklist_steps"] = [
            serialize_checklist_step(step)
            for step in spawned.checklist_steps.order_by("position", "id")
        ]
    return result


def _set_status(item, requested):
    """The one branch that can return two tasks."""
    if requested == Item.Status.ACTIVE:
        return services.reopen_item(item), None
    if requested == Item.Status.ARCHIVED:
        return services.archive_item(item), None
    if requested == Item.Status.COMPLETED:
        if item.status == Item.Status.ARCHIVED:
            return services.restore_item(item), None
        item = services.complete_item(item)
        return item, getattr(item, "_spawned", None)
    raise HttpError(400, "Choose a valid task status.")


@router.delete("/tasks/{task_id}", response=DeletedOut, auth=SessionAuthIfLoggedIn())
def delete_task(request, task_id: int):
    """Session only, and deliberately not in `_TASK_WRITE`.

    The view this replaces authenticated a bearer token and *then* answered
    403. Leaving `TokenAuth` off the operation says the same thing one step
    earlier and in a place `test_api_auth_surface.py` can read.

    **`SessionAuthIfLoggedIn()` explicitly rather than the API-wide default**,
    which is plain `SessionAuth` and runs its CSRF check *before* looking for a
    session -- so an unauthenticated caller gets `403 CSRF check Failed`
    instead of a 401, which is both the wrong status and a misleading reason.
    Money's endpoints already name it for this reason; the older ones on this
    router inherit the default and still answer 403.
    """
    item = _owned_task(request, task_id)
    try:
        services.delete_archived_item(item)
    except services.InvalidTaskTransition as error:
        raise HttpError(400, str(error))
    return {"deleted": task_id}


class ReorderIn(Schema):
    ordered_ids: list[int]


@router.post(
    "/areas/{area_id}/tasks/reorder",
    response=list[TaskOut],
    auth=SessionAuthIfLoggedIn(),
)
def reorder_tasks(request, area_id: int, payload: ReorderIn):
    """Session only, and explicitly session-authed, for the two reasons
    `delete_task` gives."""
    our_list = _owned_area(request, area_id)
    try:
        services.reorder_items(our_list, payload.ordered_ids)
    except services.TaskConflict as error:
        raise HttpError(400, str(error))
    items = (
        our_list.item_set.exclude(status=Item.Status.ARCHIVED)
        .select_related("list")
        .prefetch_related("tags")
        .order_by("position", "id")
    )
    return [serialize_item(each) for each in items]


class NewChecklistStepIn(Schema):
    text: str
    #: Null means "the service decides", which is not the same as `false`.
    carries_forward: bool | None = None


class ChecklistStepPatchIn(Schema):
    """One field per request, as the task endpoint above does and for the same
    reasons."""

    text: str | None = None
    is_done: bool | None = None
    carries_forward: bool | None = None


def _owned_step(request, step_id):
    return get_object_or_404(
        ChecklistStep.objects.select_related("task"),
        id=step_id,
        task__owner=request.user,
    )


@router.post(
    "/tasks/{task_id}/checklist-steps",
    response={201: ChecklistStepOut},
    auth=SessionAuthIfLoggedIn(),
)
def create_checklist_step(request, task_id: int, payload: NewChecklistStepIn):
    """Session only. A checklist is a desk-sized act and the phone has no
    surface for one, so this is not in `_TASK_WRITE`."""
    task = _owned_task(request, task_id)
    try:
        step = services.add_checklist_step(
            task, payload.text, carries_forward=payload.carries_forward
        )
    except services.TaskConflict as error:
        raise HttpError(400, str(error))
    except services.InvalidTaskTransition as error:
        raise HttpError(400, str(error))
    return 201, serialize_checklist_step(step)


@router.post(
    "/tasks/{task_id}/checklist-steps/reorder",
    response=list[ChecklistStepOut],
    auth=SessionAuthIfLoggedIn(),
)
def reorder_checklist_steps(request, task_id: int, payload: ReorderIn):
    task = _owned_task(request, task_id)
    try:
        steps = services.reorder_checklist_steps(task, payload.ordered_ids)
    except services.TaskConflict as error:
        raise HttpError(409, str(error))
    return [serialize_checklist_step(step) for step in steps]


@router.patch(
    "/checklist-steps/{step_id}",
    response=ChecklistStepOut,
    auth=SessionAuthIfLoggedIn(),
)
def update_checklist_step(request, step_id: int, payload: ChecklistStepPatchIn):
    step = _owned_step(request, step_id)
    changed = payload.__fields_set__ & set(ChecklistStepPatchIn.model_fields)
    if len(changed) != 1:
        raise HttpError(
            400, "Change exactly one of text, is_done, or carries_forward per request."
        )
    field = next(iter(changed))
    try:
        if field == "text":
            step = services.edit_checklist_step_text(step, payload.text)
        elif field == "is_done":
            step = services.set_checklist_step_done(step, payload.is_done)
        else:
            step = services.set_checklist_step_carries_forward(
                step, payload.carries_forward
            )
    except services.TaskConflict as error:
        raise HttpError(409, str(error))
    except services.InvalidTaskTransition as error:
        raise HttpError(400, str(error))
    return serialize_checklist_step(step)


@router.delete(
    "/checklist-steps/{step_id}", response=DeletedOut, auth=SessionAuthIfLoggedIn()
)
def delete_checklist_step(request, step_id: int):
    step = _owned_step(request, step_id)
    try:
        services.delete_checklist_step(step)
    except services.InvalidTaskTransition as error:
        raise HttpError(400, str(error))
    return {"deleted": step_id}


@router.post(
    "/checklist-steps/{step_id}/promote",
    response={201: TaskOut},
    auth=SessionAuthIfLoggedIn(),
)
def promote_checklist_step(request, step_id: int):
    """Turns a step into a task of its own. The step no longer exists after."""
    step = _owned_step(request, step_id)
    try:
        task = services.promote_checklist_step(step)
    except services.TaskConflict as error:
        raise HttpError(409, str(error))
    except services.InvalidTaskTransition as error:
        raise HttpError(400, str(error))
    return 201, serialize_item(_fresh(task))


class ProjectOut(Schema):
    id: int
    title: str
    # Always a string, never null -- the model is blank-not-null and the wire
    # keeps that, so a client has one representation of "nothing written"
    # rather than two to coerce.
    purpose: str
    # Same blank-not-null contract as `purpose` above, and for the same reason.
    desired_outcome: str
    # What going wrong looks like -- S10, and D4's answer that this is not
    # `desired_outcome`. Same contract again.
    abandon_if: str
    notes: str
    due_date: str | None
    is_completed: bool
    completed_at: str | None
    # **Only the timestamp, where completion sends a flag and a stamp.** That
    # pair exists because `is_completed` predates `completed_at` and a check
    # constraint keeps them honest; there is nothing to keep honest here, and
    # `paused_at !== null` is a client-side expression rather than a second
    # field free to disagree with the first.
    paused_at: str | None
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
    # `str | None = None` rather than `str = ""`, which is the shape the field
    # actually wants and not what it looks like. A pydantic default reaches the
    # contract as `"default": ""`, and openapi-typescript 7 emits any property
    # carrying a default as *required* -- it always has a value, so the
    # generator says so -- which made `purpose` mandatory at every call site
    # that creates a project and broke the build. `due_date` above already has
    # this shape, which is why it did not.
    purpose: str | None = None
    due_date: str | None = None


class ProjectUpdateIn(Schema):
    """Every field optional; absent means "leave it alone".

    `due_date` has to distinguish absent from explicitly null, because
    clearing a due date and not mentioning it are different requests and
    `str | None = None` cannot tell them apart on its own. The handler reads
    `exclude_unset` rather than inventing a sentinel default.

    **`purpose` needs none of that**, and the asymmetry is worth naming
    because it looks like an oversight. Its cleared state is `""`, not null,
    so `None` is free to mean exactly one thing -- the client did not mention
    the field. That is what blank-not-null buys at the boundary.
    """

    title: str | None = None
    purpose: str | None = None
    # Same shape as `purpose`, same reason: "" is its cleared state, so None
    # means only "not mentioned".
    desired_outcome: str | None = None
    abandon_if: str | None = None
    notes: str | None = None
    due_date: str | None = None
    is_completed: bool | None = None
    # A boolean like `is_completed` rather than a verb route, because both
    # answer "which state is this project in" and two spellings of one idea is
    # the near-identical-controls problem C2 found in the task UI.
    is_paused: bool | None = None
    #: **S12's fourth clause.** Written after the work stops rather than
    #: with the completion, because the lesson arrives while reading what the
    #: retrospective shows.
    learned: str | None = None


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
        "purpose": project.purpose,
        "desired_outcome": project.desired_outcome,
        "abandon_if": project.abandon_if,
        "learned": project.learned,
        "notes": project.notes,
        "paused_at": (
            project.paused_at.isoformat() if project.paused_at else None
        ),
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


class BriefItemOut(Schema):
    """One retrieved note, with the evidence that selected it.

    `reason` is not decoration. Without it the interface can only say
    "related", which is the unfalsifiable label this whole mechanic exists to
    avoid -- `precision.md`'s point is that a person can check "these share
    three words appearing in none of your other notes" and cannot check a
    score.
    """

    id: str
    text: str
    captured_at: str
    reason: str
    distinctive_terms: list[str]


class BriefCommitmentOut(Schema):
    id: int
    text: str
    due_date: str | None


class BriefSourceOut(Schema):
    """Something read that this project's material came out of — **S16**.

    `reason` is a fact rather than a score, like `BriefItemOut`'s and for the
    same argument: the person can check *a note here came out of it* and cannot
    check a number.
    """

    id: str
    title: str
    author: str
    url: str
    reason: str
    note_count: int


class BriefDecisionOut(Schema):
    """A choice made while looking at this project's material — **S16**.

    `superseded` rather than omitting the ones that were replaced: *what he
    learned last time* includes the answer he later changed, and hiding it would
    remove the part that makes keeping the record worth anything.
    """

    id: str
    question: str
    chose: str
    considered: str
    decided_at: str
    superseded: bool
    reason: str


class BriefLessonOut(Schema):
    """What an earlier finished project taught — **S12's *kept for next time***.

    Named with its project, because a lesson with no source is an aphorism.
    """

    project_id: int
    project_title: str
    learned: str


class ProjectBriefOut(Schema):
    material: list[BriefItemOut]
    questions: list[BriefItemOut]
    commitments: list[BriefCommitmentOut]
    #: **S16's other two nouns.** The story's done-means is *notes, decisions
    #: and sources*, and this payload carried one of three until August 22,
    #: 2026 — because `Source` and `Decision` did not exist until that day.
    sources: list[BriefSourceOut]
    decisions: list[BriefDecisionOut]
    #: Why the two sections above are empty, when they are and it is not
    #: because nothing bears on the project. D5's discipline, one axis over.
    provenance_says: str
    #: What earlier finished projects taught. Delivered on the **brief**
    #: rather than the retrospective, because *next time* is a different
    #: project from the one that learned it — and the brief is what somebody
    #: opens while a project is still running.
    learned_before: list[BriefLessonOut]
    #: **S10's second clause**, which this payload dropped from the day the
    #: field was added until August 22, 2026. `ProjectBrief.abandon_if` says *a
    #: field nobody sees at the moment of deciding is a field that may as well
    #: not exist* — and nobody saw it, because it stopped here.
    abandon_if: str


def _brief_source_out(each):
    return {
        "id": str(each.source.public_id),
        "title": each.source.title,
        "author": each.source.author,
        "url": each.source.url,
        "reason": each.reason,
        "note_count": len(each.through),
    }


def _brief_decision_out(each):
    return {
        "id": str(each.decision.public_id),
        "question": each.decision.question,
        "chose": each.decision.chose,
        "considered": each.decision.considered,
        "decided_at": each.decision.decided_at.isoformat(),
        # Whether a later decision replaced this one. `revisited_at` alone would
        # not say: looking again and changing your mind are different acts, and
        # only the second supersedes.
        "superseded": each.decision.superseded_by.exists(),
        "reason": each.reason,
    }


def _brief_item_out(item):
    return {
        "id": str(item.node.public_id),
        "text": item.node.original_content,
        "captured_at": item.node.captured_at.isoformat(),
        "reason": item.reason,
        "distinctive_terms": list(item.distinctive_terms),
    }


class RetroWeekOut(Schema):
    week_start: str
    met: int
    unfinished: int
    set_aside: int


class RetroNoteOut(Schema):
    id: str
    text: str
    captured_at: str


class RetroDecisionOut(Schema):
    id: str
    question: str
    chose: str
    considered: str
    decided_at: str


class ProjectRetrospectiveOut(Schema):
    """What a project came to — **S12**.

    Week by week rather than one pair of numbers: a project that started well
    and stalled and one that ground along evenly have the same totals, and only
    the first is worth knowing about.
    """

    weeks: list[RetroWeekOut]
    met: int
    unfinished: int
    set_aside: int
    notes: list[RetroNoteOut]
    decisions: list[RetroDecisionOut]
    learned: str
    #: One sentence rather than a run of empty rows — see
    #: `projects.Retrospective.quiet_weeks_before_closing`.
    quiet_says: str


@router.get(
    "/projects/{project_id}/retrospective", response=ProjectRetrospectiveOut
)
def project_retrospective(request, project_id: int):
    """What a project came to, assembled rather than remembered — **S12**.

    **Its own route rather than part of the brief**, and the split is the point:
    a brief prompts a project that is *running* and may answer topically; a
    retrospective is a record of one that is over, and every item in it is a row
    somebody wrote. Same argument that gave the brief its own route, one state
    later.

    Reads only. There is nothing to confirm and nothing to stamp — see
    `projects.Retrospective`.
    """
    project = project_reader.project_for(request.user, project_id)
    if project is None:
        raise HttpError(404, "Project not found.")

    looking_back = project_reader.retrospective_for(request.user, project)
    return {
        "weeks": [
            {
                "week_start": week.week_start.isoformat(),
                "met": week.met,
                "unfinished": week.unfinished,
                "set_aside": week.set_aside,
            }
            for week in looking_back.weeks
        ],
        "met": looking_back.met,
        "unfinished": looking_back.unfinished,
        "set_aside": looking_back.set_aside,
        "notes": [
            {
                "id": str(node.public_id),
                "text": node.original_content,
                "captured_at": node.captured_at.isoformat(),
            }
            for node in looking_back.notes
        ],
        "decisions": [
            {
                "id": str(decision.public_id),
                "question": decision.question,
                "chose": decision.chose,
                "considered": decision.considered,
                "decided_at": decision.decided_at.isoformat(),
            }
            for decision in looking_back.decisions
        ],
        "learned": looking_back.learned,
        "quiet_says": looking_back.quiet_says,
    }


@router.get("/projects/{project_id}/brief", response=ProjectBriefOut)
def project_brief(request, project_id: int):
    """What bears on this project, asked for rather than implied.

    **Its own route rather than a fatter `ProjectOut`.** A brief runs a
    full-text retrieval and a project detail is fetched on every render of a
    page that mostly wants a title; paying for the search each time would be
    the wrong default. It also matches what this is -- a briefing somebody
    opens, which is the Attention Policy's condition for showing a queue at
    all.

    Reads only, and records nothing. See `projects.ProjectBrief` for why that
    differs from `/mind/review/`, which records being opened on purpose.
    """
    project = project_reader.project_for(request.user, project_id)
    if project is None:
        raise HttpError(404, "Project not found.")

    brief = project_reader.brief_for(request.user, project)
    return {
        "material": [_brief_item_out(each) for each in brief.material],
        "questions": [_brief_item_out(each) for each in brief.questions],
        "commitments": [
            {
                "id": task.id,
                "text": task.text,
                "due_date": task.due_date.isoformat() if task.due_date else None,
            }
            for task in brief.commitments
        ],
        "sources": [_brief_source_out(each) for each in brief.sources],
        "decisions": [_brief_decision_out(each) for each in brief.decisions],
        "learned_before": [
            {
                "project_id": each.project.id,
                "project_title": each.project.title,
                "learned": each.learned,
            }
            for each in brief.learned_before
        ],
        "provenance_says": brief.provenance_says,
        "abandon_if": brief.abandon_if,
    }


@router.post("/projects", response=ProjectOut)
def create_project(request, payload: ProjectCreateIn):
    try:
        project = services.create_project(
            request.user,
            payload.title,
            due_date=_parse_date(payload.due_date),
            purpose=payload.purpose or "",
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
    # After completion, deliberately. `complete_project` clears the pause, so a
    # request that finished and paused in one call would otherwise depend on
    # the order these branches happen to be written in.
    if payload.is_paused is not None:
        if payload.is_paused:
            services.pause_project(project)
        else:
            services.resume_project(project)

    fields = []
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HttpError(409, services.EMPTY_PROJECT_TITLE_ERROR)
        project.title = title
        fields.append("title")
    if payload.purpose is not None:
        # No exclude_unset dance: "" is the cleared state, so None already
        # means only "not mentioned". See ProjectUpdateIn.
        project.purpose = payload.purpose.strip()
        fields.append("purpose")
    if "due_date" in payload.dict(exclude_unset=True):
        project.due_date = _parse_date(payload.due_date)
        fields.append("due_date")
    if fields:
        project.save(update_fields=fields)

    # Through their services rather than assigned here, which is the entire
    # reason those services were written -- `set_desired_outcome` says so in
    # its own docstring, and the call site was never switched over, so the pair
    # it exists to keep distinguishable had one half in each place for two
    # days. The services strip and store `""` for the cleared state, so `None`
    # still means only *not mentioned*.
    #
    # After the title check, so a 409 on an empty title writes none of them.
    if payload.desired_outcome is not None:
        services.set_desired_outcome(project, payload.desired_outcome)
    if payload.abandon_if is not None:
        services.set_abandonment_condition(project, payload.abandon_if)
    if payload.notes is not None:
        services.set_project_notes(project, payload.notes)
    # **S12**, and it belongs here with the rest. An earlier pass left this one
    # assigned in the handler on the stated grounds that it had no service to
    # route to -- it has had `record_what_was_learned` since August 23, and the
    # comment saying otherwise was written without looking. The same omission
    # as the three above, found the same way.
    if payload.learned is not None:
        services.record_what_was_learned(project, payload.learned)

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
