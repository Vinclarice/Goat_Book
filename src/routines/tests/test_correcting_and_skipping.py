"""Crane 2 slice 2 — fixing a mis-tap, and deciding not to.

Two write paths that both exist because a routine records what actually
happened rather than what the system would prefer to assume.

**Correction** is the same path as logging with a different amount, per
`crane-plan.md` §3. The rule that matters is the reversal: a count that is
no longer true must not leave an outcome that says otherwise, so dropping
below the target reopens the period.

**Skip** is a distinct action rather than silence, and the distinction it
buys is the whole reason it exists: "I chose not to today" and "I meant to
and didn't" are different facts about a week. A period that merely elapses
with nothing logged stays open — that is a fact about what happened, not a
verdict the system asserts on the person's behalf.
"""
from datetime import date, timedelta

from django.test import TestCase

from accounts.models import User
from routines import reads, services
from routines.models import Routine, RoutineOccurrence


MONDAY = date(2026, 8, 3)


class CorrectionTest(TestCase):
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

    def test_correcting_below_the_target_reopens_the_period(self):
        """crane-plan.md §3, verbatim: 'if the owner later realizes they only
        actually did 4, correcting the 3rd's progress down to 4 reverts its
        outcome from completed to open'."""
        services.log_progress(self.alice, self.routine, MONDAY, amount=5)

        occurrence = services.log_progress(
            self.alice, self.routine, MONDAY, amount=-1
        )

        self.assertEqual(occurrence.progress, 4)
        self.assertEqual(occurrence.outcome, RoutineOccurrence.Outcome.OPEN)

    def test_reopening_clears_the_moment_it_was_decided(self):
        """decided_at says when the outcome stopped being open. Leaving a
        stamp on a period that is open again would make a later review
        report a completion that was taken back."""
        services.log_progress(self.alice, self.routine, MONDAY, amount=5)

        occurrence = services.log_progress(
            self.alice, self.routine, MONDAY, amount=-1
        )

        self.assertIsNone(occurrence.decided_at)

    def test_correcting_back_up_completes_it_again(self):
        services.log_progress(self.alice, self.routine, MONDAY, amount=5)
        services.log_progress(self.alice, self.routine, MONDAY, amount=-2)

        occurrence = services.log_progress(
            self.alice, self.routine, MONDAY, amount=2
        )

        self.assertEqual(occurrence.progress, 5)
        self.assertEqual(occurrence.outcome, RoutineOccurrence.Outcome.COMPLETED)
        self.assertIsNotNone(occurrence.decided_at)

    def test_a_correction_cannot_take_a_count_below_nothing(self):
        services.log_progress(self.alice, self.routine, MONDAY, amount=2)

        occurrence = services.log_progress(
            self.alice, self.routine, MONDAY, amount=-5
        )

        self.assertEqual(occurrence.progress, 0)

    def test_correcting_a_period_nobody_logged_writes_nothing(self):
        """There is nothing to correct, so pressing minus on an untouched
        routine must not conjure a row saying it was touched."""
        result = services.log_progress(
            self.alice, self.routine, MONDAY, amount=-1
        )

        self.assertIsNone(result)
        self.assertEqual(RoutineOccurrence.objects.count(), 0)


class SkipTest(TestCase):
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

    def test_skipping_records_the_decision(self):
        occurrence = services.skip_period(self.alice, self.routine, MONDAY)

        self.assertEqual(occurrence.outcome, RoutineOccurrence.Outcome.SKIPPED)
        self.assertIsNotNone(occurrence.decided_at)

    def test_skipping_a_period_nobody_logged_still_records_it(self):
        """The main case: deciding on Monday morning that today is not one.
        Unlike a correction, there is something to record."""
        self.assertEqual(RoutineOccurrence.objects.count(), 0)

        services.skip_period(self.alice, self.routine, MONDAY)

        self.assertEqual(RoutineOccurrence.objects.count(), 1)

    def test_skipping_keeps_whatever_was_already_done(self):
        """§3's weekly example: skipping sets the whole occurrence to
        skipped regardless of the partial progress already logged."""
        services.log_progress(self.alice, self.routine, MONDAY, amount=2)

        occurrence = services.skip_period(self.alice, self.routine, MONDAY)

        self.assertEqual(occurrence.progress, 2)
        self.assertEqual(occurrence.outcome, RoutineOccurrence.Outcome.SKIPPED)

    def test_a_skipped_period_is_not_the_same_as_one_that_merely_elapsed(self):
        """The distinction the whole action exists for, asserted directly."""
        other = services.create_routine(
            self.alice, title="Move today", target_quantity=1
        )
        services.skip_period(self.alice, self.routine, MONDAY)

        standings = {
            each.routine.title: each.outcome
            for each in reads.standings_for(self.alice, MONDAY)
        }

        self.assertEqual(standings["Practice Spanish"], "skipped")
        self.assertEqual(standings["Move today"], "open")
        self.assertEqual(other.title, "Move today")

    def test_logging_after_a_skip_takes_the_skip_back(self):
        """Changing your mind and doing some of it is the un-skip. A skip is
        a statement about intent, and doing the thing contradicts it."""
        services.skip_period(self.alice, self.routine, MONDAY)

        occurrence = services.log_progress(
            self.alice, self.routine, MONDAY, amount=2
        )

        self.assertEqual(occurrence.outcome, RoutineOccurrence.Outcome.OPEN)
        self.assertEqual(occurrence.progress, 2)

    def test_logging_to_the_target_after_a_skip_completes_it(self):
        services.skip_period(self.alice, self.routine, MONDAY)

        occurrence = services.log_progress(
            self.alice, self.routine, MONDAY, amount=5
        )

        self.assertEqual(occurrence.outcome, RoutineOccurrence.Outcome.COMPLETED)
        self.assertIsNotNone(occurrence.decided_at)

    def test_skipping_twice_is_not_an_error(self):
        services.skip_period(self.alice, self.routine, MONDAY)

        occurrence = services.skip_period(self.alice, self.routine, MONDAY)

        self.assertEqual(occurrence.outcome, RoutineOccurrence.Outcome.SKIPPED)
        self.assertEqual(RoutineOccurrence.objects.count(), 1)

    def test_a_skip_belongs_to_one_period_only(self):
        services.skip_period(self.alice, self.routine, MONDAY)

        tuesday = reads.occurrence_for(
            self.alice, self.routine, MONDAY + timedelta(days=1)
        )

        self.assertIsNone(tuesday)

    def test_one_person_cannot_skip_anothers_routine(self):
        with self.assertRaises(services.RoutineError):
            services.skip_period(self.bob, self.routine, MONDAY)

        self.assertEqual(RoutineOccurrence.objects.count(), 0)
