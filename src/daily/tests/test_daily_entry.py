"""Crane 1 slice 1 — a day is a record you write, not a page you rebuild.

The Daily Entry is the first record in the daily domain. It owns only what
belongs to *this day for this person*: what they meant to do, what they were
grateful for, what actually happened. It references no task and copies no
task state -- that is slice 2's job, and doing it here is precisely the
"duplicate a task into a day page merely to make it visible" the vision
document forbids.

One entry per owner per date, enforced in the database rather than by the
service remembering to check, because two rows for one day is the kind of
thing that only shows up as a lost paragraph.
"""
from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import User
from daily import reads, services
from daily.models import DailyEntry


AUGUST_3 = date(2026, 8, 3)


class DailyEntryServiceTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user(
            "bob", "bob@example.com", "another password"
        )

    def test_writing_a_day_stores_what_was_written(self):
        entry = services.write_entry(
            self.alice,
            AUGUST_3,
            intentions="Finish the slice",
            gratitude="Rain, finally",
            happenings="Shipped it",
        )

        self.assertEqual(entry.owner, self.alice)
        self.assertEqual(entry.date, AUGUST_3)
        self.assertEqual(entry.intentions, "Finish the slice")
        self.assertEqual(entry.gratitude, "Rain, finally")
        self.assertEqual(entry.happenings, "Shipped it")

    def test_an_unwritten_field_is_empty_rather_than_null(self):
        """Same trade as Item.notes: nothing has to handle both."""
        entry = services.write_entry(self.alice, AUGUST_3, intentions="Just this")

        self.assertEqual(entry.gratitude, "")
        self.assertEqual(entry.happenings, "")

    def test_writing_the_same_day_twice_updates_the_one_entry(self):
        services.write_entry(self.alice, AUGUST_3, intentions="First thought")

        entry = services.write_entry(self.alice, AUGUST_3, intentions="Second thought")

        self.assertEqual(entry.intentions, "Second thought")
        self.assertEqual(DailyEntry.objects.filter(owner=self.alice).count(), 1)

    def test_a_field_left_out_of_a_write_is_not_cleared(self):
        """The page saves what it is showing; a later partial write must not
        blank a field the caller never mentioned."""
        services.write_entry(
            self.alice, AUGUST_3, intentions="Ship it", gratitude="Rain"
        )

        entry = services.write_entry(self.alice, AUGUST_3, happenings="Shipped")

        self.assertEqual(entry.intentions, "Ship it")
        self.assertEqual(entry.gratitude, "Rain")
        self.assertEqual(entry.happenings, "Shipped")

    def test_a_second_entry_for_one_owner_and_date_is_refused_by_the_database(self):
        services.write_entry(self.alice, AUGUST_3, intentions="Mine")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DailyEntry.objects.create(owner=self.alice, date=AUGUST_3)

    def test_two_people_each_get_their_own_entry_for_the_same_date(self):
        services.write_entry(self.alice, AUGUST_3, intentions="Alice's day")
        services.write_entry(self.bob, AUGUST_3, intentions="Bob's day")

        self.assertEqual(DailyEntry.objects.count(), 2)
        self.assertEqual(
            reads.entry_for(self.alice, AUGUST_3).intentions, "Alice's day"
        )
        self.assertEqual(reads.entry_for(self.bob, AUGUST_3).intentions, "Bob's day")


class DailyEntryReadTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user(
            "bob", "bob@example.com", "another password"
        )

    def test_a_day_nobody_has_written_reads_as_none(self):
        self.assertIsNone(reads.entry_for(self.alice, AUGUST_3))

    def test_one_owner_never_reads_another_owners_day(self):
        """The isolation test principles.md asks of every owner-scoped read."""
        services.write_entry(self.bob, AUGUST_3, intentions="Bob's private day")

        self.assertIsNone(reads.entry_for(self.alice, AUGUST_3))
