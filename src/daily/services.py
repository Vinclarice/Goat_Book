"""Write-side logic for the daily domain.

Mutations and the invariants they have to hold. Reads live in daily.reads.
"""
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from clarice import life_log
from daily.models import DailyEntry, DailyFocus
# The task core calling the knowledge core, which is the direction that already
# runs: `review/reads.py` reads nodes, and `Facet.task` points the other way.
from mind import services as mind_services


class FocusError(Exception):
    """A pin that cannot be made -- today, only somebody else's task."""


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
        # The journal's own producer -- planning-assistant-plan.md increment 2.
        # Only when the writing actually changed: `write_entry` is also how an
        # entry comes into existence for a pin, and re-reading unchanged prose
        # there is work nobody asked for.
        #
        # **On the live path, and for capture's reason.** The parser is a regex
        # over a few sentences: no model, no network, no per-call cost. So the
        # suggestion is ready by the time the page comes back and nothing was
        # asked at the moment of writing.
        #
        # Invoked here rather than left for a batch job, because a producer
        # nothing calls is not a producer -- the lesson `run_detectors` taught
        # by being green and uninvoked for weeks.
        #
        # The clock is read here rather than injected, which is the one place
        # this module bends that rule: `now` only stamps the log entry, every
        # date the parser reads comes from `entry.date`, and threading a
        # parameter through every caller to timestamp an event would be
        # ceremony. The proposal itself is reproducible without it.
        mind_services.propose_journal_commitments(
            entry, now=timezone.now(), actor=owner.get_username()
        )
    return entry


def _entry_for_writing(owner, day):
    """The day's entry, created if this is the first thing written to it.

    Pinning is often the first thing that happens to a day, before a word
    has been typed into it.
    """
    entry, _ = DailyEntry.objects.get_or_create(owner=owner, date=day)
    return entry


@transaction.atomic
def pin_task(owner, day, task, *, from_draft=False):
    """Choose ``task`` as work for ``day``.

    Touches nothing on the task itself -- not its due date, its status, or
    its ownership. A pin is a statement about the person's intent for a
    day, and the task goes on meaning exactly what it meant before.

    Repinning something previously released clears the release rather than
    writing a second row: one task chosen for one day is one decision,
    however many times it was turned over.
    """
    if task.owner_id != owner.id:
        # Fails closed, per principles.md. The API addresses tasks by id, so
        # this is the check that stops one person pinning another's work --
        # and the reason it lives here rather than in the view is that every
        # caller needs it.
        raise FocusError("That task isn't yours to plan.")

    focus = DailyFocus.objects.filter(
        owner=owner, entry__date=day, task=task
    ).first()
    if focus is not None:
        if focus.released_at is not None:
            focus.released_at = None
            focus.save(update_fields=["released_at"])
            # "One task chosen for one day is one decision, however many times
            # it was turned over" is a rule about the *row*. Turning it over is
            # exactly what the log is for, so choosing it again after releasing
            # it is a second event against the one row.
            life_log.record(
                owner, life_log.FOCUS_PINNED, task=task, entry=focus.entry
            )
        return focus

    entry = _entry_for_writing(owner, day)
    highest = DailyFocus.objects.filter(entry=entry).aggregate(
        top=Max("position")
    )["top"]
    focus = DailyFocus.objects.create(
        owner=owner,
        entry=entry,
        task=task,
        # Snapshotted now, while there is still a task to read it from.
        task_text=task.text,
        position=0 if highest is None else highest + 1,
        accepted_from_draft=from_draft,
    )
    # Both subjects. What a pin is *about* is a date; the task is the object of
    # the decision, and `around()` will want to enter the log from either.
    #
    # No flag for whether a draft did it: `accepted_from_draft` above already
    # carries that, and a second copy in the log is a second opinion.
    life_log.record(owner, life_log.FOCUS_PINNED, task=task, entry=entry)
    return focus


@transaction.atomic
def accept_draft(owner, day, tasks):
    """Take the day's draft as it was shown.

    **The ids come from the caller, not from a fresh read.** The draft is
    computed on read and stored nowhere, so between rendering and accepting a
    task can be completed elsewhere or a recurrence can fire -- accepting
    *what was shown* is the honest contract, and re-deriving would pin
    something nobody saw.

    Each pin goes through `pin_task`, so the ownership check, the
    repin-clears-release rule and the position are one definition rather than
    two. What is added here is only the record that this was a draft.
    """
    return [pin_task(owner, day, task, from_draft=True) for task in tasks]


@transaction.atomic
def unpin_task(owner, day, task):
    """Take ``task`` off ``day``, keeping the record that it was chosen.

    Not a delete. "I decided this wasn't for today" and "I never got to it"
    are different facts, and Crane 3's review has to be able to tell them
    apart -- see the model docstring.

    Unpinning something that was never pinned is a no-op rather than an
    error: the caller's intent is already satisfied.
    """
    focus = DailyFocus.objects.filter(
        owner=owner, entry__date=day, task=task, released_at__isnull=True
    ).first()
    if focus is None:
        return None
    focus.released_at = timezone.now()
    focus.save(update_fields=["released_at"])
    # The other half of the pair the review block rests on. `released_at` is
    # how a pin ends, so a decommitment can be told from a failure; logging the
    # choice and not the release would put that distinction back out of reach.
    life_log.record(
        owner,
        life_log.FOCUS_RELEASED,
        task=task,
        entry=focus.entry,
        occurred_at=focus.released_at,
    )
    return focus
