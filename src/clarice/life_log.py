"""What happened to a life, written to the one append-only log.

`temporal-substrate-plan.md` Track A increment 2, and the answer to its D1:
**a module in `clarice/`, belonging to neither core.** The same placement
`clarice/search.py` has for a rule both cores need -- and `search-plan.md`'s
own D1 named `clarice/search.py` as where this question would be asked again,
which is what this is -- and the same placement `clarice/scheduled_mail.py`
took for the same reason a week earlier.

**The payoff is an import that does not happen.** `lists`, `daily` and `review`
name none of `mind`, `ActivityEvent` or `EventType`; this module is the only
one that knows the log exists, and the vocabulary is re-exported below so a
caller never reaches past it. The alternative -- each app creating rows -- would
restate the emit rules in three places, and two definitions of one thing is how
they come to disagree.

**Facts, not derivations.** *"This commitment was released on the 14th"* is a
fact and belongs in an append-only row. *"This project is stalling"* is a
derivation and stays computed on demand, the way `review` does today. Nothing
may be recorded here that a read could have produced, which is what keeps
`commercial-blueprint.md` Part 4's refusal of an event bus standing --
this is a function three service modules call by name, not a signal, not a bus,
and not something that fires without a caller you can grep for.

**Both or neither.** `record` is called inside the caller's own atomic block
and raises rather than swallowing. A completion whose event could not be written
is not a completion. Swallowing would make the log a sample rather than a
record, and every read over it would inherit a silent hole -- the exact failure
`MAINTENANCE_RAN` exists to prevent, one layer up.

**D3, for slice 1 only: a foreign key where one exists, the payload only for
what has none.** A week is neither a task nor a day's entry and has nothing to
point at, so its Monday goes in the payload. Nothing here snapshots a subject it
could join to: a copy of a task's text in the log is a second opinion about the
task, and `DailyFocus.task_text` already exists for the one case where a
snapshot is the point.
"""

from django.utils import timezone

from mind.models import ActivityEvent, EventType


# The vocabulary, re-exported so the task core never imports the knowledge
# core's models. These are the ten life events increment 1 added; the note
# events above them in `EventType` stay `mind`'s own business and are
# deliberately not surfaced here.
TASK_COMPLETED = EventType.TASK_COMPLETED
TASK_REOPENED = EventType.TASK_REOPENED
TASK_ARCHIVED = EventType.TASK_ARCHIVED
COMMITMENT_CHANGED = EventType.COMMITMENT_CHANGED
COMMITMENT_ENDED = EventType.COMMITMENT_ENDED
FOCUS_PINNED = EventType.FOCUS_PINNED
FOCUS_RELEASED = EventType.FOCUS_RELEASED
WEEK_REVIEWED = EventType.WEEK_REVIEWED
INTENTION_SET = EventType.INTENTION_SET
OUTCOME_CHOSEN = EventType.OUTCOME_CHOSEN

LIFE_EVENTS = frozenset(
    {
        TASK_COMPLETED,
        TASK_REOPENED,
        TASK_ARCHIVED,
        COMMITMENT_CHANGED,
        COMMITMENT_ENDED,
        FOCUS_PINNED,
        FOCUS_RELEASED,
        WEEK_REVIEWED,
        INTENTION_SET,
        OUTCOME_CHOSEN,
    }
)


def record(
    owner,
    event_type,
    *,
    task=None,
    entry=None,
    occurred_at=None,
    actor=None,
    week_start=None,
):
    """Write one fact to the log. Raises rather than failing quietly.

    ``occurred_at`` is **the fact's own time, not the write's**. Increment 3 is
    built on that distinction: a backfilled event carries the timestamp already
    recorded against the thing that happened, and an event stamped when it was
    written is a re-presentation wearing a record's clothes. It defaults to now
    only because something happening now has no other honest time.

    ``actor`` defaults to the owner's username. A scheduled pass should name
    itself instead -- a log that credits the person for what a cron did makes
    every later reading about attention wrong.
    """
    if event_type not in LIFE_EVENTS:
        # Fails here rather than at the database check constraint three layers
        # down, where the message names a column and not a caller.
        raise ValueError(f"{event_type!r} is not a life event")

    payload = {}
    if week_start is not None:
        # The one payload key slice 1 has. A week has nothing to point at, and
        # inventing a subject column for one cadence would be a column the next
        # cadence does not fit.
        payload["week_start"] = week_start.isoformat()

    return ActivityEvent.objects.create(
        owner=owner,
        event_type=event_type,
        task=task,
        entry=entry,
        occurred_at=occurred_at if occurred_at is not None else timezone.now(),
        actor=actor if actor is not None else owner.get_username(),
        payload=payload,
    )
