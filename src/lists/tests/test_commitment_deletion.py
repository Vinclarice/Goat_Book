"""Deleting an account must not be blocked by its own commitment records.

`Item.commitment` is PROTECT so a series can't be silently dissolved into
one-off tasks. But an account deletion cascades to both the commitments and
the tasks that point at them, and PROTECT does not care that the referring
rows are on their way out in the same operation.
"""
from django.test import TestCase

from accounts.models import User
from lists import services
from lists.models import Item, List, RecurringCommitment


class CommitmentDeletionTest(TestCase):
    def test_deleting_an_owner_removes_their_commitments_and_tasks(self):
        user = User.objects.create_user("zed", "zed@example.com", "a password")
        list_ = List.objects.create(owner=user, title="Home")
        services.create_item(list_, "Pay rent", recurrence=Item.Recurrence.MONTHLY)
        self.assertEqual(RecurringCommitment.objects.count(), 1)

        user.delete()

        self.assertEqual(RecurringCommitment.objects.count(), 0)
        self.assertEqual(Item.objects.count(), 0)

    def test_deleting_a_list_leaves_the_commitment_and_its_owner(self):
        """A list going away is not the series being disowned."""
        user = User.objects.create_user("zed", "zed@example.com", "a password")
        list_ = List.objects.create(owner=user, title="Home")
        services.create_item(list_, "Pay rent", recurrence=Item.Recurrence.MONTHLY)

        list_.delete()

        self.assertEqual(Item.objects.count(), 0)
        self.assertEqual(RecurringCommitment.objects.filter(owner=user).count(), 1)
