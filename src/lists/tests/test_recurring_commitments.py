"""Crane 0a: a recurring commitment keeps its identity across occurrences.

`_spawn_next_occurrence` copies a fair amount of content onto the next
occurrence -- text, due date, cadence, tags, children -- and never wrote
anything saying the two rows were the same commitment. The only thing marking
occurrence five of "Pay rent" as occurrence four's successor was a matching
string in one list, so renaming a task split its series silently in two and no
trend, streak or completion rate could be assembled from it.

`RecurringCommitment` is deliberately thin: an owner and a lifespan, nothing
else. It is an identity anchor, not a template. Text and cadence stay on
`Item` until release D moves the whole vocabulary at once -- copying them here
would create the second source of truth this is supposed to prevent. See
design/crane-plan.md 3, "Crane 0a -- the identity slice".
"""
from django.test import TestCase

from accounts.models import User
from lists import services
from lists.models import Item, List, RecurringCommitment


class CommitmentIdentityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.list_ = List.objects.create(owner=self.user, title="Home")

    def complete(self, item):
        return services.complete_item(item)

    def test_recurring_task_created_with_a_cadence_gets_a_commitment(self):
        item = services.create_item(
            self.list_, "Pay rent", recurrence=Item.Recurrence.MONTHLY
        )

        self.assertIsNotNone(item.commitment)
        self.assertEqual(item.commitment.owner, self.user)
        self.assertIsNone(item.commitment.ended_at)

    def test_one_off_task_has_no_commitment(self):
        item = services.create_item(self.list_, "Buy milk")

        self.assertIsNone(item.commitment)

    def test_setting_a_cadence_later_creates_the_commitment(self):
        item = services.create_item(self.list_, "Pay rent")
        self.assertIsNone(item.commitment)

        item = services.set_recurrence(item, Item.Recurrence.MONTHLY)

        self.assertIsNotNone(item.commitment)
        self.assertEqual(item.commitment.owner, self.user)

    def test_spawned_occurrence_joins_the_same_commitment(self):
        first = services.create_item(
            self.list_, "Pay rent", recurrence=Item.Recurrence.MONTHLY
        )
        commitment = first.commitment

        second = self.complete(first)._spawned

        self.assertEqual(second.commitment, commitment)

    def test_the_series_survives_a_rename_of_one_occurrence(self):
        """The acceptance example from crane-plan.md 3, run end to end."""
        item = services.create_item(
            self.list_, "Pay rent", recurrence=Item.Recurrence.MONTHLY
        )
        commitment = item.commitment

        item = self.complete(item)._spawned
        item = self.complete(item)._spawned
        item = self.complete(item)._spawned
        services.edit_item(item, "Pay rent - new landlord")

        occurrences = list(commitment.occurrences.order_by("created_at", "id"))
        self.assertEqual(len(occurrences), 4)
        self.assertEqual(
            [each.text for each in occurrences],
            ["Pay rent", "Pay rent", "Pay rent", "Pay rent - new landlord"],
        )

    def test_clearing_the_cadence_ends_the_commitment_but_keeps_the_link(self):
        item = services.create_item(
            self.list_, "Pay rent", recurrence=Item.Recurrence.MONTHLY
        )
        commitment = item.commitment

        item = services.set_recurrence(item, Item.Recurrence.NONE)

        # The link stays: this task really was an occurrence of that series,
        # and clearing the key would rewrite history to say it never was.
        self.assertEqual(item.commitment, commitment)
        commitment.refresh_from_db()
        self.assertIsNotNone(commitment.ended_at)

    def test_resuming_reuses_the_commitment_rather_than_starting_a_new_one(self):
        item = services.create_item(
            self.list_, "Pay rent", recurrence=Item.Recurrence.MONTHLY
        )
        commitment = item.commitment
        item = services.set_recurrence(item, Item.Recurrence.NONE)

        item = services.set_recurrence(item, Item.Recurrence.MONTHLY)

        self.assertEqual(item.commitment, commitment)
        self.assertEqual(RecurringCommitment.objects.count(), 1)
        commitment.refresh_from_db()
        self.assertIsNone(commitment.ended_at)

    def test_a_legacy_recurring_task_is_adopted_when_it_spawns(self):
        """No path may leave the accrual running.

        Rows that predate this slice have no commitment and cannot be given a
        shared one retroactively. What they can do is stop losing *new*
        history: the first completion after this ships anchors the series, and
        links the completed occurrence into it as well as the new one.
        """
        legacy = Item.objects.create(
            list=self.list_,
            text="Pay rent",
            recurrence=Item.Recurrence.MONTHLY,
        )
        self.assertIsNone(legacy.commitment)

        spawned = self.complete(legacy)._spawned

        legacy.refresh_from_db()
        self.assertIsNotNone(spawned.commitment)
        self.assertEqual(legacy.commitment, spawned.commitment)

    def test_a_commitment_with_history_cannot_be_deleted(self):
        """RESTRICT, deliberately.

        SET_NULL would silently turn a series back into unrelated one-off
        tasks, which is the exact failure this slice exists to fix. Deleting
        the owner is a different case and is allowed -- see
        test_commitment_deletion.
        """
        item = services.create_item(
            self.list_, "Pay rent", recurrence=Item.Recurrence.MONTHLY
        )

        with self.assertRaises(Exception):
            item.commitment.delete()

    def test_commitments_are_owner_scoped(self):
        bob = User.objects.create_user("bob", "bob@example.com", "another password")
        bob_list = List.objects.create(owner=bob, title="Bob's home")
        services.create_item(
            self.list_, "Pay rent", recurrence=Item.Recurrence.MONTHLY
        )
        services.create_item(
            bob_list, "Pay rent", recurrence=Item.Recurrence.MONTHLY
        )

        self.assertEqual(RecurringCommitment.objects.filter(owner=self.user).count(), 1)
        self.assertEqual(RecurringCommitment.objects.filter(owner=bob).count(), 1)
