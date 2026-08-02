"""Crane 2 slice 3 — routines on the Daily Page.

The day is a lens over durable records, so it reads routines the way it
reads the agenda: live, at display time, owning no copy. A unit logged here
is the same occurrence as one logged anywhere else, because there is only
one place it lives.

**Routines show on a past day where Action Items cannot, and the asymmetry
is the point.** A task carries no record of what it looked like on the
30th, so bucketing today's open work against that date would assert
something that was never true. A routine occurrence *is* a dated record of
what happened in a period -- reading one back is history rather than
inference. Same page, two kinds of record, two honest answers.
"""
import json
from datetime import date, timedelta

from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User
from lists import services as list_services
from lists.models import List
from routines import services as routine_services
from routines.models import Routine, RoutineOccurrence


PASSWORD = "correct horse battery staple 47!"


class RoutinesOnTheDayTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.alice)
        response = self.client.get("/accounts/password/change/")
        self.csrf = response.cookies["csrftoken"].value
        self.routine = routine_services.create_routine(
            self.alice,
            title="Practice Spanish",
            target_quantity=5,
            unit="lessons",
        )

    def day(self, day=None):
        url = "/api/v1/day" if day is None else f"/api/v1/day/{day.isoformat()}"
        return self.client.get(url).json()

    def post(self, url, payload):
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def test_the_day_carries_todays_routines(self):
        body = self.day()

        self.assertEqual(
            [(each["title"], each["progress"], each["target"]) for each in body["routines"]],
            [("Practice Spanish", 0, 5)],
        )

    def test_a_unit_logged_elsewhere_is_the_same_occurrence(self):
        """Slice 3's acceptance condition. Logged through the routines
        endpoint, read back through the day -- one record, two doors."""
        self.post(f"/api/v1/routines/{self.routine.id}/log", {"amount": 2})

        self.assertEqual(self.day()["routines"][0]["progress"], 2)
        self.assertEqual(RoutineOccurrence.objects.count(), 1)

    def test_a_routine_never_appears_in_action_items(self):
        """The agenda is tasks. A routine is not one, and the whole design
        rests on that staying true."""
        list_ = List.objects.create(owner=self.alice, title="Home")
        list_services.create_item(
            list_, "Pay rent", due_date=timezone.localdate()
        )

        body = self.day()

        self.assertEqual(
            [each["text"] for each in body["action_items"]], ["Pay rent"]
        )
        self.assertNotIn(
            "Practice Spanish", [each["text"] for each in body["action_items"]]
        )

    def test_reading_the_day_creates_no_occurrence(self):
        """A page view must not invent history."""
        self.day()

        self.assertEqual(RoutineOccurrence.objects.count(), 0)

    def test_a_past_day_still_shows_what_the_routine_did(self):
        """Where Action Items must stay empty, routines can answer -- an
        occurrence is a dated record rather than an inference from current
        state."""
        yesterday = timezone.localdate() - timedelta(days=1)
        routine_services.log_progress(
            self.alice, self.routine, yesterday, amount=3
        )

        body = self.day(yesterday)

        self.assertFalse(body["shows_action_items"])
        self.assertEqual(body["routines"][0]["progress"], 3)

    def test_a_past_day_reports_that_period_and_not_today(self):
        routine_services.log_progress(
            self.alice, self.routine, timezone.localdate(), amount=5
        )
        yesterday = timezone.localdate() - timedelta(days=1)

        self.assertEqual(self.day(yesterday)["routines"][0]["progress"], 0)
        self.assertEqual(self.day()["routines"][0]["progress"], 5)

    def test_only_today_can_be_logged_into(self):
        """Back-logging is legitimate and is not built here -- §3 allows
        logging after the fact, but slice 3's acceptance does not need it
        and a date-taking log endpoint is a wider surface than it earns."""
        yesterday = timezone.localdate() - timedelta(days=1)

        body = self.day(yesterday)

        self.assertFalse(body["routines_are_loggable"])
        self.assertTrue(self.day()["routines_are_loggable"])

    def test_one_person_never_sees_anothers_routines_on_their_day(self):
        routine_services.create_routine(self.bob, title="Bob's practice")

        titles = [each["title"] for each in self.day()["routines"]]

        self.assertEqual(titles, ["Practice Spanish"])

    def test_a_weekly_routine_reports_the_period_it_belongs_to(self):
        routine_services.create_routine(
            self.alice,
            title="Guitar practice",
            cadence=Routine.Cadence.WEEKLY,
            target_quantity=3,
        )

        weekly = [
            each for each in self.day()["routines"] if each["cadence"] == "weekly"
        ][0]
        today = timezone.localdate()

        self.assertEqual(
            weekly["period_start"],
            (today - timedelta(days=today.weekday())).isoformat(),
        )
