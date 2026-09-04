"""One box, and the four places a line can go.

`superlists-2.0-plan.md` increment 4. Two questions decide it -- *is it done?*
and *is it for today?* -- so there are four destinations and one existing
service underneath all of them:

    Destination   Node   Facet and Item   Pin               Completed
    Note          yes    no               no                --
    Did           yes    yes              below the line    yes
    Today         yes    yes              below the line    no
    Pool          yes    yes              no                no

**Every line is a `Node` first**, which is what makes the log an intake pipe
rather than a second task list: a line is searchable, mentionable and
proposable the moment it is written, whatever else happens to it.

**Here rather than in `mind/services.py`, and the reason is the pin.**
`confirm_actionable` already reaches from the knowledge core into the task
core, and its own comment keeps that seam *"visible at the one call site that
uses it, not in a header that suggests a wider coupling"*. A Today line also
pins, which is `daily`'s -- and `daily.services` imports `mind.services`, so
the reverse cannot be a module-level import at all. `clarice/` is where a write
that is a peer of all three belongs, the same placement `life_log.py` and
`day_log.py` already have.

**Nothing new is stored.** A destination is not a column: it is which of four
existing services ran, and everything a reader can ask afterwards -- is it a
task, is it chosen for today, is it done -- is answered by the rows those
services wrote.
"""

from django.db import transaction

from daily import services as daily_services
from lists import services as task_services
from mind import services as mind_services
from mind.models import NodeSource

from . import clocks


#: Words, and nothing else happens to them.
NOTE = "note"
#: Done on the spot: a task, chosen for today, and finished.
DID = "did"
#: To do later today: a task, chosen for today, still open.
TODAY = "today"
#: For whenever: a task, chosen for no day.
POOL = "pool"

#: In the order the box offers them, which is the order of *how much this
#: commits you* -- and an allowlist rather than a check for the negative, on
#: `life_log.record`'s precedent: an unrecognised destination is refused rather
#: than quietly treated as a note.
DESTINATIONS = (NOTE, DID, TODAY, POOL)

#: The three that make a task. `NOTE` is the absence of this rather than a
#: fourth branch, which is what keeps the phone's existing behaviour exactly
#: what it was.
MAKE_A_TASK = frozenset({DID, TODAY, POOL})

#: The two that are acts of execution -- `superlists-2.0-plan.md` rule 3, whose
#: enumeration is *a tick on a chosen task, or a Did or Today line*. Increment
#: 2 built the tick, in `lists.services`; this is the other half, and the two
#: sites are the whole of it.
DRAW_THE_LINE = frozenset({DID, TODAY})


class ComposerError(Exception):
    """A line that cannot be written where it was aimed."""


@transaction.atomic
def write_a_line(owner, *, text, destination, now, captured_at=None, public_id=None,
                 tags=(), from_a_phone=False):
    """Write one line, and put it where the destination says.

    **One transaction, for `confirm_actionable`'s own reason.** A node, a facet
    and a task are written together so that *"a confirmed actionable facet with
    no live task"* is not a state anything can reach -- and a Did line adds a
    pin and a completion to that same all-or-nothing.

    **The line is drawn before the pin, not after.** A Did or Today line is an
    act of execution, so it closes the morning's list -- and then joins *below*
    what it just closed, which is the plan's table. Drawing afterwards would
    stamp `list_closed_at` later than the pin's `selected_at` and put the line
    that ended the morning inside it. The ordinary tick in `lists.services` has
    the opposite shape for the same rule: there the pin was made hours earlier
    and belongs above.

    **The day pinned to is the owner's today, whatever `captured_at` says.**
    *Today* means today. A capture that waited in a phone's offline queue keeps
    the timestamp of the thought, so its words land on the day it was written,
    while a commitment it carried would be for the day it arrives. That
    combination is unreachable today -- the phone sends `note` and nothing else
    -- and is written down rather than guarded against, because guarding would
    mean refusing a capture, and `principles.md` puts durability above
    cleverness.

    Returns the node, which is the one thing every destination produces.
    """
    if destination not in DESTINATIONS:
        raise ComposerError(f"{destination!r} is not one of {', '.join(DESTINATIONS)}")

    node, created = mind_services.capture_idempotent(
        owner,
        content=text,
        captured_at=captured_at or now,
        source=NodeSource.MOBILE if from_a_phone else NodeSource.WEB,
        actor=owner.get_username(),
        public_id=public_id,
        tags=list(tags),
    )
    # A replay of a key already seen. `capture_idempotent` returned the row the
    # first attempt made, and everything below is idempotent in its own right --
    # but running it again would be doing work for an act that already happened,
    # and `complete_item` on a task somebody has since reopened would undo their
    # correction. The first attempt's outcome is the one that counts, exactly as
    # it is for the capture itself.
    if not created:
        return node, created

    if destination in MAKE_A_TASK:
        facet = mind_services.attach_commitment(
            node, now=now, actor=owner.get_username()
        )
        today = clocks.day_for(owner, now)
        if destination in DRAW_THE_LINE:
            daily_services.draw_the_line(owner, today, now=now)
            daily_services.pin_task(owner, today, facet.task)
        if destination == DID:
            task_services.complete_item(facet.task)

    return node, created
