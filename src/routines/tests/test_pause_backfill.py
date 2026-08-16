"""The 0004 backfill, exercised as a migration rather than described.

It seeds the one part of the past that is recoverable: a routine that is
down *right now* still carries `Routine.paused_at`, which is exactly the
open interval `RoutinePause` wants. Without it, resuming such a routine
after the deploy would close nothing, and however many weeks it had been
down for would be lost at the moment it ended.

Driven through the real MigrationExecutor against the real migration file,
following lists/test_commitment_backfill.py -- reimplementing the query here
would assert the test back at itself.
"""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from accounts.models import User


# The real User, not a historical one: only `routines` is rewound here, so
# the accounts table stays at its latest schema.
BEFORE = [("routines", "0003_routinepause")]
AFTER = [("routines", "0004_seed_open_pauses")]


class PauseBackfillTest(TransactionTestCase):
    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def tearDown(self):
        # Every app forward -- see the note in
        # lists/tests/test_checklist_step_backfill.py.
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_a_routine_that_is_down_now_gets_the_pause_it_is_down_in(self):
        old_apps = self.migrate(BEFORE)
        Routine = old_apps.get_model("routines", "Routine")
        alice = User.objects.create_user("alice", "alice@example.com", "a password")
        paused = Routine.objects.create(
            owner_id=alice.pk, title="Practice Spanish", cadence="daily"
        )
        Routine.objects.filter(pk=paused.pk).update(
            is_active=False, paused_at="2026-07-20T08:00:00Z"
        )
        running = Routine.objects.create(
            owner_id=alice.pk, title="Move today", cadence="daily"
        )

        new_apps = self.migrate(AFTER)
        RoutinePause = new_apps.get_model("routines", "RoutinePause")

        [seeded] = RoutinePause.objects.all()
        self.assertEqual(seeded.routine_id, paused.pk)
        self.assertEqual(seeded.owner_id, alice.pk)
        self.assertIsNone(seeded.resumed_at)
        self.assertEqual(seeded.paused_at.date().isoformat(), "2026-07-20")
        # A routine that was never put down gets nothing: this recovers a
        # pause in progress, it does not invent one.
        self.assertFalse(RoutinePause.objects.filter(routine_id=running.pk).exists())
