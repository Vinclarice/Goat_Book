"""Write-side logic for the daily domain.

Mutations and the invariants they have to hold. Reads live in daily.reads.
"""
from django.db import transaction

from daily.models import DailyEntry


# Sentinel for "the caller did not mention this field", which is different
# from "the caller cleared it to empty". Without it a partial write would
# blank whatever it left out.
_UNSET = object()


@transaction.atomic
def write_entry(
    owner,
    day,
    *,
    intentions=_UNSET,
    gratitude=_UNSET,
    happenings=_UNSET,
):
    """Create or update this owner's entry for ``day``.

    There is no separate create and update, because a person writing in
    their day does not know or care whether a row exists yet -- the first
    keystroke of the morning and the last of the evening are the same
    action. `get_or_create` under the unique constraint makes that safe:
    two concurrent first-writes cannot produce two rows.

    Fields left unmentioned keep their stored value. That is what lets a
    caller save one section without carrying the other two, and what stops
    a partial write silently clearing a paragraph it never displayed.

    ``day`` is passed in, never read from the clock here -- the request
    boundary decides what "today" means using the owner's own time zone.
    """
    entry, _ = DailyEntry.objects.get_or_create(owner=owner, date=day)
    updated = []
    for field, value in (
        ("intentions", intentions),
        ("gratitude", gratitude),
        ("happenings", happenings),
    ):
        if value is _UNSET:
            continue
        setattr(entry, field, value or "")
        updated.append(field)
    if updated:
        entry.save(update_fields=[*updated, "updated_at"])
    return entry
