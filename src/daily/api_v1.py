"""The daily domain's slice of the /api/v1/ contract.

Two shapes of the same read: `/day` for "whatever today is for me", and
`/day/{day}` for a named date. The undated form exists so the client never
has to decide what day it is -- that is a per-user time-zone question, and
`principles.md` puts the answer on the server.
"""
from datetime import date

from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from daily import reads, services
from lists import agenda
from lists.api_v1 import TaskOut, TaskParentOut
from lists.models import Item
from lists.serializers import serialize_item
from routines import reads as routine_reads
from routines.api_v1 import PausedRoutineOut, StandingOut


router = Router()


class DayOut(Schema):
    date: str
    intentions: str
    gratitude: str
    happenings: str
    # Carried on every response so a page for the 3rd can tell whether the
    # 3rd is today, and offer yesterday/tomorrow, without a second request
    # or a client-side guess at the owner's zone.
    today: str
    # The agenda's rows, read live. Not stored on the entry and not cached:
    # the day displays the task, so completing one anywhere is reflected on
    # the next load with nothing to reconcile.
    #
    # TaskOut rather than a daily-shaped copy, because these *are* the same
    # records the agenda serves and a second schema would be free to drift
    # from the first.
    action_items: list["DayActionItemOut"]
    # Whether this day is showing them at all, decided by the server so the
    # client is not left inferring it from an empty list. Empty-because-done
    # and empty-because-not-today are different, and only one of them
    # deserves "nothing due today".
    shows_action_items: bool
    # What was deliberately chosen for this day, in the order it was chosen.
    # Released pins are absent -- they are Crane 3's history, not today's
    # work.
    focus: list["FocusOut"]
    # The Personal Compass, read from the user on every request and stored
    # on no day. Sent with the day rather than fetched separately so the
    # page renders in one round trip -- and because a day is exactly the
    # context it is meant to be read in. Editing it changes every day at
    # once, including ones already written, which is the point of it.
    compass_purpose: str
    compass_question: str
    # Where each routine stands in the period this day falls in, read live
    # like the agenda and owned no more than it is.
    #
    # StandingOut rather than a daily-shaped copy: these are the same
    # answers /api/v1/routines gives, and a second schema would be free to
    # drift from the first.
    #
    # **Present on a past day, where action_items cannot be.** A task holds
    # no record of what it looked like on the 30th, so showing today's open
    # work there would assert something never true. An occurrence *is* a
    # dated record of a period, so reading one back is history rather than
    # inference. Two kinds of record, two honest answers, one page.
    routines: list[StandingOut]
    # Whether this day can be logged into. Back-logging is legitimate --
    # §3 allows logging after the fact -- and is not built: slice 3's
    # acceptance does not need it, and a date-taking log endpoint is a wider
    # surface than it has earned. The server says so rather than leaving the
    # client to infer it from the date.
    routines_are_loggable: bool
    # Put down, and findable so they can be picked back up. Not in
    # `routines` above, because a paused routine has no standing in this or
    # any period -- that is what pausing means.
    paused_routines: list[PausedRoutineOut]


class DayActionItemOut(TaskOut):
    """A task, plus the one thing the day knows about it that the agenda
    does not: how long it has been waiting.

    A subclass rather than a field added to TaskOut, so the agenda's
    contract is untouched by a number only this page renders. Age needs a
    "today" to be measured against, and TaskOut is serialised in places that
    do not have one.
    """

    age_in_days: int


class FocusOut(Schema):
    """A pinned task, as the day needs to render it.

    Not TaskOut: a focus row is a different statement from an agenda row,
    and the fields that differ are the point. `selected_at` says when the
    choice was made, and `task_id` is nullable because a task can be
    permanently deleted while the record of having planned it survives.
    """

    task_id: int | None
    text: str
    status: str | None
    due_date: str | None
    parent: TaskParentOut | None
    selected_at: str


class FocusIn(Schema):
    task_id: int


class DayIn(Schema):
    """Every field optional, and absent is not the same as empty.

    The page may save one section without carrying the other two, so a
    field left out keeps its stored value -- see services.write_entry.
    """

    intentions: str | None = None
    gratitude: str | None = None
    happenings: str | None = None


def _today_for_request():
    """The requesting user's local date.

    `timezone.localdate()` reads the zone the middleware activated for this
    request, which is the owner's own -- see per-user-time-zones-plan.md.
    Read once, here at the boundary, and passed down.
    """
    return timezone.localdate()


def _action_item_out(item, today):
    # The age rule itself lives in lists.agenda, because Crane 3's weekly
    # review reports the same number about the same tasks and a second
    # implementation would drift the first time one was corrected.
    return {
        **serialize_item(item),
        "age_in_days": agenda.age_in_days(item.created_at, today),
    }


def _focus_out(focus):
    task = focus.task
    return {
        "task_id": focus.task_id,
        # The live task while there is one, per charter rule 5 -- a renamed
        # task should read the same here as everywhere else. `task_text` is
        # the fallback for a task that has since been deleted, which is the
        # only case where the snapshot is the better answer because it is
        # the only answer.
        "text": task.text if task else focus.task_text,
        "status": task.status if task else None,
        "due_date": task.due_date.isoformat() if task and task.due_date else None,
        "parent": (
            {"id": task.parent_id, "text": task.parent.text}
            if task and task.parent_id
            else None
        ),
        "selected_at": focus.selected_at.isoformat(),
    }


def _day_out(owner, day):
    entry = reads.entry_for(owner, day)
    today = _today_for_request()
    # Action Items are live task state, and a task carries no history of
    # what it looked like on a past date. Showing today's open work on the
    # page for the 30th would assert something that was never true -- the
    # same mistake daily-operating-system-vision.md refuses when it says
    # habit metrics must not infer the past from a task's current state.
    #
    # So a day that is not today shows what was *written*, which is a real
    # record, and no work at all. A future day is excluded for the same
    # reason in reverse.
    shows_action_items = day == today
    return {
        "date": day.isoformat(),
        # An unwritten day is a blank page, not a missing one: there is
        # nothing to have found, so 404 would be answering the wrong
        # question and would make the client handle a case that is not an
        # error.
        "intentions": entry.intentions if entry else "",
        "gratitude": entry.gratitude if entry else "",
        "happenings": entry.happenings if entry else "",
        "today": today.isoformat(),
        "action_items": (
            [
                _action_item_out(item, today)
                for item in reads.action_items_for(owner, day)
            ]
            if shows_action_items
            else []
        ),
        "shows_action_items": shows_action_items,
        "focus": [_focus_out(focus) for focus in reads.focus_for(owner, day)],
        "compass_purpose": owner.compass_purpose,
        "compass_question": owner.compass_question,
        "routines": [
            {
                "routine_id": standing.routine.id,
                "title": standing.routine.title,
                "cadence": standing.routine.cadence,
                "period_start": standing.period_start,
                "progress": standing.progress,
                "target": standing.target,
                "unit": standing.unit,
                "outcome": standing.outcome,
                "is_met": standing.is_met,
            }
            for standing in routine_reads.standings_for(owner, day)
        ],
        "routines_are_loggable": day == today,
        "paused_routines": [
            {
                "routine_id": routine.id,
                "title": routine.title,
                "cadence": routine.cadence,
                "target": routine.target_quantity,
                "unit": routine.unit,
            }
            for routine in routine_reads.paused_routines_for(owner)
        ],
    }


def _own_task_or_404(owner, task_id):
    """A task this owner actually has.

    Scoped in the lookup rather than fetched and then checked, so there is
    no comparison to forget -- and 404 rather than 403, so the endpoint does
    not confirm that somebody else's task id exists.
    """
    return get_object_or_404(Item, pk=task_id, list__owner=owner)


@router.get("/day", response=DayOut)
def get_today(request):
    return _day_out(request.user, _today_for_request())


@router.get("/day/{day}", response=DayOut)
def get_day(request, day: date):
    return _day_out(request.user, day)


@router.post("/day/{day}/focus", response=DayOut)
def pin_to_day(request, day: date, payload: FocusIn):
    """Choose a task as work for this day.

    Returns the whole day rather than the one pin: the client has to
    re-render the focus list and the action items together anyway, and one
    response keeps them from disagreeing for a frame.
    """
    task = _own_task_or_404(request.user, payload.task_id)
    try:
        services.pin_task(request.user, day, task)
    except services.FocusError as error:
        raise HttpError(403, str(error))
    return _day_out(request.user, day)


@router.delete("/day/{day}/focus/{task_id}", response=DayOut)
def unpin_from_day(request, day: date, task_id: int):
    """Take a task off this day, keeping the record that it was chosen."""
    task = _own_task_or_404(request.user, task_id)
    services.unpin_task(request.user, day, task)
    return _day_out(request.user, day)


@router.patch("/day/{day}", response=DayOut)
def write_day(request, day: date, payload: DayIn):
    """Write into the requesting user's day.

    There is no ownership check to forget: the entry is addressed by
    (request.user, day), so the path names a date and never a record. One
    person cannot reach another's day through this endpoint at all, which
    is a smaller surface than an id would be.
    """
    services.write_entry(
        request.user,
        day,
        **{
            field: value
            for field, value in (
                ("intentions", payload.intentions),
                ("gratitude", payload.gratitude),
                ("happenings", payload.happenings),
            )
            if value is not None
        },
    )
    return _day_out(request.user, day)
