"""The day's log -- what happened, read rather than stored.

`superlists-2.0-plan.md` increment 3, and its rule 6: *the log is a read, not a
table. Written lines are `Node`s; derived lines are task completions, routine
occurrences, bill payments, appointments that passed, and pins -- every one of
which already carries a timestamp. No new model holds the log.*

**And the half of rule 6 that found the design wrong rather than incomplete**:
derived task lines come from the life-event log, not from the task's current
fields. Unticking clears `completed_at`; the log must not lose the completion
with it.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from clarice import day_log
from clarice.testing import CrossCoreTestCase, make_user
from daily import services as daily_services
from lists import services as task_services
from money.models import Bill
from routines import services as routine_services
from routines.models import Routine


class TheDaysLogTest(CrossCoreTestCase):
    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()

    def lines(self, day=None):
        return day_log.lines_for(self.alice, day or self.today, now=timezone.now())

    def kinds(self, day=None):
        return [(line.kind, line.text) for line in self.lines(day)]

    def test_a_day_with_nothing_in_it_has_an_empty_log(self):
        self.assertEqual(self.lines(), [])

    def test_a_note_written_today_is_a_written_line(self):
        self.a_node("Neighbour asked about the fence")

        self.assertEqual(
            self.kinds(), [(day_log.WRITTEN, "Neighbour asked about the fence")]
        )

    def test_a_note_written_on_another_day_is_not_in_it(self):
        self.a_node("Yesterday's thought", when=timezone.now() - timedelta(days=2))

        self.assertEqual(self.lines(), [])

    def test_a_note_put_away_is_not_in_it(self):
        """`queries.live_nodes` is the one node-visibility rule and this obeys
        it: a note somebody deleted is not a line of their day.
        """
        node = self.a_node("Regretted")
        node.deleted_at = timezone.now()
        node.save(update_fields=["deleted_at"])

        self.assertEqual(self.lines(), [])

    def test_ticking_a_task_is_a_derived_line(self):
        task_services.complete_item(self.a_task("Fix the fence latch"))

        self.assertEqual(
            self.kinds(), [(day_log.COMPLETED, "Fix the fence latch")]
        )

    def test_a_reopen_is_a_second_line_and_does_not_erase_the_first(self):
        """Rule 6's correction, and the reason the log reads events rather than
        `completed_at`: unticking clears that column, and a read over it would
        lose a completion that really happened.
        """
        task = self.a_task("Fix the fence latch")
        task_services.complete_item(task)
        task_services.reopen_item(task)

        self.assertEqual(
            self.kinds(),
            [
                (day_log.COMPLETED, "Fix the fence latch"),
                (day_log.REOPENED, "Fix the fence latch"),
            ],
        )

    def test_choosing_and_releasing_a_line_are_both_in_it(self):
        task = self.a_task("Book dentist")
        daily_services.pin_task(self.alice, self.today, task)
        daily_services.unpin_task(self.alice, self.today, task)

        self.assertEqual(
            self.kinds(),
            [(day_log.CHOSE, "Book dentist"), (day_log.RELEASED, "Book dentist")],
        )

    def test_a_routine_decided_today_is_a_line_with_what_it_came_to(self):
        routine = Routine.objects.create(
            owner=self.alice,
            title="Practice Spanish",
            target_quantity=5,
            unit="lessons",
        )
        routine_services.log_progress(self.alice, routine, self.today, amount=5)

        self.assertEqual(
            [(line.kind, line.text, line.detail) for line in self.lines()],
            [(day_log.ROUTINE, "Practice Spanish", "5 of 5 lessons")],
        )

    def test_a_routine_still_open_is_not_a_line(self):
        """An undecided period has not happened yet, and `decided_at` is null
        precisely so that an elapsed-open period is not relabelled.
        """
        routine = Routine.objects.create(
            owner=self.alice,
            title="Practice Spanish",
            target_quantity=5,
            unit="lessons",
        )
        routine_services.log_progress(self.alice, routine, self.today, amount=1)

        self.assertEqual(self.lines(), [])

    def test_a_bill_paid_today_is_a_line_with_what_actually_moved(self):
        Bill.objects.create(
            owner=self.alice,
            payee="Car insurance",
            due_date=self.today,
            amount=400,
            paid_amount=412,
            paid_at=timezone.now(),
        )

        self.assertEqual(
            [(line.kind, line.text, line.detail) for line in self.lines()],
            [(day_log.BILL, "Car insurance", "412.00 USD")],
        )

    def test_an_unpaid_bill_is_not_a_line(self):
        Bill.objects.create(
            owner=self.alice, payee="Rent", due_date=self.today, amount=950
        )

        self.assertEqual(self.lines(), [])

    def test_everything_is_in_one_order_by_time_oldest_first(self):
        """Newest at the bottom -- the log is read the way it was written."""
        task = self.a_task("Fix the fence latch")
        daily_services.pin_task(self.alice, self.today, task)
        self.a_node("Neighbour asked about the fence")
        task_services.complete_item(task)

        self.assertEqual(
            [line.kind for line in self.lines()],
            [day_log.CHOSE, day_log.WRITTEN, day_log.COMPLETED],
        )
        self.assertEqual(
            [line.at for line in self.lines()],
            sorted(line.at for line in self.lines()),
        )

    def test_one_persons_day_never_holds_anothers(self):
        bob = make_user("bob")
        task_services.complete_item(self.a_task("Mine"))
        from clarice.testing import make_area, make_task

        task_services.complete_item(make_task(make_area(bob), "Not mine"))

        self.assertEqual(self.kinds(), [(day_log.COMPLETED, "Mine")])

    def test_a_line_whose_subject_is_gone_keeps_its_place_and_says_so(self):
        """The log outlives what it names -- `ActivityEvent.task` is
        `DO_NOTHING` with no database constraint, so a deleted task leaves the
        event standing with nothing to read. The alternative is a day that
        quietly reports less work than was done.
        """
        task = self.a_task("Fix the fence latch")
        task_services.complete_item(task)
        task.delete()

        [line] = self.lines()
        self.assertEqual(line.kind, day_log.COMPLETED)
        self.assertIsNone(line.text)
        self.assertTrue(line.subject_withheld)


class TheDayBelongsToTheOwnerTest(CrossCoreTestCase):
    """The day's edges are the account's zone, never the server's.

    A fixture at UTC midday would pass in every zone and prove nothing -- the
    hour these use is one where the two calendars genuinely disagree.
    """

    def setUp(self):
        super().setUp()
        self.alice.time_zone = "America/New_York"
        self.alice.save(update_fields=["time_zone"])

    def test_an_evening_in_new_york_is_that_evening_and_not_the_next_day(self):
        # 22:00 on the 3rd in New York is 02:00 on the 4th in UTC.
        evening = datetime(2026, 9, 4, 2, 0, tzinfo=ZoneInfo("UTC"))
        self.a_node("Late thought", when=evening)

        self.assertEqual(
            [
                line.text
                for line in day_log.lines_for(
                    self.alice, date(2026, 9, 3), now=timezone.now()
                )
            ],
            ["Late thought"],
        )
        self.assertEqual(
            day_log.lines_for(self.alice, date(2026, 9, 4), now=timezone.now()), []
        )


class AnAppointmentThatPassedTest(CrossCoreTestCase):
    """The fifth source, and the only one that can name something still ahead.

    `superlists-2.0-plan.md`: *the log, as a derived line when its start passes
    -- whether you went is a line you write, not something inferred -- and a
    cancelled one produces no log line.*
    """

    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()

    def at(self, hour):
        """An instant today, in the owner's own zone."""
        from clarice import clocks

        start, _ = clocks.day_bounds(self.alice, self.today)
        return start + timedelta(hours=hour)

    def an_appointment(self, text="Call with the accountant", **fields):
        from appointments import services as appointment_services

        return appointment_services.make(
            self.alice, text=text, starts_on=self.today, **fields
        )

    def lines(self, now):
        return [
            (line.kind, line.text, line.detail)
            for line in day_log.lines_for(self.alice, self.today, now=now)
        ]

    def test_one_that_has_started_is_a_line(self):
        from datetime import time

        self.an_appointment(starts_at=time(14, 0), location="phone")

        self.assertEqual(
            self.lines(self.at(15)),
            [(day_log.APPOINTMENT, "Call with the accountant", "phone")],
        )

    def test_one_still_ahead_is_not_a_line_yet(self):
        """The log is what happened. A three o'clock showing at nine would be
        the page asserting something that has not occurred.
        """
        from datetime import time

        self.an_appointment(starts_at=time(15, 0))

        self.assertEqual(self.lines(self.at(9)), [])

    def test_an_all_day_one_lands_at_the_start_of_its_day(self):
        """The only honest instant for something with no time of day -- and it
        puts it above the day's first tick, where the thing the day was
        arranged around belongs.
        """
        self.an_appointment(text="Dutch Wonderland")

        [(kind, text, _)] = self.lines(self.at(12))
        self.assertEqual((kind, text), (day_log.APPOINTMENT, "Dutch Wonderland"))

    def test_a_cancelled_one_produces_no_line(self):
        """Rule 6 from the other end: it stays visible on its day, struck, in
        the strip -- and it did not happen, so the record of what happened does
        not name it.
        """
        from appointments import services as appointment_services

        appointment_services.cancel(self.an_appointment())

        self.assertEqual(self.lines(self.at(23)), [])

    def test_a_span_is_one_line_on_the_day_it_began(self):
        """A weekend away is one thing that began on Saturday; a second line on
        Sunday would be the log reporting the same event twice.
        """
        self.an_appointment(
            text="Dutch Wonderland", ends_on=self.today + timedelta(days=1)
        )

        tomorrow = self.today + timedelta(days=1)
        from clarice import clocks

        start, _ = clocks.day_bounds(self.alice, tomorrow)
        self.assertEqual(
            day_log.lines_for(self.alice, tomorrow, now=start + timedelta(hours=23)),
            [],
        )

