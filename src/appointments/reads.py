"""Read-side logic for appointments.

Query and derivation only; every mutation is in `appointments.services`. Split
from the first slice per `architecture-trajectory.md` §4 rule 4 -- the one
charter rule about where code goes rather than what a table holds.

**Four surfaces read this and none of them owns it**: the day's strip, the
pool's fixed lines, the calendar as a fourth source, and the day's log when a
start has passed. That is rule 5 -- reference, never copy -- and the reason
these are queries rather than something written onto `DailyEntry`.
"""
from datetime import timedelta

from django.db.models import Q

from appointments.models import Appointment


def live(owner):
    """Everything this owner has written down and not deleted.

    **Cancelled ones are here**, which is the one thing to know about this
    read: rule 6 keeps a cancelled appointment visible on its day, struck. A
    surface that wants only what is still happening filters on `cancelled_at`
    itself, and each says why -- the day strip shows both, the log shows
    neither.

    Owner-scoped in the query rather than checked afterwards, per
    `principles.md`: a read that fetches and then compares is one forgotten
    comparison from serving somebody else's diary.
    """
    return Appointment.objects.filter(owner=owner, deleted_at__isnull=True)


def on_day(owner, day):
    """Everything covering ``day``, cancelled ones included.

    **Every day of its span, not only the first.** *Dutch Wonderland, the 5th
    to the 6th* is on the page for the 6th too, which is the whole reason the
    record is a span rather than an instant.

    `ends_on` is null for a one-day thing, so the second clause is what makes
    that case work rather than an oversight -- `last_day` says the same thing
    in Python and this says it in SQL.
    """
    return live(owner).filter(
        Q(starts_on__lte=day)
        & (Q(ends_on__gte=day) | (Q(ends_on__isnull=True) & Q(starts_on=day)))
    )


#: How far ahead the day's strip and the pool's fixed lines look. A week,
#: matching `lists.agenda.WEEK_HORIZON_DAYS`, because *what is coming up* means
#: the same stretch of time whether the thing coming up is a task with a due
#: date or a Tuesday afternoon at the dentist. Read from there rather than
#: restated, so the two cannot drift.
def coming_up(owner, today, *, days=None):
    """What is ahead, soonest first, and nothing that has started.

    Strictly after today: what is happening *today* is the strip's other half,
    and a surface that showed one thing in both places would be saying it
    twice. Cancelled ones are dropped -- a strip of what is coming is a plan,
    and a plan does not include something called off.
    """
    from lists.agenda import WEEK_HORIZON_DAYS

    horizon = WEEK_HORIZON_DAYS if days is None else days
    return live(owner).filter(
        cancelled_at__isnull=True,
        starts_on__gt=today,
        starts_on__lte=today + timedelta(days=horizon),
    )


def in_month(owner, first, last):
    """Everything touching the month, for the calendar's fourth source.

    Overlap rather than containment: an appointment that starts in August and
    ends in September belongs to both months' calendars, and a filter on
    `starts_on` alone would drop it from the second.
    """
    return live(owner).filter(
        Q(cancelled_at__isnull=True)
        & Q(starts_on__lte=last)
        & (Q(ends_on__gte=first) | (Q(ends_on__isnull=True) & Q(starts_on__gte=first)))
    )


def days_covered(appointment, first, last):
    """Which dates inside ``[first, last]`` this appointment falls on.

    Computed in Python rather than expanded in SQL: a span is at most a handful
    of days and a `generate_series` join would be a lot of machinery for a
    calendar square's count.
    """
    start = max(appointment.starts_on, first)
    end = min(appointment.last_day, last)
    return [
        start + timedelta(days=offset) for offset in range((end - start).days + 1)
    ]
