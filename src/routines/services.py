"""Write-side logic for routines. Reads live in routines.reads."""
from django.db import transaction
from django.utils import timezone

from routines.models import Routine, RoutineOccurrence, RoutinePause
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


def _active_routine(owner, routine):
    """Owned, and not put down.

    Checked here rather than by hiding the button, because pausing has to
    actually stop new occurrences being created -- an endpoint that still
    accepted a log would make "paused" a decoration.
    """
    _own_routine(owner, routine)
    if not routine.is_active:
        raise RoutineError("That routine is paused.")
    return routine


@transaction.atomic
def pause_routine(owner, routine):
    """Put a routine down, keeping everything it has already done.

    Paused rather than deleted: the person means to come back to it, and
    the occurrences already recorded are history either way.

    Pausing something already paused keeps the original stamp -- it records
    when the routine was put down, not when somebody last said so.
    """
    _own_routine(owner, routine)
    if not routine.is_active:
        return routine
    now = timezone.now()
    routine.is_active = False
    routine.paused_at = now
    routine.save(update_fields=["is_active", "paused_at"])
    # The durable half, added in Crane 3 slice 7. The flags above answer
    # "is it down right now"; this answers "what weeks was it down for",
    # which no later migration could reconstruct once a pause has ended.
    RoutinePause.objects.create(owner=owner, routine=routine, paused_at=now)
    return routine


@transaction.atomic
def resume_routine(owner, routine):
    """Pick it back up, without inventing the time it was down.

    Nothing is written for the periods it missed. Lazy occurrence creation
    makes that the default rather than an achievement, which is exactly why
    the test asserts it: a later "helpful" job that pre-created rows would
    break the rule silently. Those weeks are a fact about somebody's month,
    not missing data.
    """
    _own_routine(owner, routine)
    routine.is_active = True
    routine.paused_at = None
    routine.save(update_fields=["is_active", "paused_at"])
    # Closed rather than deleted: the stretch it was down for is the thing
    # being recorded, and a row that vanished here would leave exactly the
    # gap RoutinePause exists to fill. Resuming something already running
    # closes nothing, because there is nothing open.
    RoutinePause.objects.filter(routine=routine, resumed_at__isnull=True).update(
        resumed_at=timezone.now()
    )
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

    A negative ``amount`` is a correction, which `crane-plan.md` §3 asks to
    be "the same write path with a different amount" rather than an action
    of its own -- fixing a mis-tap is the same kind of statement as making
    one. Two rules follow, and both are about not inventing history:
    progress never goes below nothing, and correcting a period nobody has
    logged does nothing at all rather than conjuring a row that says it was
    touched. Returns None in that case.

    ``day`` is passed in and never read from the clock here: the request
    boundary decides what today means using the owner's own zone.
    """
    _active_routine(owner, routine)
    if amount <= 0:
        occurrence = RoutineOccurrence.objects.filter(
            routine=routine, period_start=period_start_for(routine.cadence, day)
        ).first()
        if occurrence is None:
            return None
    else:
        occurrence = _occurrence_for_writing(owner, routine, day)
    # Clamped rather than allowed to go negative and be caught by the
    # column's check constraint: "you cannot have done less than none of it"
    # is a domain rule, and a database error is not how a person hears it.
    occurrence.progress = max(0, occurrence.progress + amount)
    _settle_outcome(occurrence)
    occurrence.save(update_fields=["progress", "outcome", "decided_at"])
    return occurrence


@transaction.atomic
def skip_period(owner, routine, day):
    """Record that this period was deliberately not done.

    A distinct action rather than silence, and the distinction is the whole
    point: "I chose not to today" and "I meant to and didn't" are different
    facts about a week, and Crane 3 reports them differently. A period that
    merely elapses with nothing logged stays open, which is a fact about
    what happened rather than a verdict asserted on the person's behalf.

    Creates the occurrence if there isn't one -- unlike a correction, a
    decision not to do something is itself worth recording, and it is the
    common case: deciding on Monday morning that today is not one.

    Whatever was already logged is kept. §3's weekly example is explicit
    that skipping sets the occurrence to skipped regardless of partial
    progress, because the decision is about the period rather than the
    count.
    """
    _active_routine(owner, routine)
    occurrence = _occurrence_for_writing(owner, routine, day)
    occurrence.outcome = RoutineOccurrence.Outcome.SKIPPED
    occurrence.decided_at = timezone.now()
    occurrence.save(update_fields=["outcome", "decided_at"])
    return occurrence


@transaction.atomic
def close_period_as_enough(owner, routine, day):
    """Close a period at what was done, content with it.

    The third way out of open, and neither of the other two. Reaching the
    target completes a period automatically and a skip says the thing was
    not done at all; this says some of it was and that was the right
    amount. `crane-plan.md` §8 settles what it means for a report: never a
    met target, and out of the denominator like a skip, because both are
    decisions rather than periods that merely elapsed.

    It refuses a period with nothing logged, because "I did some of it"
    needs some of it -- with nothing done the honest statement is a skip,
    which has its own action. And it refuses one already met, which is
    completed and has nothing left to be content about.

    Unlike a skip it never creates the occurrence: there is by definition
    something already there.
    """
    _active_routine(owner, routine)
    occurrence = RoutineOccurrence.objects.filter(
        routine=routine, period_start=period_start_for(routine.cadence, day)
    ).first()
    if occurrence is None or occurrence.progress == 0:
        raise RoutineError("Nothing has been logged for that period yet.")
    if occurrence.progress >= occurrence.target_quantity:
        raise RoutineError("That period is already met.")
    occurrence.outcome = RoutineOccurrence.Outcome.PARTIAL
    occurrence.decided_at = timezone.now()
    occurrence.save(update_fields=["outcome", "decided_at"])
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

    Corrections run through here, which is why it reverts rather than only
    advancing: a count that is no longer true must not leave an outcome
    saying otherwise.

    Only ever called from the logging path, which is what makes the skip
    branch safe -- reaching it means something was logged, and doing some of
    the thing contradicts having decided not to.
    """
    reached = occurrence.progress >= occurrence.target_quantity
    if occurrence.outcome in (
        RoutineOccurrence.Outcome.SKIPPED,
        RoutineOccurrence.Outcome.PARTIAL,
    ):
        # Logging is the un-skip, and equally the un-enough. Both are
        # statements about intent, and somebody who carries on has
        # withdrawn whichever one they made.
        occurrence.outcome = (
            RoutineOccurrence.Outcome.COMPLETED
            if reached
            else RoutineOccurrence.Outcome.OPEN
        )
        occurrence.decided_at = timezone.now() if reached else None
        return
    if reached and occurrence.outcome == RoutineOccurrence.Outcome.OPEN:
        occurrence.outcome = RoutineOccurrence.Outcome.COMPLETED
        occurrence.decided_at = timezone.now()
    elif not reached and occurrence.outcome == RoutineOccurrence.Outcome.COMPLETED:
        occurrence.outcome = RoutineOccurrence.Outcome.OPEN
        occurrence.decided_at = None
