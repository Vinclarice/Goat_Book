"""The 0023 backfill, exercised as a migration rather than described.

`_anchor_commitment` already catches a legacy row on its next completion, so
this migration only decides whether existing series start today or up to a
month from now. That still makes it the difference between a gap and no gap,
and an unrun data migration is exactly the "looks like success until somebody
checks" pattern this project keeps meeting.

Driven through the real MigrationExecutor against the real migration file --
reimplementing the query here would assert the test back at itself.
"""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from accounts.models import User


# The real User, not a historical one: only `lists` is rewound here, so the
# accounts table stays at its latest schema and the historical User model
# would be missing columns the table still requires.
BEFORE = [("lists", "0022_recurringcommitment_item_commitment_and_more")]
AFTER = [("lists", "0023_anchor_existing_recurring_items")]


class CommitmentBackfillTest(TransactionTestCase):
    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def tearDown(self):
        # Every app forward -- see the note in test_checklist_step_backfill.py.
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_existing_repeating_roots_are_anchored_and_others_left_alone(self):
        old_apps = self.migrate(BEFORE)
        List = old_apps.get_model("lists", "List")
        Item = old_apps.get_model("lists", "Item")

        alice = User.objects.create_user("alice", "alice@example.com", "a password")
        bob = User.objects.create_user("bob", "bob@example.com", "another password")
        alice_list = List.objects.create(owner_id=alice.pk, title="Home")
        bob_list = List.objects.create(owner_id=bob.pk, title="Home")

        repeating = Item.objects.create(
            list=alice_list, text="Pay rent", recurrence="monthly"
        )
        bobs = Item.objects.create(
            list=bob_list, text="Pay rent", recurrence="monthly"
        )
        one_off = Item.objects.create(
            list=alice_list, text="Buy milk", recurrence="none"
        )
        # A subtask can't repeat, so it can't be a series of its own.
        subtask = Item.objects.create(
            list=alice_list, text="Check the meter", parent=repeating
        )

        new_apps = self.migrate(AFTER)
        Item = new_apps.get_model("lists", "Item")
        RecurringCommitment = new_apps.get_model("lists", "RecurringCommitment")

        self.assertEqual(RecurringCommitment.objects.count(), 2)
        self.assertIsNotNone(Item.objects.get(pk=repeating.pk).commitment)
        self.assertIsNone(Item.objects.get(pk=one_off.pk).commitment)
        self.assertIsNone(Item.objects.get(pk=subtask.pk).commitment)

        # Two people's identically titled commitments are two series, and each
        # belongs to its own owner -- the string was never the identity.
        self.assertEqual(
            Item.objects.get(pk=repeating.pk).commitment.owner_id, alice.pk
        )
        self.assertEqual(Item.objects.get(pk=bobs.pk).commitment.owner_id, bob.pk)
        self.assertNotEqual(
            Item.objects.get(pk=repeating.pk).commitment_id,
            Item.objects.get(pk=bobs.pk).commitment_id,
        )

    def test_an_ownerless_list_is_skipped_rather_than_failing_the_migration(self):
        """List.owner is still nullable, and a commitment's owner is not."""
        old_apps = self.migrate(BEFORE)
        List = old_apps.get_model("lists", "List")
        Item = old_apps.get_model("lists", "Item")

        orphan_list = List.objects.create(owner=None, title="Anonymous era")
        orphan = Item.objects.create(
            list=orphan_list, text="Pay rent", recurrence="monthly"
        )

        new_apps = self.migrate(AFTER)
        Item = new_apps.get_model("lists", "Item")
        RecurringCommitment = new_apps.get_model("lists", "RecurringCommitment")

        self.assertEqual(RecurringCommitment.objects.count(), 0)
        self.assertIsNone(Item.objects.get(pk=orphan.pk).commitment)
