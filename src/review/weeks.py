"""Which week a date belongs to.

Delegates rather than decides. `routines.periods.period_start_for` is the
authority on when a week begins, settled as Monday in `crane-plan.md` §6 on
the evidence that `lists/agenda.py` has resolved the snooze menu's "Next
week" to the coming Monday since Albatross. §6 also names the hazard this
module exists to avoid: two definitions of "this week" between a routine and
the report about it would be wrong in a way nobody would see.

So this is a thin, clock-free wrapper that adds the end date and nothing
else. If a third caller ever wants a week boundary, that is the moment to
move `period_start_for` somewhere neutral -- not before, because moving it
now would be churn in exchange for a tidier import graph.
"""
from datetime import timedelta

from routines.models import Routine
from routines.periods import period_start_for


DAYS_IN_WEEK = 7


def week_start_for(day):
    """The Monday of the week ``day`` falls in."""
    return period_start_for(Routine.Cadence.WEEKLY, day)


def week_end_for(day):
    """The Sunday that closes the week ``day`` falls in."""
    return week_start_for(day) + timedelta(days=DAYS_IN_WEEK - 1)


def days_in(week_start):
    """Monday through Sunday, as dates.

    Materialised rather than derived at each use site, because several
    sections of the review render one row per day and each of them getting
    the arithmetic right independently is how a Sunday goes missing.
    """
    return [week_start + timedelta(days=offset) for offset in range(DAYS_IN_WEEK)]
