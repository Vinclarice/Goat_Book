"""The daily domain's slice of the /api/v1/ contract.

Two shapes of the same read: `/day` for "whatever today is for me", and
`/day/{day}` for a named date. The undated form exists so the client never
has to decide what day it is -- that is a per-user time-zone question, and
`principles.md` puts the answer on the server.
"""
from datetime import date, timedelta

from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from accounts.auth import SessionAuthIfLoggedIn, TokenAuth
from accounts.models import SCOPE_DAY_READ, SCOPE_DAY_WRITE
from daily import reads, services
from lists import agenda
from lists import projects as project_reader
from lists.api_v1 import (
    AgendaProjectSummaryOut,
    AreaColorKey,
    TaskOut,
)
from money import reads as money_reads
from money.api_v1 import AgendaBillOut
from lists.models import Item
from lists.serializers import project_ref_for, serialize_item
from mind import services as mind_services
from review import reads as review_reads
from mind.models import Facet, FacetKind
from routines import reads as routine_reads
from routines.api_v1 import PausedRoutineOut, StandingOut


router = Router()


class DayAreaSummaryOut(Schema):
    """An action item's area, joined the way the Agenda's `areas` already
    is -- minus the fields only a create-task form needs, which the Daily
    Page doesn't have.
    """

    id: int
    title: str
    url: str
    color_key: AreaColorKey


class SuggestionOut(Schema):
    """One commitment read out of this day's writing, as a card to answer.

    `planning-assistant-plan.md` increment 2. Five fields, and the fourth had
    no implementation anywhere in this application until now.

    `text` is the **cited sentence**, not the whole day -- the evidence, so the
    claim can be checked against the passage that caused it rather than taken
    on trust. `reason` says why it was read as a commitment.

    **`effect` says what confirming will do**, and it is computed here rather
    than phrased by the client. "Creates a task" and "creates a task due 4
    June" are different things to agree to; slice C decided a promise with no
    date makes a task with none, and somebody approving one should be told that
    rather than discover it in their agenda. One wording, server-side, so two
    clients cannot describe the same button differently.
    """

    id: int
    text: str
    reason: str
    effect: str


class DayOut(Schema):
    date: str
    intentions: str
    gratitude: str
    happenings: str
    # Carried on the day rather than fetched separately: a suggestion belongs
    # beside the writing that caused it, and two requests would let the two
    # arrive apart.
    suggestions: list[SuggestionOut]
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
    # Every action item already carried area_id and project_id (TaskOut),
    # but nothing here said what either was -- ui-second-pass-plan.md F2's
    # Daily Page finding: the row showed less than the Agenda even though
    # the Agenda's own join was one field away. Sent regardless of
    # shows_action_items, since a past day's own areas/projects don't change.
    areas: list[DayAreaSummaryOut]
    projects: list[AgendaProjectSummaryOut]
    # Whether this day is showing them at all, decided by the server so the
    # client is not left inferring it from an empty list. Empty-because-done
    # and empty-because-not-today are different, and only one of them
    # deserves "nothing due today".
    shows_action_items: bool
    # **Bills, in an array of their own.** They were action items until
    # August 31, 2026 because a bill was an `Item`; they are here because it
    # is about to stop being one and decision 4 in bill-as-a-model-plan.md
    # keeps them on this page anyway -- paying is a real thing to do on a day.
    #
    # `AgendaBillOut` rather than a daily-shaped copy, for exactly the reason
    # `action_items` reuses `TaskOut`: these are the same rows the agenda
    # serves, and a second schema would be free to drift from the first.
    #
    # Gated by `shows_action_items` too. An unpaid bill today was not
    # necessarily unpaid on the 30th, and the row carries no history to say
    # otherwise -- the same refusal, for the same reason.
    bills: list[AgendaBillOut]
    # Where a brand-new account makes its first area, and with it its first
    # task. Additive, and sent on every day rather than only an empty one:
    # deciding here that a client "needs" it would be the server guessing at
    # a rendering question, and the field is a string.
    #
    # What was deliberately chosen for this day, in the order it was chosen.
    # Released pins are absent -- they are Crane 3's history, not today's
    # work.
    focus: list["FocusOut"]
    #: What today could hold, and whether it holds it. Always present; its
    #: `typical` is None and its `proposed` empty when there is no evidence
    #: to justify a number.
    draft: "DayDraftOut"
    #: What changed since yesterday. Empty on a quiet day.
    brief: "DayBriefOut"
    #: The evening's ask, or null. S5: the record and the morning's choice were
    #: already good, and nothing ever asked for the first.
    closing: "DayClosingOut | None"
    #: When the first act of execution drew the line under this day's list, or
    #: null while it is still open -- `superlists-2.0-plan.md` rules 3 and 11.
    list_closed_at: str | None
    # The Personal Compass, read from the user on every request and stored
    # on no day. Sent with the day rather than fetched separately so the
    # page renders in one round trip -- and because a day is exactly the
    # context it is meant to be read in. Editing it changes every day at
    # once, including ones already written, which is the point of it.
    # What this week is for -- S9. Read from the week containing this day, so
    # Wednesday shows what Sunday decided, and empty when nothing was set.
    #
    # Sent with the day like the Compass above it, and for the same reason: it
    # is context a day is meant to be read *in*, not a thing the day owns. The
    # day displays it and holds no copy that could drift -- charter rule 5.
    week_intention: str
    # How much this person finishes on a day they planned — product-stories.md
    # S3, at the grain that story asks for. `kestrel` shipped this a week wide
    # and on the review; D2's worked example was always a Tuesday.
    #
    # **Null rather than zero below the evidence floor**, and the contract says
    # so rather than leaving a client to infer it. "No evidence yet" and "you
    # have room" call for opposite responses, and a client handed 0 would
    # render the second — the same reason `WeekDraftOut.typical_week` is
    # nullable.
    typical_day: int | None
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


class CalendarDayOut(Schema):
    date: date
    #: Open tasks due on this date -- the agenda's own definition of open.
    due: int
    #: Whether the day has words in it, not merely a row.
    written: bool


class CalendarOut(Schema):
    month_start: date
    #: Both neighbours, always. The same rule `WeekOut` follows: a surface
    #: reachable only by editing the address bar is a gap this sequence has
    #: already shipped twice.
    previous_month: date
    next_month: date
    today: date
    days: list[CalendarDayOut]


class BriefTaskOut(Schema):
    id: int
    text: str
    due_date: str | None


class BriefProjectOut(Schema):
    id: int
    title: str
    quiet_for_days: int


class DayBriefOut(Schema):
    """What changed since yesterday. Three lists, never one ordering.

    Everything here is deliberately something the Day page does *not* already
    show: overdue work is on the page, and the fact that you chose one of them
    yesterday is not. Empty on a quiet day, and empty is what it says.
    """

    slipped: list[BriefTaskOut]
    coming: list[BriefTaskOut]
    gone_quiet: list[BriefProjectOut]


class DayClosingOut(Schema):
    """What the day held, at the point of being asked to write it down.

    Present only in the evening, only on today, and only until the record
    exists -- see `reads.closing_for`. Null the rest of the time, which is why
    the client has no hour of its own to reason about.
    """

    chosen: int
    finished: int
    unfinished: int
    #: Reported apart from `unfinished`, because "I decided this wasn't for
    #: today" and "I never got to it" are different facts.
    released: int


class DayDraftOut(Schema):
    """What today could hold -- the day's own draft.

    **A proposal, never a plan.** Nothing here is pinned; accepting it is a
    separate, deliberate act, because `DailyFocus` records what a person
    *chose* and a focus the system pinned would change what the finish rate
    measures.
    """

    #: What a typical day finishes, or None below the evidence floor -- never
    #: zero, because "no evidence yet" and "you have room" call for opposite
    #: responses.
    typical: int | None
    #: What the draft would pin, in the agenda's own order.
    proposed: list["FocusTaskOut"]
    #: How many tasks have a claim on the day in total, so the page can say
    #: "two of nine" rather than quietly showing two. Bounding the proposal is
    #: not hiding the work.
    available: int


class FocusTaskOut(Schema):
    id: int
    text: str
    due_date: str | None


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
    selected_at: str
    #: Whether this was in the morning's set or joined after the day's work
    #: began -- `superlists-2.0-plan.md` rule 4, *the line is a boundary, not a
    #: wall*. What joined later is shown, and counted apart rather than folded
    #: into what was chosen.
    #:
    #: **Not a stored field.** `daily.reads.above_the_line` computes it from
    #: `selected_at` against the day's `list_closed_at`, which is what keeps it
    #: from ever disagreeing with its own inputs. Sent rather than left to the
    #: client for the same reason: the comparison is on timestamps in the
    #: owner's zone and the browser is not necessarily in it.
    above_the_line: bool
    #: Where the task itself lives, so the day can *act* rather than only
    #: render -- `principles.md`'s *the main surface can do the main thing*.
    #: The server supplies it for the reason it supplies every other URL: a
    #: client that assembles one holds a second definition of the route.
    #: **Not a new mutation path** -- this is the address every other surface
    #: already completes through. Nullable beside `task_id` and for the same
    #: reason: a pin for a deleted task has nothing to address.
    url: str | None


class DraftIn(Schema):
    #: The ids the draft actually displayed, not a fresh read. The draft is
    #: computed on read and stored nowhere, so accepting *what was shown* is
    #: the honest contract; re-deriving here would pin something nobody saw.
    task_ids: list[int]


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


def _hour_for_request():
    """The requesting user's local hour of day.

    Beside `_today_for_request` and for the same reason: the middleware
    activated the owner's zone, so "evening" means theirs rather than the
    server's. Read once here at the boundary and passed down, per
    `principles.md`'s injected clock.
    """
    return timezone.localtime().hour


def _action_item_out(item, today):
    # The age rule itself lives in lists.agenda, because Crane 3's weekly
    # review reports the same number about the same tasks and a second
    # implementation would drift the first time one was corrected.
    return {
        **serialize_item(item),
        "age_in_days": agenda.age_in_days(item.created_at, today),
    }


def _focus_out(focus, closed_at):
    task = focus.task
    return {
        "task_id": focus.task_id,
        "above_the_line": reads.above_the_line(focus, closed_at),
        # The live task while there is one, per charter rule 5 -- a renamed
        # task should read the same here as everywhere else. `task_text` is
        # the fallback for a task that has since been deleted, which is the
        # only case where the snapshot is the better answer because it is
        # the only answer.
        "text": task.text if task else focus.task_text,
        "status": task.status if task else None,
        "due_date": task.due_date.isoformat() if task and task.due_date else None,
        "selected_at": focus.selected_at.isoformat(),
        "url": reverse("api_item_detail", args=[task.pk]) if task else None,
    }


def _brief_out(owner, day, today):
    brief = reads.brief_for(owner, day, today=today)

    def task_of(focus):
        # A slipped pin keeps its snapshot text, because the task it names may
        # have been deleted since -- `task_text` is exactly what that snapshot
        # is for.
        return {
            "id": focus.task_id or 0,
            "text": focus.task.text if focus.task else focus.task_text,
            "due_date": (
                focus.task.due_date.isoformat()
                if focus.task and focus.task.due_date
                else None
            ),
        }

    return {
        "slipped": [task_of(focus) for focus in brief.slipped],
        "coming": [
            {
                "id": item.id,
                "text": item.text,
                "due_date": item.due_date.isoformat() if item.due_date else None,
            }
            for item in brief.coming
        ],
        "gone_quiet": [
            {
                "id": row.project.id,
                "title": row.project.title,
                "quiet_for_days": row.quiet_for_days,
            }
            for row in brief.gone_quiet
        ],
    }


def _closing_out(owner, day, today):
    closing = reads.closing_for(
        owner, day, today=today, hour=_hour_for_request()
    )
    if closing is None:
        return None
    return {
        "chosen": closing.chosen,
        "finished": closing.finished,
        "unfinished": closing.unfinished,
        "released": closing.released,
    }


def _draft_out(owner, day, today):
    draft = reads.draft_day(owner, day, today=today)
    return {
        "typical": draft.typical,
        "available": draft.available,
        "proposed": [
            {
                "id": task.id,
                "text": task.text,
                "due_date": task.due_date.isoformat() if task.due_date else None,
            }
            for task in draft.proposed
        ],
    }


def _day_out(owner, day):
    entry = reads.entry_for(owner, day)
    bounded = reads.bounded_list_for(owner, day)
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
        "suggestions": _suggestions_out(entry),
        "action_items": (
            [
                _action_item_out(item, today)
                for item in reads.action_items_for(owner, day)
            ]
            if shows_action_items
            else []
        ),
        "areas": [
            {
                "id": each.id,
                "title": each.title,
                "url": each.get_absolute_url(),
                "color_key": each.color_key,
            }
            for each in agenda.list_summaries(owner)
        ],
        "projects": [
            project_ref_for(each) for each in project_reader.projects_for(owner)
        ],
        "shows_action_items": shows_action_items,
        "bills": (
            [
                money_reads.bill_row(bill)
                for bill in money_reads.actionable_bills_for(owner, day)
            ]
            if shows_action_items
            else []
        ),
        # **Chosen first, then what joined below the line** -- rule 4. One
        # array rather than two, because it is one list a person reads down and
        # the boundary is a rule about *order plus a marker*, not about two
        # collections. `above_the_line` on each row is the marker; the sort is
        # the order.
        "focus": [
            _focus_out(focus, bounded.closed_at)
            for focus in [*bounded.chosen, *bounded.joined]
        ],
        # When the day's work began, or null on a day that closed unclosed --
        # rule 11 refuses to write a midnight row into a day nobody executed
        # on. The client needs it to draw the line itself, and to say *the list
        # is still open* rather than guessing from an empty `joined`.
        "list_closed_at": (
            bounded.closed_at.isoformat() if bounded.closed_at else None
        ),
        "draft": _draft_out(owner, day, today),
        "brief": _brief_out(owner, day, today),
        "closing": _closing_out(owner, day, today),
        "week_intention": _week_intention_for(owner, day),
        # Asked of the day being shown, so a past day reports what was typical
        # *before it*, not what is typical now. A capacity figure that moved
        # under a day already lived would be the mutable denominator the whole
        # focus model exists to avoid.
        #
        # Computed for every day and not only for today, even though only today
        # renders it. Skipping it would make null mean two things -- "too little
        # history" and "not today" -- and the day payload already refuses that
        # conflation once, at `shows_action_items`. What it costs is measured
        # rather than guessed: `daily/tests/test_typical_day.py` pins it at one
        # query per day looked back, and says what the cheaper shape would be.
        "typical_day": reads.typical_day_for(owner, day),
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


def _refuse_a_past_day(day):
    """Rule 11: a past day is read-only -- `superlists-2.0-plan.md`.

    **A list is written *for* a day and never *on* one that has already
    happened.** A pin backdated into last Tuesday would add a commitment to a
    week whose finish rate has already been read, and `DailyFocus` exists
    precisely so that denominator cannot be reconstructed after the fact.

    **Here rather than in `daily.services.pin_task`, which is where the plan
    asks for it.** That function is also how sixty tests across four apps build
    history, and a service that cannot write a past day cannot express *on
    August 3rd I pinned this*. The rule is about what a person may add to a day
    they are looking at, and these two endpoints are the only door to that --
    the SPA offers *Pin to today* and nothing else, so nothing but a hand-made
    request can reach a past date at all. The tests in
    `daily/tests/test_the_line.py` hold the door rather than the doorway.

    409 rather than 403: the request is authorised and well-formed, and what it
    conflicts with is the state of the day. The same code every other refused-
    but-permitted write on this API answers with.

    Nothing stops a *future* day. Tomorrow's list is the whole point of
    increment 2, and the plan's *written for a day, never on it*.
    """
    if day < _today_for_request():
        raise HttpError(409, "A day that has already happened cannot be planned.")


def _own_task_or_404(owner, task_id):
    """A task this owner actually has.

    Scoped in the lookup rather than fetched and then checked, so there is
    no comparison to forget -- and 404 rather than 403, so the endpoint does
    not confirm that somebody else's task id exists.
    """
    return get_object_or_404(Item, pk=task_id, owner=owner)


_TOKEN_OR_SESSION_READ = [TokenAuth(SCOPE_DAY_READ), SessionAuthIfLoggedIn()]
_TOKEN_OR_SESSION_WRITE = [TokenAuth(SCOPE_DAY_WRITE), SessionAuthIfLoggedIn()]


# Token auth as well as session -- android-full-client-plan.md's slice 1,
# found blocked on a real device because this router used to be session-only
# by design ("a day is written from the browser," per clarice/api.py's own
# comment). day:read and day:write are separate scopes, added one at a time
# as Android actually needed each -- see token-scopes-plan.md.
@router.get("/day", response=DayOut, auth=_TOKEN_OR_SESSION_READ)
def get_today(request):
    return _day_out(request.user, _today_for_request())


@router.get("/day/{day}", response=DayOut, auth=_TOKEN_OR_SESSION_READ)
def get_day(request, day: date):
    return _day_out(request.user, day)


# Session-only, deliberately, and unlike the day reads beside it. A month is a
# new *surface* rather than an existing act in a new shape, and the phone has
# no calendar to put it on -- so token-reaching it now would be the
# un-switched-on seam this project has found five times in a fortnight. One
# line and a deliberate decision if Android ever grows one.
@router.get("/calendar/{day}", response=CalendarOut, auth=SessionAuthIfLoggedIn())
def calendar_month(request, day: date):
    """The month containing ``day``, so a date can be reached without typing.

    `/app/day/:date` has had no UI entry point at all -- reaching a day twelve
    weeks back meant clicking "the week before" twelve times.

    Any day of the month answers with the same month, the courtesy
    `intention_for` gives a week: a client that had to know which day a month
    starts on would hold a second definition of the calendar.
    """
    days = reads.month_for(request.user, day)
    month_start = days[0].date
    previous_end = month_start - timedelta(days=1)
    return {
        "month_start": month_start,
        "previous_month": previous_end.replace(day=1),
        "next_month": days[-1].date + timedelta(days=1),
        "today": _today_for_request(),
        "days": [
            {"date": each.date, "due": each.due, "written": each.written}
            for each in days
        ],
    }


@router.post("/day/{day}/focus", response=DayOut, auth=_TOKEN_OR_SESSION_WRITE)
def pin_to_day(request, day: date, payload: FocusIn):
    """Choose a task as work for this day.

    Returns the whole day rather than the one pin: the client has to
    re-render the focus list and the action items together anyway, and one
    response keeps them from disagreeing for a frame.
    """
    _refuse_a_past_day(day)
    task = _own_task_or_404(request.user, payload.task_id)
    try:
        services.pin_task(request.user, day, task)
    except services.FocusError as error:
        raise HttpError(403, str(error))
    return _day_out(request.user, day)


@router.post("/day/{day}/focus/draft", response=DayOut, auth=_TOKEN_OR_SESSION_WRITE)
def accept_days_draft(request, day: date, payload: DraftIn):
    """Take the day's draft as it was shown, in one act.

    One decision rather than one per task, which is the whole point: the
    manual cost of the daily loop was choosing five things by hand every
    morning. It is still a decision -- the draft is bounded by observed
    capacity and says what it left out.
    """
    _refuse_a_past_day(day)
    tasks = [_own_task_or_404(request.user, task_id) for task_id in payload.task_ids]
    try:
        services.accept_draft(request.user, day, tasks)
    except services.FocusError as error:
        raise HttpError(403, str(error))
    return _day_out(request.user, day)


@router.delete("/day/{day}/focus/{task_id}", response=DayOut, auth=_TOKEN_OR_SESSION_WRITE)
def unpin_from_day(request, day: date, task_id: int):
    """Take a task off this day, keeping the record that it was chosen."""
    task = _own_task_or_404(request.user, task_id)
    services.unpin_task(request.user, day, task)
    return _day_out(request.user, day)


@router.patch("/day/{day}", response=DayOut, auth=_TOKEN_OR_SESSION_WRITE)
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


def _effect_of(facet):
    """What confirming this will do, in one sentence the server owns.

    Phrased here rather than in the client so two clients cannot describe the
    same button differently — and because the wording depends on a decision
    the server made: slice C settled that a promise with no date makes a task
    with none, and that is exactly what a person is being asked to approve.
    """
    due = facet.data.get("due_date")
    return f"Creates a task due {due}" if due else "Creates a task with no due date"


def _suggestions_out(entry):
    """This day's unanswered commitments, oldest first.

    Answered ones are gone from here by construction: confirming stamps
    `confirmed_at` and dismissing stamps `retired_at`, so a decided card
    disappears without anything having to remember to remove it.
    """
    if entry is None:
        return []
    return [
        {
            "id": facet.id,
            # The cited sentence, which is the evidence. A card quoting the
            # whole day would make the reader find the promise themselves.
            "text": facet.cited_text.strip(),
            "reason": facet.reason or "",
            "effect": _effect_of(facet),
        }
        for facet in entry.facets.filter(
            kind=FacetKind.ACTIONABLE,
            confirmed_at__isnull=True,
            retired_at__isnull=True,
        ).order_by("span_start", "id")
    ]


def _own_suggestion_or_404(user, suggestion_id):
    """Owner-scoped in the query, so a caller cannot forget the second half.

    `principles.md`: guards fail closed. The route addresses facets by id, and
    this is what stops one person answering another's suggestion.
    """
    facet = Facet.objects.filter(
        id=suggestion_id, kind=FacetKind.ACTIONABLE, entry__owner=user
    ).select_related("entry").first()
    if facet is None:
        raise HttpError(404, "Suggestion not found.")
    return facet


@router.post("/suggestions/{suggestion_id}/confirm", response=DayOut)
def confirm_suggestion(request, suggestion_id: int):
    """Accept a commitment the journal offered, making it a real task.

    Answers with the whole day rather than the facet: every other write on this
    surface does, and a client reconciling its own state after a decision is a
    client that can disagree with the server about what just happened.
    """
    facet = _own_suggestion_or_404(request.user, suggestion_id)
    mind_services.confirm_actionable(
        facet, now=timezone.now(), actor=request.user.get_username()
    )
    return _day_out(request.user, facet.entry.date)


@router.post("/suggestions/{suggestion_id}/dismiss", response=DayOut)
def dismiss_suggestion(request, suggestion_id: int):
    """Say no, and have it stay said.

    Retired rather than deleted, so the fingerprint keeps matching and the next
    save does not offer it again — dismissing and then typing another word is
    the ordinary case, and a suggestion that came back would make this button
    meaningless.
    """
    facet = _own_suggestion_or_404(request.user, suggestion_id)
    mind_services.dismiss_facet(
        facet, now=timezone.now(), actor=request.user.get_username()
    )
    return _day_out(request.user, facet.entry.date)


def _week_intention_for(owner, day):
    """The week's intention as a plain string, empty when unset — S9.

    A string rather than an object because the day renders text and nothing
    else, and blank-not-null the whole way through means a client never has to
    tell "no intention" from "field absent".

    Read through `review.reads`, which owns what a week is. Resolving the
    Monday here would be a second definition of "this week" — the drift
    `crane-plan.md` §6 names, and the reason S9's own model borrows that
    function rather than taking a date from its caller.
    """
    intention = review_reads.intention_for(owner, day)
    return intention.text if intention else ""
