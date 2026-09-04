"""The line under the day's list, and what falls above and below it.

`superlists-2.0-plan.md` increment 2, and the three rules it builds:

- Rule 3, **the first act of execution draws the line** -- a tick on a chosen
  task. Mechanical rather than a button, so it cannot be forgotten.
- Rule 4, **the line is a boundary, not a wall.** What joins later sits below
  it and is counted apart. *Above or below is not a field*; it is a comparison
  of two timestamps the tables already carry.
- Rule 11, **a past day is read-only**, and the line not drawn stays not drawn.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from daily import reads, services
from daily.models import DailyEntry, DailyFocus
from lists import services as task_services
from lists.models import Item
from review import reads as review_reads


class DrawingTheLineTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.today = timezone.localdate()

    def task(self, text="Book dentist"):
        return Item.objects.create(owner=self.owner, text=text)

    def closed_at(self, day=None):
        entry = DailyEntry.objects.filter(
            owner=self.owner, date=day or self.today
        ).first()
        return entry.list_closed_at if entry else None

    def test_a_day_starts_with_no_line_drawn(self):
        services.pin_task(self.owner, self.today, self.task())

        self.assertIsNone(self.closed_at())

    def test_ticking_a_chosen_task_draws_the_line(self):
        task = self.task()
        services.pin_task(self.owner, self.today, task)

        task_services.complete_item(task)

        self.assertIsNotNone(self.closed_at())

    def test_the_line_does_not_move_once_drawn(self):
        first, second = self.task("First"), self.task("Second")
        services.pin_task(self.owner, self.today, first)
        services.pin_task(self.owner, self.today, second)
        task_services.complete_item(first)
        drawn = self.closed_at()

        task_services.complete_item(second)

        self.assertEqual(self.closed_at(), drawn)

    def test_ticking_a_task_nobody_chose_leaves_the_list_open(self):
        """Rule 3 enumerates what draws the line and this is not on the list.

        The morning's planning ends when the day's own work starts, and a
        stray tick on something never chosen is not that. See the plan's D7.
        """
        task_services.complete_item(self.task())

        self.assertIsNone(self.closed_at())

    def test_reopening_does_not_undo_the_line(self):
        """The line records that the day started, not that a task is done.

        Rule 6's argument in the other direction: a reopen must not erase what
        happened, and *work began at 08:12* happened.
        """
        task = self.task()
        services.pin_task(self.owner, self.today, task)
        task_services.complete_item(task)
        drawn = self.closed_at()

        task_services.reopen_item(task)

        self.assertEqual(self.closed_at(), drawn)

    def test_ticking_a_task_chosen_for_a_past_day_draws_no_line_on_it(self):
        """Rule 11. The line is drawn on the day the work happened, which is
        today -- never backwards onto a day that closed unclosed.
        """
        yesterday = self.today - timedelta(days=1)
        task = self.task()
        services.pin_task(self.owner, yesterday, task)

        task_services.complete_item(task)

        self.assertIsNone(self.closed_at(yesterday))


class AboveAndBelowTheLineTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.today = timezone.localdate()

    def task(self, text):
        return Item.objects.create(owner=self.owner, text=text)

    def test_a_pin_made_before_the_line_is_above_it(self):
        chosen = self.task("Chosen")
        services.pin_task(self.owner, self.today, chosen)
        task_services.complete_item(chosen)
        joined = self.task("Joined")
        services.pin_task(self.owner, self.today, joined)

        bounded = reads.bounded_list_for(self.owner, self.today)

        self.assertEqual([each.task_text for each in bounded.chosen], ["Chosen"])
        self.assertEqual([each.task_text for each in bounded.joined], ["Joined"])

    def test_everything_is_above_a_line_that_was_never_drawn(self):
        """Rule 11: a day nothing executed on keeps `list_closed_at` null, and
        a pin on such a day is still something that was chosen.
        """
        services.pin_task(self.owner, self.today, self.task("Chosen"))

        bounded = reads.bounded_list_for(self.owner, self.today)

        self.assertEqual(len(bounded.chosen), 1)
        self.assertEqual(bounded.joined, [])
        self.assertIsNone(bounded.closed_at)

    def test_a_released_pin_is_on_neither_side(self):
        released = self.task("Released")
        services.pin_task(self.owner, self.today, released)
        services.unpin_task(self.owner, self.today, released)

        bounded = reads.bounded_list_for(self.owner, self.today)

        self.assertEqual(bounded.chosen, [])
        self.assertEqual(bounded.joined, [])


class WhatTheNumbersCountTest(TestCase):
    """Capacity and the finish rate count above-the-line pins only.

    The plan's *The composer*: a day of below-the-line lines would otherwise
    raise what a typical day holds and quietly hide over-commitment on the next
    draft. Below-the-line pins are reported, never used as evidence.
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.today = timezone.localdate()

    def task(self, text):
        return Item.objects.create(owner=self.owner, text=text)

    def draw_the_line(self):
        opener = self.task("Opened the day")
        services.pin_task(self.owner, self.today, opener)
        task_services.complete_item(opener)
        return opener

    def test_the_denominator_is_what_was_chosen(self):
        self.draw_the_line()
        services.pin_task(self.owner, self.today, self.task("Joined later"))

        planned = review_reads.planned_in_week(self.owner, self.today, self.today)

        self.assertEqual(planned.total, 1)
        self.assertEqual([each.task_text for each in planned.met], ["Opened the day"])

    def test_what_joined_below_is_still_shown_on_the_day(self):
        """Counted apart, not hidden -- rule 4. The week grain does not read it
        until the closing ritual needs it; the day does, from the first.
        """
        self.draw_the_line()
        done_late = self.task("Done late")
        services.pin_task(self.owner, self.today, done_late)
        task_services.complete_item(done_late)

        bounded = reads.bounded_list_for(self.owner, self.today)

        self.assertEqual([each.task_text for each in bounded.joined], ["Done late"])

    def test_a_day_of_nothing_but_below_the_line_pins_counts_as_unplanned(self):
        """Rule 10's shape: `typical_day_for` skips a day with no plan rather
        than averaging in a zero, and a day whose whole list joined after the
        line was drawn had no plan.
        """
        entry, _ = DailyEntry.objects.get_or_create(owner=self.owner, date=self.today)
        entry.list_closed_at = timezone.now() - timedelta(hours=1)
        entry.save(update_fields=["list_closed_at"])
        services.pin_task(self.owner, self.today, self.task("Joined later"))

        planned = review_reads.planned_in_week(self.owner, self.today, self.today)

        self.assertEqual(planned.total, 0)


class APastDayIsReadOnlyTest(TestCase):
    """Rule 11, held at the door rather than in the doorway.

    The refusal is in `daily.api_v1` and not in `pin_task`, which the plan asks
    for -- `pin_task`'s docstring says why, and these tests are the reason that
    trade is safe: the endpoints are the only way a person reaches a date at
    all, so this is where the rule has to be true.
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.today = timezone.localdate()
        self.client.force_login(self.owner)

    def task(self, text="Book dentist"):
        return Item.objects.create(owner=self.owner, text=text)

    def pin(self, day, task):
        return self.client.post(
            f"/api/v1/day/{day.isoformat()}/focus",
            data={"task_id": task.id},
            content_type="application/json",
        )

    def test_pinning_to_a_past_day_is_refused(self):
        response = self.pin(self.today - timedelta(days=1), self.task())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(DailyFocus.objects.filter(owner=self.owner).count(), 0)

    def test_accepting_a_draft_onto_a_past_day_is_refused(self):
        """The second door, and it would have stayed open.

        `accept_draft` pins through `pin_task` like everything else, so a guard
        on one endpoint would have read as covering both.
        """
        task = self.task()

        response = self.client.post(
            f"/api/v1/day/{(self.today - timedelta(days=1)).isoformat()}/focus/draft",
            data={"task_ids": [task.id]},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(DailyFocus.objects.filter(owner=self.owner).count(), 0)

    def test_pinning_to_today_and_tomorrow_is_allowed(self):
        """Tomorrow is the point of the increment, not an edge case: the
        morning's pick can be made the evening before.
        """
        self.assertEqual(self.pin(self.today, self.task()).status_code, 200)
        self.assertEqual(
            self.pin(self.today + timedelta(days=1), self.task("Tomorrow's")).status_code,
            200,
        )

        self.assertEqual(DailyFocus.objects.filter(owner=self.owner).count(), 2)


class TheDayCarriesTheLineTest(TestCase):
    """The payload says where the line is and which side each pin fell.

    Without this the page could only guess, and rule 4's whole point is that
    what joined later is *visible* rather than quietly folded in.
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.today = timezone.localdate()
        self.client.force_login(self.owner)

    def task(self, text):
        return Item.objects.create(owner=self.owner, text=text)

    def day(self):
        return self.client.get("/api/v1/day").json()

    def test_an_open_list_has_no_line_and_everything_above_it(self):
        services.pin_task(self.owner, self.today, self.task("Chosen"))

        payload = self.day()

        self.assertIsNone(payload["list_closed_at"])
        self.assertEqual(
            [(each["text"], each["above_the_line"]) for each in payload["focus"]],
            [("Chosen", True)],
        )

    def test_the_chosen_come_first_and_what_joined_is_marked(self):
        chosen = self.task("Chosen")
        services.pin_task(self.owner, self.today, chosen)
        task_services.complete_item(chosen)
        services.pin_task(self.owner, self.today, self.task("Joined"))

        payload = self.day()

        self.assertIsNotNone(payload["list_closed_at"])
        self.assertEqual(
            [(each["text"], each["above_the_line"]) for each in payload["focus"]],
            [("Chosen", True), ("Joined", False)],
        )
