"""Something that happens at a time whether or not you act.

`superlists-2.0-plan.md`'s *Appointment*, and the model `clarice-v3-plan.md`
argued for against `architecture-trajectory.md` §4's test: **a concept earns
its own model when it has a different life cycle, not when it has a different
name.** A task you did not do is unfinished; a dentist appointment you did not
attend still happened to the afternoon.

The shape comes from Vince's own example -- *"events such as me going to Dutch
Wonderland this weekend"* -- which is a span with no time of day, and is why
this is dates plus an optional time rather than a pair of instants.
"""
import uuid
from datetime import date, time, timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from appointments import reads, services
from appointments.models import Appointment
from clarice import life_log
from mind.models import ActivityEvent


SEPTEMBER_4 = date(2026, 9, 4)


class MakingOneTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_the_least_it_takes_is_words_and_a_date(self):
        appointment = services.make(
            self.owner, text="Call with the accountant", starts_on=SEPTEMBER_4
        )

        self.assertEqual(appointment.starts_on, SEPTEMBER_4)
        self.assertIsNone(appointment.ends_on)
        self.assertIsNone(appointment.starts_at)
        self.assertTrue(appointment.is_all_day)
        self.assertEqual(appointment.last_day, SEPTEMBER_4)

    def test_a_weekend_is_two_dates_and_no_time(self):
        """The Dutch Wonderland case, which is what settled the shape."""
        appointment = services.make(
            self.owner,
            text="Dutch Wonderland",
            starts_on=SEPTEMBER_4,
            ends_on=SEPTEMBER_4 + timedelta(days=1),
            location="Lancaster, PA",
        )

        self.assertEqual(appointment.last_day, SEPTEMBER_4 + timedelta(days=1))
        self.assertTrue(appointment.is_all_day)

    def test_one_day_said_twice_is_stored_once(self):
        """*One day* and *the 4th to the 4th* are the same fact, and a column
        that can say it two ways will eventually say it two ways in one table.
        """
        appointment = services.make(
            self.owner, text="Dentist", starts_on=SEPTEMBER_4, ends_on=SEPTEMBER_4
        )

        self.assertIsNone(appointment.ends_on)

    def test_a_span_that_ends_before_it_starts_is_refused(self):
        with self.assertRaises(services.AppointmentError):
            services.make(
                self.owner,
                text="Backwards",
                starts_on=SEPTEMBER_4,
                ends_on=SEPTEMBER_4 - timedelta(days=1),
            )

    def test_the_database_refuses_it_too(self):
        """The service is the message; the constraint is the guarantee."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            Appointment.objects.create(
                owner=self.owner,
                text="Backwards",
                starts_on=SEPTEMBER_4,
                ends_on=SEPTEMBER_4 - timedelta(days=1),
            )

    def test_an_end_time_needs_a_start_time(self):
        with self.assertRaises(services.AppointmentError):
            services.make(
                self.owner,
                text="Ends but never begins",
                starts_on=SEPTEMBER_4,
                ends_at=time(15, 0),
            )

    def test_a_blank_line_is_refused(self):
        with self.assertRaises(services.AppointmentError):
            services.make(self.owner, text="   ", starts_on=SEPTEMBER_4)

    def test_making_it_is_a_life_event(self):
        services.make(self.owner, text="Dentist", starts_on=SEPTEMBER_4)

        self.assertEqual(
            ActivityEvent.objects.filter(
                owner=self.owner, event_type=life_log.APPOINTMENT_MADE
            ).count(),
            1,
        )

    def test_a_retry_naming_the_same_id_makes_one_appointment(self):
        key = uuid.uuid4()

        first = services.make(
            self.owner, text="Dentist", starts_on=SEPTEMBER_4, public_id=key
        )
        again = services.make(
            self.owner, text="Dentist", starts_on=SEPTEMBER_4, public_id=key
        )

        self.assertEqual(first.pk, again.pk)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_somebody_elses_id_is_refused_rather_than_taken_over(self):
        intruder = User.objects.create_user(
            "mallory", "mallory@example.com", "another secure password"
        )
        theirs = services.make(intruder, text="Theirs", starts_on=SEPTEMBER_4)

        with self.assertRaises(services.AppointmentError):
            services.make(
                self.owner,
                text="Mine now",
                starts_on=SEPTEMBER_4,
                public_id=theirs.public_id,
            )


class HowItEndsTest(TestCase):
    """Rule 6: two states with two meanings."""

    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.appointment = services.make(
            self.owner, text="Parents' evening", starts_on=SEPTEMBER_4
        )

    def test_a_cancelled_appointment_stays_on_its_day(self):
        """*The parents' evening was cancelled* is a fact about that Thursday,
        and a row that vanished would make it unanswerable a month later.
        """
        services.cancel(self.appointment)

        on_the_day = reads.on_day(self.owner, SEPTEMBER_4)
        self.assertEqual([each.text for each in on_the_day], ["Parents' evening"])
        self.assertIsNotNone(on_the_day.first().cancelled_at)

    def test_cancelling_is_a_life_event_and_removing_is_not(self):
        """Being called off happened to a life; a typo being deleted did not."""
        services.cancel(self.appointment)
        services.remove(self.appointment)

        self.assertEqual(
            ActivityEvent.objects.filter(
                owner=self.owner, event_type=life_log.APPOINTMENT_CANCELLED
            ).count(),
            1,
        )

    def test_a_removed_appointment_leaves_the_reads_but_keeps_its_row(self):
        """Soft, because rule 2's public identifier needs a tombstone: a device
        holding the id must not be able to recreate the row by retrying.
        """
        services.remove(self.appointment)

        self.assertEqual(list(reads.on_day(self.owner, SEPTEMBER_4)), [])
        self.assertEqual(Appointment.objects.count(), 1)

    def test_a_retry_after_a_removal_does_not_resurrect_it(self):
        key = self.appointment.public_id
        services.remove(self.appointment)

        again = services.make(
            self.owner, text="Parents' evening", starts_on=SEPTEMBER_4, public_id=key
        )

        self.assertIsNotNone(again.deleted_at)
        self.assertEqual(Appointment.objects.count(), 1)


class WhichDaysItIsOnTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_a_span_is_on_every_day_of_itself(self):
        """*Dutch Wonderland, the 4th to the 6th* is on the page for the 6th
        too -- which is the whole reason this is a span rather than an instant.
        """
        services.make(
            self.owner,
            text="Dutch Wonderland",
            starts_on=SEPTEMBER_4,
            ends_on=SEPTEMBER_4 + timedelta(days=2),
        )

        for offset in range(3):
            with self.subTest(offset=offset):
                self.assertEqual(
                    [
                        each.text
                        for each in reads.on_day(
                            self.owner, SEPTEMBER_4 + timedelta(days=offset)
                        )
                    ],
                    ["Dutch Wonderland"],
                )

    def test_a_one_day_appointment_is_on_exactly_one_day(self):
        services.make(self.owner, text="Dentist", starts_on=SEPTEMBER_4)

        self.assertEqual(list(reads.on_day(self.owner, SEPTEMBER_4 + timedelta(days=1))), [])

    def test_what_is_coming_up_excludes_today_and_anything_called_off(self):
        services.make(self.owner, text="Today's", starts_on=SEPTEMBER_4)
        services.make(
            self.owner, text="Tomorrow's", starts_on=SEPTEMBER_4 + timedelta(days=1)
        )
        called_off = services.make(
            self.owner, text="Called off", starts_on=SEPTEMBER_4 + timedelta(days=2)
        )
        services.cancel(called_off)
        services.make(
            self.owner, text="Next month", starts_on=SEPTEMBER_4 + timedelta(days=40)
        )

        coming = reads.coming_up(self.owner, SEPTEMBER_4)

        self.assertEqual([each.text for each in coming], ["Tomorrow's"])

    def test_all_day_comes_before_a_timed_one_on_the_same_date(self):
        """An all-day thing frames the day the timed ones sit inside."""
        services.make(
            self.owner, text="At two", starts_on=SEPTEMBER_4, starts_at=time(14, 0)
        )
        services.make(self.owner, text="All day", starts_on=SEPTEMBER_4)

        self.assertEqual(
            [each.text for each in reads.on_day(self.owner, SEPTEMBER_4)],
            ["All day", "At two"],
        )

    def test_a_month_holds_a_span_that_only_overlaps_it(self):
        """Containment would drop an August-to-September trip from September."""
        services.make(
            self.owner,
            text="Straddles",
            starts_on=date(2026, 8, 30),
            ends_on=date(2026, 9, 2),
        )

        in_september = reads.in_month(
            self.owner, date(2026, 9, 1), date(2026, 9, 30)
        )

        self.assertEqual([each.text for each in in_september], ["Straddles"])

    def test_the_days_a_span_covers_are_clipped_to_the_window(self):
        appointment = services.make(
            self.owner,
            text="Straddles",
            starts_on=date(2026, 8, 30),
            ends_on=date(2026, 9, 2),
        )

        self.assertEqual(
            reads.days_covered(appointment, date(2026, 9, 1), date(2026, 9, 30)),
            [date(2026, 9, 1), date(2026, 9, 2)],
        )

    def test_one_persons_diary_is_never_anothers(self):
        intruder = User.objects.create_user(
            "mallory", "mallory@example.com", "another secure password"
        )
        services.make(intruder, text="Not mine", starts_on=SEPTEMBER_4)

        self.assertEqual(list(reads.on_day(self.owner, SEPTEMBER_4)), [])
        self.assertEqual(list(reads.coming_up(self.owner, SEPTEMBER_4 - timedelta(days=1))), [])
