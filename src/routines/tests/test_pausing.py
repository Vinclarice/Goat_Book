"""Crane 2 slice 4 — putting a routine down without losing what it did.

Paused rather than deleted, because the person intends to come back to it
and the occurrences already recorded are history either way.

The rule that gives the slice its name: **resuming does not backfill.** The
weeks a routine was put down are a fact about somebody's month, not missing
data, and a system that quietly filled them in would be asserting something
that never happened -- the same refusal as an elapsed-open period not being
relabelled "missed".
"""
from datetime import date, timedelta

from django.test import TestCase

from accounts.models import User
from routines import reads, services
from routines.models import Routine, RoutineOccurrence


MONDAY = date(2026, 8, 3)


class PausingTest(TestCase):
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
            target_quantity=5,
            unit="lessons",
        )

    def test_pausing_puts_it_down(self):
        routine = services.pause_routine(self.alice, self.routine)

        self.assertFalse(routine.is_active)
        self.assertIsNotNone(routine.paused_at)

    def test_a_paused_routine_leaves_the_days_standings(self):
        services.pause_routine(self.alice, self.routine)

        self.assertEqual(reads.standings_for(self.alice, MONDAY), [])

    def test_a_paused_routine_is_still_findable_to_be_resumed(self):
        """Hidden from the day is not the same as gone. A routine nobody can
        see is one nobody can pick back up."""
        services.pause_routine(self.alice, self.routine)

        paused = reads.paused_routines_for(self.alice)

        self.assertEqual([each.title for each in paused], ["Practice Spanish"])

    def test_pausing_leaves_every_occurrence_untouched(self):
        """The first half of the acceptance condition."""
        services.log_progress(self.alice, self.routine, MONDAY, amount=5)

        services.pause_routine(self.alice, self.routine)

        occurrence = RoutineOccurrence.objects.get()
        self.assertEqual(occurrence.progress, 5)
        self.assertEqual(occurrence.outcome, RoutineOccurrence.Outcome.COMPLETED)

    def test_a_paused_routine_cannot_be_logged_against(self):
        """Pausing has to actually stop new occurrences, not merely hide the
        button that makes them."""
        services.pause_routine(self.alice, self.routine)

        with self.assertRaises(services.RoutineError):
            services.log_progress(self.alice, self.routine, MONDAY)

        self.assertEqual(RoutineOccurrence.objects.count(), 0)

    def test_a_paused_routine_cannot_be_skipped_either(self):
        """Skipping creates an occurrence too, so it is the same hole."""
        services.pause_routine(self.alice, self.routine)

        with self.assertRaises(services.RoutineError):
            services.skip_period(self.alice, self.routine, MONDAY)

        self.assertEqual(RoutineOccurrence.objects.count(), 0)

    def test_resuming_brings_it_back_to_the_day(self):
        services.pause_routine(self.alice, self.routine)

        services.resume_routine(self.alice, self.routine)

        self.assertEqual(
            [each.routine.title for each in reads.standings_for(self.alice, MONDAY)],
            ["Practice Spanish"],
        )

    def test_resuming_does_not_backfill_the_gap(self):
        """The second half, and the one the slice is named for.

        Nothing is written for the periods the routine was down. Lazy
        creation makes that the default rather than an achievement, which is
        exactly why it is asserted -- a later 'helpfully' pre-creating job
        would break it silently.
        """
        services.log_progress(self.alice, self.routine, MONDAY, amount=5)
        services.pause_routine(self.alice, self.routine)

        services.resume_routine(self.alice, self.routine)

        self.assertEqual(RoutineOccurrence.objects.count(), 1)
        self.assertEqual(
            RoutineOccurrence.objects.get().period_start, MONDAY
        )

    def test_resuming_clears_the_pause_stamp(self):
        services.pause_routine(self.alice, self.routine)

        routine = services.resume_routine(self.alice, self.routine)

        self.assertTrue(routine.is_active)
        self.assertIsNone(routine.paused_at)

    def test_logging_works_again_after_resuming(self):
        services.pause_routine(self.alice, self.routine)
        services.resume_routine(self.alice, self.routine)

        occurrence = services.log_progress(self.alice, self.routine, MONDAY)

        self.assertEqual(occurrence.progress, 1)

    def test_pausing_twice_is_not_an_error(self):
        first = services.pause_routine(self.alice, self.routine)
        stamped = first.paused_at

        again = services.pause_routine(self.alice, self.routine)

        self.assertFalse(again.is_active)
        # The stamp is when it was put down, not when somebody last said so.
        self.assertEqual(again.paused_at, stamped)

    def test_one_person_cannot_pause_anothers_routine(self):
        with self.assertRaises(services.RoutineError):
            services.pause_routine(self.bob, self.routine)

        self.routine.refresh_from_db()
        self.assertTrue(self.routine.is_active)

    def test_one_person_never_sees_anothers_paused_routines(self):
        services.pause_routine(self.alice, self.routine)

        self.assertEqual(reads.paused_routines_for(self.bob), [])
