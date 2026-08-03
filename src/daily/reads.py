"""Read-side logic for the daily domain.

Query and derivation only; every mutation lives in daily.services. Split
from the first slice per architecture-trajectory.md §4 rule 4, which is the
one charter rule that is about where code goes rather than what a table
holds -- and the reason it is a rule is that `lists` got this right and it
has stayed right.
"""
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
