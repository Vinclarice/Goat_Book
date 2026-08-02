"""Crane 3 slice 7 — a paused week says it was paused.

The answer §8 gives to the first of the two questions `crane-plan.md` §3
left open. Silence was the alternative and it is wrong twice over: it reads
the same as a routine that did not exist yet, and it makes a week somebody
deliberately put a routine down look like a week it elapsed open. That is
the distinction `skip_period` already draws inside a single period, and a
review that lost it across a week would undo the reason skipping got a route
of its own.

The rule that keeps it honest: **where the record says nothing, the review
says nothing.** A pause that started and ended before `RoutinePause` existed
leaves no row, and the week it covered is described exactly as any other --
no pause inferred from an absence.
"""
from datetime import date, datetime, timedelta

from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User
from routines import services as routine_services
from routines.models import Routine, RoutinePause


PASSWORD = "correct horse battery staple 47!"

JULY_27 = date(2026, 7, 27)


def instant_on(day, hour=9):
    return timezone.make_aware(
        datetime.combine(day, datetime.min.time()) + timedelta(hours=hour)
    )


class PausedWeekTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.alice)
        self.routine = routine_services.create_routine(
            self.alice, title="Practice Spanish", target_quantity=5, unit="lessons"
        )
        Routine.objects.filter(pk=self.routine.pk).update(
            created_at=instant_on(JULY_27 - timedelta(days=30))
        )
        self.routine.refresh_from_db()

    def pause_between(self, paused_on, resumed_on=None):
        """A pause recorded as having run over those days.

        Written through the service and then moved, for the same reason the
        completion tests move `completed_at`: the clock is not something a
        test gets to hold still.
        """
        routine_services.pause_routine(self.alice, self.routine)
        if resumed_on is not None:
            routine_services.resume_routine(self.alice, self.routine)
        RoutinePause.objects.filter(routine=self.routine).update(
            paused_at=instant_on(paused_on),
            resumed_at=instant_on(resumed_on) if resumed_on else None,
        )

    def habit(self, week=JULY_27):
        response = self.client.get(f"/api/v1/review/{week}")
        self.assertEqual(response.status_code, 200)
        habits = response.json()["habits"]
        self.assertEqual(len(habits), 1)
        return habits[0]

    def test_a_week_it_was_down_for_says_so_and_expects_nothing(self):
        self.pause_between(JULY_27 - timedelta(days=7))

        habit = self.habit()

        self.assertEqual(habit["paused_since"], (JULY_27 - timedelta(days=7)).isoformat())
        self.assertEqual((habit["met"], habit["expected"]), (0, 0))
        self.assertEqual(habit["periods"], [])

    def test_a_routine_down_for_part_of_the_week_is_asked_about_the_rest(self):
        """Paused Wednesday, picked back up on Friday: the days it was up
        count and the days it was down do not."""
        self.pause_between(JULY_27 + timedelta(days=2), JULY_27 + timedelta(days=4))

        habit = self.habit()

        self.assertEqual(
            [period["period_start"] for period in habit["periods"]],
            ["2026-07-27", "2026-07-28", "2026-08-01", "2026-08-02"],
        )
        self.assertEqual(habit["paused_days"], 3)
        # Not currently down, so there is no "paused since" to report.
        self.assertIsNone(habit["paused_since"])

    def test_a_day_it_was_down_but_something_was_logged_is_still_reported(self):
        """A record that exists is never hidden. Dropping a day somebody
        actually logged would be the review deciding their history was
        inconvenient."""
        routine_services.log_progress(
            self.alice, self.routine, JULY_27 + timedelta(days=2), amount=5
        )
        self.pause_between(JULY_27 + timedelta(days=2), JULY_27 + timedelta(days=4))

        habit = self.habit()

        self.assertIn(
            "2026-07-29", [period["period_start"] for period in habit["periods"]]
        )
        self.assertEqual(habit["met"], 1)

    def test_a_week_before_the_record_existed_says_nothing_about_pausing(self):
        """The honest limit, asserted rather than assumed. A pause that
        began and ended before this table leaves no row, and the review
        does not invent one from an empty stretch."""
        self.assertEqual(RoutinePause.objects.count(), 0)

        habit = self.habit()

        self.assertIsNone(habit["paused_since"])
        self.assertEqual(habit["paused_days"], 0)
        self.assertEqual(habit["expected"], 7)

    def test_a_routine_paused_after_the_week_leaves_that_week_alone(self):
        """Pausing today says nothing about a week that has already been
        lived, and a review of it must not be rewritten by a later
        decision."""
        self.pause_between(JULY_27 + timedelta(days=14))

        habit = self.habit()

        self.assertIsNone(habit["paused_since"])
        self.assertEqual(habit["expected"], 7)
