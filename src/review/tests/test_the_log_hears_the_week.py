"""What the week tells the append-only log.

`temporal-substrate-plan.md` Track A increment 2, the week-grained third of it.

**These three are subject-less**, like `MAINTENANCE_RAN` before them. A week is
neither a task nor a day's entry, so the Monday goes in the payload rather than
into a subject column invented for one cadence -- which would be a column the
next cadence does not fit, and `clarice-v3-plan.md` says the wider horizons
reuse this model rather than growing their own.

**The week is normalised, not taken from the caller.** `week_start_for` is the
one definition of which week a day is in, and a log carrying a second one would
be the drift `crane-plan.md` §6 names, recorded permanently.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from mind.models import ActivityEvent, EventType
from review import services


WEDNESDAY = datetime.date(2026, 6, 10)
ITS_MONDAY = datetime.date(2026, 6, 8)


class TheLogHearsTheWeekTest(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def watermark(self):
        last = ActivityEvent.objects.order_by("id").last()
        return last.pk if last else 0

    def types(self, since=0):
        return [
            e.event_type
            for e in ActivityEvent.objects.filter(pk__gt=since).order_by("id")
        ]

    def test_reviewing_a_week_is_recorded_against_its_monday(self):
        services.complete_review(self.alice, WEDNESDAY)

        event = ActivityEvent.objects.get(event_type=EventType.WEEK_REVIEWED)
        self.assertEqual(event.payload, {"week_start": ITS_MONDAY.isoformat()})
        self.assertIsNone(event.task_id)
        self.assertIsNone(event.entry_id)

    def test_reviewing_an_already_reviewed_week_records_nothing_further(self):
        """`complete_review` keeps the first answer -- it records when the week
        was reviewed, not when somebody last pressed the button -- and the log
        has to make the same call or the two disagree about one week."""
        services.complete_review(self.alice, WEDNESDAY)
        mark = self.watermark()

        services.complete_review(self.alice, WEDNESDAY)

        self.assertEqual(self.types(mark), [])

    def test_setting_what_the_week_is_for_is_recorded(self):
        services.set_intention(self.alice, WEDNESDAY, "Finish the chapter")

        self.assertEqual(
            ActivityEvent.objects.get(
                event_type=EventType.INTENTION_SET
            ).payload,
            {"week_start": ITS_MONDAY.isoformat()},
        )

    def test_clearing_an_intention_is_still_a_decision(self):
        """"Blank is a value, not a delete" -- "I set none this week" and "I
        never opened it" are different facts, and only one of them says the
        practice lapsed. The log has to be able to tell them apart too."""
        services.set_intention(self.alice, WEDNESDAY, "Finish the chapter")
        mark = self.watermark()

        services.set_intention(self.alice, WEDNESDAY, "")

        self.assertEqual(self.types(mark), [EventType.INTENTION_SET])

    def test_choosing_an_outcome_is_recorded(self):
        services.choose_outcome(self.alice, WEDNESDAY, text="Chapter three done")

        self.assertEqual(
            ActivityEvent.objects.get(
                event_type=EventType.OUTCOME_CHOSEN
            ).payload,
            {"week_start": ITS_MONDAY.isoformat()},
        )

    def test_the_text_of_an_outcome_stays_out_of_the_log(self):
        """D3 for slice 1: a foreign key where one exists, and the payload only
        for what has none. `WeeklyOutcome` already snapshots its own text and
        its project's title; a third copy in an append-only row is a copy that
        can never be corrected."""
        services.choose_outcome(self.alice, WEDNESDAY, text="Chapter three done")

        event = ActivityEvent.objects.get(event_type=EventType.OUTCOME_CHOSEN)
        self.assertNotIn("Chapter three done", str(event.payload))

    def test_opening_a_planning_session_is_not_a_life_event(self):
        """Deferred by name. Opening the planner is navigation, and a log that
        records being looked at is a log about the product rather than about a
        life."""
        services.open_planning_session(self.alice, WEDNESDAY)

        self.assertEqual(self.types(), [])
