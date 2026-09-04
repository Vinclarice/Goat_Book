"""The three decisions a leftover gets, and nothing else.

`superlists-2.0-plan.md` rule 7: **leftovers get one decision each, never a
move.** Tomorrow, back to the pool, or let go. Underneath it, unchanged, is
`daily-operating-system-vision.md`'s first rule -- *never automatically
reschedule everything left incomplete* -- which is why these are three verbs a
person applies one at a time and not a button that sweeps a list.

**None of the three rewrites today.** Each decides what happens *next*; the
day's own record is what it was. That is the difference the plan means by *one
decision, never a move*: a move would take the commitment off the day it was
made on, and the honest denominator `DailyFocus` exists to hold would go with
it.

**And never a date move.** *Tomorrow* pins to tomorrow; it does not touch the
task's due date. A due date is a promise to somebody -- a bill, a person, a
deadline -- and choosing to work on something tomorrow is not the same act as
re-promising it for tomorrow. The Day page's own row-level *Tomorrow* did move
the due date until September 3, 2026, and that was two buttons with one word
and opposite meanings.

**Here rather than in one app**, on `composer.py`'s reasoning: letting go
archives an `Item`, retires a `mind.Facet` and releases a `daily.DailyFocus`,
so it is a peer of three apps and belongs to none of them.

Increment 6's stale prompt is a second caller for `let_go` and nothing else --
rule 8's *let go archives the task and retires its facet while the node stays*
is this function, reached from a different question.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from clarice import life_log
from daily import services as daily_services
from lists import services as task_services
from lists.models import Item
from mind.models import Facet, FacetKind


class LeftoverError(Exception):
    """A decision that cannot be applied to this task."""


#: What a leftover can be told to do. An allowlist, so an unrecognised decision
#: is refused rather than quietly doing the least surprising thing.
TOMORROW = "tomorrow"
POOL = "pool"
LET_GO = "let_go"
DECISIONS = (TOMORROW, POOL, LET_GO)


def _owned(owner, task):
    if task.owner_id != owner.id:
        # Fails closed, per `principles.md`, and here rather than in the view
        # because all three of these need it.
        raise LeftoverError("That task isn't yours to decide about.")


@transaction.atomic
def tomorrow(owner, task, *, today):
    """Choose it for tomorrow. Today's record is untouched.

    **Today's pin stays**, and that is the decision rather than an oversight:
    you chose it, you did not do it, and you are choosing it again. Releasing
    it would move an unfinished commitment out of the denominator, and a finish
    rate nobody can fail describes nothing.

    `pin_task` rather than a due date -- see this module's own note on why
    those are different acts.
    """
    _owned(owner, task)
    return daily_services.pin_task(owner, today + timedelta(days=1), task)


@transaction.atomic
def back_to_the_pool(owner, task, *, today):
    """Unchoose it, and leave it open.

    The task is already in the pool -- the pool is every active `Item` -- so
    what this does is end the *choice*, which `unpin_task` records as a
    release rather than a deletion. `set_aside` is where that lands, reported
    beside the denominator rather than inside it, so a week where four things
    were reconsidered reads differently from one where nothing was.
    """
    _owned(owner, task)
    return daily_services.unpin_task(owner, today, task)


@transaction.atomic
def let_go(owner, task, *, today=None):
    """Stop carrying it. The thought stays.

    Rule 8: *let go archives the task and retires its facet while the node
    stays.* Paper could not drop a task without losing the idea; this can, and
    that is most of the argument for the pool pruning itself at all.

    **Retired, not dismissed.** `dismiss_facet` means *this was never a
    commitment* and is the one correction the commitment parser will ever get;
    spending that signal on a commitment that was real and is now over would
    teach it the wrong lesson. This sets `retired_at` and nothing else, so the
    node leaves the commitment tier and returns to quiet knowledge.

    **Archived, not deleted**, which is what makes this reversible: the archive
    is a place somebody browses, and restoring is one click. `principles.md`
    asks for a confirmation on anything that leaves no trace, and this leaves
    the task, the node and the record of having chosen it.

    `today` is optional because increment 6's stale prompt lets go of things
    nobody pinned; `unpin_task` is a no-op where there is no live pin.
    """
    _owned(owner, task)
    if today is not None:
        daily_services.unpin_task(owner, today, task)
    # Every live actionable facet, not one: the constraint allows a single live
    # one per node, but a task can be reached from more than one node once
    # anything else points at it, and letting go of the task ends all of them.
    Facet.objects.filter(
        task=task, kind=FacetKind.ACTIONABLE, retired_at__isnull=True
    ).update(retired_at=timezone.now())
    # Read before the archive, because after it every call looks the same.
    # Doing the same thing twice is one fact -- the contract
    # `test_emitters_are_idempotent.py` holds over every emitter, and this one
    # over-recorded until that file failed on it.
    was_open = (
        Item.objects.filter(pk=task.pk)
        .exclude(status=Item.Status.ARCHIVED)
        .exists()
    )
    archived = task_services.archive_item(task)
    if was_open:
        # **Its own fact, beside the archive rather than instead of it.**
        # `archive_item` writes `TASK_ARCHIVED` for filing a finished task too,
        # so a count over that cannot tell tidying from abandoning -- and rule
        # 8's payoff is that the weekly review can report lines let go, *"a
        # better number than lines open"*. Two rows, because two things
        # happened.
        life_log.record(owner, life_log.TASK_LET_GO, task=task)
    return archived


def decide(owner, task, decision, *, today):
    """Apply one of `DECISIONS` by name, for a boundary that took a string."""
    if decision == TOMORROW:
        return tomorrow(owner, task, today=today)
    if decision == POOL:
        return back_to_the_pool(owner, task, today=today)
    if decision == LET_GO:
        return let_go(owner, task, today=today)
    raise LeftoverError(f"{decision!r} is not one of {', '.join(DECISIONS)}")
