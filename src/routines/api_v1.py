"""The routines slice of the /api/v1/ contract.

Serves *standings* rather than occurrence rows. A period nobody has logged
has no row -- occurrences are created lazily -- so returning occurrences
would leave a routine at 0 of 5 undescribable without writing one, and a
GET that writes is how a page view starts inventing history. A standing is
the derived answer: what this routine expects, and where it has got to.
"""
from datetime import date

from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from routines import reads, services
from routines.models import Routine


router = Router()


class StandingOut(Schema):
    routine_id: int
    title: str
    cadence: str
    period_start: date
    progress: int
    target: int
    unit: str
    outcome: str
    is_met: bool


class StandingsOut(Schema):
    # The owner's own today, so the client never has to work out what day it
    # is -- the day boundary belongs to their time zone and that lives here.
    today: date
    standings: list[StandingOut]


class RoutineIn(Schema):
    title: str
    cadence: str = Routine.Cadence.DAILY
    target_quantity: int = 1
    unit: str = ""


class LogIn(Schema):
    amount: int = 1


def _standings_out(owner):
    today = timezone.localdate()
    return {
        "today": today,
        "standings": [
            {
                "routine_id": standing.routine.id,
                "title": standing.routine.title,
                "cadence": standing.routine.cadence,
                "period_start": standing.period_start,
                "progress": standing.progress,
                "target": standing.target,
                "unit": standing.unit,
                "outcome": standing.outcome,
                "is_met": standing.is_met,
            }
            for standing in reads.standings_for(owner, today)
        ],
    }


def _own_routine_or_404(owner, routine_id):
    """Scoped in the lookup rather than fetched and then compared, so there
    is no check to forget -- and 404 rather than 403, so the endpoint does
    not confirm that somebody else's routine id exists."""
    return get_object_or_404(Routine, pk=routine_id, owner=owner)


@router.get("/routines", response=StandingsOut)
def routine_standings(request):
    return _standings_out(request.user)


@router.post("/routines", response=StandingsOut)
def new_routine(request, payload: RoutineIn):
    if payload.cadence not in Routine.Cadence.values:
        raise HttpError(400, "Choose a valid cadence.")
    if payload.target_quantity < 1:
        # A target of zero is not a routine, it is a routine you have not
        # decided about yet.
        raise HttpError(400, "A target needs to be at least one.")
    services.create_routine(
        request.user,
        title=payload.title.strip(),
        cadence=payload.cadence,
        target_quantity=payload.target_quantity,
        unit=payload.unit.strip(),
    )
    return _standings_out(request.user)


@router.post("/routines/{routine_id}/log", response=StandingsOut)
def log_routine(request, routine_id: int, payload: LogIn):
    """Add to the current period, returning every standing rather than one.

    The Daily Page renders them together, so one response keeps the list
    from disagreeing with itself for a frame -- the same reason the day's
    focus endpoints answer with the whole day.

    A negative amount is a correction, which is deliberately this endpoint
    rather than one of its own: fixing a mis-tap is the same kind of
    statement as making one, and a separate route would invite a separate
    rule. Correcting a period nobody has logged is a no-op, so the response
    is the unchanged standings rather than an error about a row that ought
    not to exist.
    """
    routine = _own_routine_or_404(request.user, routine_id)
    services.log_progress(
        request.user, routine, timezone.localdate(), amount=payload.amount
    )
    return _standings_out(request.user)


@router.post("/routines/{routine_id}/skip", response=StandingsOut)
def skip_routine(request, routine_id: int):
    """Record that this period was deliberately not done.

    Its own route rather than a flag on the log endpoint, because it is a
    different statement: logging says what happened, skipping says what was
    decided. Collapsing them would be the near-identical-controls problem
    C2 found in the task UI, one layer down.
    """
    routine = _own_routine_or_404(request.user, routine_id)
    services.skip_period(request.user, routine, timezone.localdate())
    return _standings_out(request.user)
