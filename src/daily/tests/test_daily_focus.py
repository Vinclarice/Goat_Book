"""Crane 1 slice 4 — pinning work to a day, and remembering that you did.

A Daily Focus says "I chose this, on this day". It is the planned
denominator the vision document says a finish rate needs: "completed
planned commitments / planned commitments", where the denominator "cannot
be reconstructed after the fact from a mutable due date".

Which is why unpinning does not delete. Deciding on Tuesday morning that
something is not for today, and never getting to it, are different facts
about a person's week, and a review that cannot tell them apart is worse
than one that reports nothing -- it invites a conclusion.
"""
from datetime import date, timedelta

from django.test import TestCase

from accounts.models import User
from daily import reads, services
from daily.models import DailyEntry, DailyFocus
from lists import services as list_services
from lists.models import List


AUGUST_3 = date(2026, 8, 3)


class PinningTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user(
            "bob", "bob@example.com", "another password"
        )
        self.list_ = List.objects.create(owner=self.alice, title="Home")
        self.task = list_services.create_item(
            self.list_, "Pay rent", due_date=AUGUST_3
        )

    def test_pinning_records_the_choice(self):
        focus = services.pin_task(self.alice, AUGUST_3, self.task)

        self.assertEqual(focus.owner, self.alice)
        self.assertEqual(focus.task, self.task)
        self.assertEqual(focus.entry.date, AUGUST_3)
        self.assertIsNotNone(focus.selected_at)
        self.assertIsNone(focus.released_at)

    def test_pinning_changes_nothing_about_the_task(self):
        """The first half of slice 4's acceptance condition."""
        before = (self.task.due_date, self.task.status, self.task.list.owner_id)

        services.pin_task(self.alice, AUGUST_3, self.task)

        self.task.refresh_from_db()
        after = (self.task.due_date, self.task.status, self.task.list.owner_id)
        self.assertEqual(before, after)

    def test_pinning_creates_the_day_if_it_does_not_exist_yet(self):
        """Pinning is often the first thing done to a day."""
        self.assertEqual(DailyEntry.objects.count(), 0)

        services.pin_task(self.alice, AUGUST_3, self.task)

        self.assertEqual(DailyEntry.objects.count(), 1)

    def test_pins_keep_the_order_they_were_made_in(self):
        second = list_services.create_item(self.list_, "Call the plumber")

        services.pin_task(self.alice, AUGUST_3, self.task)
        services.pin_task(self.alice, AUGUST_3, second)

        self.assertEqual(
            [focus.task_id for focus in reads.focus_for(self.alice, AUGUST_3)],
            [self.task.id, second.id],
        )

    def test_pinning_the_same_task_twice_does_not_double_it(self):
        services.pin_task(self.alice, AUGUST_3, self.task)
        services.pin_task(self.alice, AUGUST_3, self.task)

        self.assertEqual(len(reads.focus_for(self.alice, AUGUST_3)), 1)

    def test_a_task_can_be_pinned_to_more_than_one_day(self):
        """Carrying something forward is choosing it again, not moving a pin."""
        services.pin_task(self.alice, AUGUST_3, self.task)
        services.pin_task(self.alice, AUGUST_3 + timedelta(days=1), self.task)

        self.assertEqual(DailyFocus.objects.filter(task=self.task).count(), 2)

    def test_one_person_cannot_pin_anothers_task(self):
        """The isolation test principles.md asks of every id-taking surface."""
        bobs_list = List.objects.create(owner=self.bob, title="Bob's home")
        bobs_task = list_services.create_item(bobs_list, "Bob's private task")

        with self.assertRaises(services.FocusError):
            services.pin_task(self.alice, AUGUST_3, bobs_task)

        self.assertEqual(DailyFocus.objects.count(), 0)


class UnpinningTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.list_ = List.objects.create(owner=self.alice, title="Home")
        self.task = list_services.create_item(self.list_, "Pay rent")

    def test_unpinning_takes_it_off_the_day(self):
        services.pin_task(self.alice, AUGUST_3, self.task)

        services.unpin_task(self.alice, AUGUST_3, self.task)

        self.assertEqual(reads.focus_for(self.alice, AUGUST_3), [])

    def test_unpinning_keeps_the_record_of_having_chosen_it(self):
        """The second half of the acceptance condition, and the whole reason
        this is not a delete."""
        services.pin_task(self.alice, AUGUST_3, self.task)

        services.unpin_task(self.alice, AUGUST_3, self.task)

        released = DailyFocus.objects.get(task=self.task)
        self.assertIsNotNone(released.released_at)
        self.assertIsNotNone(released.selected_at)

    def test_a_deliberate_unpin_is_distinguishable_from_unfinished_work(self):
        """The distinction a weekly review has to be able to make."""
        abandoned = list_services.create_item(self.list_, "Deliberately dropped")
        services.pin_task(self.alice, AUGUST_3, self.task)
        services.pin_task(self.alice, AUGUST_3, abandoned)

        services.unpin_task(self.alice, AUGUST_3, abandoned)

        still_planned = DailyFocus.objects.get(task=self.task)
        decommitted = DailyFocus.objects.get(task=abandoned)
        self.assertIsNone(still_planned.released_at)
        self.assertIsNotNone(decommitted.released_at)

    def test_repinning_puts_it_back_rather_than_starting_a_second_record(self):
        services.pin_task(self.alice, AUGUST_3, self.task)
        services.unpin_task(self.alice, AUGUST_3, self.task)

        services.pin_task(self.alice, AUGUST_3, self.task)

        self.assertEqual(DailyFocus.objects.filter(task=self.task).count(), 1)
        self.assertIsNone(DailyFocus.objects.get(task=self.task).released_at)

    def test_unpinning_something_never_pinned_is_not_an_error(self):
        services.unpin_task(self.alice, AUGUST_3, self.task)

        self.assertEqual(DailyFocus.objects.count(), 0)


class FocusSurvivalTest(TestCase):
    """What is left when the task itself goes away."""

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.list_ = List.objects.create(owner=self.alice, title="Home")
        self.task = list_services.create_item(self.list_, "Pay rent")

    def test_deleting_the_task_does_not_delete_the_day_it_was_planned_for(self):
        """Otherwise the denominator silently shrinks, and a finish rate
        computed later is quietly wrong rather than obviously missing."""
        services.pin_task(self.alice, AUGUST_3, self.task)
        list_services.archive_item(self.task)
        self.task.refresh_from_db()
        list_services.delete_archived_item(self.task)

        focus = DailyFocus.objects.get()
        self.assertIsNone(focus.task_id)
        self.assertEqual(focus.task_text, "Pay rent")

    def test_the_pinned_text_is_captured_when_the_choice_is_made(self):
        focus = services.pin_task(self.alice, AUGUST_3, self.task)

        self.assertEqual(focus.task_text, "Pay rent")
