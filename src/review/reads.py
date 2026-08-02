"""Read-side logic for the weekly review.

Query and derivation only. There is no `review.services` yet because slice 1
writes nothing at all -- the module arrives with the first record, at slice
4, rather than being created empty to satisfy a rule. What charter rule 4
actually asks for is that reads and writes never share a home, and a review
that reads is the strictest possible case of it: **this module must not
write.** The routines domain creates its occurrences lazily, so a review
that touched one in order to describe it would be a page view inventing
history. `test_reading_a_week_writes_nothing` holds that as a statement
about executed SQL rather than about intent.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import F
from django.utils import timezone

from daily.models import DailyFocus
from lists.models import Item
from review.weeks import week_end_for, week_start_for


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
            list__owner=owner,
            completed_at__gte=start,
            completed_at__lt=end,
        )
        .select_related("parent")
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
        .select_related("task", "task__parent", "entry")
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
