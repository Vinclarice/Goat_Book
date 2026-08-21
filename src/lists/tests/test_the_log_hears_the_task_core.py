"""What the task core now tells the append-only log.

`temporal-substrate-plan.md` Track A increment 2. The log has been able to say
these things since increment 1; this is where something says them.

**Scoped to durable decisions, and deliberately no wider.** Completing,
reopening, archiving, and starting or stopping a series. Every other field edit
is deferred by name -- a log recording each keystroke of a task's text is a log
nobody can read, and the brief says so.

**Both or neither.** The write happens inside the service's own atomic block,
so a completion whose event could not be recorded is not a completion. The last
test here is that guarantee, and it is the reason the log can later say *"since
then, nothing was recorded"* and mean it.
"""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from lists import services
from lists.models import Item, List
from mind.models import ActivityEvent, EventType


class TheLogHearsTheTaskCoreTest(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.area = List.objects.create(owner=self.alice, title="Home")
        self.task = services.create_item(self.area, "Call the plumber")

    def watermark(self):
        """A test cannot clear the log between arrangement and act -- the
        append-only trigger refuses a DELETE, which is the point of it. So
        setup is fenced off by id rather than removed."""
        last = ActivityEvent.objects.order_by("id").last()
        return last.pk if last else 0

    def types(self, since=0):
        return [
            e.event_type
            for e in ActivityEvent.objects.filter(pk__gt=since).order_by("id")
        ]

    def only(self, event_type):
        events = list(ActivityEvent.objects.filter(event_type=event_type))
        self.assertEqual(len(events), 1, self.types())
        return events[0]

    def test_completing_a_task_is_recorded_against_the_task(self):
        services.complete_item(self.task)

        event = self.only(EventType.TASK_COMPLETED)
        self.assertEqual(event.task_id, self.task.pk)
        self.assertEqual(event.owner_id, self.alice.pk)

    def test_it_records_when_the_task_was_completed_not_when_this_ran(self):
        """The fact's own time. `completed_at` is the recorded moment and the
        log must agree with it, or a reading joining the two sees a task
        finished twice a millisecond apart."""
        services.complete_item(self.task)

        self.assertEqual(
            self.only(EventType.TASK_COMPLETED).occurred_at,
            Item.objects.get(pk=self.task.pk).completed_at,
        )

    def test_completing_an_already_completed_task_records_nothing_further(self):
        """Nothing happened the second time, and a log that says otherwise
        makes every count over it wrong."""
        services.complete_item(self.task)
        services.complete_item(self.task)

        self.assertEqual(self.types().count(EventType.TASK_COMPLETED), 1)

    def test_a_recurring_task_records_the_completion_and_not_the_archive(self):
        """Completing a recurring task archives it immediately to free its
        text for the next occurrence. That archive is mechanism, not a
        decision, and logging it would put a retirement in the record of a
        habit somebody is keeping."""
        services.set_recurrence(self.task, Item.Recurrence.WEEKLY)
        mark = self.watermark()

        services.complete_item(self.task)

        self.assertEqual(self.types(mark), [EventType.TASK_COMPLETED])

    def test_reopening_a_task_un_says_the_completion(self):
        """Without this the log asserts a completion it can never retract, and
        any projection folded over it drifts the first time somebody ticks the
        wrong row."""
        services.complete_item(self.task)

        services.reopen_item(self.task)

        self.assertEqual(
            self.types(), [EventType.TASK_COMPLETED, EventType.TASK_REOPENED]
        )

    def test_archiving_a_task_is_recorded(self):
        services.archive_item(self.task)

        self.assertEqual(self.only(EventType.TASK_ARCHIVED).task_id, self.task.pk)

    def test_archiving_something_already_archived_records_nothing(self):
        services.archive_item(self.task)
        services.archive_item(self.task)

        self.assertEqual(self.types().count(EventType.TASK_ARCHIVED), 1)

    def test_starting_a_series_is_a_change_of_commitment(self):
        services.set_recurrence(self.task, Item.Recurrence.WEEKLY)

        self.assertEqual(
            self.only(EventType.COMMITMENT_CHANGED).task_id, self.task.pk
        )

    def test_stopping_a_series_is_the_end_of_one(self):
        services.set_recurrence(self.task, Item.Recurrence.WEEKLY)
        mark = self.watermark()

        services.set_recurrence(self.task, Item.Recurrence.NONE)

        self.assertEqual(self.types(mark), [EventType.COMMITMENT_ENDED])

    def test_an_ordinary_edit_is_not_a_life_event(self):
        """The deferral, held by a test so it is a decision rather than an
        omission. Renaming a task, moving it, or giving it a due date changes
        nothing about what somebody committed to or completed."""
        services.edit_item(self.task, "Call the plumber back")
        services.set_due_date(self.task, datetime.date(2026, 9, 1))
        services.set_priority(self.task, Item.Priority.HIGH)

        self.assertEqual(self.types(), [])

    def test_a_failed_write_takes_the_completion_with_it(self):
        """Both or neither, which is what makes the log a record rather than a
        sample. Swallowing here would leave a silent hole in every read over
        it -- the exact failure `MAINTENANCE_RAN` exists one layer up to
        prevent."""
        with patch("clarice.life_log.record", side_effect=RuntimeError("log down")):
            with self.assertRaises(RuntimeError):
                services.complete_item(self.task)

        self.assertEqual(
            Item.objects.get(pk=self.task.pk).status, Item.Status.ACTIVE
        )
