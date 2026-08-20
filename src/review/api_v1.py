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
from ninja.errors import HttpError

from lists import agenda
from review import reads, services
from lists.models import Project
from review.models import PlanningSession, WeeklyOutcome
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
    # Nullable since `Item.list` was widened on August 14 (`0857835`), and
    # this schema was missed. Ninja validates responses, so a non-optional
    # int here did not degrade one row -- it 500d the whole week, for good:
    # `reads.completed_in_week` filters on `completed_at` alone, so archiving
    # the task does not clear it and only setting an Area by hand ever did.
    area_id: int | None


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
    #: What this person's weeks actually hold -- the median finished across up
    #: to eight prior weeks that had a plan in them, **strictly before this
    #: one**, so a week is never its own evidence.
    #:
    #: **`None` below the sample floor rather than zero.** "No evidence yet"
    #: and "you committed to more than you can hold" call for opposite
    #: responses, and a zero would say the second while meaning the first.
    typical: int | None
    #: S3's last clause. `met` over `total` is honest as a rate and cannot on
    #: its own tell *over-committed* from *under-delivered*; this is the same
    #: comparison `draft_week` already makes for the week ahead, pointed at the
    #: week being reviewed.
    over_committed: bool


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


class ThoughtOut(Schema):
    """Something captured this week.

    Was `IdeaOut`, which carried a `status` because an Idea could be exploring,
    reference or promoted. A node has no such state -- a thought is a thought,
    and what became of it is recorded on the facets and edges around it rather
    than on the thing itself.
    """

    public_id: str
    text: str
    captured_on: date


class NameToConfirmOut(Schema):
    """A name that has recurred enough to be worth a question.

    Replaces the Inbox backlog, which the graph has no equivalent of because
    nothing waits for triage. `mentions` is the evidence and the reason it is
    being asked about at all -- a count with no basis is the system asking for
    trust, which every other proposal here refuses to do.
    """

    label: str
    mentions: int


class LooseEndTaskOut(Schema):
    id: int
    text: str
    due_date: date | None


class UnansweredQuestionOut(Schema):
    """A question nothing has answered, with the date that makes it a loose end.

    `asked_on` is the evidence: "you asked this" is a fact, "twelve days ago" is
    what makes it worth showing. Neither is a claim about the question.
    """

    public_id: str
    text: str
    asked_on: date


class UnansweredCommitmentOut(Schema):
    """A commitment proposed from a capture and never accepted or dismissed.

    `text` is the note it was read out of, which is the evidence for the
    proposal. The actionable facet is the one proposal type with no expiry, so
    this backlog can only shrink by somebody answering it -- which is exactly
    why it belongs in a review rather than in a notification.
    """

    id: int
    text: str
    # Which surface it was read out of, so the review can say where to answer
    # it. The two are answered in different places and look identical without
    # this.
    source: str
    proposed_on: date


class LooseEndsOut(Schema):
    unanswered: list[UnansweredQuestionOut]
    unanswered_commitments: list[UnansweredCommitmentOut]
    overdue: list[LooseEndTaskOut]


class UpcomingProjectOut(Schema):
    id: int
    title: str
    due_date: date | None


class UpcomingOut(Schema):
    tasks: list[LooseEndTaskOut]
    projects: list[UpcomingProjectOut]


class DraftRoutineOut(Schema):
    id: int
    title: str
    cadence: str


class DraftedTaskOut(Schema):
    id: int
    text: str
    due_date: date | None
    # Whether it serves something the week is for -- v2 increment 7. Marked and
    # never cut: a draft that quietly dropped unconnected work would be
    # deciding, which is the one thing this proposal does not do.
    serves_an_outcome: bool


class DraftedDayOut(Schema):
    """One day of the drafted week.

    Sent for all seven, empty ones included: an empty day is where anything
    being moved would go, and a week showing only its busy days answers a
    different question.
    """

    date: date
    tasks: list[DraftedTaskOut]
    over_committed: bool
    # False when a scenario has taken this day out of the week. The work due on
    # it is still listed here, because it has not moved.
    available: bool


class WeekDraftOut(Schema):
    """Next week, proposed — increment 6.

    **Nothing here is committed**, and the shape says so: no ids to confirm, no
    state to reconcile. A draft is read, edited by acting on the tasks it names
    through their own endpoints, or ignored — and ignoring it costs nothing,
    which is what keeps it a proposal rather than a plan somebody has to undo.

    `typical_week` is null rather than zero when there is too little history.
    "No evidence yet" and "you have room" call for opposite responses, and a
    client shown zero would render the second.
    """

    week_start: date
    intention: str
    proposed: list[LooseEndTaskOut]
    routines: list[DraftRoutineOut]
    typical_week: int | None
    over_committed: bool
    # The same work laid out on the days it is already due. Overdue work is in
    # `proposed` and on no day at all -- placing a late task onto a weekday
    # would be re-dating it, and nothing here re-dates anything.
    days: list[DraftedDayOut]
    # Work dated onto days the scenario removed. Named, never re-dated.
    displaced: list[DraftedTaskOut]
    # Null below the evidence floor, like `typical_week`, and for the same
    # reason: a client handed zero would render "you have room".
    typical_day: int | None


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
    thoughts: list[ThoughtOut]
    # Not week-scoped, and named so that is visible in the contract rather
    # than only in the read: an Inbox is a backlog, not seven days.
    names_to_confirm: list[NameToConfirmOut]
    # Neither is week-scoped, and both are named here so the contract says so.
    # A loose end does not become tidy because a Monday passed, and a
    # constraint is what arrives before the *next* review -- so one looks
    # backwards without a bound and the other looks exactly one week forward.
    loose_ends: LooseEndsOut
    upcoming: UpcomingOut
    # Next week, proposed. Carried on the review because that is when somebody
    # is already looking backwards and is the one moment they are placed to
    # look forwards -- `design-concept.md`'s ritual, not a second surface.
    draft: WeekDraftOut
    # What the planning session believes about the week being drafted — v2
    # increment 4. Carried on the review because that is where the ritual's
    # forward half lives, and keyed to the *drafted* week like the draft above
    # rather than to the week on screen.
    check_in: CheckInOut
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
        "area_id": item.list_id,
    }


def _week_out(owner, day):
    week_start, week_end = reads.week_bounds(day)
    today = timezone.localdate()
    planned = reads.planned_in_week(owner, week_start, week_end)
    typical = reads.typical_week_for(owner, week_start)
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
            "typical": typical,
            # The same expression `draft_week` uses, deliberately -- two
            # spellings of "more than usual" would eventually disagree.
            "over_committed": typical is not None and planned.total > typical,
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
        "thoughts": [
            {
                "public_id": str(node.public_id),
                "text": node.original_content,
                # The thought's own day, not the row's -- see the read.
                "captured_on": timezone.localtime(node.captured_at).date(),
            }
            for node in reads.thoughts_captured_in_week(owner, week_start, week_end)
        ],
        "names_to_confirm": [
            {"label": candidate.label, "mentions": candidate.mention_count}
            for candidate in reads.names_worth_confirming(owner)
        ],
        "loose_ends": _loose_ends_out(owner, today),
        "upcoming": _upcoming_out(owner, week_end),
        "draft": _draft_out(owner, week_start, today),
        # Keyed to the week being *drafted*, like the draft above it. A
        # check-in about the week on screen would be asking somebody to plan a
        # week that has already happened.
        "check_in": _check_in_out(owner, week_start + timedelta(days=DAYS_IN_WEEK)),
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


class ProjectToConfirmOut(Schema):
    id: int
    title: str
    quiet_for_days: int
    looks_active: bool


class CheckInOut(Schema):
    """What the session believes, so it can be corrected rather than asked.

    Every field here is something already recorded or derived. The plan's rule
    is that a check-in asking what the system knows makes the ritual longer and
    the answers worse, so this is a page of statements with controls beside
    them, not a form.

    `started` is the session's *existence*, which is the fact the record is for
    -- "I planned and had little to change" and "I never opened it" are
    different, and only the first says the ritual is happening.
    """

    started: bool
    unusual: str
    projects: list[ProjectToConfirmOut]
    # What has been chosen for the week, and what is worth choosing. Both, so
    # the section can say "here are your two" and "here is a third worth
    # considering" without a second request.
    outcomes: list[OutcomeOut]
    proposals: list[OutcomeProposalOut]
    # Both triaged against the outcomes above, which is why they are in this
    # block rather than beside the review's own loose ends: those are the
    # oldest few unconditionally, these are defined by what the week is for.
    blockers: list[BlockerOut]
    carryover: list[CarryoverOut]


class OutcomeOut(Schema):
    id: int
    text: str
    # The snapshot, not the project's current title -- what it was called when
    # this was chosen. Empty for an outcome written from nothing.
    project_title: str
    # Null once the project is deleted, which leaves the outcome standing and
    # readable from the copy above.
    project_id: int | None


class OutcomeProposalOut(Schema):
    """A project the week has a reason to be about, and the reason.

    `because` is stated facts rather than a score, and `suggested_text` is the
    project's own words -- never a phrasing this composed. D1 defers generated
    prose, and rewording somebody's own sentence would be the least defensible
    place to start.
    """

    project_id: int
    project_title: str
    suggested_text: str
    because: list[str]


class BlockerOut(Schema):
    """An open question standing in the way of a chosen outcome.

    `outcome_text` is the evidence for the word "blocker" -- naming what it
    blocks is what stops this being a list of questions with an adjective.
    `came_back` is how many later notes returned to it, from the read that
    waited since increment 1 for a caller willing to pay one retrieval per
    question; a ritual asking about five is where that cost is finally worth it.
    """

    public_id: str
    text: str
    days_open: int
    came_back: int
    outcome_text: str


class CarryoverOut(Schema):
    id: int
    text: str
    due_date: date | None
    # Whether it serves something the week is for. Ordered by this and never
    # filtered: a leftover connected to nothing is the row most worth deciding
    # about, and hiding it would make triage a backlog nobody sees.
    serves_an_outcome: bool


class ChooseOutcomeIn(Schema):
    text: str
    project_id: int | None = None


class RewordOutcomeIn(Schema):
    text: str


class WeekUnusualIn(Schema):
    unusual: str


class WeekIntentionIn(Schema):
    """One field, and blank is a value.

    Not optional the way `ReviewIn`'s two are. That payload is partial because
    the review page may save reflections without carrying the plan; this
    resource *is* the text, so absent and empty would be the same request
    wearing two shapes.
    """

    text: str


class WeekIntentionOut(Schema):
    """The week that was written, named rather than implied.

    `week_start` is returned because the request addresses a week by *any* of
    its days, and a client that resolved the Monday itself would be the second
    definition of "this week" — the drift `crane-plan.md` §6 names and the
    reason `set_intention` normalises rather than demanding a Monday.
    """

    week_start: date
    text: str


@router.put("/weeks/{day}/intention", response=WeekIntentionOut)
def write_week_intention(request, day: date, payload: WeekIntentionIn):
    """Say what the week containing ``day`` is for — S9's missing half.

    **`/weeks/` rather than `/review/{day}/intention`**, and the URL is doing
    real work here. `WeeklyIntention` is its own model precisely so that
    writing one cannot invent a `WeeklyReview` row, since that row's existence
    is the only evidence of whether the practice is happening. Addressing the
    intention through the review's path would put the confusion the model
    exists to prevent into the contract, where the next person adding a field
    has to rediscover it. The week is the resource; the review is a different
    record about the same seven days.

    **PUT rather than PATCH**, because the body is the whole resource. Sending
    it twice leaves the same state, and sending it empty clears the text
    without deleting the record — "I set none this week" and "I never opened
    it" stay different facts.

    There is no ownership check to forget: the record is addressed by
    (`request.user`, the week containing `day`), so the path names a date and
    never a record — the same shape `write_review` uses, and a smaller surface
    than an id would be.
    """
    intention = services.set_intention(request.user, day, payload.text)
    return {"week_start": intention.week_start, "text": intention.text}


def _check_in_out(owner, week_start):
    session = reads.planning_session_for(owner, week_start)
    return {
        "started": session is not None,
        # The default rather than null when no session is open. "Nobody has
        # said otherwise" and "somebody said it is usual" call for the same
        # rendering, and a nullable enum would make every client handle both.
        "unusual": (
            session.unusual if session else PlanningSession.Unusual.USUAL
        ),
        "projects": [
            {
                "id": each.project.id,
                "title": each.project.title,
                "quiet_for_days": each.quiet_for_days,
                "looks_active": each.looks_active,
            }
            for each in reads.projects_to_confirm(owner)
        ],
        "outcomes": [
            {
                "id": each.id,
                "text": each.text,
                "project_title": each.project_title,
                "project_id": each.project_id,
            }
            for each in reads.outcomes_for(owner, week_start)
        ],
        "blockers": [
            {
                "public_id": str(each.question.node.public_id),
                "text": each.question.node.original_content,
                "days_open": each.question.days_open,
                "came_back": len(each.question.mentions),
                "outcome_text": each.outcome.text,
            }
            for each in reads.blockers_for(owner, week_start, now=timezone.now())
        ],
        "carryover": [
            {
                "id": each.task.id,
                "text": each.task.text,
                "due_date": each.task.due_date,
                "serves_an_outcome": each.serves_an_outcome,
            }
            for each in reads.carryover_for(
                owner, week_start, today=timezone.localdate()
            )
        ],
        "proposals": [
            {
                "project_id": each.project.id,
                "project_title": each.project.title,
                "suggested_text": each.suggested_text,
                "because": each.because,
            }
            for each in reads.outcomes_worth_proposing(
                owner, week_start_for(week_start)
            )
        ],
    }


@router.get("/weeks/{day}/draft", response=WeekDraftOut)
def draft_under_a_scenario(request, day: date, unavailable: str = ""):
    """The week drafted again with some days taken out — v2 increment 8.

    **A GET, because a scenario is a question rather than a decision.** Nothing
    about it is stored: *"what if I only have three productive days"* asks what
    the week would look like, and a what-if that persisted would be a plan
    somebody has to undo. Ask it twice and nothing has changed either time.

    Its own route rather than a parameter on the review, so asking a what-if
    costs one draft rather than the whole week -- the review carries habits,
    recent weeks, loose ends and a check-in that a scenario does not touch.

    `unavailable` is a comma-separated list of ISO dates. A malformed one is
    refused rather than ignored, because a scenario silently dropping the day
    somebody named would answer a different question and look like an answer.
    """
    try:
        gone = [
            date.fromisoformat(each.strip())
            for each in unavailable.split(",")
            if each.strip()
        ]
    except ValueError:
        raise HttpError(422, "Those are not dates.")
    return _draft_out(
        request.user,
        # The path names the week being *reviewed*, exactly as `/review/{day}`
        # does, and `_draft_out` steps forward to the week being planned. Two
        # ways of saying which week would be two chances to disagree.
        week_start_for(day),
        timezone.localdate(),
        unavailable=gone,
    )


@router.post("/weeks/{day}/outcomes", response=CheckInOut)
def choose_outcome(request, day: date, payload: ChooseOutcomeIn):
    """Commit to something being true by the end of this week.

    The project is looked up owner-scoped, so a foreign id is a 404 rather
    than an outcome pointing at somebody else's work.
    """
    text = payload.text.strip()
    if not text:
        raise HttpError(422, "An outcome needs words.")
    project = None
    if payload.project_id is not None:
        project = Project.objects.filter(
            owner=request.user, pk=payload.project_id
        ).first()
        if project is None:
            raise HttpError(404, "Project not found.")
    services.choose_outcome(request.user, day, text=text, project=project)
    return _check_in_out(request.user, day)


@router.patch("/weeks/{day}/outcomes/{outcome_id}", response=CheckInOut)
def reword_outcome(request, day: date, outcome_id: int, payload: RewordOutcomeIn):
    text = payload.text.strip()
    if not text:
        raise HttpError(422, "An outcome needs words.")
    try:
        services.reword_outcome(request.user, outcome_id, text)
    except WeeklyOutcome.DoesNotExist:
        raise HttpError(404, "Outcome not found.")
    return _check_in_out(request.user, day)


@router.delete("/weeks/{day}/outcomes/{outcome_id}", response=CheckInOut)
def drop_outcome(request, day: date, outcome_id: int):
    """Take it off the week. A real delete — see the model on why this one
    record is allowed it."""
    try:
        services.drop_outcome(request.user, outcome_id)
    except WeeklyOutcome.DoesNotExist:
        raise HttpError(404, "Outcome not found.")
    return _check_in_out(request.user, day)


@router.post("/weeks/{day}/planning-session", response=CheckInOut)
def start_planning_session(request, day: date):
    """Record that somebody sat down to plan this week.

    **A POST, because loading the review must not count as planning.**
    `review.reads` is query-only and a session created by a page view would
    make every refresh a planning session, destroying the only number this
    record exists to produce. Opening the check-in is an act; reading the
    review is not.

    Idempotent: opening it twice is one session, and the second call does not
    move when it started.
    """
    services.open_planning_session(request.user, day)
    return _check_in_out(request.user, day)


@router.patch("/weeks/{day}/planning-session", response=CheckInOut)
def correct_planning_session(request, day: date, payload: WeekUnusualIn):
    """Say this week is not a typical one — or take it back.

    Opens a session if none is open, because correcting what the system
    believed *is* planning; requiring a separate POST first would let the
    ritual's denominator miss anybody who only corrected something.
    """
    if payload.unusual not in PlanningSession.Unusual.values:
        raise HttpError(422, "That is not a week shape.")
    services.set_week_unusual(request.user, day, payload.unusual)
    return _check_in_out(request.user, day)


def _drafted_task_out(each):
    return {
        "id": each.id,
        "text": each.text,
        "due_date": each.due_date,
        "serves_an_outcome": each.serves_an_outcome,
    }


def _draft_out(owner, week_start, today, *, unavailable=()):
    """Next week's draft, from the week being reviewed.

    **The week after the one on screen**, which is the whole point of drafting
    here: somebody reviewing a week is already looking backwards, and this is
    the one moment they are placed to look forwards. Drafting the week they are
    reading about would propose a week that has already happened.
    """
    draft = reads.draft_week(
        owner,
        week_start + timedelta(days=DAYS_IN_WEEK),
        today=today,
        unavailable=unavailable,
    )
    return {
        "week_start": draft.week_start,
        "intention": draft.intention,
        "proposed": [
            {"id": task.id, "text": task.text, "due_date": task.due_date}
            for task in draft.proposed
        ],
        "routines": [
            {"id": routine.id, "title": routine.title, "cadence": routine.cadence}
            for routine in draft.routines
        ],
        "days": [
            {
                "date": day.date,
                "tasks": [_drafted_task_out(each) for each in day.tasks],
                "over_committed": day.over_committed,
                "available": day.available,
            }
            for day in draft.days
        ],
        "typical_day": draft.typical_day,
        "displaced": [_drafted_task_out(each) for each in draft.displaced],
        "typical_week": draft.typical_week,
        "over_committed": draft.over_committed,
    }


def _loose_ends_out(owner, today):
    """Serialise what is still hanging — planning-assistant-plan.md increment 5.

    Dates travel as the person's own local dates, matching every other date on
    this response. `captured_at` is an instant, and reading it on the client
    would file a late-evening question into tomorrow for anybody west of UTC.
    """
    ends = reads.loose_ends(owner, today=today)
    return {
        "unanswered": [
            {
                "public_id": str(node.public_id),
                "text": node.original_content,
                "asked_on": timezone.localtime(node.captured_at).date(),
            }
            for node in ends.unanswered
        ],
        "unanswered_commitments": [
            {
                # The facet's own id, not the source's. The facet *is* the
                # proposal, it is what a confirm or dismiss will name, and it
                # is the only identifier that exists for both sources -- a
                # `DailyEntry` has no public id and reaching through
                # `facet.node` would 500 on every journal-backed one.
                "id": facet.id,
                # The cited passage, which is the evidence for the proposal
                # rather than decoration, and falls back to the whole source
                # when nothing narrower was recorded.
                "text": facet.cited_text,
                "source": "journal" if facet.entry_id else "capture",
                "proposed_on": timezone.localtime(facet.created_at).date(),
            }
            for facet in ends.unanswered_commitments
        ],
        "overdue": [
            {"id": task.id, "text": task.text, "due_date": task.due_date}
            for task in ends.overdue
        ],
    }


def _upcoming_out(owner, week_end):
    upcoming = reads.upcoming_constraints(owner, week_end=week_end)
    return {
        "tasks": [
            {"id": task.id, "text": task.text, "due_date": task.due_date}
            for task in upcoming.tasks
        ],
        "projects": [
            {"id": project.id, "title": project.title, "due_date": project.due_date}
            for project in upcoming.projects
        ],
    }
