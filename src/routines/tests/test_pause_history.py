"""Crane 3 slice 7 — a pause is a fact worth recording while it happens.

`Routine.paused_at` was added in Crane 2 slice 4 with its own limitation
written into the docstring: it records only the *current* pause, so a
routine put down in July and picked back up in August leaves July's review
nothing to read. That was said there as a finding rather than a surprise,
and this is where it gets fixed.

It is the Crane 0a argument applied a second time. A pause is recordable
only while it is happening -- no later migration can invent one that has
already ended -- so the record is built before there is a reader clamouring
for it, which this project does exactly when retrofitting is impossible and
not otherwise.

The record lives in `routines` rather than in `review`, because a pause is a
fact about a routine. The review reads it; it does not own it.
"""
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from routines import services
from routines.models import Routine, RoutinePause


class PauseHistoryTest(TestCase):
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

    def test_pausing_opens_a_record_of_the_pause(self):
        services.pause_routine(self.alice, self.routine)

        [pause] = RoutinePause.objects.filter(routine=self.routine)
        self.assertEqual(pause.owner, self.alice)
        self.assertIsNotNone(pause.paused_at)
        self.assertIsNone(pause.resumed_at)

    def test_resuming_closes_it_rather_than_deleting_it(self):
        """The stretch it was down for is the thing being recorded. A row
        that vanished on resume would leave exactly the gap this slice
        exists to close."""
        services.pause_routine(self.alice, self.routine)

        services.resume_routine(self.alice, self.routine)

        [pause] = RoutinePause.objects.filter(routine=self.routine)
        self.assertIsNotNone(pause.resumed_at)

    def test_a_routine_put_down_twice_remembers_both(self):
        """What `Routine.paused_at` could not do, and the whole reason for
        the table."""
        services.pause_routine(self.alice, self.routine)
        services.resume_routine(self.alice, self.routine)
        services.pause_routine(self.alice, self.routine)
        services.resume_routine(self.alice, self.routine)

        self.assertEqual(RoutinePause.objects.filter(routine=self.routine).count(), 2)
        self.assertEqual(
            RoutinePause.objects.filter(
                routine=self.routine, resumed_at__isnull=True
            ).count(),
            0,
        )

    def test_pausing_something_already_paused_does_not_open_a_second(self):
        """It records when the routine was put down, not when somebody last
        said so -- the same rule the flag on the routine already follows."""
        services.pause_routine(self.alice, self.routine)
        first = RoutinePause.objects.get(routine=self.routine).paused_at

        services.pause_routine(self.alice, self.routine)

        [pause] = RoutinePause.objects.filter(routine=self.routine)
        self.assertEqual(pause.paused_at, first)

    def test_resuming_something_already_running_writes_nothing(self):
        services.resume_routine(self.alice, self.routine)

        self.assertEqual(RoutinePause.objects.count(), 0)

    def test_the_flags_and_the_record_agree(self):
        """`Routine.is_active` and `paused_at` stay as the fast answer to
        "is it down right now", and the record is the authority for how
        long and how often. They are written in one transaction, and this
        holds them to saying the same thing."""
        services.pause_routine(self.alice, self.routine)
        self.routine.refresh_from_db()
        open_pause = RoutinePause.objects.get(
            routine=self.routine, resumed_at__isnull=True
        )

        self.assertFalse(self.routine.is_active)
        self.assertEqual(self.routine.paused_at, open_pause.paused_at)

        services.resume_routine(self.alice, self.routine)
        self.routine.refresh_from_db()

        self.assertTrue(self.routine.is_active)
        self.assertIsNone(self.routine.paused_at)
        self.assertFalse(
            RoutinePause.objects.filter(
                routine=self.routine, resumed_at__isnull=True
            ).exists()
        )

    def test_somebody_elses_routine_cannot_be_put_down(self):
        with self.assertRaises(services.RoutineError):
            services.pause_routine(self.bob, self.routine)

        self.assertEqual(RoutinePause.objects.count(), 0)
