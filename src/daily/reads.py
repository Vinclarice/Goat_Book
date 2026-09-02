"""Read-side logic for the daily domain.

Query and derivation only; every mutation lives in daily.services. Split
from the first slice per architecture-trajectory.md §4 rule 4, which is the
one charter rule that is about where code goes rather than what a table
holds -- and the reason it is a rule is that `lists` got this right and it
has stayed right.
"""
from calendar import monthrange
from collections import Counter
from dataclasses import dataclass
from datetime import date as date_type, timedelta

from django.contrib.postgres.search import SearchRank
from django.db.models import F

from clarice.search import to_query
from daily.models import DailyEntry, DailyFocus
from lists import agenda
from money import reads as money


# Which of the agenda's buckets a day surfaces: what is late, and what is
# due. Later and Someday are a backlog rather than a plan for the day, and
# putting them here would make the Daily Page another agenda.
#
# Written out rather than reusing lists.agenda.DIGEST_BUCKETS, which happens
# to hold the same two keys today. That constant answers "what does the
# morning email mention"; this one answers "what does a day show". Sharing
# it would mean a change to the email silently redesigning the Daily Page.
# What is *not* duplicated is the rule underneath -- which bucket a due date
# falls into stays lists.agenda.bucket_for's decision, and only its.
DAY_BUCKETS = (agenda.OVERDUE, agenda.TODAY)


def entry_for(owner, day):
    """This owner's entry for ``day``, or None if they have not written one.

    Owner-scoped in the query rather than checked afterwards: a read that
    fetches by date and then compares owners is one forgotten comparison
    away from serving somebody else's day.
    """
    return DailyEntry.objects.filter(owner=owner, date=day).first()


def search_entries(owner, text):
    """This owner's days matching `text`, best first.

    `design/search-plan.md` slice 1, and the read the trigger actually fired
    on. Before this a day was reachable only by knowing its date, and there is
    no date picker -- so an entry from three weeks ago was, in practice, gone.

    Owner-scoped in the query for the reason `entry_for` states above, and more
    so: a journal is the most private material this application holds, and a
    read that filters afterwards is one forgotten comparison from serving it to
    the wrong person.

    Ties break by recency rather than by nothing. The same phrase on several
    days is ordinary in a journal, and an unstable order there means the same
    search puts a different day first each time it runs.
    """
    query = to_query(text)
    if query is None:
        return DailyEntry.objects.none()

    return (
        DailyEntry.objects.filter(owner=owner, search_document=query)
        .annotate(rank=SearchRank(F("search_document"), query))
        .order_by("-rank", "-date")
    )


def action_items_for(owner, day):
    """This owner's open tasks that ``day`` has a claim on -- late, then due.

    The agenda's own query and the agenda's own bucketing, called at display
    time. Nothing is copied onto the Daily Entry and nothing is cached: the
    day shows the task, so completing one anywhere shows up here with no
    reconciliation step. See daily-operating-system-vision.md, "The Daily
    Page is a lens over durable records, not a new place to copy them."

    ``day`` is injected rather than read from the clock, so a page for the
    1st and a page for the 5th can disagree about the same task -- which is
    the correct answer, not a quirk.

    **Bills are not here, and are still on the day.** They left this list on
    August 31, 2026 and arrive in the payload's own ``bills`` array instead:
    `bill-as-a-model-plan.md` decision 4 keeps them on the surfaces where
    paying is a real thing to do, while the model split stops them being
    tasks. No parameter, because both callers want the same answer -- see
    `draft_day`, which wants it for a second reason.
    """
    grouped = agenda.bucketed(
        agenda.open_items_for(owner), day
    )
    return [item for key in DAY_BUCKETS for item in grouped[key]]


@dataclass(frozen=True)
class DayBrief:
    """What changed since yesterday, and nothing that merely *is*.

    The awareness half of the daily brief. Its whole contract is **change, not
    state**, which is what keeps it from becoming the dashboard the
    destination refuses -- so every list here is deliberately something the Day
    page does not already show. Overdue work is on the page; the fact that you
    *chose* one of them yesterday is not.

    **Three lists, never one ordering.** A slipped commitment against a bill
    against a quiet project is `SearchRank` over two document sets again: a
    number that does not exist as relevance, failing silently.

    **Reading 4 is absent**, and honestly so. *Where intention and attention
    disagree* needs the temporal substrate, and nothing here pretends to it.
    """

    #: Pins from yesterday that were neither finished nor released.
    slipped: list
    #: Tasks inside their own lead time -- until now this existed only in the
    #: digest, so it was invisible to anybody reading the day itself.
    coming: list
    #: Projects nothing has moved for long enough to be worth a question.
    gone_quiet: list

    @property
    def has_anything(self):
        """Whether there is anything to read.

        Short or absent is the correct output: a brief that filled three
        sections every morning would be skipped by the end of the week.
        """
        return bool(self.slipped or self.coming or self.gone_quiet)


def brief_for(owner, day, *, today):
    """What changed since yesterday, for a day being lived.

    Nothing for a day already lived, the refusal `draft_day` and
    `closing_for` both make: telling somebody what changed on a day they have
    finished is a verdict rather than a brief.
    """
    from lists import agenda as lists_agenda
    from review import reads as review_reads

    if day != today:
        return DayBrief(slipped=[], coming=[], gone_quiet=[])

    yesterday = day - timedelta(days=1)
    # `planned_in_week` for a one-day window, the same borrowing
    # `typical_day_for` and the closing ritual do -- what counts as finished
    # and what a released pin means are its calls and only its.
    slipped = review_reads.planned_in_week(owner, yesterday, yesterday).unfinished
    return DayBrief(
        slipped=slipped,
        coming=lists_agenda.coming_up_for(owner, day),
        # **Only the ones that are actually quiet.** `projects_to_confirm`
        # returns every open project, quietest first, because the weekly
        # check-in is a review of all of them. A brief that listed every
        # project every morning would be the dashboard this refuses, so the
        # ones still moving are dropped -- `looks_active` is the read's own
        # judgement of that and is not re-decided here.
        gone_quiet=[
            row
            for row in review_reads.projects_to_confirm(owner)
            if not row.looks_active
        ],
    )


@dataclass(frozen=True)
class CalendarDay:
    """One square of the month.

    Counts and a flag rather than the rows themselves: a month is for choosing
    a day to open, and shipping every task on every date would be the Day page
    thirty-one times over.
    """

    date: date_type
    #: Open tasks due on this date. The agenda's own definition of open, not a
    #: second one -- a calendar that kept counting completed work would show a
    #: month that never empties.
    due: int
    #: Whether the day has words in it. A `DailyEntry` row exists as soon as
    #: anything is pinned, so an empty one is the ordinary state of a planned
    #: day rather than something written -- the same call `written_in_week`
    #: makes for the review.
    written: bool


def month_for(owner, day):
    """The month containing ``day``, and what each of its dates holds.

    S13's second require: `/app/day/:date` has had no UI entry point at all,
    so reaching a day twelve weeks back meant clicking "the week before"
    twelve times.

    **A view over what is already there.** Two queries over rows that exist.
    The calendar that carries *events* is later work and needs a model this
    does not; routines are deferred by name here because they are measured
    over a period rather than due on a date. **Bills are counted**, and were
    before they had a model of their own -- see the comment below, which is
    the correction of what this paragraph used to claim.

    **Any day of the month addresses the same month**, the courtesy
    `intention_for` gives a week -- a client that had to know which day a month
    starts on would hold a second definition of the calendar.
    """
    first = day.replace(day=1)
    last = first.replace(day=monthrange(first.year, first.month)[1])

    due = Counter(
        agenda.open_items_for(owner)
        .filter(due_date__gte=first, due_date__lte=last)
        .values_list("due_date", flat=True)
    )
    # **Bills, counted deliberately rather than by accident.** They were in
    # this figure before increment 4 of bill-as-a-model-plan.md because a bill
    # was a task with a due date and this asks for tasks with due dates -- so
    # the split would have quietly emptied it. A day with rent due is a day
    # with something on it, which is decision 4 on the surface that shows
    # thirty-one days at once.
    due.update(
        money.open_bills_for(owner)
        .filter(due_date__gte=first, due_date__lte=last)
        .values_list("due_date", flat=True)
    )
    written = {
        entry.date
        for entry in DailyEntry.objects.filter(
            owner=owner, date__gte=first, date__lte=last
        )
        if entry.intentions.strip()
        or entry.gratitude.strip()
        or entry.happenings.strip()
    }
    return [
        CalendarDay(
            date=first + timedelta(days=offset),
            due=due.get(first + timedelta(days=offset), 0),
            written=(first + timedelta(days=offset)) in written,
        )
        for offset in range((last - first).days + 1)
    ]


# When the day stops being something to plan and starts being something to
# record. Named here rather than scattered, the same call `DIGEST_HOUR` makes
# for the morning -- and read in the owner's own zone, so "evening" means
# theirs rather than the server's.
#
# Six is early enough to catch somebody before the evening gets away and late
# enough that it is not still the working day. One threshold and no per-user
# setting, because a preference nobody has asked for is a decision deferred
# rather than made.
CLOSING_HOUR = 18


@dataclass(frozen=True)
class DayClosing:
    """What the day held, at the point of writing it down.

    Counts rather than lists: the ask is for the record, and a closing prompt
    that re-listed the day would be the page somebody already read.
    """

    #: Planned commitments still standing -- the denominator S6 rests on.
    chosen: int
    finished: int
    unfinished: int
    #: Deliberately taken off. Outside `chosen` entirely, because deciding on
    #: Wednesday that something is not for today is a decommitment and
    #: counting it as a failure would be the product disagreeing with a
    #: decision somebody made.
    released: int


def closing_for(owner, day, *, today, hour):
    """Whether to ask for the day's record, and what to say while asking.

    S5's missing half. `DailyEntry.happenings` and `DailyFocus` were already
    good; nothing ever asked.

    **Only for today, and only in the evening.** A prompt on a past day would
    ask somebody to reconstruct one, and the record is worth reading in six
    months precisely because it was written while it was still true. A day
    nobody answered closes unclosed, which is itself a fact -- `DailyEntry` has
    no deleted or archived state for the same reason.

    **It stops once the record exists.** The ask is for the writing, so a
    prompt that stayed after it would be nagging about something done.

    **The counts are `planned_in_week`'s, for a one-day window** -- the same
    borrowing `typical_day_for` does, because D2 is explicit that two
    definitions of "what I got through" would drift. Safe on a day in progress
    because that read judges against the window's *end*: with the window
    ending today, finished-today counts as met and released-today as set
    aside, which is exactly "so far".
    """
    if day != today or hour < CLOSING_HOUR:
        return None
    return closing_summary_for(owner, day)


def closing_summary_for(owner, day):
    """What the day held, or None once the record exists.

    Split out of `closing_for` so the evening mail and the page ask the same
    question. The page's gate is *today, and evening*; the mail's is the
    scheduler's own window, which has already decided both by the time it
    composes. What neither may decide twice is what the day held and whether
    it has already been written -- so that lives here.
    """
    entry = entry_for(owner, day)
    if entry is not None and entry.happenings.strip():
        return None
    from review import reads as review_reads

    planned = review_reads.planned_in_week(owner, day, day)
    return DayClosing(
        chosen=planned.total,
        finished=len(planned.met),
        unfinished=len(planned.unfinished),
        released=len(planned.set_aside),
    )


@dataclass(frozen=True)
class DayDraft:
    """What today could hold, and whether it holds it.

    Named apart from `review.reads.DraftedDay`, which is a *week's* view of one
    of its days and carries different fields. Two shapes, two names.
    """

    #: What a typical day finishes, or None below the evidence floor.
    typical: int | None
    #: What the draft would pin, in the agenda's own order. Empty when there is
    #: no capacity to justify a number, and empty on a day already lived.
    proposed: list
    #: How many tasks have a claim on the day in total, pinned or not, so a
    #: surface can say "two of nine" rather than quietly showing two.
    available: int


def draft_day(owner, day, *, today):
    """Propose what to commit to today. Writes nothing.

    **Not a new planner.** The selection is `action_items_for` -- the agenda's
    own query and bucketing, late then due -- and the capacity is
    `typical_day_for`. D2 is explicit that the daily grain is the same
    computation as the weekly one, and two definitions of "what I got through"
    would drift; nothing here counts, buckets or dates anything of its own.

    **It proposes and never pins.** `draft_week`'s rule, and for a sharper
    reason at this grain: `DailyFocus` records what a person *chose*, which is
    the one thing almost no competitor stores, and a focus pinned by the system
    would quietly turn the finish rate into a measure of how good the draft is.
    That is not reconstructible afterwards.

    **No capacity, no proposal.** `typical_day_for` answers `None` rather than
    zero below its floor, because "no evidence yet" and "you have room" call
    for opposite responses -- so a draft with no figure proposes nothing rather
    than proposing a number it cannot justify.

    **What is already chosen is subtracted, not added to.** Proposing on top of
    a day somebody has already filled would make this an argument for
    over-committing rather than a check on it.

    **Nothing for a day already lived.** The same refusal `typical_day_for`
    makes by excluding the day being planned from its own evidence: telling
    somebody what they should have done is a verdict, not a plan.

    **And nothing about bills**, which `action_items_for` no longer returns.
    That is not only decision 4 arriving here by inheritance: a pin is a
    `DailyFocus` with a foreign key to `Item`, so a bill that is not an
    `Item` cannot be pinned at all. Proposing one would be offering a verb the
    model has taken away. Paying is the verb a bill has, and the day offers it
    on the bill's own row.
    """
    available = action_items_for(owner, day)
    typical = typical_day_for(owner, day)
    if typical is None or day < today:
        return DayDraft(typical=typical, proposed=[], available=len(available))
    chosen = {focus.task_id for focus in focus_for(owner, day)}
    room = typical - len(chosen)
    unchosen = [task for task in available if task.id not in chosen]
    return DayDraft(
        typical=typical,
        proposed=unchosen[: room] if room > 0 else [],
        available=len(available),
    )


def focus_for(owner, day):
    """What this owner has deliberately chosen for ``day``, in their order.

    Released pins are excluded: they are history for Crane 3's review to
    read, not work still on the page. A read that wants them -- to tell a
    decommitment from an unfinished commitment -- should ask for them
    explicitly rather than filter this one, so that the page can never show
    a pin somebody took off.
    """
    return list(
        DailyFocus.objects.filter(
            owner=owner, entry__date=day, released_at__isnull=True
        ).select_related("task", "task__list")
    )


# How far back a day's capacity looks, and how little evidence is too little.
# Thirty days is D2's own window; five planned days is a working week's worth
# of practice, and fewer than that is not a pattern.
#
# Deliberately not derived from review.reads' week-grain constants. Those
# answer "how many weeks make a habit"; these answer "how many days make one",
# and tying them together would mean a change to the review's planner silently
# redesigning the Daily Page -- the same reasoning DAY_BUCKETS gives above for
# not reusing DIGEST_BUCKETS.
TYPICAL_DAY_LOOKBACK = 30
TYPICAL_DAY_MINIMUM_SAMPLE = 5


def typical_day_for(owner, before):
    """How much this person finishes on a day they planned, or None — S3.

    **The rule underneath is borrowed and not re-decided.** What counts as
    finished, what a released pin means, and the judging-at-the-window's-end
    discipline are all `review.reads.planned_in_week`'s, asked here for a
    single day. D2 is explicit that the daily grain is the same computation as
    the weekly one and that two definitions of "what I got through" would
    drift; this is that instruction, so the only thing decided here is the
    window.

    **Days nobody planned are skipped, not counted as zero.** A day with no
    plan is not a day that finished nothing, and averaging it in would drag
    the figure toward a number nobody lived. Thirty days will contain plenty
    of them — weekends, days off, days that got away — which is exactly why
    this iterates days rather than running one query over a range.

    **The median, not the mean.** One heroic Thursday and one lost to flu
    should not move what a typical day looks like, and a planner is where an
    outlier would do the most damage. Its convention matches
    `typical_week_for`'s — the upper of the two middles on an even sample —
    because two capacity figures on one product rounding different ways is a
    difference somebody would eventually have to explain.

    **None below the sample floor**, never zero: "no evidence yet" and "you
    have room" call for opposite responses, and only one of them is honest
    with a fortnight of history.

    Strictly before ``before``, so the day being planned is never its own
    evidence — a figure that moved as somebody pinned would be measuring the
    plan rather than the person.
    """
    # Imported here rather than at module scope: review.reads imports
    # daily.models, and a module-level import back would make the two packages
    # import-order dependent for no gain. The same shape mind.queries uses for
    # its detector import.
    from review.reads import planned_in_week

    met_counts = []
    for index in range(1, TYPICAL_DAY_LOOKBACK + 1):
        day = before - timedelta(days=index)
        planned = planned_in_week(owner, day, day)
        if planned.total == 0:
            continue
        met_counts.append(len(planned.met))

    if len(met_counts) < TYPICAL_DAY_MINIMUM_SAMPLE:
        return None
    met_counts.sort()
    return met_counts[len(met_counts) // 2]
