"""What the day tells the append-only log.

`temporal-substrate-plan.md` Track A increment 2. **These two are the pair the
whole review block rests on**: `DailyFocus` records what somebody *chose*,
which is the one thing almost no competitor stores, and `released_at` is how a
pin ends -- so a decommitment can be told from a failure. Logging one without
the other would put that distinction back out of reach.

The event names the **day's entry**, not just the task. What a pin is about is
a date; the task is the object of the decision, and both are recorded because
`around()` will want to enter the log from either.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from daily import services
from lists import services as list_services
from lists.models import List
from mind.models import ActivityEvent, EventType


DAY = datetime.date(2026, 6, 10)


class TheLogHearsTheDayTest(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.area = List.objects.create(owner=self.alice, title="Home")
        self.task = list_services.create_item(self.area, "Call the plumber")

    def watermark(self):
        last = ActivityEvent.objects.order_by("id").last()
        return last.pk if last else 0

    def types(self, since=0):
        return [
            e.event_type
            for e in ActivityEvent.objects.filter(pk__gt=since).order_by("id")
        ]

    def test_choosing_a_task_for_a_day_is_recorded(self):
        focus = services.pin_task(self.alice, DAY, self.task)

        event = ActivityEvent.objects.get(event_type=EventType.FOCUS_PINNED)
        self.assertEqual(event.task_id, self.task.pk)
        self.assertEqual(event.entry_id, focus.entry_id)

    def test_releasing_a_pin_is_recorded_as_its_own_decision(self):
        services.pin_task(self.alice, DAY, self.task)
        mark = self.watermark()

        services.unpin_task(self.alice, DAY, self.task)

        self.assertEqual(self.types(mark), [EventType.FOCUS_RELEASED])

    def test_it_records_when_the_pin_was_released(self):
        focus = services.pin_task(self.alice, DAY, self.task)

        services.unpin_task(self.alice, DAY, self.task)

        focus.refresh_from_db()
        self.assertEqual(
            ActivityEvent.objects.get(
                event_type=EventType.FOCUS_RELEASED
            ).occurred_at,
            focus.released_at,
        )

    def test_pinning_something_already_pinned_records_nothing_further(self):
        services.pin_task(self.alice, DAY, self.task)
        mark = self.watermark()

        services.pin_task(self.alice, DAY, self.task)

        self.assertEqual(self.types(mark), [])

    def test_choosing_it_again_after_releasing_it_is_a_new_choice(self):
        """"One task chosen for one day is one decision, however many times it
        was turned over" is about the *row*. Turning it over is exactly what
        the log is for."""
        services.pin_task(self.alice, DAY, self.task)
        services.unpin_task(self.alice, DAY, self.task)
        mark = self.watermark()

        services.pin_task(self.alice, DAY, self.task)

        self.assertEqual(self.types(mark), [EventType.FOCUS_PINNED])

    def test_unpinning_something_never_pinned_records_nothing(self):
        services.unpin_task(self.alice, DAY, self.task)

        self.assertEqual(self.types(), [])

    def test_accepting_a_draft_records_one_choice_per_task(self):
        """`accept_draft` is one act by the person and several by the system.
        The log records the pins, because what a later reading needs is which
        tasks were chosen -- and `DailyFocus.accepted_from_draft` already
        carries the fact that one click did it."""
        second = list_services.create_item(self.area, "Book the dentist")

        services.accept_draft(self.alice, DAY, [self.task, second])

        self.assertEqual(
            self.types(), [EventType.FOCUS_PINNED, EventType.FOCUS_PINNED]
        )

    def test_writing_in_the_day_is_not_a_life_event(self):
        """Deferred by name, and held by a test. A journal entry is content the
        knowledge core already indexes; an event per keystroke is the log
        nobody can read."""
        services.write_entry(self.alice, DAY, happenings="A long afternoon.")

        self.assertEqual(self.types(), [])
