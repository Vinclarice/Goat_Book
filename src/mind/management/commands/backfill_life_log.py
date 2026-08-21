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

**Idempotent by subject, not by a marker.** A second run finds the events the
first one wrote and skips their subjects, which also means it will never
duplicate what increment 2 recorded live. A marker row would have been a
seventh thing to keep true.

**Here rather than beside `clarice/life_log.py`, which is where it belongs
conceptually.** `clarice` is the project package and not an installed app, so
Django never discovers commands under it -- and `mind` is where the log's other
backfill already lives (`backfill_typed_tags`). The seam itself stays in
`clarice/`; only this operational script moved, and it still writes through
`life_log` rather than touching `ActivityEvent.objects.create` directly.

Its tests are in `clarice/tests/test_life_log_backfill.py`, with the rest of
the cross-core seam and on the Django runner. New tests for the knowledge core
belong on pytest; this is not one.
"""

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

        seen_tasks = self._task_subjects_already_logged(owner)
        for task in Item.objects.filter(owner=owner).exclude(
            completed_at=None, archived_at=None
        ):
            if task.completed_at and (
                task.pk,
                life_log.TASK_COMPLETED,
            ) not in seen_tasks:
                emit(life_log.TASK_COMPLETED, task.completed_at, task=task)
            if task.archived_at and (
                task.pk,
                life_log.TASK_ARCHIVED,
            ) not in seen_tasks:
                emit(life_log.TASK_ARCHIVED, task.archived_at, task=task)

        for focus in DailyFocus.objects.filter(owner=owner).select_related("entry", "task"):
            if (focus.task_id, life_log.FOCUS_PINNED) not in seen_tasks:
                emit(
                    life_log.FOCUS_PINNED,
                    focus.selected_at,
                    task=focus.task,
                    entry=focus.entry,
                )
            if focus.released_at and (
                focus.task_id,
                life_log.FOCUS_RELEASED,
            ) not in seen_tasks:
                emit(
                    life_log.FOCUS_RELEASED,
                    focus.released_at,
                    # May be None: a focus outlives the task it named, which
                    # is why `task_text` is snapshotted on the row. The day is
                    # still a real subject, so the event is still worth having.
                    task=focus.task,
                    entry=focus.entry,
                )

        seen_weeks = self._week_subjects_already_logged(owner)
        for review in WeeklyReview.objects.filter(owner=owner).exclude(
            completed_at=None
        ):
            key = (review.week_start.isoformat(), life_log.WEEK_REVIEWED)
            if key not in seen_weeks:
                emit(
                    life_log.WEEK_REVIEWED,
                    review.completed_at,
                    week_start=review.week_start,
                )

        for intention in WeeklyIntention.objects.filter(owner=owner):
            key = (intention.week_start.isoformat(), life_log.INTENTION_SET)
            if key not in seen_weeks:
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
            key = (outcome.week_start.isoformat(), life_log.OUTCOME_CHOSEN)
            if key not in seen_weeks:
                emit(
                    life_log.OUTCOME_CHOSEN,
                    outcome.created_at,
                    week_start=outcome.week_start,
                )

        return counts

    # -- what is already there -------------------------------------------

    def _task_subjects_already_logged(self, owner):
        """Every (task, type) pair the log already holds, live or reconstructed.

        Read once rather than asked per row: this is the check that makes a
        second run safe, and doing it as a query per task would make the safe
        thing the slow thing.
        """
        return set(
            ActivityEvent.objects.filter(owner=owner, task__isnull=False)
            .values_list("task_id", "event_type")
        )

    def _week_subjects_already_logged(self, owner):
        """The same, for the three events whose subject lives in the payload.

        `week_start` is the one payload key slice 1 has, so this reads it
        directly rather than through a JSONB index that does not exist -- the
        set of week-grained events per owner is small enough that it does not
        need one, and saying so here is cheaper than adding an index nothing
        else uses.
        """
        return {
            (event.payload.get("week_start"), event.event_type)
            for event in ActivityEvent.objects.filter(
                owner=owner,
                event_type__in=(
                    life_log.WEEK_REVIEWED,
                    life_log.INTENTION_SET,
                    life_log.OUTCOME_CHOSEN,
                ),
            )
        }
