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
from datetime import datetime, timedelta

from django.db.models import F
from django.utils import timezone

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
