"""Leftovers get one decision each, never a move.

`superlists-2.0-plan.md` rule 7, and increment 5: *the closing ritual that
already exists gains the three moves on each unfinished pin, above or below the
line: tomorrow, pool, let go. Never a date move.*

The vision document's first rule, unchanged underneath it: **never
automatically reschedule everything left incomplete.**

**None of the three rewrites today.** Each decides what happens next, and the
day's own record -- you chose N, you finished M -- is what it was. Pooling and
letting go are decommitments and land in `set_aside`, which `PlannedOut` reports
apart from the denominator precisely so a week where four things were
reconsidered reads differently from one where nothing was.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from clarice import composer, leftovers
from clarice.testing import CrossCoreTestCase, make_area, make_task, make_user
from daily import reads as daily_reads
from daily import services as daily_services
from lists.models import Item
from mind.models import Facet, FacetKind, Node


class TheThreeMovesTest(CrossCoreTestCase):
    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()
        self.tomorrow = self.today + timedelta(days=1)

    def chosen(self, text="Book dentist"):
        task = self.a_task(text)
        daily_services.pin_task(self.alice, self.today, task)
        return task

    def pins_on(self, day):
        return [each.task_text for each in daily_reads.focus_for(self.alice, day)]

    def test_tomorrow_chooses_it_for_tomorrow_and_leaves_today_alone(self):
        """**Never a date move.** The task's own due date is untouched: a due
        date is a promise to somebody, and choosing to work on something is not
        the same act as re-promising it.
        """
        task = self.chosen()
        due = task.due_date

        leftovers.tomorrow(self.alice, task, today=self.today)

        task.refresh_from_db()
        self.assertEqual(task.due_date, due)
        self.assertEqual(self.pins_on(self.tomorrow), ["Book dentist"])

    def test_tomorrow_keeps_todays_commitment_on_the_record(self):
        """Honest rather than flattering: you chose it, you did not do it, and
        you are choosing it again. Releasing today's pin would make the finish
        rate a number nobody could fail.
        """
        task = self.chosen()

        leftovers.tomorrow(self.alice, task, today=self.today)

        self.assertEqual(self.pins_on(self.today), ["Book dentist"])

    def test_back_to_the_pool_unchooses_it_and_keeps_the_task(self):
        task = self.chosen()

        leftovers.back_to_the_pool(self.alice, task, today=self.today)

        self.assertEqual(self.pins_on(self.today), [])
        task.refresh_from_db()
        self.assertEqual(task.status, Item.Status.ACTIVE)

    def test_letting_go_archives_the_task_and_keeps_the_thought(self):
        """Rule 8: *let go archives the task and retires its facet while the
        node stays.* Paper could not drop a task without losing the idea.
        """
        composer.write_a_line(
            self.alice,
            text="Sort the garage shelves",
            destination=composer.POOL,
            now=timezone.now(),
        )
        task = Item.objects.get(owner=self.alice)
        daily_services.pin_task(self.alice, self.today, task)

        leftovers.let_go(self.alice, task, today=self.today)

        task.refresh_from_db()
        self.assertEqual(task.status, Item.Status.ARCHIVED)
        self.assertEqual(self.pins_on(self.today), [])
        facet = Facet.objects.get(kind=FacetKind.ACTIONABLE)
        self.assertIsNotNone(facet.retired_at)
        node = Node.objects.get(owner=self.alice)
        self.assertIsNone(node.deleted_at)
        self.assertIsNone(node.archived_at)

    def test_letting_go_of_a_task_with_no_thought_behind_it_still_works(self):
        """Most tasks have no facet at all -- they were typed into the Agenda
        long before the composer existed.
        """
        task = self.chosen()

        leftovers.let_go(self.alice, task, today=self.today)

        task.refresh_from_db()
        self.assertEqual(task.status, Item.Status.ARCHIVED)

    def test_a_move_on_somebody_elses_task_is_refused(self):
        bob = make_user("bob")
        theirs = make_task(make_area(bob), "Not mine")

        for move in (leftovers.tomorrow, leftovers.back_to_the_pool, leftovers.let_go):
            with self.subTest(move=move.__name__):
                with self.assertRaises(leftovers.LeftoverError):
                    move(self.alice, theirs, today=self.today)

        theirs.refresh_from_db()
        self.assertEqual(theirs.status, Item.Status.ACTIVE)


class WhatIsLeftOverTest(CrossCoreTestCase):
    """What the evening asks about: every unfinished pin, whichever side of the
    line it fell.
    """

    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()

    def closing(self):
        return daily_reads.closing_summary_for(self.alice, self.today)

    def chosen(self, text):
        task = self.a_task(text)
        daily_services.pin_task(self.alice, self.today, task)
        return task

    def test_a_finished_line_is_not_left_over(self):
        from lists import services as task_services

        task_services.complete_item(self.chosen("Done"))

        self.assertEqual(self.closing().leftovers, [])

    def test_an_unfinished_line_above_the_line_is_left_over(self):
        self.chosen("Still open")

        self.assertEqual(
            [(each.text, each.above_the_line) for each in self.closing().leftovers],
            [("Still open", True)],
        )

    def test_something_that_joined_below_the_line_is_left_over_too(self):
        """Rule 7 says *each unfinished pin, above or below the line*. A thing
        added at noon and not done is still a thing to decide about.
        """
        composer.write_a_line(
            self.alice,
            text="Call the vet back",
            destination=composer.TODAY,
            now=timezone.now(),
        )

        self.assertEqual(
            [(each.text, each.above_the_line) for each in self.closing().leftovers],
            [("Call the vet back", False)],
        )

    def test_a_line_moved_to_tomorrow_says_so_rather_than_disappearing(self):
        """*Each gets one decision*, so the page has to be able to say which
        ones are still waiting -- and derive it rather than store it.
        """
        task = self.chosen("Book dentist")

        leftovers.tomorrow(self.alice, task, today=self.today)

        [leftover] = self.closing().leftovers
        self.assertTrue(leftover.moved_to_tomorrow)

    def test_a_pooled_line_leaves_the_list_entirely(self):
        task = self.chosen("Book dentist")

        leftovers.back_to_the_pool(self.alice, task, today=self.today)

        self.assertEqual(self.closing().leftovers, [])

    def test_the_counts_report_both_sides_of_the_line(self):
        """Both pins are made **before** anything is ticked, and that ordering
        is the design rather than tidiness: the first tick draws the line, so a
        morning pick made after it would be a joined line. The first version of
        this test pinned the second one afterwards and read 1 of 1 chosen.
        """
        from lists import services as task_services

        done = self.chosen("Chosen and done")
        self.chosen("Chosen and open")
        task_services.complete_item(done)
        composer.write_a_line(
            self.alice, text="Did later", destination=composer.DID, now=timezone.now()
        )
        composer.write_a_line(
            self.alice, text="Joined and open", destination=composer.TODAY,
            now=timezone.now(),
        )

        closing = self.closing()

        self.assertEqual((closing.chosen, closing.finished), (2, 1))
        self.assertEqual((closing.joined, closing.joined_finished), (2, 1))


class TheEveningOverTheApiTest(TestCase):
    def setUp(self):
        self.owner = make_user("alice")
        self.today = timezone.localdate()
        self.tomorrow = self.today + timedelta(days=1)
        self.client.force_login(self.owner)
        self.task = Item.objects.create(owner=self.owner, text="Book dentist")
        daily_services.pin_task(self.owner, self.today, self.task)

    def decide(self, decision, day=None, task=None):
        return self.client.post(
            f"/api/v1/day/{(day or self.today).isoformat()}"
            f"/leftovers/{(task or self.task).id}",
            data={"decision": decision},
            content_type="application/json",
        )

    def test_tomorrow_puts_it_on_tomorrows_list(self):
        response = self.decide("tomorrow")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [each.task_text for each in daily_reads.focus_for(self.owner, self.tomorrow)],
            ["Book dentist"],
        )

    def test_the_pool_takes_it_off_today(self):
        self.decide("pool")

        self.assertEqual(daily_reads.focus_for(self.owner, self.today), [])

    def test_letting_go_archives_it(self):
        self.decide("let_go")

        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Item.Status.ARCHIVED)

    def test_a_past_day_is_read_only(self):
        """Rule 11. The evening's moves are about today, and reaching back into
        a day that closed would put a decision into a week already read.
        """
        response = self.decide("tomorrow", day=self.today - timedelta(days=1))

        self.assertEqual(response.status_code, 409)

    def test_an_unknown_decision_is_refused(self):
        self.assertEqual(self.decide("burn it").status_code, 422)

    def test_another_persons_leftover_is_not_found(self):
        intruder = make_user("mallory")
        self.client.force_login(intruder)

        response = self.decide("let_go")

        self.assertEqual(response.status_code, 404)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Item.Status.ACTIVE)
