"""Which period a date belongs to, for each cadence.

Its own module because it is the one rule both reads and services need and
neither owns. Pure and clock-free: the date is always passed in, so a
period is testable without freezing anything -- `principles.md`'s injected
clock, applied to the smallest piece it has.
"""
from datetime import timedelta

from routines.models import Routine


def period_start_for(cadence, day):
    """The first date of the period ``day`` falls in, for ``cadence``.

    Weekly periods are anchored to Monday. That is settled in
    `crane-plan.md` §6 on evidence rather than taste: `lists/agenda.py`
    resolves the snooze menu's "Next week" to the coming Monday, so the
    product has been telling people a week starts there since Albatross.
    Crane 3's weekly review has to use this same function, because two
    definitions of "this week" between a routine and the report about it
    would be wrong in a way nobody would see.
    """
    if cadence == Routine.Cadence.WEEKLY:
        # date.weekday() is 0 on Monday, so this subtracts however far into
        # the week the date already is.
        return day - timedelta(days=day.weekday())
    return day
