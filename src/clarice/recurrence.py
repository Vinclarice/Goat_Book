"""How often a thing repeats, and when the next one falls due.

**Neither core owns this and both depend on it.** A task recurs and so does a
bill, and the calendar arithmetic that answers *when is the next one* is the
same arithmetic for both — it is a fact about months and weeks, not about
tasks or money.

**Extracted September 2, 2026**, as step 2 of moving Money into an app of its
own. Before that, `lists/bills.py` imported `Item.Recurrence` to spell
*monthly* and `lists.services._advance_due_date` — a **private** function — to
work out a date. Both worked. Both said a bill's schedule was a property of the
task core, which stopped being true nine increments earlier, and the second gave
money a claim on a name whose owner had written *this may change* into it.

**A neutral module rather than a copy**, which is the whole point:
`advance_due_date` carries a month of argument about a single `>` and the
consequences of getting it wrong are a task due the day you finished it. Two
copies of that reasoning would be one copy too many —
`principles.md`'s *one rule, one authoritative definition*.

**The doctrine it encodes is the task core's, and money deliberately departs
from it.** *Missed periods are skipped, not replayed*: five missed bin rounds
are five things that did not happen. A missed payment is still owed, so
`money`'s replay asks this function for exactly one interval and then steps
forward itself, rather than changing what it means here. That asymmetry is the
argument `Bill` exists on — `architecture-trajectory.md` §4, and
`roadmap-history.md` under *A bill earns its own model*.

`lists.models` and `lists.services` re-export what they used to define, so
`Item.Recurrence.WEEKLY` and `services._advance_due_date` still resolve. Those
are aliases of these objects, not copies, and cannot drift.
"""
from calendar import monthrange
from datetime import timedelta

from django.db import models
from django.utils import timezone


class Recurrence(models.TextChoices):
    """How often a commitment repeats.

    Module level rather than nested in `Item` because RecurringCommitment is
    declared above `Item` and needs the same choices -- the cadence is the
    commitment's rule, and an occurrence's copy is a snapshot of what it ran
    under. `Item.Recurrence` remains an alias below, so nothing that already
    says `Item.Recurrence.WEEKLY` has to change.
    """

    NONE = "none", "Doesn't repeat"
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    #: Added August 27, 2026, because a salary every two weeks is ordinary and
    #: this had no word for it. Not a special case: `_nth_occurrence_after`
    #: already advances weekly by whole weeks, so a fortnight is two of them.
    FORTNIGHTLY = "fortnightly", "Every two weeks"
    MONTHLY = "monthly", "Monthly"
    # Added August 20, 2026 for the commitments that come round least often
    # and are hardest to hold in your head -- a property tax bill due 5
    # October could not be expressed at all. Both are the monthly arithmetic
    # with a multiplier rather than new branches, so they inherit its
    # anchor-and-clamp behaviour instead of restating it.
    QUARTERLY = "quarterly", "Quarterly"
    ANNUAL = "annual", "Annually"


class CadenceMode(models.TextChoices):
    """Whether a repeating commitment is fixed to the calendar or to the last
    time it was actually done.

    `design-concept.md` calls this distinction load-bearing, and it is: the two
    modes disagree by months on a commitment done late, and each is plainly
    wrong for the other's cases.

    ANCHORED is the default, and the asymmetry is deliberate. A mortgage that
    quietly drifts off the 1st is a missed payment; a furnace filter changed six
    days early is nothing. Somebody who never discovers this setting keeps the
    behaviour that cannot hurt them.
    """

    #: The calendar rule is the truth. Due the 1st whether or not last month's
    #: was paid on time. Missed periods are skipped, never replayed.
    ANCHORED = "anchored", "On a fixed schedule"
    #: The elapsed interval is the truth. A filter lasts a month from when it
    #: was changed, not from when it was notionally due.
    FLOATING = "floating", "A set time after it is done"


def nth_occurrence_after(base, recurrence, n):
    """The nth scheduled date after `base`, counting in calendar units.

    Computed from the anchor each time rather than by stepping one interval
    off the last result, which matters for monthly: the 31st advanced through
    February and then carried forward would spend the rest of the year on the
    28th. Here February is the only month that clamps, and March is the 31st
    again.
    """
    if recurrence == Recurrence.DAILY:
        return base + timedelta(days=n)
    if recurrence == Recurrence.WEEKLY:
        return base + timedelta(weeks=n)
    if recurrence == Recurrence.FORTNIGHTLY:
        return base + timedelta(weeks=2 * n)
    # Quarterly and annual are monthly with a multiplier, deliberately: the
    # anchor arithmetic below is the part that is easy to get wrong, and three
    # copies of it would be three chances to.
    months = {
        Recurrence.MONTHLY: 1,
        Recurrence.QUARTERLY: 3,
        Recurrence.ANNUAL: 12,
    }.get(recurrence)
    if months is not None:
        n = n * months
        month_index = base.month - 1 + n
        year = base.year + month_index // 12
        month = month_index % 12 + 1
        return base.replace(
            year=year, month=month, day=min(base.day, monthrange(year, month)[1])
        )
    return None


def advance_due_date(due_date, recurrence, today=None, mode=CadenceMode.ANCHORED):
    """The next occurrence's due date, which is always strictly after today.

    **Strictly after, and the strictness is the decision** -- corrected here on
    August 28, 2026. This line read *"never already in the past"* for a month,
    which is a weaker claim than the code makes: today is not the past, so that
    wording promised an occurrence falling exactly on today would be kept, and
    `candidate > today` drops it. The code was right and the sentence was
    wrong.

    **Why dropping it is right: the completion is happening today.** Bins every
    Monday, last done June 1, done again today -- today's slot has just been
    satisfied by the act that triggered this call, so returning it would hand
    somebody a task due the day they did it. `>=` was measured rather than
    argued about: it breaks
    `test_a_very_late_weekly_commitment_skips_every_missed_week`, which spawns
    August 10 instead of August 17 on a Monday-anchored series. That test pins
    this boundary on purpose, and
    `test_a_series_never_spawns_overdue.test_the_slot_the_completion_lands_on_is_not_respawned`
    now says so by name rather than by coincidence.

    **What this does not decide** is whether *money* should skip a missed period
    at all -- a bill you did not pay is still owed in a way a bin round you
    missed is not. **Answered on September 1, 2026, and answered elsewhere**:
    `lists/bills.py` replays them, and does it by calling this function for
    exactly one interval rather than by changing what it means. So this
    comparison and the doctrine below are still the task core's, unchanged and
    still correct for tasks -- which is the point of the two models, and what
    `test_a_missed_bill_is_still_owed.test_a_task_still_skips` exists to keep
    true from the other side.

    It used to be one interval past the *previous due date*, full stop. A
    monthly commitment due July 4 and completed August 10 therefore produced a
    successor due August 4 -- overdue at the instant it was created, on a task
    the person had just finished. `roadmap.md` carried this as "one defect to
    fix on the way in rather than port"; the way in happened and it was not.

    **Missed periods are skipped, not replayed.** The schedule keeps its anchor
    and moves forward until it clears today, so a filter changed on the 4th is
    still on the 4th afterwards, and five missed weeks produce one task rather
    than five. Occurrences that did not happen are not invented -- a fabricated
    history is worse than an absent one, and `principles.md` refuses it.

    All of that describes **anchored**, which is the default and was the only
    mode until August 15, 2026. **Floating** counts from the completion instead
    -- a furnace filter lasts a month from when it was changed, not from a date
    nobody acted on -- and needs no skipping, because it starts from today by
    construction.

    See `CadenceMode` for why anchored is the default rather than a coin toss.
    """
    if today is None:
        today = timezone.localdate()
    if mode == CadenceMode.FLOATING:
        # The old due date is deliberately ignored, including a future one:
        # floating means the clock restarts when the work is actually done.
        return nth_occurrence_after(today, recurrence, 1)

    base = due_date or today

    # Bounded rather than `while True`: a corrupt cadence or a due date far in
    # the past should not spin. Two thousand steps clears five years of daily.
    for n in range(1, 2001):
        candidate = nth_occurrence_after(base, recurrence, n)
        if candidate is None:
            return None
        if candidate > today:
            return candidate
    return None
