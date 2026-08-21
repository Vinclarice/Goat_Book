"""Give the log the history the task core already held.

`temporal-substrate-plan.md` Track A increment 3, and the answer to its **D2**.

**How far back: as far as the data goes.** There is no date cutoff, because the
limit is not age -- it is whether a timestamp exists. A horizon would discard
real records to satisfy a number nobody chose.

**Nothing invented. No recorded time, no event.** Six of the ten life events
can be reconstructed because something already stores when they happened. Four
cannot, and are simply absent:

- `TASK_REOPENED` -- reopening clears `completed_at`, erasing its own evidence.
- `COMMITMENT_CHANGED` -- nothing records when a task started repeating.
- Every rewrite of an intention but the first -- one row per week, edited in
  place.
- Any release before the last -- repinning clears `released_at`.

**Under-recording is the safe direction**, and it is the whole shape of this
command. A log that says less than happened can be added to; one that says more
cannot be corrected, because the trigger refuses `UPDATE` and `DELETE`.

**A command rather than a data migration**, departing from this repository's
habit deliberately. The backfills in `lists/migrations` fix columns and can be
fixed again. This one writes to the append-only log, where a wrong run is
permanent -- so it is run when somebody is looking, after `--dry-run` has said
what it would do.

**Idempotent by counting what is already there**, not by a marker. A second run
finds the events the first one wrote and spends them, which also means it never
duplicates what increment 2 recorded live. A marker row would have been a
seventh thing to keep true.

**Three of its four repairs are recorded in `code-review-2026-08-21.md`** as
C1-C3, found the day after it first ran, and
`clarice/tests/test_life_log_repairs.py` holds them. All three were live when
this ran against production and none of them fired -- not because they were
harmless, but because the data was too thin to reach any of them.

**Here rather than beside `clarice/life_log.py`, which is where it belongs
conceptually.** `clarice` is the project package and not an installed app, so
Django never discovers commands under it -- and `mind` is where the log's other
backfill already lives (`backfill_typed_tags`). The seam itself stays in
`clarice/`; only this operational script moved, and it still writes through
`life_log` rather than touching `ActivityEvent.objects.create` directly.

Its tests are in `clarice/tests/`, with the rest of the cross-core seam and on
the Django runner. New tests for the knowledge core belong on pytest; these are
not.
"""

from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from clarice import life_log
from daily.models import DailyFocus
from lists.models import Item
from mind.models import ActivityEvent
from review.models import WeeklyIntention, WeeklyOutcome, WeeklyReview


class Command(BaseCommand):
    help = "Reconstruct life events from timestamps the task core already holds"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Say what would be written, and write nothing.",
        )
        parser.add_argument(
            "--owner",
            help="Limit to one username. Everybody, if not given.",
        )

    def handle(self, *args, **options):
        owners = get_user_model().objects.all()
        if options["owner"]:
            owners = owners.filter(username=options["owner"])
            if not owners.exists():
                raise CommandError(f"No user named {options['owner']!r}")

        dry_run = options["dry_run"]
        counts = {}
        # One transaction for the whole run rather than one per row: a
        # half-finished backfill is the worst outcome available here, because
        # the second attempt cannot tell which half it already did from which
        # half increment 2 recorded live.
        with transaction.atomic():
            for owner in owners:
                for event_type, count in self._for_owner(owner, dry_run).items():
                    counts[event_type] = counts.get(event_type, 0) + count
            if dry_run:
                transaction.set_rollback(True)

        if not counts:
            # Said out loud rather than left as silence. "Ran and found
            # nothing" and "never ran" is the distinction MAINTENANCE_RAN
            # exists for one layer up, and a command that prints nothing
            # teaches the same wrong lesson.
            self.stdout.write("Nothing to reconstruct.")
            return

        self.stdout.write("Would write:" if dry_run else "Wrote:")
        for event_type in sorted(counts):
            self.stdout.write(f"  {event_type}: {counts[event_type]}")

    # -- per owner -------------------------------------------------------

    def _for_owner(self, owner, dry_run):
        counts = {}

        def emit(event_type, occurred_at, **subjects):
            counts[event_type] = counts.get(event_type, 0) + 1
            if not dry_run:
                life_log.record(
                    owner,
                    event_type,
                    occurred_at=occurred_at,
                    origin=life_log.RECONSTRUCTED,
                    # The person did do this. The log simply was not there,
                    # which is what `origin` says -- crediting the backfill as
                    # the actor would lose the one fact that is not in doubt.
                    actor=owner.get_username(),
                    **subjects,
                )

        subjects = self._ledger_of_subject_events(owner)
        weeks = self._ledger_of_week_events(owner)

        for task in Item.objects.filter(owner=owner).exclude(
            completed_at=None, archived_at=None
        ):
            if task.completed_at and not subjects.already_have(
                (task.pk, None, life_log.TASK_COMPLETED)
            ):
                emit(life_log.TASK_COMPLETED, task.completed_at, task=task)
            if self._is_a_real_archive(task) and not subjects.already_have(
                (task.pk, None, life_log.TASK_ARCHIVED)
            ):
                emit(life_log.TASK_ARCHIVED, task.archived_at, task=task)

        for focus in DailyFocus.objects.filter(owner=owner).select_related(
            "entry", "task"
        ):
            # Keyed on the day as well as the task, which is the grain
            # `DailyFocus.unique_daily_focus_per_entry_task` already enforces.
            # Keyed on the task alone, one live pin stood for every pin of that
            # task there had ever been, and the rest were skipped in silence.
            if not subjects.already_have(
                (focus.task_id, focus.entry_id, life_log.FOCUS_PINNED)
            ):
                emit(
                    life_log.FOCUS_PINNED,
                    focus.selected_at,
                    task=focus.task,
                    entry=focus.entry,
                )
            if focus.released_at and not subjects.already_have(
                (focus.task_id, focus.entry_id, life_log.FOCUS_RELEASED)
            ):
                emit(
                    life_log.FOCUS_RELEASED,
                    focus.released_at,
                    # May be None: a focus outlives the task it named, which
                    # is why `task_text` is snapshotted on the row. The day is
                    # still a real subject, so the event is still worth having.
                    task=focus.task,
                    entry=focus.entry,
                )

        for review in WeeklyReview.objects.filter(owner=owner).exclude(
            completed_at=None
        ):
            key = (review.week_start.isoformat(), life_log.WEEK_REVIEWED)
            if not weeks.already_have(key):
                emit(
                    life_log.WEEK_REVIEWED,
                    review.completed_at,
                    week_start=review.week_start,
                )

        for intention in WeeklyIntention.objects.filter(owner=owner):
            key = (intention.week_start.isoformat(), life_log.INTENTION_SET)
            if not weeks.already_have(key):
                # `created_at`, not `updated_at`. The first setting is a real
                # recorded moment; the rewrites after it left no trace, and
                # stamping this with the last edit would date a decision to a
                # day it was not made.
                emit(
                    life_log.INTENTION_SET,
                    intention.created_at,
                    week_start=intention.week_start,
                )

        for outcome in WeeklyOutcome.objects.filter(owner=owner):
            # Counted, not set-tested: a week has as many outcomes as it has
            # commitments, so one event cannot stand for the whole week the way
            # WEEK_REVIEWED and INTENTION_SET legitimately do.
            key = (outcome.week_start.isoformat(), life_log.OUTCOME_CHOSEN)
            if not weeks.already_have(key):
                emit(
                    life_log.OUTCOME_CHOSEN,
                    outcome.created_at,
                    week_start=outcome.week_start,
                )

        return counts

    @staticmethod
    def _is_a_real_archive(task):
        """Whether this archive was a decision, or the mechanism behind one.

        A recurring task is archived the instant it is completed, to free its
        text for the next occurrence. `complete_item` refuses to log that and
        says why in four lines: logging it *"would put a retirement in the
        record of a habit somebody is keeping."* Reading the two timestamps
        independently wrote exactly that retirement, for every recurring task
        anybody had ever completed.

        Narrow on purpose. A recurring task archived *later* than it was
        completed is somebody ending the undertaking, which is a decision and
        belongs in the record.
        """
        if task.archived_at is None:
            return False
        return not (
            task.recurrence != Item.Recurrence.NONE
            and task.archived_at == task.completed_at
        )

    # -- what is already there -------------------------------------------

    def _ledger_of_subject_events(self, owner):
        """Every subject-bearing event the log already holds, **counted**.

        Counted rather than set-tested, which is the repair C3 needed:
        hard-deleting a pinned task leaves `DailyFocus.task` NULL, so two
        orphaned rows on one day share a key exactly. A set says "seen it" and
        loses one of them for ever; a count says "seen two of these", which is
        the truth. Ordinary SQL NULL semantics let both rows exist -- the model
        says so out loud -- so the ledger has to permit both too.

        Read once rather than asked per row: this is the check that makes a
        second run safe, and a query per subject would make the safe thing the
        slow thing.
        """
        return _Ledger(
            Counter(
                ActivityEvent.objects.filter(owner=owner)
                .exclude(task__isnull=True, entry__isnull=True)
                .values_list("task_id", "entry_id", "event_type")
            )
        )

    def _ledger_of_week_events(self, owner):
        """The same, for the three events whose subject lives in the payload.

        `week_start` is the one payload key slice 1 has, so this reads it
        directly rather than through a JSONB index that does not exist -- the
        set of week-grained events per owner is small enough that it does not
        need one, and saying so here is cheaper than adding an index nothing
        else uses.
        """
        return _Ledger(
            Counter(
                (event.payload.get("week_start"), event.event_type)
                for event in ActivityEvent.objects.filter(
                    owner=owner,
                    event_type__in=(
                        life_log.WEEK_REVIEWED,
                        life_log.INTENTION_SET,
                        life_log.OUTCOME_CHOSEN,
                    ),
                )
            )
        )


class _Ledger:
    """Events the log already holds, spent as the pass accounts for them.

    `already_have(key)` answers *"is one of these already recorded that I have
    not yet matched?"* and spends it if so. That is what makes the pass
    idempotent against its own previous runs **and** against what increment 2
    recorded live, without having to tell the two apart -- both are simply rows
    that are already there.
    """

    def __init__(self, counts):
        self._counts = counts

    def already_have(self, key):
        if self._counts.get(key, 0) > 0:
            self._counts[key] -= 1
            return True
        return False
