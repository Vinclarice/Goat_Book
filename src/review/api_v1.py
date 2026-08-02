"""The review slice of the /api/v1/ contract.

Two shapes of one read, following the day's precedent: `/review` for "the
week I am in", and `/review/{day}` for a named one. The undated form exists
so the client never has to work out what week it is -- that is a per-user
time-zone question and `principles.md` puts the answer on the server.

**Any date addresses its week.** The path takes a date rather than a week
number and snaps it to the Monday `routines.periods.period_start_for`
returns, so there is no way to name a week the routines domain would
disagree about. `crane-plan.md` §6 is explicit that two definitions of "this
week" between a routine and the report on it would be wrong invisibly.

**The default is the current week, not the preceding one.** The vision
document describes a review as gathering "from the preceding week", which is
true of when a review gets written and is a poor rule for what an undated
URL means -- a server that silently showed last week on a Wednesday would be
answering a question nobody asked. The week before is one step away instead,
which is the same click on the Monday morning a review actually happens.
"""
from datetime import date, timedelta

from django.utils import timezone
from ninja import Router, Schema

from lists import agenda
from lists.api_v1 import TaskParentOut
from review import reads
from review.weeks import DAYS_IN_WEEK, week_start_for


router = Router()


class CompletedTaskOut(Schema):
    """A finished task, as a week needs to read it.

    Not `TaskOut`: a week reports what happened rather than offering
    something to act on, and the field that matters here -- which day it was
    finished on -- is one the agenda's contract has no reason to carry.
    """

    task_id: int
    text: str
    # The owner's local date, computed here rather than in the browser,
    # whose zone is not the account's.
    completed_on: date
    list_id: int
    parent: TaskParentOut | None


class PlannedTaskOut(Schema):
    """A commitment somebody chose for a day in this week.

    Nullable `task_id`, because a task can be permanently deleted from the
    archive while the record of having planned it survives -- that
    asymmetry is the whole design of DailyFocus and the reason a
    denominator can be trusted at all.
    """

    task_id: int | None
    text: str
    # Which day it was chosen for. A week is seven decisions, not one.
    day: date
    due_date: date | None
    parent: TaskParentOut | None
    # The same number the Daily Page shows, from the same rule in
    # lists.agenda -- reported rather than judged, per Crane 2 slice 5.
    age_in_days: int
    completed_on: date | None


class PlannedOut(Schema):
    """The finish rate, and the three groups behind it.

    `met` over `total` is the figure daily-operating-system-vision.md
    demands be honest: completed planned commitments over planned
    commitments. `set_aside` is deliberately outside `total` and is sent
    anyway, because a week where four things were reconsidered is a
    different week from one where nothing was.
    """

    total: int
    met: int
    met_tasks: list[PlannedTaskOut]
    unfinished: list[PlannedTaskOut]
    set_aside: list[PlannedTaskOut]


class WeekOut(Schema):
    week_start: date
    week_end: date
    # Carried on every response so the page can say whether the week it is
    # showing is the one in progress without a second request or a
    # client-side guess at the owner's zone.
    today: date
    is_current_week: bool
    # Both neighbours, always. A review written on a Monday is about the
    # week before, and a surface that could only be reached by editing the
    # URL is the gap this slice sequence has already shipped twice.
    previous_week: date
    next_week: date
    completed: list[CompletedTaskOut]
    planned: PlannedOut


def _planned_task_out(focus, today):
    task = focus.task
    return {
        "task_id": focus.task_id,
        # The live task while there is one, per charter rule 5 -- a renamed
        # task reads the same here as everywhere else. `task_text` is the
        # answer only when it is the only answer.
        "text": task.text if task else focus.task_text,
        "day": focus.entry.date,
        "due_date": task.due_date if task else None,
        "parent": (
            {"id": task.parent_id, "text": task.parent.text}
            if task and task.parent_id
            else None
        ),
        # Falls back to when it was chosen, for a task that no longer
        # exists: something was planned that day either way, and zero would
        # claim it was new.
        "age_in_days": agenda.age_in_days(
            task.created_at if task else focus.selected_at, today
        ),
        "completed_on": (
            timezone.localtime(task.completed_at).date()
            if task and task.completed_at
            else None
        ),
    }


def _completed_out(item):
    return {
        "task_id": item.id,
        "text": item.text,
        "completed_on": timezone.localtime(item.completed_at).date(),
        "list_id": item.list_id,
        "parent": (
            {"id": item.parent_id, "text": item.parent.text}
            if item.parent_id
            else None
        ),
    }


def _week_out(owner, day):
    week_start, week_end = reads.week_bounds(day)
    today = timezone.localdate()
    planned = reads.planned_in_week(owner, week_start, week_end)
    return {
        "week_start": week_start,
        "week_end": week_end,
        "today": today,
        "is_current_week": week_start == week_start_for(today),
        "previous_week": week_start - timedelta(days=DAYS_IN_WEEK),
        "next_week": week_start + timedelta(days=DAYS_IN_WEEK),
        "completed": [
            _completed_out(item)
            for item in reads.completed_in_week(owner, week_start, week_end)
        ],
        "planned": {
            "total": planned.total,
            "met": len(planned.met),
            "met_tasks": [_planned_task_out(each, today) for each in planned.met],
            "unfinished": [
                _planned_task_out(each, today) for each in planned.unfinished
            ],
            "set_aside": [
                _planned_task_out(each, today) for each in planned.set_aside
            ],
        },
    }


@router.get("/review", response=WeekOut)
def get_current_week(request):
    return _week_out(request.user, timezone.localdate())


@router.get("/review/{day}", response=WeekOut)
def get_week(request, day: date):
    return _week_out(request.user, day)
