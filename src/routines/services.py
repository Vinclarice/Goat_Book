"""Write-side logic for routines. Reads live in routines.reads."""
from django.db import transaction
from django.utils import timezone

from routines.models import Routine, RoutineOccurrence
from routines.periods import period_start_for


class RoutineError(Exception):
    """A routine action that cannot be taken -- today, only somebody else's."""


def create_routine(
    owner, *, title, cadence=Routine.Cadence.DAILY, target_quantity=1, unit=""
):
    return Routine.objects.create(
        owner=owner,
        title=title,
        cadence=cadence,
        target_quantity=target_quantity,
        unit=unit,
    )


def _own_routine(owner, routine):
    """Fails closed, per principles.md, and in the service rather than the
    view because every caller needs it."""
    if routine.owner_id != owner.id:
        raise RoutineError("That routine isn't yours.")
    return routine


@transaction.atomic
def log_progress(owner, routine, day, amount=1):
    """Add ``amount`` to the period ``day`` falls in, creating it if needed.

    Occurrences are created lazily -- on the first log or view of a period,
    not by a nightly job pre-creating a row for every routine every day.
    That is a smaller and more reversible piece of infrastructure, and
    nothing yet needs the "you haven't logged anything today" prompt a
    scheduled job would exist to power.

    Reaching the target completes the period automatically. There is no
    separate "mark done" once the count is there, which is the whole
    difference between measuring practice and ticking a box.

    ``day`` is passed in and never read from the clock here: the request
    boundary decides what today means using the owner's own zone.
    """
    _own_routine(owner, routine)
    occurrence = _occurrence_for_writing(owner, routine, day)
    occurrence.progress += amount
    _settle_outcome(occurrence)
    occurrence.save(update_fields=["progress", "outcome", "decided_at"])
    return occurrence


def _occurrence_for_writing(owner, routine, day):
    """This period's row, created with its snapshot if it does not exist.

    get_or_create under the unique constraint, so two concurrent first-logs
    cannot produce two rows for one period.
    """
    occurrence, _ = RoutineOccurrence.objects.get_or_create(
        routine=routine,
        period_start=period_start_for(routine.cadence, day),
        defaults={
            "owner": owner,
            # Copied now, while the routine still says what it says. Never
            # re-read: see the model docstring on charter rule 3.
            "target_quantity": routine.target_quantity,
            "unit": routine.unit,
        },
    )
    return occurrence


def _settle_outcome(occurrence):
    """Completed once the target is reached, open again if it stops being.

    Correction runs through here too (slice 2), which is why this reverts
    rather than only advancing: a count that is no longer true must not
    leave an outcome that says otherwise.
    """
    reached = occurrence.progress >= occurrence.target_quantity
    if reached and occurrence.outcome == RoutineOccurrence.Outcome.OPEN:
        occurrence.outcome = RoutineOccurrence.Outcome.COMPLETED
        occurrence.decided_at = timezone.now()
    elif not reached and occurrence.outcome == RoutineOccurrence.Outcome.COMPLETED:
        occurrence.outcome = RoutineOccurrence.Outcome.OPEN
        occurrence.decided_at = None
