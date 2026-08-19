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

from daily.models import DailyEntry, DailyFocus
from mind import queries as mind_queries
from mind.models import Facet, FacetKind, Node
from lists.models import Item, Project
from review.models import WeeklyReview
from review.weeks import DAYS_IN_WEEK, days_in, week_end_for, week_start_for
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

    projects = Project.objects.filter(
        owner=owner,
        is_completed=False,
        due_date__gt=week_end,
        due_date__lte=horizon,
    ).order_by("due_date", "id")

    return Upcoming(tasks=tasks, projects=projects)
