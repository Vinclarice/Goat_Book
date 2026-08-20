"""Read-side logic for the daily domain.

Query and derivation only; every mutation lives in daily.services. Split
from the first slice per architecture-trajectory.md §4 rule 4, which is the
one charter rule that is about where code goes rather than what a table
holds -- and the reason it is a rule is that `lists` got this right and it
has stayed right.
"""
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.postgres.search import SearchRank
from django.db.models import F

from clarice.search import to_query
from daily.models import DailyEntry, DailyFocus
from lists import agenda


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
    """
    grouped = agenda.bucketed(agenda.open_items_for(owner), day)
    return [item for key in DAY_BUCKETS for item in grouped[key]]


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
