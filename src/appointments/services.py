"""Write-side logic for appointments.

Mutations and the invariants they hold. Reads live in `appointments.reads` --
split from the first slice per `architecture-trajectory.md` §4 rule 4.
"""
from django.db import transaction
from django.utils import timezone

from clarice import life_log
from appointments.models import Appointment


class AppointmentError(Exception):
    """An appointment that cannot be made or changed as asked."""


@transaction.atomic
def make(
    owner,
    *,
    text,
    starts_on,
    ends_on=None,
    starts_at=None,
    ends_at=None,
    location="",
    notes="",
    public_id=None,
):
    """Write down something that is going to happen.

    **Validated here rather than left to the constraints**, because a database
    error names a column and not a person's mistake -- the constraints are the
    guarantee, and these are the message.

    `ends_on` equal to `starts_on` is normalised to null: *one day* and *the
    5th to the 5th* are the same fact, and a column that can say it two ways
    will eventually say it two ways in one table.

    **Idempotent on `public_id`**, on `mind.services.capture`'s precedent: a
    client that names the row can retry a request it never saw succeed, and a
    retry is not an error. The tombstone matters here -- a deleted appointment
    keeps its id, so a retry after a deletion returns the deleted row rather
    than resurrecting it.
    """
    text = (text or "").strip()
    if not text:
        raise AppointmentError("An appointment needs something written on it.")
    if ends_on is not None and ends_on < starts_on:
        raise AppointmentError("An appointment cannot end before it starts.")
    if ends_on == starts_on:
        ends_on = None
    if ends_at is not None and starts_at is None:
        raise AppointmentError("An end time needs a start time.")

    if public_id is not None:
        existing = Appointment.objects.filter(public_id=public_id).first()
        if existing is not None:
            if existing.owner_id != owner.pk:
                raise AppointmentError("That id belongs to someone else.")
            return existing

    appointment = Appointment.objects.create(
        owner=owner,
        text=text,
        starts_on=starts_on,
        ends_on=ends_on,
        starts_at=starts_at,
        ends_at=ends_at,
        location=(location or "").strip(),
        notes=(notes or "").strip(),
        **({"public_id": public_id} if public_id is not None else {}),
    )
    life_log.record(
        owner, life_log.APPOINTMENT_MADE, occurred_at=appointment.created_at
    )
    return appointment


@transaction.atomic
def cancel(appointment):
    """It was called off.

    **Not a deletion**, and the difference is the whole of rule 6: a cancelled
    Thursday afternoon is a fact about that Thursday. The row stays on its day,
    struck, and produces no log line when its start passes -- because it did
    not.

    Idempotent: cancelling twice is one cancellation, which is the contract
    `test_emitters_are_idempotent.py` holds over every emitter.
    """
    if appointment.cancelled_at is not None:
        return appointment
    appointment.cancelled_at = timezone.now()
    appointment.save(update_fields=["cancelled_at", "updated_at"])
    life_log.record(
        appointment.owner,
        life_log.APPOINTMENT_CANCELLED,
        occurred_at=appointment.cancelled_at,
    )
    return appointment


@transaction.atomic
def remove(appointment):
    """It should never have been written down.

    **Soft, and no life event.** Rule 2's public identifier needs a tombstone,
    so the row stays and the id can never be reused. And nothing happened to a
    life: deleting a typo is housekeeping, the same call `lists.services.keep`
    makes about answering a prompt. Cancelling is the one that is a fact.
    """
    if appointment.deleted_at is not None:
        return appointment
    appointment.deleted_at = timezone.now()
    appointment.save(update_fields=["deleted_at", "updated_at"])
    return appointment
