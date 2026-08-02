"""Crane 2 slice 1 — keeping a routine, and logging against it.

A routine measures repeated practice toward a quantity over a period. A
recurring task represents one discrete commitment whose completion creates
the next occurrence. They are peer domains with their own life cycles, and
the boundary is the single most load-bearing thing in the design: five daily
lesson sessions are a `Routine`, not five `Item`s and not
`Item.Recurrence.DAILY` standing in for a count it was never designed to
hold.

The acceptance examples here are `crane-plan.md` §3's own, run end to end
rather than paraphrased -- if the built thing disagrees with the brief, one
of them is wrong and this is where that shows.
"""
from datetime import date, timedelta

from django.test import TestCase

from accounts.models import User
from routines import reads, services
from routines.models import Routine, RoutineOccurrence


# A Monday, chosen so the weekly cases are readable rather than arithmetic.
MONDAY = date(2026, 8, 3)


class RoutineTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user(
            "bob", "bob@example.com", "another password"
        )

    def test_a_routine_belongs_to_one_person(self):
        routine = services.create_routine(
            self.alice,
            title="Practice Spanish",
            cadence=Routine.Cadence.DAILY,
            target_quantity=5,
            unit="lessons",
        )

        self.assertEqual(routine.owner, self.alice)
        self.assertTrue(routine.is_active)

    def test_a_target_can_be_a_plain_yes_or_no(self):
        """The daily-exercise case: nothing to count, so a blank unit."""
        routine = services.create_routine(
            self.alice,
            title="Move today",
            cadence=Routine.Cadence.DAILY,
            target_quantity=1,
            unit="",
        )

        self.assertEqual(routine.unit, "")
        self.assertEqual(routine.target_quantity, 1)

    def test_one_person_never_sees_anothers_routines(self):
        services.create_routine(
            self.bob, title="Bob's practice", cadence=Routine.Cadence.DAILY
        )

        self.assertEqual(reads.active_routines_for(self.alice), [])


class DailyLoggingTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.routine = services.create_routine(
            self.alice,
            title="Practice Spanish",
            cadence=Routine.Cadence.DAILY,
            target_quantity=5,
            unit="lessons",
        )

    def test_a_lesson_target_across_one_day(self):
        """crane-plan.md §3's first acceptance example, verbatim."""
        services.log_progress(self.alice, self.routine, MONDAY, amount=2)
        occurrence = services.log_progress(
            self.alice, self.routine, MONDAY, amount=3
        )

        self.assertEqual(occurrence.period_start, MONDAY)
        self.assertEqual(occurrence.progress, 5)
        self.assertEqual(occurrence.outcome, RoutineOccurrence.Outcome.COMPLETED)
        self.assertIsNotNone(occurrence.decided_at)

    def test_reaching_the_target_needs_no_separate_mark_done(self):
        occurrence = services.log_progress(
            self.alice, self.routine, MONDAY, amount=5
        )

        self.assertEqual(occurrence.outcome, RoutineOccurrence.Outcome.COMPLETED)

    def test_the_occurrence_is_created_on_first_log_and_not_before(self):
        """Lazily, rather than by a nightly job pre-creating every row."""
        self.assertEqual(RoutineOccurrence.objects.count(), 0)

        services.log_progress(self.alice, self.routine, MONDAY)

        self.assertEqual(RoutineOccurrence.objects.count(), 1)

    def test_logging_defaults_to_one_unit(self):
        occurrence = services.log_progress(self.alice, self.routine, MONDAY)

        self.assertEqual(occurrence.progress, 1)

    def test_the_occurrence_snapshots_what_was_expected_of_it(self):
        """A later change to the routine must not rewrite last month."""
        occurrence = services.log_progress(self.alice, self.routine, MONDAY)
        self.routine.target_quantity = 3
        self.routine.unit = "chapters"
        self.routine.save(update_fields=["target_quantity", "unit"])

        occurrence.refresh_from_db()
        self.assertEqual(occurrence.target_quantity, 5)
        self.assertEqual(occurrence.unit, "lessons")

    def test_the_next_day_is_its_own_period(self):
        services.log_progress(self.alice, self.routine, MONDAY, amount=5)

        tuesday = services.log_progress(
            self.alice, self.routine, MONDAY + timedelta(days=1), amount=1
        )

        self.assertEqual(tuesday.progress, 1)
        self.assertEqual(RoutineOccurrence.objects.count(), 2)

    def test_logging_a_new_day_never_touches_the_one_before(self):
        monday = services.log_progress(
            self.alice, self.routine, MONDAY, amount=5
        )

        services.log_progress(self.alice, self.routine, MONDAY + timedelta(days=1))

        monday.refresh_from_db()
        self.assertEqual(monday.progress, 5)
        self.assertEqual(monday.outcome, RoutineOccurrence.Outcome.COMPLETED)

    def test_an_occurrence_carries_its_own_owner(self):
        """Charter rule 1: reachable in one hop, so an isolation test is a
        single assertion rather than a join nobody re-reads."""
        occurrence = services.log_progress(self.alice, self.routine, MONDAY)

        self.assertEqual(occurrence.owner, self.alice)

    def test_one_person_cannot_log_against_anothers_routine(self):
        bob = User.objects.create_user("bob", "bob@example.com", "another one")

        with self.assertRaises(services.RoutineError):
            services.log_progress(bob, self.routine, MONDAY)

        self.assertEqual(RoutineOccurrence.objects.count(), 0)


class WeeklyLoggingTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.routine = services.create_routine(
            self.alice,
            title="Guitar practice",
            cadence=Routine.Cadence.WEEKLY,
            target_quantity=3,
            unit="sessions",
        )

    def test_a_weekly_practice_target(self):
        """crane-plan.md §3's third acceptance example.

        Monday and Wednesday of one week land in the same period, which sits
        open all week -- there is no sub-weekly partial state.
        """
        services.log_progress(self.alice, self.routine, MONDAY)
        occurrence = services.log_progress(
            self.alice, self.routine, MONDAY + timedelta(days=2)
        )

        self.assertEqual(occurrence.period_start, MONDAY)
        self.assertEqual(occurrence.progress, 2)
        self.assertEqual(occurrence.outcome, RoutineOccurrence.Outcome.OPEN)
        self.assertEqual(RoutineOccurrence.objects.count(), 1)

    def test_a_week_is_anchored_to_its_monday(self):
        """Settled in §6 on the evidence of agenda.py's snooze presets,
        which have told people "next week" means Monday since Albatross."""
        sunday = MONDAY + timedelta(days=6)

        occurrence = services.log_progress(self.alice, self.routine, sunday)

        self.assertEqual(occurrence.period_start, MONDAY)

    def test_the_following_monday_begins_a_new_period(self):
        services.log_progress(self.alice, self.routine, MONDAY, amount=2)

        next_week = services.log_progress(
            self.alice, self.routine, MONDAY + timedelta(days=7)
        )

        self.assertEqual(next_week.period_start, MONDAY + timedelta(days=7))
        self.assertEqual(next_week.progress, 1)


class OccurrenceReadTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user(
            "bob", "bob@example.com", "another password"
        )
        self.routine = services.create_routine(
            self.alice,
            title="Practice Spanish",
            cadence=Routine.Cadence.DAILY,
            target_quantity=5,
            unit="lessons",
        )

    def test_a_period_nobody_has_logged_reads_as_none(self):
        self.assertIsNone(
            reads.occurrence_for(self.alice, self.routine, MONDAY)
        )

    def test_reading_a_period_finds_what_was_logged(self):
        services.log_progress(self.alice, self.routine, MONDAY, amount=2)

        occurrence = reads.occurrence_for(self.alice, self.routine, MONDAY)

        self.assertEqual(occurrence.progress, 2)

    def test_the_days_routines_come_back_with_their_progress(self):
        """What the Daily Page will ask for in slice 3."""
        services.log_progress(self.alice, self.routine, MONDAY, amount=2)
        services.create_routine(
            self.alice, title="Move today", cadence=Routine.Cadence.DAILY
        )

        standings = reads.standings_for(self.alice, MONDAY)

        self.assertEqual(
            [(each.routine.title, each.progress, each.target) for each in standings],
            [("Practice Spanish", 2, 5), ("Move today", 0, 1)],
        )

    def test_one_person_never_reads_anothers_standings(self):
        services.log_progress(self.alice, self.routine, MONDAY, amount=2)

        self.assertEqual(reads.standings_for(self.bob, MONDAY), [])
