"""Crane 3 slice 6 — how habits performed.

The sentence `daily-operating-system-vision.md` asks for by name: "4 of 5
planned lesson targets met". Getting it honest is three decisions rather
than one query.

**The denominator is the periods the week actually expected**, not seven.
A routine kept from Thursday is not asked about Monday, and a week that has
not finished is not asked about the days still ahead of it -- both would be
the product asserting a miss for a period that never came round.

**A skipped period leaves the denominator**, exactly as a released pin
leaves the planned one. "I chose not to today" is a decommitment and not a
failure, and the parallel is deliberate: the two are the same kind of
statement about different domains. The skips stay on the page beside the
figure, so the number cannot hide them.

**A period that merely elapsed stays open.** Not missed, not failed --
open. `crane-plan.md` §3 is explicit that Crane 3 is where an elapsed-open
occurrence "gets described, not where it gets silently relabelled."
"""
from datetime import date, datetime, timedelta

from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User
from routines import services as routine_services
from routines.models import Routine, RoutineOccurrence


PASSWORD = "correct horse battery staple 47!"

JULY_27 = date(2026, 7, 27)


class HabitsInAWeekTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        self.client = Client()
        self.client.force_login(self.alice)

    def routine_kept_since(self, day, owner=None, **kwargs):
        routine = routine_services.create_routine(
            owner or self.alice, title=kwargs.pop("title", "Practice Spanish"), **kwargs
        )
        Routine.objects.filter(pk=routine.pk).update(
            created_at=timezone.make_aware(
                datetime.combine(day, datetime.min.time()) + timedelta(hours=8)
            )
        )
        routine.refresh_from_db()
        return routine

    def habits(self, week=JULY_27):
        response = self.client.get(f"/api/v1/review/{week}")
        self.assertEqual(response.status_code, 200)
        return response.json()["habits"]

    def test_a_daily_routine_reads_as_met_of_the_days_the_week_expected(self):
        routine = self.routine_kept_since(
            JULY_27 - timedelta(days=30), target_quantity=5, unit="lessons"
        )
        for offset in range(5):
            routine_services.log_progress(
                self.alice, routine, JULY_27 + timedelta(days=offset), amount=5
            )

        [habit] = self.habits()

        self.assertEqual((habit["met"], habit["expected"]), (5, 7))
        self.assertEqual(habit["title"], "Practice Spanish")

    def test_a_routine_kept_from_thursday_is_not_asked_about_monday(self):
        """Four days, not seven. The floor is the routine's own beginning."""
        self.routine_kept_since(JULY_27 + timedelta(days=3))

        [habit] = self.habits()

        self.assertEqual(habit["expected"], 4)
        self.assertEqual(
            [period["period_start"] for period in habit["periods"]],
            ["2026-07-30", "2026-07-31", "2026-08-01", "2026-08-02"],
        )

    def test_a_week_that_has_not_happened_expects_nothing_of_a_routine(self):
        """The other end of the same rule. A week still ahead cannot have
        been missed, and reporting 0 of 7 for it would say it had been."""
        self.routine_kept_since(JULY_27 - timedelta(days=30))
        next_month = timezone.localdate() + timedelta(days=28)

        [habit] = self.habits(week=next_month - timedelta(days=next_month.weekday()))

        self.assertEqual((habit["met"], habit["expected"]), (0, 0))
        self.assertEqual(habit["periods"], [])

    def test_a_skipped_day_is_reported_as_skipped_and_leaves_the_denominator(self):
        routine = self.routine_kept_since(JULY_27 - timedelta(days=30))
        routine_services.skip_period(self.alice, routine, JULY_27)

        [habit] = self.habits()

        self.assertEqual((habit["met"], habit["expected"]), (0, 6))
        self.assertEqual(habit["skipped"], 1)
        self.assertEqual(habit["periods"][0]["outcome"], "skipped")

    def test_a_day_that_merely_elapsed_is_open_rather_than_missed(self):
        self.routine_kept_since(JULY_27 - timedelta(days=30))

        [habit] = self.habits()

        outcomes = {period["outcome"] for period in habit["periods"]}
        self.assertEqual(outcomes, {"open"})
        # Nothing anywhere in the payload calls it a miss. The word is the
        # verdict crane-plan.md §3 refuses to assert on somebody's behalf.
        self.assertNotIn("missed", str(self.habits()))

    def test_a_weekly_routine_contributes_one_period_not_seven(self):
        routine = self.routine_kept_since(
            JULY_27 - timedelta(days=30),
            title="Guitar practice",
            cadence=Routine.Cadence.WEEKLY,
            target_quantity=3,
            unit="sessions",
        )
        routine_services.log_progress(
            self.alice, routine, JULY_27 + timedelta(days=2), amount=2
        )

        [habit] = self.habits()

        self.assertEqual(habit["expected"], 1)
        self.assertEqual(len(habit["periods"]), 1)
        self.assertEqual(
            (habit["periods"][0]["progress"], habit["periods"][0]["target"]), (2, 3)
        )

    def test_a_routine_kept_after_the_week_is_absent_rather_than_zero(self):
        """The distinction this release is about: no data is not a nought."""
        self.routine_kept_since(JULY_27 + timedelta(days=14))

        self.assertEqual(self.habits(), [])

    def test_another_accounts_routines_never_appear(self):
        self.routine_kept_since(
            JULY_27 - timedelta(days=30), owner=self.bob, title="Bob's routine"
        )

        self.assertEqual(self.habits(), [])

    def test_describing_a_week_creates_no_occurrence(self):
        """Occurrences are created lazily, so a period nobody logged has no
        row -- and a review that wrote one in order to describe it would be
        a page view inventing history."""
        self.routine_kept_since(JULY_27 - timedelta(days=30))

        self.habits()

        self.assertEqual(RoutineOccurrence.objects.count(), 0)
