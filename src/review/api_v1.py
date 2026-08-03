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
from review import reads, services
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


class WrittenDayOut(Schema):
    """One day's own words, as they were written.

    All three fields, blank ones included, so the client renders the
    sections it has rather than inferring which exist. The date is here
    because the page links back to the day itself: a review reads writing,
    and changing it belongs on the page that owns it.
    """

    date: date
    intentions: str
    gratitude: str
    happenings: str


class IdeaOut(Schema):
    idea_id: int
    text: str
    status: str
    added_on: date


class WaitingCaptureOut(Schema):
    """A thought still in the Inbox, and how long it has been there.

    Same age rule as a task's, from the same place -- how long something
    has been waiting means one thing in this product.
    """

    capture_id: int
    text: str
    age_in_days: int


class HabitPeriodOut(Schema):
    """One period of one routine, described and not judged.

    `outcome` is the occurrence's own word -- open, completed, skipped --
    and there is deliberately no "missed" among them. crane-plan.md §3:
    Crane 3 is where an elapsed-open period gets described, not where it
    gets silently relabelled.
    """

    period_start: date
    outcome: str
    progress: int
    target: int


class HabitOut(Schema):
    """A routine's week.

    `expected` is the periods the week actually asked of it -- floored at
    the routine's own beginning, capped at today, and with skips removed --
    so `met` over `expected` is the vision document's "4 of 5 planned
    lesson targets met" rather than a fraction of an arbitrary seven.
    `skipped` rides alongside so the number cannot hide them.
    """

    routine_id: int
    title: str
    cadence: str
    unit: str
    met: int
    expected: int
    skipped: int
    # Periods closed at "that was enough". Out of `expected` like a skip,
    # because both are decisions rather than periods that merely ran out --
    # and reported separately from skips, because "I did some and stopped"
    # and "I chose not to" are different facts. crane-plan.md §8.
    enough: int
    # When the pause that was still running at the week's end began, and how
    # many of the week's days it was down for. Both null/zero wherever
    # RoutinePause has nothing to say -- a pause that began and ended before
    # that record existed leaves no row, and §8's rule is that the review
    # stays silent rather than inferring one from an empty stretch.
    paused_since: date | None
    paused_days: int
    periods: list[HabitPeriodOut]


class WeekSummaryOut(Schema):
    """One row of the trend, or a row saying there is nothing to show.

    Every figure is nullable, and that is the contract rather than an
    oversight: a week from before the owner had anything recorded reads as
    no data, not as nought. `daily-operating-system-vision.md` asks for
    trustworthy denominators, and "0 of 0" for a week somebody was not here
    for is the least trustworthy number a page could print.
    """

    week_start: date
    is_shown_week: bool
    planned_met: int | None
    planned_total: int | None
    habits_met: int | None
    habits_expected: int | None


class ReviewOut(Schema):
    """The written half of a week, and what was concluded from it.

    Always present, even for a week nobody has reviewed -- an unwritten
    review is a blank page rather than a missing one, so 404 would answer
    the wrong question and make the client handle a case that is not an
    error. The same call the day's endpoint makes for an unwritten day.
    """

    reflections: str
    plan: str
    completed_at: str | None
    # What the finish rate said when the week was reviewed. Null while it
    # is still open, because an unfinished review has concluded nothing --
    # and null again after a reopen, for the same reason.
    recorded_total: int | None
    recorded_met: int | None


class ReviewIn(Schema):
    """Both fields optional, and absent is not the same as empty.

    The page may save reflections without carrying the plan, so a field
    left out keeps its stored value -- see services.write_review.
    """

    reflections: str | None = None
    plan: str | None = None


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
    written: list[WrittenDayOut]
    ideas: list[IdeaOut]
    # Not week-scoped, and named so that is visible in the contract rather
    # than only in the read: an Inbox is a backlog, not seven days.
    unresolved_captures: list[WaitingCaptureOut]
    habits: list[HabitOut]
    # The shown week and the four before it. Not an analytics surface: the
    # six questions architecture-trajectory.md §4 names are release F's, and
    # this is the same two figures the page already shows, four times more.
    recent_weeks: list[WeekSummaryOut]
    review: ReviewOut


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
    }


def _week_out(owner, day):
    week_start, week_end = reads.week_bounds(day)
    today = timezone.localdate()
    planned = reads.planned_in_week(owner, week_start, week_end)
    review = reads.review_for(owner, week_start)
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
        "written": [
            {
                "date": entry.date,
                "intentions": entry.intentions,
                "gratitude": entry.gratitude,
                "happenings": entry.happenings,
            }
            for entry in reads.written_in_week(owner, week_start, week_end)
        ],
        "ideas": [
            {
                "idea_id": idea.id,
                "text": idea.text,
                "status": idea.status,
                "added_on": timezone.localtime(idea.created_at).date(),
            }
            for idea in reads.ideas_added_in_week(owner, week_start, week_end)
        ],
        "unresolved_captures": [
            {
                "capture_id": capture.id,
                "text": capture.text,
                "age_in_days": agenda.age_in_days(capture.created_at, today),
            }
            for capture in reads.captures_still_waiting(owner)
        ],
        "habits": [
            {
                "routine_id": habit.routine.id,
                "title": habit.routine.title,
                "cadence": habit.routine.cadence,
                "unit": habit.routine.unit,
                "met": habit.met,
                "expected": habit.expected,
                "skipped": habit.skipped,
                "enough": habit.enough,
                "paused_since": habit.paused_since,
                "paused_days": habit.paused_days,
                "periods": [
                    {
                        "period_start": period.period_start,
                        "outcome": period.outcome,
                        "progress": period.progress,
                        "target": period.target,
                    }
                    for period in habit.periods
                ],
            }
            for habit in reads.habits_in_week(owner, week_start, week_end, today)
        ],
        "recent_weeks": [
            {
                "week_start": summary.week_start,
                "is_shown_week": summary.is_shown_week,
                "planned_met": summary.planned_met,
                "planned_total": summary.planned_total,
                "habits_met": summary.habits_met,
                "habits_expected": summary.habits_expected,
            }
            for summary in reads.recent_weeks(owner, week_start, today)
        ],
        "review": {
            "reflections": review.reflections if review else "",
            "plan": review.plan if review else "",
            "completed_at": (
                review.completed_at.isoformat()
                if review and review.completed_at
                else None
            ),
            "recorded_total": review.recorded_planned_total if review else None,
            "recorded_met": review.recorded_planned_met if review else None,
        },
    }


@router.get("/review", response=WeekOut)
def get_current_week(request):
    return _week_out(request.user, timezone.localdate())


@router.get("/review/{day}", response=WeekOut)
def get_week(request, day: date):
    return _week_out(request.user, day)


@router.patch("/review/{day}", response=WeekOut)
def write_review(request, day: date, payload: ReviewIn):
    """Write into the requesting user's review of that week.

    There is no ownership check to forget: the record is addressed by
    (request.user, the week containing day), so the path names a date and
    never a record. One person cannot reach another's review through this
    endpoint at all, which is a smaller surface than an id would be -- the
    same shape as the day's own write endpoint.
    """
    services.write_review(
        request.user,
        day,
        **{
            field: value
            for field, value in (
                ("reflections", payload.reflections),
                ("plan", payload.plan),
            )
            if value is not None
        },
    )
    return _week_out(request.user, day)


@router.post("/review/{day}/complete", response=WeekOut)
def complete_review(request, day: date):
    """Say the week has been reviewed, recording the figure it reported.

    Its own route rather than a field on the PATCH above, because it is a
    different statement: one saves what somebody wrote, the other records
    that they finished reading the week. Collapsing them would be the
    near-identical-controls problem C2 found in the task UI.
    """
    services.complete_review(request.user, day)
    return _week_out(request.user, day)


@router.post("/review/{day}/reopen", response=WeekOut)
def reopen_review(request, day: date):
    """Un-finish it, dropping the recorded figure with it."""
    services.reopen_review(request.user, day)
    return _week_out(request.user, day)
