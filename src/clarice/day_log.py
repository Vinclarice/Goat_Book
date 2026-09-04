"""What happened on one day, read rather than stored.

`superlists-2.0-plan.md` rule 6: **the log is a read, not a table.** Written
lines are `Node`s; derived lines are task completions, routine occurrences,
bill payments and pins -- every one of which already carries a timestamp. No
new model holds this, because `nightjar`'s own rule for the substrate is that
nothing may write a row a read could have produced.

**Here rather than in `daily/`, for the reason `recall.py` gives**: a read that
crosses both cores cannot belong to either, and `clarice/` is where the rules
that outrank one app already live. This one reaches into `mind`, `lists`,
`daily`, `routines` and `money` at once, which is four apps more than any of
them should know about.

**And beside `recall.py` rather than inside it.** That module answers *what
else was going on near this instant* and reads the log alone. This answers
*what happened on this date*, and most of its sources are not in the log at
all -- a bill's `paid_at` and an occurrence's `decided_at` are columns on
records that were never events. Two questions, two reads, one shared idea:
records that already carry a time.

**Derived task lines come from the life-event log, not from the task.** This is
rule 6's second half, and the plan records that it found the design wrong
rather than incomplete: unticking clears `completed_at`, so a read over that
column would lose a completion that really happened. `TASK_COMPLETED` and
`TASK_REOPENED` are separate append-only rows, so the log shows *done at 14:02,
reopened at 14:05* and what happened never changes retroactively.

**An appointment that passed joins at increment 7**, as a sixth source and
without either of the five changing -- each is read on its own and merged by
time, so there is no shape for a new one to disturb.
"""

from dataclasses import dataclass
from datetime import datetime

from mind.models import ActivityEvent, EventType

from . import clocks


#: A line somebody wrote. The only kind whose words are their own.
WRITTEN = "written"
#: A task ticked, and a task unticked. Two kinds because they are two facts,
#: and rule 6 exists so the second cannot erase the first.
COMPLETED = "completed"
REOPENED = "reopened"
#: A line chosen for the day, and one taken back off it.
CHOSE = "chose"
RELEASED = "released"
#: A routine period that stopped being open.
ROUTINE = "routine"
#: A bill that got paid.
BILL = "bill"

#: Every kind a line can be, so a boundary can mirror the set rather than
#: guess at it -- the same shape `lists.api_v1` uses for `Item.Recurrence`,
#: with an assertion that shouts when the two part company.
KINDS = (WRITTEN, COMPLETED, REOPENED, CHOSE, RELEASED, ROUTINE, BILL)

#: Which life event makes which line.
#:
#: **An allowlist, on `life_log.record`'s precedent and against `recall.py`'s
#: R8.** Deriving this by subtraction from `EventType` would put every future
#: event on somebody's day with nobody having decided it belonged there.
#:
#: `TASK_ARCHIVED` is deliberately absent. A recurring task archives itself the
#: instant it is completed -- mechanism, not a decision -- and a day's log that
#: reported a retirement beside the habit somebody is keeping would be
#: describing the machinery rather than the life. `lists.services` makes the
#: same call at the point of writing, and logs the completion alone.
#:
#: The week-grain events -- `WEEK_REVIEWED`, `INTENTION_SET`, `OUTCOME_CHOSEN`
#: -- are absent for a different reason: they are about a week, and a week has
#: no instant a day can put in order beside a tick at 14:02.
EVENT_KINDS = {
    EventType.TASK_COMPLETED: COMPLETED,
    EventType.TASK_REOPENED: REOPENED,
    EventType.FOCUS_PINNED: CHOSE,
    EventType.FOCUS_RELEASED: RELEASED,
}


@dataclass(frozen=True)
class LogLine:
    """One thing that happened, at the time it happened.

    `text` is the subject's own words, never a sentence composed here: a note's
    content, a task's text, a routine's title, a payee. `detail` is the short
    qualifier its own domain words -- `routines.reads.progress_detail` and
    `money.reads.paid_detail` -- so that the log never says a figure or a
    tally in a way its own module would not.

    **`text` is None when the subject is gone**, and the line stays. The log
    outlives what it names: `ActivityEvent.task` is `DO_NOTHING` with no
    database constraint, precisely so an append-only row can point at something
    since deleted. Dropping the line instead would make a day quietly report
    less work than was done, and `subject_withheld` is what lets a surface say
    *something happened here* rather than render a bare verb -- the same
    distinction `recall.Neighbour` draws and for the same reason.
    """

    at: datetime
    kind: str
    text: str | None
    detail: str = ""
    subject_withheld: bool = False


def lines_for(owner, day):
    """Everything the records say about ``day``, in one order by time.

    **Oldest first.** The log is read the way it was written and the newest
    line is at the bottom, which is where somebody adding to it is already
    looking.

    **The day's edges are the owner's**, from `clocks.day_bounds`. Two events
    at 21:00 and 22:00 in New York are the 3rd and the 4th in UTC, and they are
    one evening.

    **Not gated on the day being today**, unlike the day payload's action items
    and bills. Those are live task state, and a task carries no history of what
    it looked like on the 30th -- showing today's open work there would assert
    something never true. Every source here is a dated record of something that
    happened, so reading one back is history rather than inference. That is the
    same split `routines` already makes on the same page.

    Five queries, one per source, merged in Python. A single query cannot span
    five tables with nothing in common but a timestamp, and a `UNION` over five
    different shapes would be the same merge written where it cannot be read.
    """
    start, end = clocks.day_bounds(owner, day)
    lines = [
        *_written(owner, start, end),
        *_from_the_log(owner, start, end),
        *_routines(owner, start, end),
        *_bills(owner, start, end),
    ]
    # By time, and by kind where two land in the same microsecond -- which
    # happens in tests and, one day, on a fast enough machine. An unstable sort
    # would make the same day render in two orders.
    return sorted(lines, key=lambda line: (line.at, line.kind))


def _written(owner, start, end):
    """Notes captured inside the day.

    **`live_nodes`, so there is one node-visibility rule.** A note somebody
    deleted or archived is not a line of their day -- and unlike `recall.py`,
    which withholds the *subject* of an event that still stands, there is no
    event here to keep: the note is the line. Its `CAPTURED` row remains in the
    log for anything that reads the log, which is what keeps `attendance_between`
    honest about a day somebody wrote in and then emptied.

    `captured_at` and not `created_at`: when the thought happened, not when the
    row was written. The two diverge on every imported record.
    """
    from mind.queries import live_nodes

    return [
        LogLine(at=node.captured_at, kind=WRITTEN, text=node.original_content)
        for node in live_nodes(owner)
        .filter(captured_at__gte=start, captured_at__lt=end)
        .only("original_content", "captured_at")
    ]


def _from_the_log(owner, start, end):
    """Ticks, unticks and picks, from the append-only log.

    `select_related("task")` rather than a query per row: a busy day is thirty
    of these, and a surface that has to ask what each one was about will ask
    thirty times.
    """
    return [
        LogLine(
            at=event.occurred_at,
            kind=EVENT_KINDS[event.event_type],
            text=event.task.text if event.task else None,
            subject_withheld=event.task_id is not None and event.task is None,
        )
        for event in ActivityEvent.objects.filter(
            owner=owner,
            event_type__in=EVENT_KINDS,
            occurred_at__gte=start,
            occurred_at__lt=end,
        ).select_related("task")
    ]


def _routines(owner, start, end):
    """Periods that stopped being open inside the day.

    **`decided_at`, so an elapsed-open period is not a line.** It is null while
    the outcome is still open, which the model keeps deliberately: a period
    nobody answered is not the same as one they skipped, and Crane 3 describes
    that rather than relabelling it.
    """
    from routines.models import RoutineOccurrence
    from routines.reads import progress_detail

    return [
        LogLine(
            at=occurrence.decided_at,
            kind=ROUTINE,
            text=occurrence.routine.title,
            detail=progress_detail(occurrence),
        )
        for occurrence in RoutineOccurrence.objects.filter(
            owner=owner, decided_at__gte=start, decided_at__lt=end
        ).select_related("routine")
    ]


def _bills(owner, start, end):
    """Bills paid inside the day.

    A bill stopped being an `Item` on September 1, 2026, so no task completion
    stands for one -- which is exactly why this is its own source rather than
    something the log already had.

    **Money in is included here and excluded everywhere else**, and the
    asymmetry is deliberate. `open_bills_for` drops income because a salary is
    not something to *do* on a Tuesday; a salary that arrived is something that
    *happened*, and a log of the day that silently omitted it would be a record
    with a hole in it rather than a list with one fewer chore.
    """
    from money.models import Bill
    from money.reads import paid_detail

    return [
        LogLine(
            at=bill.paid_at,
            kind=BILL,
            text=bill.payee,
            detail=paid_detail(bill),
        )
        for bill in Bill.objects.filter(
            owner=owner, paid_at__gte=start, paid_at__lt=end
        )
    ]
