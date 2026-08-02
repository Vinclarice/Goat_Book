"""The daily domain's slice of the /api/v1/ contract.

Two shapes of the same read: `/day` for "whatever today is for me", and
`/day/{day}` for a named date. The undated form exists so the client never
has to decide what day it is -- that is a per-user time-zone question, and
`principles.md` puts the answer on the server.
"""
from datetime import date

from django.utils import timezone
from ninja import Router, Schema

from daily import reads, services
from lists.api_v1 import TaskOut
from lists.serializers import serialize_item


router = Router()


class DayOut(Schema):
    date: str
    intentions: str
    gratitude: str
    happenings: str
    # Carried on every response so a page for the 3rd can tell whether the
    # 3rd is today, and offer yesterday/tomorrow, without a second request
    # or a client-side guess at the owner's zone.
    today: str
    # The agenda's rows, read live. Not stored on the entry and not cached:
    # the day displays the task, so completing one anywhere is reflected on
    # the next load with nothing to reconcile.
    #
    # TaskOut rather than a daily-shaped copy, because these *are* the same
    # records the agenda serves and a second schema would be free to drift
    # from the first.
    action_items: list[TaskOut]
    # Whether this day is showing them at all, decided by the server so the
    # client is not left inferring it from an empty list. Empty-because-done
    # and empty-because-not-today are different, and only one of them
    # deserves "nothing due today".
    shows_action_items: bool


class DayIn(Schema):
    """Every field optional, and absent is not the same as empty.

    The page may save one section without carrying the other two, so a
    field left out keeps its stored value -- see services.write_entry.
    """

    intentions: str | None = None
    gratitude: str | None = None
    happenings: str | None = None


def _today_for_request():
    """The requesting user's local date.

    `timezone.localdate()` reads the zone the middleware activated for this
    request, which is the owner's own -- see per-user-time-zones-plan.md.
    Read once, here at the boundary, and passed down.
    """
    return timezone.localdate()


def _day_out(owner, day):
    entry = reads.entry_for(owner, day)
    today = _today_for_request()
    # Action Items are live task state, and a task carries no history of
    # what it looked like on a past date. Showing today's open work on the
    # page for the 30th would assert something that was never true -- the
    # same mistake daily-operating-system-vision.md refuses when it says
    # habit metrics must not infer the past from a task's current state.
    #
    # So a day that is not today shows what was *written*, which is a real
    # record, and no work at all. A future day is excluded for the same
    # reason in reverse.
    shows_action_items = day == today
    return {
        "date": day.isoformat(),
        # An unwritten day is a blank page, not a missing one: there is
        # nothing to have found, so 404 would be answering the wrong
        # question and would make the client handle a case that is not an
        # error.
        "intentions": entry.intentions if entry else "",
        "gratitude": entry.gratitude if entry else "",
        "happenings": entry.happenings if entry else "",
        "today": today.isoformat(),
        "action_items": (
            [serialize_item(item) for item in reads.action_items_for(owner, day)]
            if shows_action_items
            else []
        ),
        "shows_action_items": shows_action_items,
    }


@router.get("/day", response=DayOut)
def get_today(request):
    return _day_out(request.user, _today_for_request())


@router.get("/day/{day}", response=DayOut)
def get_day(request, day: date):
    return _day_out(request.user, day)


@router.patch("/day/{day}", response=DayOut)
def write_day(request, day: date, payload: DayIn):
    """Write into the requesting user's day.

    There is no ownership check to forget: the entry is addressed by
    (request.user, day), so the path names a date and never a record. One
    person cannot reach another's day through this endpoint at all, which
    is a smaller surface than an id would be.
    """
    services.write_entry(
        request.user,
        day,
        **{
            field: value
            for field, value in (
                ("intentions", payload.intentions),
                ("gratitude", payload.gratitude),
                ("happenings", payload.happenings),
            )
            if value is not None
        },
    )
    return _day_out(request.user, day)
