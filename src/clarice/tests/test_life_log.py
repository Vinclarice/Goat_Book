"""The one place the task core records that something happened.

`temporal-substrate-plan.md` **D1, answered August 20, 2026: a module in
`clarice/`**, belonging to neither core. The same placement `clarice/search.py`
has -- and `search-plan.md`'s own D1 predicted this second asking by name --
and the same placement `clarice/scheduled_mail.py` took this week.

**The payoff is an import that does not happen.** `lists`, `daily` and `review`
never mention `ActivityEvent`, `EventType` or `mind` at all; this module is the
only one that knows the log exists. Had each app written rows itself, the emit
rules -- what the actor is, which time is recorded, what may go in the payload
-- would be restated in three places, which is how two definitions of one thing
come to disagree.

**Both or neither**, also decided August 20. `record` is called inside the
caller's own atomic block and raises rather than swallowing, so a completion
whose event could not be written is not a completion. The alternative makes the
log a sample rather than a record, and every read over it inherits a silent
hole -- the exact failure `MAINTENANCE_RAN` exists to prevent.

**D3, answered for slice 1 only: foreign key, and payload for what has no key.**
A week is neither a task nor a day's entry and has nothing to point at, so its
Monday goes in the payload. Nothing here snapshots a subject it could join to;
a copy of a task's text in the log is a second opinion about the task.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from clarice import life_log
from daily import services as daily_services
from lists import services as list_services
from lists.models import List
from mind.models import ActivityEvent, EventType


WHEN = datetime.datetime(2026, 6, 10, 9, 0, tzinfo=datetime.timezone.utc)
DAY = datetime.date(2026, 6, 10)


class LifeLogTest(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.area = List.objects.create(owner=self.alice, title="Home")
        self.task = list_services.create_item(self.area, "Call the plumber")

    def only_event(self):
        events = list(ActivityEvent.objects.all())
        self.assertEqual(len(events), 1, events)
        return events[0]

    def test_it_records_what_happened_to_a_task(self):
        life_log.record(
            self.alice, life_log.TASK_COMPLETED, task=self.task, occurred_at=WHEN
        )

        event = self.only_event()
        self.assertEqual(event.event_type, EventType.TASK_COMPLETED)
        self.assertEqual(event.task_id, self.task.pk)
        self.assertEqual(event.occurred_at, WHEN)

    def test_it_records_what_happened_to_a_day(self):
        entry = daily_services.write_entry(self.alice, DAY, happenings="Something.")

        life_log.record(
            self.alice, life_log.FOCUS_PINNED, entry=entry, occurred_at=WHEN
        )

        self.assertEqual(self.only_event().entry_id, entry.pk)

    def test_the_actor_is_the_owner_unless_somebody_else_is_named(self):
        """Three apps inventing an actor string would produce three formats,
        and `actor` is a plain column nothing normalises after the fact."""
        life_log.record(self.alice, life_log.TASK_COMPLETED, task=self.task)

        self.assertEqual(self.only_event().actor, "alice")

    def test_a_caller_may_name_a_different_actor(self):
        """A scheduled pass is not the person, and a log that says otherwise
        makes every reading about attention wrong."""
        life_log.record(
            self.alice, life_log.COMMITMENT_ENDED, task=self.task, actor="scheduler"
        )

        self.assertEqual(self.only_event().actor, "scheduler")

    def test_it_records_the_fact_s_own_time_and_not_the_write_s(self):
        """The distinction increment 3 is built on: a backfilled event carries
        the timestamp already recorded against the thing that happened, and an
        event stamped when it was written is a re-presentation pretending to be
        a record."""
        life_log.record(
            self.alice, life_log.TASK_COMPLETED, task=self.task, occurred_at=WHEN
        )

        self.assertEqual(self.only_event().occurred_at, WHEN)

    def test_it_falls_back_to_now_for_something_happening_now(self):
        before = timezone.now()

        life_log.record(self.alice, life_log.TASK_COMPLETED, task=self.task)

        self.assertGreaterEqual(self.only_event().occurred_at, before)

    def test_a_week_carries_its_monday_because_it_has_nothing_to_point_at(self):
        """D3 for slice 1: a foreign key where one exists, and the payload only
        for what no key can carry."""
        life_log.record(
            self.alice,
            life_log.WEEK_REVIEWED,
            week_start=datetime.date(2026, 6, 8),
            occurred_at=WHEN,
        )

        event = self.only_event()
        self.assertEqual(event.payload, {"week_start": "2026-06-08"})
        self.assertIsNone(event.task_id)
        self.assertIsNone(event.entry_id)

    def test_it_refuses_a_type_it_does_not_know(self):
        """The vocabulary is re-exported here so the task core never imports
        `EventType`; a typo must therefore fail here rather than at the
        database check constraint three layers down."""
        with self.assertRaises(ValueError):
            life_log.record(self.alice, "task_dry_cleaned", task=self.task)

    def test_it_does_not_swallow_a_failed_write(self):
        """Both or neither. `record` raising is what makes the caller's atomic
        block mean something."""
        with self.assertRaises(Exception):
            life_log.record(self.alice, life_log.TASK_COMPLETED, occurred_at="not a time")
