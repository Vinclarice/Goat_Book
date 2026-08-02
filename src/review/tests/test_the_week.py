"""Crane 3 slice 1 — a week you can open, and what you finished in it.

The first feature that reads the record back rather than adding to it, so
two of its obligations are structural rather than cosmetic and are asserted
here as such.

A week is Monday to Sunday because `routines.periods.period_start_for` says
so, and it says so on the evidence in crane-plan.md §6 -- the snooze menu
has resolved "Next week" to the coming Monday since Albatross. Any date in
the URL snaps to its Monday, so there is no way to address a week the
routines domain would not recognise.

And a read must not write. The routines domain creates its occurrences
lazily, so a review that touched one to describe it would be a page view
inventing history -- the same thing §7's standings-rather-than-rows decision
was made to prevent, over a seven-times-wider surface.
"""
from datetime import date, datetime, timedelta

from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounts.models import User
from lists import services as list_services
from lists.models import Item, List
from routines import services as routine_services


PASSWORD = "correct horse battery staple 47!"

# A Monday, and the Wednesday inside it.
JULY_27 = date(2026, 7, 27)
JULY_29 = date(2026, 7, 29)


class WeekReviewTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        self.alices_list = List.objects.create(owner=self.alice, title="Home")
        self.bobs_list = List.objects.create(owner=self.bob, title="Home")
        self.client = Client()
        self.client.force_login(self.alice)

    def complete_on(self, task, day):
        """Finish a task, then move the timestamp to the day being tested.

        Through the real service first so the completion is a real one --
        recurrence spawning, subtask rules and all -- and only then moved,
        because the clock is not something a test gets to hold still.
        """
        list_services.complete_item(task)
        Item.objects.filter(pk=task.pk).update(
            completed_at=timezone.make_aware(
                datetime.combine(day, datetime.min.time()) + timedelta(hours=9)
            )
        )
        task.refresh_from_db()
        return task

    def review(self, week=None):
        url = "/api/v1/review" if week is None else f"/api/v1/review/{week}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_the_week_gathers_what_was_finished_inside_it(self):
        task = list_services.create_item(self.alices_list, "Pay rent")
        self.complete_on(task, JULY_29)

        week = self.review(JULY_27)

        self.assertEqual(
            [(each["text"], each["completed_on"]) for each in week["completed"]],
            [("Pay rent", "2026-07-29")],
        )

    def test_work_finished_in_another_week_is_not_in_this_one(self):
        task = list_services.create_item(self.alices_list, "Pay rent")
        self.complete_on(task, JULY_29)

        week = self.review(JULY_27 - timedelta(days=7))

        self.assertEqual(week["completed"], [])

    def test_another_accounts_finished_work_never_appears(self):
        task = list_services.create_item(self.bobs_list, "Bob's rent")
        self.complete_on(task, JULY_29)

        week = self.review(JULY_27)

        self.assertEqual(week["completed"], [])

    def test_any_date_in_the_week_resolves_to_its_monday(self):
        """One definition of a week, and it is the routines domain's.

        Addressed by a date rather than by a week number precisely so that
        a link to "the week containing the 29th" cannot mean something the
        routines side would disagree with.
        """
        self.assertEqual(
            self.review(JULY_29)["week_start"], self.review(JULY_27)["week_start"]
        )

    def test_a_week_names_its_end_and_the_weeks_either_side(self):
        """Without these a review written on a Monday cannot reach the week
        it is about, which is the missing-surface failure this sequence has
        now made twice."""
        week = self.review(JULY_27)

        self.assertEqual(week["week_start"], "2026-07-27")
        self.assertEqual(week["week_end"], "2026-08-02")
        self.assertEqual(week["previous_week"], "2026-07-20")
        self.assertEqual(week["next_week"], "2026-08-03")

    def test_a_week_that_has_passed_says_it_is_not_the_current_one(self):
        """Ten weeks back rather than a fixed date, which is the correction
        this test needed: it first asserted that the week of July 27, 2026
        was not current, on a Sunday that fell inside it. The code was
        right and the test was wrong about the world."""
        long_ago = timezone.localdate() - timedelta(weeks=10)

        self.assertFalse(self.review(long_ago)["is_current_week"])

    def test_the_undated_week_is_the_one_today_falls_in(self):
        """The server decides what week it is, because the day boundary
        belongs to the account's time zone."""
        today = timezone.localdate()

        week = self.review()

        self.assertEqual(week["today"], today.isoformat())
        self.assertEqual(
            week["week_start"],
            (today - timedelta(days=today.weekday())).isoformat(),
        )
        self.assertTrue(week["is_current_week"])

    def test_reading_a_week_writes_nothing(self):
        """A routine with no occurrence for the period is the live hazard:
        describing it must not be what brings its row into existence."""
        routine_services.create_routine(
            self.alice, title="Practice Spanish", target_quantity=5, unit="lessons"
        )
        task = list_services.create_item(self.alices_list, "Pay rent")
        self.complete_on(task, JULY_29)

        with CaptureQueriesContext(connection) as queries:
            self.review(JULY_27)

        wrote = [
            query["sql"]
            for query in queries
            if query["sql"].strip().split()[0].upper()
            in {"INSERT", "UPDATE", "DELETE"}
        ]
        self.assertEqual(wrote, [])

    def test_a_week_is_not_readable_without_a_session(self):
        self.assertEqual(Client().get("/api/v1/review").status_code, 401)
