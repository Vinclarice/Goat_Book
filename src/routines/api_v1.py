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


class PausedRoutineOut(Schema):
    """A routine that has been put down.

    No standing, because a paused routine has no current period -- that is
    what pausing means. Just enough to recognise it and pick it back up.
    """

    routine_id: int
    title: str
    cadence: str
    target: int
    unit: str


class StandingsOut(Schema):
    # The owner's own today, so the client never has to work out what day it
    # is -- the day boundary belongs to their time zone and that lives here.
    today: date
    standings: list[StandingOut]
    # Carried alongside rather than mixed in: hidden from the day is not the
    # same as gone, and a paused routine nobody can see is one nobody can
    # resume.
    paused: list[PausedRoutineOut]


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
        "paused": [
            {
                "routine_id": routine.id,
                "title": routine.title,
                "cadence": routine.cadence,
                "target": routine.target_quantity,
                "unit": routine.unit,
            }
            for routine in reads.paused_routines_for(owner)
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
    try:
        services.log_progress(
            request.user, routine, timezone.localdate(), amount=payload.amount
        )
    except services.RoutineError as error:
        # 409 rather than 400: the request is well formed and the routine is
        # real, it is the state that refuses. Reached when a routine was
        # paused in another tab -- the button is not shown for a paused one,
        # which is exactly why the server has to say no rather than trust
        # that.
        raise HttpError(409, str(error))
    return _standings_out(request.user)


@router.post("/routines/{routine_id}/enough", response=StandingsOut)
def call_it_enough(request, routine_id: int):
    """Close this period at what was done, content with it.

    A third route because it is a third statement. Logging says what
    happened, skipping says the thing was not done, and this says some of
    it was and that was the right amount -- crane-plan.md §8, answering the
    question §3 left open. Folding it into the skip route would record
    "I chose not to" about somebody who did.
    """
    routine = _own_routine_or_404(request.user, routine_id)
    try:
        services.close_period_as_enough(
            request.user, routine, timezone.localdate()
        )
    except services.RoutineError as error:
        raise HttpError(409, str(error))
    return _standings_out(request.user)


@router.post("/routines/{routine_id}/pause", response=StandingsOut)
def pause(request, routine_id: int):
    """Put a routine down, keeping everything it has already done."""
    routine = _own_routine_or_404(request.user, routine_id)
    services.pause_routine(request.user, routine)
    return _standings_out(request.user)


@router.post("/routines/{routine_id}/resume", response=StandingsOut)
def resume(request, routine_id: int):
    """Pick it back up. Nothing is written for the time it was down."""
    routine = _own_routine_or_404(request.user, routine_id)
    services.resume_routine(request.user, routine)
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
    try:
        services.skip_period(request.user, routine, timezone.localdate())
    except services.RoutineError as error:
        raise HttpError(409, str(error))
    return _standings_out(request.user)
