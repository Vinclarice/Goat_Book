"""Read-side logic for routines.

Query and derivation only; every mutation is in routines.services. Split
from the first slice, which is the gap architecture-trajectory.md §4 named
against §3's sketch -- it had one models.py and no separation at all.
"""
from dataclasses import dataclass

from routines.models import Routine, RoutineOccurrence
from routines.periods import period_start_for


@dataclass(frozen=True)
class Standing:
    """Where a routine stands in one period.

    A derived view rather than a row, because a period nobody has logged
    yet has no row -- occurrences are created lazily, so "0 of 5, open" has
    to be describable without writing anything. Reading a page must not
    create records; that is what makes it a read.
    """

    routine: Routine
    period_start: object
    progress: int
    target: int
    unit: str
    outcome: str

    @property
    def is_met(self):
        return self.outcome == RoutineOccurrence.Outcome.COMPLETED


def active_routines_for(owner):
    return list(Routine.objects.filter(owner=owner, is_active=True))


def paused_routines_for(owner):
    """The ones put down, so they can be picked back up.

    Hidden from the day is not the same as gone: a paused routine that
    appeared nowhere would be one nobody could resume, which is the shape of
    gap slice 3 found when routine creation had no surface at all.
    """
    return list(Routine.objects.filter(owner=owner, is_active=False))


# DARK: no production caller. The read half of a live pair --
# `services._occurrence_for_writing` has two callers and does the same lookup
# with `select_for_update`, so every production path that wants an occurrence
# wants to write to it.
# Trigger: a routines surface that reads an occurrence without changing it --
# a history view, or a brief saying whether today's routine has been done.
def occurrence_for(owner, routine, day):
    """This owner's occurrence for the period ``day`` falls in, or None.

    Owner-scoped in the query rather than checked afterwards, so there is no
    comparison to forget.
    """
    return RoutineOccurrence.objects.filter(
        owner=owner,
        routine=routine,
        period_start=period_start_for(routine.cadence, day),
    ).first()


def standings_for(owner, day):
    """Every active routine and where it stands in ``day``'s period.

    One query for the routines and one for their occurrences, rather than
    one per routine: the Daily Page renders all of them together.
    """
    routines = active_routines_for(owner)
    if not routines:
        return []
    periods = {
        routine.id: period_start_for(routine.cadence, day) for routine in routines
    }
    logged = {
        (each.routine_id, each.period_start): each
        for each in RoutineOccurrence.objects.filter(
            owner=owner,
            routine__in=routines,
            period_start__in=set(periods.values()),
        )
    }
    standings = []
    for routine in routines:
        period_start = periods[routine.id]
        occurrence = logged.get((routine.id, period_start))
        standings.append(
            Standing(
                routine=routine,
                period_start=period_start,
                progress=occurrence.progress if occurrence else 0,
                # An unlogged period is described against what the routine
                # says *now*, since there is no snapshot until something is
                # logged -- and nothing has happened yet to preserve.
                target=(
                    occurrence.target_quantity
                    if occurrence
                    else routine.target_quantity
                ),
                unit=occurrence.unit if occurrence else routine.unit,
                outcome=(
                    occurrence.outcome
                    if occurrence
                    else RoutineOccurrence.Outcome.OPEN
                ),
            )
        )
    return standings
