"""Read-side logic for the weekly review.

Query and derivation only; every mutation is in review.services, which
arrived with the first record at slice 4 rather than being created empty
three slices earlier to satisfy a rule. What charter rule 4 asks for is that
reads and writes never share a home, and a surface that is almost entirely
read is the strictest case of it: **this module must not write.** The
routines domain creates its occurrences lazily, so a review
that touched one in order to describe it would be a page view inventing
history. `test_reading_a_week_writes_nothing` holds that as a statement
about executed SQL rather than about intent.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import F, Q
from django.utils import timezone

# `daily.reads` for the day-grain capacity figure the draft measures against.
# Safe at module scope in this direction: `daily.reads` imports `review.reads`
# lazily, inside the one function that needs `planned_in_week`, precisely so
# these two can read from each other without an import order to remember.
from daily import reads as daily_reads
from daily.models import DailyEntry, DailyFocus
from mind import queries as mind_queries
from mind.models import Facet, FacetKind, Node
from lists.models import Item, Project
from review.models import (
    PlanningSession,
    WeeklyIntention,
    WeeklyOutcome,
    WeeklyReview,
)
from review.weeks import DAYS_IN_WEEK, days_in, week_end_for, week_start_for
from routines import reads as routine_reads
from routines.models import Routine, RoutineOccurrence, RoutinePause


def week_bounds(day):
    """``(monday, sunday)`` for the week ``day`` falls in."""
    return week_start_for(day), week_end_for(day)


def _instant_range(week_start, week_end):
    """The week as an aware half-open datetime range, in the owner's zone.

    A range comparison rather than the `__date` transform, for the reason
    `agenda.completed_today_for` gives: it lets Postgres use the plain
    B-tree index on `completed_at` instead of needing a functional one.

    `make_aware` reads the zone the middleware activated for this request,
    which is the account's own -- so a week for somebody in Makassar starts
    and ends at their midnight, not the server's.
    """
    start = timezone.make_aware(
        datetime.combine(week_start, datetime.min.time())
    )
    return start, start + timedelta(days=(week_end - week_start).days + 1)


def completed_in_week(owner, week_start, week_end):
    """This owner's work finished inside the week, oldest first.

    Filtered on `completed_at` alone rather than on status as well, because
    archiving a finished task is filing it rather than undoing it -- a task
    completed on Wednesday and archived on Friday was still finished that
    week, and a review that quietly dropped it would understate the week
    every time somebody tidied up.
    """
    start, end = _instant_range(week_start, week_end)
    return list(
        Item.objects.filter(
            owner=owner,
            completed_at__gte=start,
            completed_at__lt=end,
        )
        .order_by(F("completed_at").asc(), "id")
    )


@dataclass(frozen=True)
class Planned:
    """What a week was committed to, and what became of each commitment.

    Three lists rather than a flag per row, because the three mean
    different things and a review that blurred them would report a number
    nobody should act on:

    - ``met`` and ``unfinished`` are the numerator and the rest of the
      denominator -- "completed planned commitments / planned
      commitments", which is the definition
      daily-operating-system-vision.md gives and the reason DailyFocus
      exists at all.
    - ``set_aside`` is outside the denominator entirely. Deciding on
      Wednesday that something is not for this week is a decommitment, and
      counting it as a failure would be the product disagreeing with a
      decision the person made deliberately.
    """

    met: list
    unfinished: list
    set_aside: list

    @property
    def total(self):
        return len(self.met) + len(self.unfinished)


def _local_date(instant):
    return timezone.localtime(instant).date() if instant else None


def planned_in_week(owner, week_start, week_end):
    """The week's pins, sorted into what became of them by the week's end.

    Both judgements are made **at the week's end** rather than at read
    time, which is what keeps a past week's figure from moving afterwards:
    a task finished the following Tuesday was unfinished when the week
    closed, and a pin dropped three weeks later was a real commitment while
    the week was running.

    A pin whose task has since been permanently deleted counts as
    unfinished, because `DailyFocus.task` is SET_NULL and there is nothing
    left to ask. The denominator survives -- that is what `task_text` is
    for -- but the numerator can quietly fall, which is why §8 has
    completing a review stamp the figure it reported.
    """
    met, unfinished, set_aside = [], [], []
    for focus in (
        DailyFocus.objects.filter(
            owner=owner,
            entry__date__gte=week_start,
            entry__date__lte=week_end,
        )
        .select_related("task", "entry")
        .order_by("entry__date", "position", "id")
    ):
        released_on = _local_date(focus.released_at)
        if released_on is not None and released_on <= week_end:
            set_aside.append(focus)
            continue
        finished_on = _local_date(focus.task.completed_at if focus.task else None)
        if finished_on is not None and finished_on <= week_end:
            met.append(focus)
        else:
            unfinished.append(focus)
    return Planned(met=met, unfinished=unfinished, set_aside=set_aside)


def written_in_week(owner, week_start, week_end):
    """The days of this week that were actually written in, in order.

    Entries with nothing in any of the three fields are left out. A row
    exists as soon as anything is pinned to a day, so an empty one is the
    ordinary state of a planned day rather than something to hand back as
    writing -- and a review that listed seven blank days would bury the two
    that say something.

    Ascending, unlike `DailyEntry.Meta.ordering`. The model's most-recent-
    first is right for "reopen a recent day"; a week is read forwards.
    """
    return list(
        DailyEntry.objects.filter(
            owner=owner, date__gte=week_start, date__lte=week_end
        )
        .exclude(intentions="", gratitude="", happenings="")
        .order_by("date")
    )


def thoughts_captured_in_week(owner, week_start, week_end):
    """Everything captured this week, oldest first.

    Was `ideas_added_in_week`, reading `capture.Idea` — a model the crossover
    deletes, and a distinction it deletes with it. A retained thought and a
    captured one were two objects because the Inbox needed somewhere to promote
    things *to*; in the graph a thought is a thought, and this reads that.

    **Filtered on `captured_at`, not `created_at`.** A node carries when the
    thought happened separately from when the row was written, and the 34
    captures migrated out of the Inbox all have an original date months before
    their row. Reading the row would file every one of them into the week of the
    migration.

    Archived material is left out. Twenty-two of those migrated captures were
    discards — device-test residue — and a review of the week should not open
    with a fortnight of "Offline test 3".
    """
    start, end = _instant_range(week_start, week_end)
    return list(
        Node.objects.filter(
            owner=owner,
            captured_at__gte=start,
            captured_at__lt=end,
            deleted_at__isnull=True,
            archived_at__isnull=True,
        ).order_by("captured_at", "id")
    )


def names_worth_confirming(owner):
    """Concept candidates that have earned a question, heaviest first.

    Replaces `captures_still_waiting`, and deliberately is not the same shape.
    That read the Inbox backlog — everything untriaged, whatever week it came
    from — and the graph has no backlog, because nothing waits for triage. An
    equivalent would have to be invented, and inventing one would reimport the
    exact concept the crossover exists to delete.

    What is genuinely waiting is the one queue this design permits: a name that
    has recurred enough to be worth asking about. It is finite by construction
    (three mentions spanning a day), it is the mechanism the concept layer grows
    by, and a chosen weekly ritual is precisely when the Attention Policy says a
    queue may be shown.
    """
    return list(mind_queries.concept_candidates(owner))


def review_for(owner, week_start):
    """This owner's review of the week, or None if they have not written one.

    None rather than a created row: an unwritten review is a blank page,
    not a missing one, and a GET that brought the record into existence
    would be the page view inventing history this module opens by
    refusing.
    """
    return WeeklyReview.objects.filter(
        owner=owner, week_start=week_start
    ).first()


@dataclass(frozen=True)
class HabitPeriod:
    """One period of one routine, and what became of it.

    ``target`` and ``progress`` come from the occurrence where there is
    one, so a routine whose target changed last month cannot rewrite what
    an older period expected -- charter rule 3, already paid for in
    RoutineOccurrence. A period nobody logged has no row, so it is
    described against what the routine says now, which is the same call
    `routines.reads.standings_for` makes and for the same reason: nothing
    has happened yet to preserve.
    """

    period_start: object
    outcome: str
    progress: int
    target: int
    unit: str

    @property
    def is_met(self):
        return self.outcome == RoutineOccurrence.Outcome.COMPLETED

    @property
    def is_skipped(self):
        return self.outcome == RoutineOccurrence.Outcome.SKIPPED

    @property
    def was_enough(self):
        return self.outcome == RoutineOccurrence.Outcome.PARTIAL

    @property
    def was_decided(self):
        """Somebody said something about this period rather than it merely
        running out. Both kinds of decision leave the denominator."""
        return self.is_skipped or self.was_enough


@dataclass(frozen=True)
class Habit:
    """A routine's week: what was expected of it, and what happened.

    ``expected`` excludes skipped periods, which is the decision worth
    knowing about. A skip is "I chose not to today", and counting it
    against the week would be the product disagreeing with a decision
    somebody made deliberately -- exactly what `DailyFocus.released_at`
    keeps out of the planned denominator. The skips are reported alongside
    rather than swallowed, so the figure cannot hide them.

    ``paused_since`` and ``paused_days`` say what a pause did to the week.
    Both are read from `RoutinePause`, and both are silent where it is:
    a pause that began and ended before that table existed leaves no row,
    and inferring one from an empty stretch is precisely what §8 rules out.
    """

    routine: object
    periods: list
    paused_since: object = None
    paused_days: int = 0

    @property
    def met(self):
        return sum(1 for period in self.periods if period.is_met)

    @property
    def skipped(self):
        return sum(1 for period in self.periods if period.is_skipped)

    @property
    def enough(self):
        return sum(1 for period in self.periods if period.was_enough)

    @property
    def expected(self):
        # Every deliberate decision comes out, not only skips: a period
        # closed at "that was enough" is a decision about it too, and
        # crane-plan.md §8 settles that it counts toward neither the met
        # nor the expected. What stays in the denominator is periods that
        # merely ran out.
        return sum(1 for period in self.periods if not period.was_decided)


def _down_days(pauses, week_start, week_end):
    """The dates in this week the routine was deliberately down for.

    A day counts as down if a pause covered any part of it, which is the
    kinder of the two readings at the boundaries: somebody who put a
    routine down on Wednesday afternoon and picked it up on Friday morning
    had it down for part of both, and asking them for those days would be
    the product asserting a miss against a decision they made.
    """
    down = set()
    for pause in pauses:
        began = timezone.localtime(pause.paused_at).date()
        ended = (
            timezone.localtime(pause.resumed_at).date() if pause.resumed_at else None
        )
        for day in days_in(week_start):
            if day < began or day > week_end:
                continue
            if ended is None or day <= ended:
                down.add(day)
    return down


def _paused_since(pauses, week_start, week_end, today):
    """When the pause that was still running at the week's end began.

    Reported only when the routine was actually down at that point, so a
    pause that started and finished mid-week leaves this null and shows up
    in the day count instead. A pause that began after the week is not this
    week's business at all: a decision taken later must not rewrite a week
    already lived.
    """
    edge = min(week_end, today)
    for pause in pauses:
        began = timezone.localtime(pause.paused_at).date()
        ended = (
            timezone.localtime(pause.resumed_at).date() if pause.resumed_at else None
        )
        if began <= edge and (ended is None or ended > edge):
            return began
    return None


def _periods_expected_of(routine, week_start, week_end, today, down):
    """Which periods this week actually asked of ``routine``.

    Floored at the routine's own beginning and capped at today, because
    both ends are the same rule: a period that never came round cannot
    have been missed, and reporting one would assert a failure the person
    never had the chance to have. A routine kept from Thursday is asked
    about four days; a week still ahead is asked about none.

    Days it was deliberately down for come out too, on the same ground --
    a paused routine is not a failing one. `down` is empty wherever
    `RoutinePause` has nothing to say, which is how a week that predates
    that record is described exactly as it was before it existed.
    """
    began = timezone.localtime(routine.created_at).date()
    last = min(week_end, today)
    if routine.cadence == Routine.Cadence.WEEKLY:
        # One period covering the whole week, so there is nothing to cap
        # day by day -- only whether the week has begun at all, and whether
        # the routine was down for the whole of it.
        if began > week_end or week_start > today:
            return []
        if down and all(day in down for day in days_in(week_start) if day <= last):
            return []
        return [week_start]
    return [
        day
        for day in days_in(week_start)
        if began <= day <= last and day not in down
    ]


def habits_in_week(owner, week_start, week_end, today):
    """Every routine this week expected something of, and how it went.

    Routines are included whether or not they are currently active: one
    put down last month still has a history in this week, and dropping it
    would make a paused routine's past disappear. What a *paused* stretch
    should say for itself is slice 7's question, not this function's.

    Two queries rather than one per routine, like `standings_for`.
    """
    routines = list(Routine.objects.filter(owner=owner))
    if not routines:
        return []
    logged = {
        (each.routine_id, each.period_start): each
        for each in RoutineOccurrence.objects.filter(
            owner=owner,
            routine__in=routines,
            period_start__gte=week_start,
            period_start__lte=week_end,
        )
    }
    pauses = {}
    for pause in RoutinePause.objects.filter(owner=owner):
        pauses.setdefault(pause.routine_id, []).append(pause)
    habits = []
    for routine in routines:
        routine_pauses = pauses.get(routine.id, [])
        down = _down_days(routine_pauses, week_start, week_end)
        # A day it was down for but somebody logged into anyway is still
        # reported. A record that exists is never hidden -- dropping it
        # would be the review deciding somebody's history was inconvenient.
        down -= {
            period_start
            for (routine_id, period_start) in logged
            if routine_id == routine.id
        }
        expected = _periods_expected_of(routine, week_start, week_end, today, down)
        if not expected and timezone.localtime(routine.created_at).date() > week_end:
            # It did not exist yet. Absent rather than nought: no data and a
            # zero are different claims, and telling them apart is what this
            # release is for.
            continue
        periods = []
        for period_start in expected:
            occurrence = logged.get((routine.id, period_start))
            periods.append(
                HabitPeriod(
                    period_start=period_start,
                    outcome=(
                        occurrence.outcome
                        if occurrence
                        else RoutineOccurrence.Outcome.OPEN
                    ),
                    progress=occurrence.progress if occurrence else 0,
                    target=(
                        occurrence.target_quantity
                        if occurrence
                        else routine.target_quantity
                    ),
                    unit=occurrence.unit if occurrence else routine.unit,
                )
            )
        habits.append(
            Habit(
                routine=routine,
                periods=periods,
                paused_since=_paused_since(
                    routine_pauses, week_start, week_end, today
                ),
                paused_days=len(down),
            )
        )
    return habits


# The week shown plus the four before it. Five is enough to see a shape and
# few enough to stay a paragraph rather than a chart -- and the six deeper
# questions architecture-trajectory.md §4 names are release F's, not this.
TREND_WEEKS = 5


@dataclass(frozen=True)
class WeekSummary:
    """One row of the trend: two figures, or none at all.

    Null rather than nought where the account has no history yet. A week
    before somebody was using Clarice is not a week in which they planned
    nothing, and the difference between no data and a zero is the thing
    this whole release exists to keep straight.
    """

    week_start: object
    is_shown_week: bool
    planned_met: object = None
    planned_total: object = None
    habits_met: object = None
    habits_expected: object = None


def first_trace_for(owner):
    """The earliest day this owner left any mark, or None if they never have.

    Their first written day, first task, first routine, first captured
    thought. Deliberately not "when the account was created", which
    `accounts.User` cannot answer -- it carries no creation timestamp at
    all -- and which is the weaker question anyway: what a trend needs to
    know is when there was first anything to report, not when a row in the
    users table appeared.

    Four cheap aggregates, run once for the whole trend rather than once
    per week.
    """
    candidates = []
    first_day = (
        DailyEntry.objects.filter(owner=owner).order_by("date").values_list("date", flat=True).first()
    )
    if first_day:
        candidates.append(first_day)
    for queryset in (
        Item.objects.filter(owner=owner),
        Routine.objects.filter(owner=owner),
        Node.objects.filter(owner=owner),
    ):
        first = (
            queryset.order_by("created_at")
            .values_list("created_at", flat=True)
            .first()
        )
        if first:
            candidates.append(timezone.localtime(first).date())
    return min(candidates) if candidates else None


def recent_weeks(owner, shown_week_start, today):
    """The shown week and the four before it, as two figures each.

    No new table and no new record: it is the same `planned_in_week` and
    `habits_in_week` the page already runs, four more times. That is the
    whole of what §8 asks for here, and the deeper analytics stay in
    release F where the charter put them.

    A week whose review was completed reports the figure that review
    recorded rather than a fresh count, so the trend and the headline above
    it can never disagree about the same week on one page.
    """
    trace = first_trace_for(owner)
    recorded = {
        review.week_start: review
        for review in WeeklyReview.objects.filter(
            owner=owner,
            week_start__gte=shown_week_start
            - timedelta(days=DAYS_IN_WEEK * (TREND_WEEKS - 1)),
            week_start__lte=shown_week_start,
            completed_at__isnull=False,
        )
    }
    summaries = []
    for offset in range(TREND_WEEKS - 1, -1, -1):
        week_start = shown_week_start - timedelta(days=DAYS_IN_WEEK * offset)
        week_end = week_start + timedelta(days=DAYS_IN_WEEK - 1)
        is_shown = week_start == shown_week_start
        if trace is None or week_end < trace:
            summaries.append(
                WeekSummary(week_start=week_start, is_shown_week=is_shown)
            )
            continue
        review = recorded.get(week_start)
        if review is not None and review.recorded_planned_total is not None:
            planned_met = review.recorded_planned_met
            planned_total = review.recorded_planned_total
        else:
            planned = planned_in_week(owner, week_start, week_end)
            planned_met, planned_total = len(planned.met), planned.total
        habits = habits_in_week(owner, week_start, week_end, today)
        summaries.append(
            WeekSummary(
                week_start=week_start,
                is_shown_week=is_shown,
                planned_met=planned_met,
                planned_total=planned_total,
                habits_met=sum(habit.met for habit in habits),
                habits_expected=sum(habit.expected for habit in habits),
            )
        )
    return summaries


@dataclass(frozen=True)
class LooseEnds:
    """What is still hanging, in the three ways a thing can hang.

    The review has always answered *what happened* -- completed work, planned
    against met, what was written and captured. It has never answered *what is
    still open*, which is half of what a review is for.

    Three kinds, because they are answered differently: a question wants an
    answer, a proposed commitment wants a yes or a no, and overdue work wants
    doing or dropping.

    Extractive. Every item already exists and already belongs to the person;
    nothing here is proposed and nothing is generated.
    """

    unanswered: list
    unanswered_commitments: object
    overdue: object


def loose_ends(owner, *, today, question_limit=5):
    """Questions, undecided commitments and overdue work — planning-assistant-plan.md 5.

    **Not week-scoped, deliberately**, and the same call `names_worth_confirming`
    already made: a loose end does not become tidy because a Monday passed. What
    is scoped is the count -- `question_limit` keeps the oldest few rather than a
    backlog, since a review that opens with forty questions is the inbox this
    design refuses to be.

    Every definition here is borrowed rather than restated. Unanswered is
    `mind.queries.unresolved_questions`; overdue is `agenda.bucket_for`'s
    boundary, which is strictly *before* today and so excludes work due now.
    Three ideas of "overdue" in one application is how a review comes to
    disagree with the page it summarises.
    """
    unanswered = mind_queries.unresolved_questions(owner)[:question_limit]

    # The one proposal type with no review window and no expiry: it sits
    # forever, costing nothing, and has appeared nowhere until now.
    # `services.commitments_without_tasks` counts a broken invariant, not an
    # unanswered question, so this is not that number by another name.
    # Both sources, or this sees half its domain and looks empty rather than
    # wrong. A facet cites a node *or* a journal entry since increment 2, and
    # filtering on `node__owner` alone silently drops every entry-backed one --
    # ownership therefore has to be asked of whichever source is set.
    #
    # Only the node branch carries liveness: a `DailyEntry` has no deleted or
    # archived state, deliberately, because "I wrote nothing on the 3rd" and "I
    # have never opened the 3rd" are different facts and neither is a deletion.
    commitments = (
        Facet.objects.filter(
            kind=FacetKind.ACTIONABLE,
            confirmed_at__isnull=True,
            retired_at__isnull=True,
        )
        .filter(
            Q(
                node__owner=owner,
                node__deleted_at__isnull=True,
                node__archived_at__isnull=True,
            )
            | Q(entry__owner=owner)
        )
        .select_related("node", "entry")
        .order_by("created_at", "id")
    )

    overdue = (
        Item.objects.filter(
            owner=owner,
            status=Item.Status.ACTIVE,
            due_date__isnull=False,
            due_date__lt=today,
        )
        .select_related("list")
        .order_by("due_date", "id")
    )

    return LooseEnds(
        unanswered=list(unanswered),
        unanswered_commitments=commitments,
        overdue=overdue,
    )


@dataclass(frozen=True)
class Upcoming:
    """What arrives before the next review does."""

    tasks: object
    projects: object


def upcoming_constraints(owner, *, week_end, horizon_days=DAYS_IN_WEEK):
    """Dated work and project deadlines in the week after this one.

    **One week forward, not the whole backlog.** Everything with a date
    eventually arrives; a constraint is what arrives before the next review
    does, and a list that reached further would be a second agenda rather than
    a review section.

    Strictly after `week_end` at the near edge, so nothing already overdue
    appears here -- that is a loose end, and one item belongs in one section.
    The project brief follows the same rule for the same reason: a thing shown
    twice makes a surface untrustworthy about its own contents.
    """
    horizon = week_end + timedelta(days=horizon_days)

    tasks = (
        Item.objects.filter(
            owner=owner,
            status=Item.Status.ACTIVE,
            due_date__gt=week_end,
            due_date__lte=horizon,
        )
        .select_related("list")
        .order_by("due_date", "id")
    )

    # Paused projects are excluded, not only completed ones. Parking a project
    # *is* the statement that it is not pressing, so a section headed "before
    # the next review" that still counted its deadline would make the pause
    # cosmetic — and a pause that changes nothing is not a pause.
    projects = Project.objects.filter(
        owner=owner,
        is_completed=False,
        paused_at__isnull=True,
        due_date__gt=week_end,
        due_date__lte=horizon,
    ).order_by("due_date", "id")

    return Upcoming(tasks=tasks, projects=projects)


def intention_for(owner, day):
    """What this owner said the week containing ``day`` is for, or None.

    None rather than a created row, exactly as `review_for` returns: an unset
    intention is a blank page and not a missing one, and a GET that brought the
    record into existence would be the page view inventing history this module
    opens by refusing.

    Any day of the week resolves to the same record -- that is S9's whole
    point, and the reason `week_start_for` is borrowed rather than a Monday
    being asked of the caller.
    """
    return WeeklyIntention.objects.filter(
        owner=owner, week_start=week_start_for(day)
    ).first()


@dataclass(frozen=True)
class DraftedTask:
    """One proposed task, and whether it serves something the week is for."""

    task: object
    serves_an_outcome: bool

    @property
    def text(self):
        return self.task.text

    @property
    def id(self):
        return self.task.id

    @property
    def due_date(self):
        return self.task.due_date


@dataclass(frozen=True)
class DraftedDay:
    """One day of the drafted week, and whether it holds more than usual."""

    date: object
    tasks: list
    over_committed: bool
    # False when a scenario has taken this day out of the week -- v2 increment
    # 8. The work due on it stays here, because it has not moved; what changed
    # is the day, not the date.
    available: bool = True


@dataclass(frozen=True)
class WeekDraft:
    """A proposed week, and whether it fits.

    Nothing here is committed. A draft is confirmed, edited or discarded, and
    until then not one task has been pinned or re-dated -- `planning-assistant-
    plan.md` increment 6, and the reason `draft_week` lives in this module and
    not in services.
    """

    week_start: object
    intention: str
    proposed: list
    routines: list
    # The same work, laid out on the days it is already due -- v2 increment 7.
    # `proposed` stays the flat list, because overdue work appears there and
    # deliberately on no day at all.
    days: list
    # What a typical day of this person's holds, measured once for the week.
    typical_day: int | None
    # Work dated onto days a scenario removed -- v2 increment 8. Named rather
    # than moved: saying "Thursday is gone" is a question about the week, not
    # permission to re-date what was due on it.
    displaced: list
    typical_week: int | None
    over_committed: bool


# How far back to look for a typical week, and how little evidence is too
# little. Eight weeks is two months of practice: fewer than two of them with a
# plan in is not a pattern, it is a fortnight.
#
# The first sentence said "four weeks is a month" beside a constant of eight
# from the day this landed (`ab0c7ab`) -- born mismatched rather than drifted,
# and corrected in favour of the code, which is the half that was doing
# anything. The second sentence is about the sample floor and was always right.
TYPICAL_WEEK_LOOKBACK = 8
TYPICAL_WEEK_MINIMUM_SAMPLE = 2


def typical_week_for(owner, before):
    """How much this person finishes in a week they planned, or None.

    **D2's decision, computed.** Capacity comes from what already happened
    rather than from estimates nobody would enter, so there is nothing to
    maintain and nothing to go unentered. `DailyFocus` records what was pinned
    and the task records what was finished; the vision document requires that
    denominator be captured at the moment of choosing precisely because it
    cannot be reconstructed afterwards.

    **Weeks nobody planned are excluded, not counted as zero.** A week with no
    plan is not a week that finished nothing, and averaging it in would drag
    the figure toward a number nobody lived -- the null-not-zero discipline
    `review/reads.py` already holds everywhere else.

    **The median, not the mean.** One heroic week and one lost to flu should
    not move what a typical week looks like, and a planner is exactly where an
    outlier would do damage.

    None below `TYPICAL_WEEK_MINIMUM_SAMPLE` planned weeks. "No evidence yet"
    and "you have room" call for opposite responses, and only one of them is
    honest with a fortnight of history.
    """
    met_counts = []
    for index in range(1, TYPICAL_WEEK_LOOKBACK + 1):
        start = week_start_for(before - timedelta(weeks=index))
        planned = planned_in_week(owner, start, week_end_for(start))
        if planned.total == 0:
            continue
        met_counts.append(len(planned.met))

    if len(met_counts) < TYPICAL_WEEK_MINIMUM_SAMPLE:
        return None
    met_counts.sort()
    return met_counts[len(met_counts) // 2]


def draft_week(owner, week_start, *, today, unavailable=()):
    """What next week could hold, and whether it holds it — increment 6.

    **Deterministic by an explicit trade.** `design-concept.md` chose
    predictable and unit-testable over adaptive and opaque for exactly this
    surface: rule-based selection and date arithmetic, no model. D1 settled
    that this assistant ships no generation, and a planner is where that would
    have been most tempting.

    **It proposes only work that already carries a date.** Overdue first,
    because a thing already late is the strongest claim on a week, then what is
    dated into the week itself. The someday pile is left alone: pulling from it
    would be the planner deciding something the person has not, which is the
    one thing every producer in this design refuses to do.

    **Routines are named apart from tasks**, because they are a different life
    cycle and folding them into one list is the misuse
    `daily-operating-system-vision.md` calls out by name -- a routine is
    measured toward a quantity over a period and never spawns a task.

    Writes nothing. A draft is a proposal: nothing is pinned, nothing is
    re-dated, and opening the planner twice changes nothing either time.

    **`unavailable` is the whole of scenario planning** — v2 increment 8.
    *"What if I only have three productive days?"* and *"make Thursday
    meeting-free"* are the same question with different arguments, and the
    answer is this function run again with a set of days removed. It contains
    no model, which is the point: what will feel most like an assistant is a
    deterministic read taking a parameter, and it is available at all only
    because this function has never written anything.

    **A scenario cannot move work.** A day being removed does not re-date what
    was due on it; that work is reported as `displaced` and stays on its own
    date, and where it actually goes is decided by a person through the task
    itself. Nothing about a scenario is stored: a what-if that persisted would
    be a plan somebody has to undo.
    """
    week_end = week_end_for(week_start)
    intention = intention_for(owner, week_start)

    overdue = list(
        Item.objects.filter(
            owner=owner,
            status=Item.Status.ACTIVE,
            due_date__isnull=False,
            due_date__lt=today,
        ).order_by("due_date", "id")
    )
    dated = list(
        Item.objects.filter(
            owner=owner,
            status=Item.Status.ACTIVE,
            due_date__gte=max(today, week_start),
            due_date__lte=week_end,
        ).order_by("due_date", "id")
    )

    typical = typical_week_for(owner, today)
    proposed = overdue + dated

    # **Measured once for the whole week.** What a typical day holds is a fact
    # about the person rather than about a date in the future, and asking per
    # day would cost thirty queries seven times over -- see the cost test on
    # `typical_day_for`. Asked of `today`, which is the only day there is
    # evidence up to.
    typical_day = daily_reads.typical_day_for(owner, today)
    outcome_projects = {
        outcome.project_id
        for outcome in outcomes_for(owner, week_start)
        if outcome.project_id is not None
    }

    def drafted(task):
        return DraftedTask(
            task=task,
            serves_an_outcome=(
                task.list is not None and task.list.project_id in outcome_projects
            ),
        )

    # **Only work already dated into the week gets a day.** Overdue tasks stay
    # in `proposed` and land on no day at all: putting a late thing on Tuesday
    # would be re-dating it, which is the one move this function promises never
    # to make. Where it goes is the person's decision, made through the task.
    #
    # All seven days, empty ones included. An empty day is information -- it is
    # where anything being moved would go -- and a week that showed only its
    # busy days would be answering a different question.
    gone = set(unavailable)
    by_day = {}
    for task in dated:
        by_day.setdefault(task.due_date, []).append(drafted(task))
    days = []
    displaced = []
    for offset in range(DAYS_IN_WEEK):
        day = week_start + timedelta(days=offset)
        on_it = by_day.get(day, [])
        available = day not in gone
        if not available:
            displaced.extend(on_it)
        days.append(
            DraftedDay(
                date=day,
                tasks=on_it,
                available=available,
                # Stated, never scolded, and absent entirely without evidence:
                # null is not zero, and flagging every day from no history
                # would be a verdict drawn from nothing.
                # A day somebody has removed is not holding too much; it is
                # not holding anything. Saying both would be noise about two
                # different problems.
                over_committed=(
                    available
                    and typical_day is not None
                    and len(on_it) > typical_day
                ),
            )
        )

    return WeekDraft(
        week_start=week_start,
        intention=intention.text if intention else "",
        proposed=proposed,
        # `routines.reads`, not a filter written here. "Active" is that
        # domain's word and it already has one definition; a second would
        # disagree the first time pausing changed meaning.
        routines=routine_reads.active_routines_for(owner),
        days=days,
        typical_day=typical_day,
        displaced=displaced,
        typical_week=typical,
        # Stated, never scolded: this says the week holds less than this, not
        # that the person is failing. `daily-operating-system-vision.md` asks
        # that history be useful without making missed work feel punishing, and
        # a planner is the surface most able to break that.
        over_committed=typical is not None and len(proposed) > typical,
    )


def planning_session_for(owner, day):
    """This owner's planning session for the week containing ``day``, or None.

    None rather than a created row, exactly as `review_for` and
    `intention_for` both return. A read that brought the record into existence
    would make every page load a planning session and destroy the only number
    the model exists to produce.
    """
    return PlanningSession.objects.filter(
        owner=owner, week_start=week_start_for(day)
    ).first()


# How long a project has to sit still before the check-in asks about it. Five
# weeks is the plan's own example and is deliberately longer than a month: work
# that pauses over a holiday should not be met with a question about whether it
# is still real.
QUIET_PROJECT_DAYS = 35


@dataclass(frozen=True)
class ProjectToConfirm:
    """One project, and whether it looks like it is still being worked on."""

    project: object
    quiet_for_days: int
    looks_active: bool


def projects_to_confirm(owner):
    """Open projects, quietest first — v2 increment 4's check-in.

    **The check-in states this rather than asking it.** A session that opened
    by asking which projects are active would be asking for something already
    recorded, which the plan names as the failure mode of a questionnaire.

    **Movement is creation or completion**, whichever is more recent. A project
    whose last act was finishing something was being worked on just as much as
    one that gained a task, and counting only new work would call a project
    quiet in the week somebody cleared it.

    **A project with no tasks is judged by its own age**, because that is the
    only evidence there is. One made this morning is not stale; one made two
    months ago and never filled is exactly what this should ask about.

    Paused and completed projects are left out: both have already been
    answered, and asking again would make those states worth nothing.

    Quietest first, because this list is a question and the rows needing an
    answer are the ones that have not moved. Sorting the active ones up would
    bury them.
    """
    now = timezone.now()
    found = []
    for project in Project.objects.filter(
        owner=owner, is_completed=False, paused_at__isnull=True
    ):
        stamps = []
        for created, completed in Item.objects.filter(
            list__project=project
        ).values_list("created_at", "completed_at"):
            stamps.append(created)
            if completed is not None:
                stamps.append(completed)
        # The project's own age is the fallback and not another candidate. It
        # can never be later than a task inside it, so including it always
        # would change nothing in production and mask the empty-project case in
        # any test that backdates a task without backdating its project — which
        # is exactly how this was first written, and how it disagreed with the
        # paragraph above while passing.
        quiet_for = (now - (max(stamps) if stamps else project.created_at)).days
        found.append(
            ProjectToConfirm(
                project=project,
                quiet_for_days=quiet_for,
                looks_active=quiet_for < QUIET_PROJECT_DAYS,
            )
        )
    found.sort(key=lambda each: (-each.quiet_for_days, each.project.id))
    return found


def outcomes_for(owner, day):
    """What this owner decided would be true by the end of that week.

    In the order they were chosen, which is the order they are shown. A list
    rather than a queryset, matching every other read here that a serialiser
    walks twice.
    """
    return list(
        WeeklyOutcome.objects.filter(
            owner=owner, week_start=week_start_for(day)
        ).select_related("project")
    )


# How many candidates the check-in offers. Five, matching the review's other
# queues -- a ritual that opens with nine choices is the pile of work this step
# exists to replace. **The cap is on what is shown and never on how many
# outcomes somebody may choose**; how much a week can hold is theirs to decide,
# and the draft further down already says what a typical week holds.
OUTCOME_PROPOSAL_LIMIT = 5


@dataclass(frozen=True)
class OutcomeProposal:
    """A project the week has a reason to be about, and the reason.

    `because` is a list of stated facts rather than a score: a deadline, work
    already dated into the week. `suggested_text` is the project's *own* words
    -- its `desired_outcome`, or failing that its title -- because D1 defers
    composed prose and a rephrasing of somebody's own sentence would be the
    least defensible generation in this plan.
    """

    project: object
    suggested_text: str
    because: list


def outcomes_worth_proposing(owner, week_start):
    """Projects this week has a reason to be about — increment 5.

    Two reasons qualify, and both are checkable facts rather than judgements:
    a deadline inside the week, and work already dated into it. A project with
    neither is not this week's, and offering every project would be the pile of
    choices the ritual replaces.

    Paused and completed projects are excluded, as everywhere else -- both have
    been answered. So is one already chosen for this week: offering it again is
    the surface asking a question it holds the answer to.

    Soonest deadline first, then by id, so the ordering is stable and none of it
    is a ranking.
    """
    week_end = week_end_for(week_start)
    already = set(
        WeeklyOutcome.objects.filter(
            owner=owner, week_start=week_start, project__isnull=False
        ).values_list("project_id", flat=True)
    )

    found = []
    for project in Project.objects.filter(
        owner=owner, is_completed=False, paused_at__isnull=True
    ).exclude(pk__in=already):
        because = []
        if project.due_date and week_start <= project.due_date <= week_end:
            because.append(f"Due {project.due_date}")
        dated = Item.objects.filter(
            owner=owner,
            list__project=project,
            status=Item.Status.ACTIVE,
            due_date__gte=week_start,
            due_date__lte=week_end,
        ).count()
        if dated:
            because.append(
                f"{dated} {'task' if dated == 1 else 'tasks'} already dated for it"
            )
        if not because:
            continue
        found.append(
            OutcomeProposal(
                project=project,
                # The person's words, never this module's.
                suggested_text=project.desired_outcome or project.title,
                because=because,
            )
        )

    found.sort(
        key=lambda each: (
            each.project.due_date is None,
            each.project.due_date or week_end,
            each.project.id,
        )
    )
    return found[:OUTCOME_PROPOSAL_LIMIT]


@dataclass(frozen=True)
class Blocker:
    """An open question standing in the way of something the week is for.

    `outcome` is the evidence for calling it a blocker at all -- without it
    this is a list of questions with an adjective attached. `question` carries
    how long it has been open and which later notes came back to it, from the
    read that has waited since increment 1 for a caller willing to pay for it.
    """

    question: object
    outcome: object


def blockers_for(owner, day, *, now):
    """Open questions bearing on this week's chosen outcomes — increment 6.

    **Defined against the outcomes, never "every open question".** That is what
    increment 5 bought by putting the choosing first: a question is a blocker
    because it stands in the way of something specific, and a week with nothing
    chosen has nothing to block. The loose-ends list on the review still shows
    the oldest few unconditionally; this is a different claim about a smaller
    set.

    **The retrieval is `material_bearing_on`**, the same rare-term gate the
    project brief anchors on, asked of the outcome's own words. A question that
    shares only common vocabulary is not a blocker, and a panel built on plain
    topical similarity is the one `detectors/__init__` rejects.

    Each question appears once even when it bears on two outcomes: a thing
    shown twice makes a surface untrustworthy about its own contents, which is
    the rule `brief_for` and `upcoming_constraints` already keep. The first
    outcome that reaches it is the one named.

    **Reading this writes nothing**, and that is what makes it safe from a
    second surface. A question carries no review window -- nothing expires and
    nothing ripens -- where a proposal is stamped when it is shown. Only the
    proposals make "where does the ritual live" a real question.
    """
    open_ids = {node.pk for node in mind_queries.unresolved_questions(owner)}
    if not open_ids:
        return []

    found = []
    seen = set()
    for outcome in outcomes_for(owner, day):
        for material in mind_queries.material_bearing_on(owner, outcome.text):
            node = material.node
            if node.pk not in open_ids or node.pk in seen:
                continue
            seen.add(node.pk)
            found.append(
                Blocker(
                    question=mind_queries.context_for_question(owner, node, now=now),
                    outcome=outcome,
                )
            )
    return found


@dataclass(frozen=True)
class Carryover:
    """One piece of overdue work, and whether it serves a chosen outcome."""

    task: object
    serves_an_outcome: bool


def carryover_for(owner, day, *, today):
    """Overdue work, the ones serving this week's outcomes first — increment 6.

    **Ordered, never filtered.** A leftover connected to nothing chosen is
    exactly the row most worth deciding about, so everything stays and the
    connected ones rise. Hiding the rest would turn triage into a backlog
    nobody looks at, which is the failure this step exists to prevent.

    Connection is by project, which is the only link a task and an outcome
    actually share: an outcome chosen from a project carries that project, and
    a task belongs to an area that belongs to one. Sorting is stable within
    each group, so the agenda's own order survives underneath.

    Overdue is `agenda.bucket_for`'s boundary via `loose_ends`, and not a
    fourth idea of the word.
    """
    projects = {
        outcome.project_id
        for outcome in outcomes_for(owner, day)
        if outcome.project_id is not None
    }
    found = [
        Carryover(
            task=task,
            serves_an_outcome=(
                task.list is not None and task.list.project_id in projects
            ),
        )
        for task in loose_ends(owner, today=today).overdue
    ]
    found.sort(key=lambda each: not each.serves_an_outcome)
    return found
