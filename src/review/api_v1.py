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
    }


@router.get("/review", response=WeekOut)
def get_current_week(request):
    return _week_out(request.user, timezone.localdate())


@router.get("/review/{day}", response=WeekOut)
def get_week(request, day: date):
    return _week_out(request.user, day)
