"""The calendar's slice of the /api/v1/ contract.

`superlists-2.0-plan.md` increment 7. Four surfaces *read* an appointment --
the day's strip, the pool's fixed lines, the calendar and the day's log -- and
each gets it inside the payload it already fetches, so none of them costs a
second request. What lives here is the writing: making one, calling one off,
and deleting a typo.

**Session only, all of it.** The phone has no calendar surface, and a bearer
token that sits in a keystore for ninety days should not gain a diary because
the day page grew a strip. `test_api_auth_surface.py` holds that.
"""
import uuid
from datetime import date, time

from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError

from accounts.auth import SessionAuthIfLoggedIn
from appointments import reads, services
from appointments.models import Appointment


router = Router()


class AppointmentOut(Schema):
    """One appointment, as every surface renders it.

    **Dates and times apart, never assembled into an instant here.** The
    boundary carries what the record holds; a client that wanted a datetime
    would be inventing a time zone for an all-day thing, which is the mistake
    the model exists to prevent.

    `ends_on` is null for a one-day appointment and `starts_at` is null for an
    all-day one, and those two nulls mean different things -- so the contract
    keeps them apart rather than sending a computed `is_all_day` a client could
    disagree with.
    """

    public_id: uuid.UUID
    text: str
    starts_on: date
    ends_on: date | None
    starts_at: time | None
    ends_at: time | None
    location: str
    notes: str
    #: Called off. Present rather than filtered out: rule 6 keeps it visible on
    #: its day, struck, because a cancelled Thursday is a fact about that
    #: Thursday.
    cancelled: bool


def appointment_out(appointment):
    """One appointment as a dict, shared by every payload that carries one.

    Here rather than in each caller, so the day, the pool and the calendar
    cannot drift into three shapes of the same record -- the same reason
    `money.reads.bill_row` exists.
    """
    return {
        "public_id": appointment.public_id,
        "text": appointment.text,
        "starts_on": appointment.starts_on,
        "ends_on": appointment.ends_on,
        "starts_at": appointment.starts_at,
        "ends_at": appointment.ends_at,
        "location": appointment.location,
        "notes": appointment.notes,
        "cancelled": appointment.cancelled_at is not None,
    }


class AppointmentIn(Schema):
    text: str
    starts_on: date
    ends_on: date | None = None
    starts_at: time | None = None
    ends_at: time | None = None
    location: str = ""
    notes: str = ""


def _own_appointment_or_404(request, public_id):
    """This owner's appointment, by public id.

    Owner-scoped in the lookup rather than fetched and then checked, per
    `principles.md`: one forgotten comparison is the whole distance between a
    private diary and somebody else's.

    Addressed by `public_id` and not by the row id, because rule 2 gave it one
    precisely so a client can name a record it created offline.
    """
    return get_object_or_404(
        Appointment, owner=request.user, public_id=public_id, deleted_at__isnull=True
    )


@router.post("/appointments", response={201: AppointmentOut}, auth=SessionAuthIfLoggedIn())
def make_appointment(request, payload: AppointmentIn):
    """Write down something that is going to happen."""
    try:
        appointment = services.make(
            request.user,
            text=payload.text,
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            location=payload.location,
            notes=payload.notes,
        )
    except services.AppointmentError as error:
        raise HttpError(409, str(error))
    return 201, appointment_out(appointment)


@router.post(
    "/appointments/{public_id}/cancel",
    response=AppointmentOut,
    auth=SessionAuthIfLoggedIn(),
)
def cancel_appointment(request, public_id: uuid.UUID):
    """It was called off -- and it stays on its day, struck.

    Not a deletion, and the two have their own endpoints for that reason: a
    surface that offered one button for both would make *"the parents' evening
    was cancelled"* unanswerable a month later.
    """
    return appointment_out(services.cancel(_own_appointment_or_404(request, public_id)))


@router.delete("/appointments/{public_id}", auth=SessionAuthIfLoggedIn())
def remove_appointment(request, public_id: uuid.UUID):
    """It should never have been written down.

    Soft, so the id can never be reused -- see `services.remove`.
    """
    services.remove(_own_appointment_or_404(request, public_id))
    return {"deleted": True}


def coming_up_for(owner, today):
    """What is ahead, as the day's strip and the pool's fixed lines carry it.

    A module-level helper rather than an endpoint, because both of those are
    already fetching a payload and a second request for a two-line strip would
    be a round trip for nothing.
    """
    return [appointment_out(each) for each in reads.coming_up(owner, today)]
