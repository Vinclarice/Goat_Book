"""Crane 3 slice 8 — "I did some of it, and that was enough."

The second question `crane-plan.md` §3 left open, answered in §8: a third
outcome, and it is not a skip.

Recording it as a skip would write a false statement. A skip says the person
chose *not* to do the thing, and they did some of it -- the model already
knows the two contradict each other, because `_settle_outcome` treats
logging as the un-skip on exactly that ground. It would also make a week of
contented partials indistinguishable from a week of deliberate non-doing,
which is the number `daily-operating-system-vision.md` names.

Two rules settled with it, so that no later reader has to guess. A partial
close is **never** a met target. And it leaves the denominator, exactly as a
skip and a released pin do, under the rule slice 6 established: deliberate
decisions come out of the count, and only periods that elapsed without one
stay in it.
"""
from datetime import date

from django.test import TestCase

from accounts.models import User
from routines import services
from routines.models import Routine, RoutineOccurrence


AUGUST_3 = date(2026, 8, 3)


class CallingItEnoughTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user(
            "bob", "bob@example.com", "another password"
        )
        self.routine = services.create_routine(
            self.alice, title="Practice Spanish", target_quantity=5, unit="lessons"
        )

    def test_closing_a_period_as_enough_keeps_what_was_done(self):
        services.log_progress(self.alice, self.routine, AUGUST_3, amount=3)

        occurrence = services.close_period_as_enough(
            self.alice, self.routine, AUGUST_3
        )

        self.assertEqual(occurrence.progress, 3)
        self.assertEqual(occurrence.outcome, RoutineOccurrence.Outcome.PARTIAL)
        self.assertIsNotNone(occurrence.decided_at)

    def test_it_is_neither_completed_nor_skipped(self):
        """The whole reason for a third value rather than reusing one."""
        services.log_progress(self.alice, self.routine, AUGUST_3, amount=3)

        occurrence = services.close_period_as_enough(
            self.alice, self.routine, AUGUST_3
        )

        self.assertNotEqual(occurrence.outcome, RoutineOccurrence.Outcome.COMPLETED)
        self.assertNotEqual(occurrence.outcome, RoutineOccurrence.Outcome.SKIPPED)

    def test_carrying_on_afterwards_settles_it_like_any_other_period(self):
        """Somebody who does more has withdrawn the statement that they
        were done, so logging behaves exactly as it does after a skip."""
        services.log_progress(self.alice, self.routine, AUGUST_3, amount=3)
        services.close_period_as_enough(self.alice, self.routine, AUGUST_3)

        occurrence = services.log_progress(
            self.alice, self.routine, AUGUST_3, amount=2
        )

        self.assertEqual(occurrence.progress, 5)
        self.assertEqual(occurrence.outcome, RoutineOccurrence.Outcome.COMPLETED)

    def test_carrying_on_but_not_reaching_the_target_leaves_it_open(self):
        services.log_progress(self.alice, self.routine, AUGUST_3, amount=3)
        services.close_period_as_enough(self.alice, self.routine, AUGUST_3)

        occurrence = services.log_progress(
            self.alice, self.routine, AUGUST_3, amount=1
        )

        self.assertEqual(occurrence.outcome, RoutineOccurrence.Outcome.OPEN)
        self.assertIsNone(occurrence.decided_at)

    def test_nothing_done_is_not_something_to_be_content_with(self):
        """"I did some of it" needs some of it. With nothing logged the
        honest statement is a skip, which has its own action."""
        with self.assertRaises(services.RoutineError):
            services.close_period_as_enough(self.alice, self.routine, AUGUST_3)

        self.assertEqual(RoutineOccurrence.objects.count(), 0)

    def test_a_period_already_met_cannot_be_called_enough(self):
        services.log_progress(self.alice, self.routine, AUGUST_3, amount=5)

        with self.assertRaises(services.RoutineError):
            services.close_period_as_enough(self.alice, self.routine, AUGUST_3)

        self.assertEqual(
            RoutineOccurrence.objects.get().outcome,
            RoutineOccurrence.Outcome.COMPLETED,
        )

    def test_a_paused_routine_cannot_be_closed_either(self):
        services.log_progress(self.alice, self.routine, AUGUST_3, amount=3)
        services.pause_routine(self.alice, self.routine)

        with self.assertRaises(services.RoutineError):
            services.close_period_as_enough(self.alice, self.routine, AUGUST_3)

    def test_somebody_elses_routine_cannot_be_closed(self):
        services.log_progress(self.alice, self.routine, AUGUST_3, amount=3)

        with self.assertRaises(services.RoutineError):
            services.close_period_as_enough(self.bob, self.routine, AUGUST_3)

    def test_a_weekly_period_can_be_called_enough_too(self):
        weekly = services.create_routine(
            self.alice,
            title="Guitar practice",
            cadence=Routine.Cadence.WEEKLY,
            target_quantity=3,
            unit="sessions",
        )
        services.log_progress(self.alice, weekly, AUGUST_3, amount=2)

        occurrence = services.close_period_as_enough(self.alice, weekly, AUGUST_3)

        self.assertEqual(occurrence.outcome, RoutineOccurrence.Outcome.PARTIAL)
        # The Monday of that week, not the day it was closed on.
        self.assertEqual(occurrence.period_start, date(2026, 8, 3))
