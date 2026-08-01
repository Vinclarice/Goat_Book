"""B1: a spawned recurring occurrence carries its fresh children back.

Completing a repeating parent creates the next occurrence and clones the
children that recur, all in one transaction. The lifecycle is already
correct and tested in test_services.py; the gap was only in the mutation
response, which serialised the new parent but not its new children -- so
the workspaces could place the parent in local state and had nothing to
nest under it until the next query.

`spawned_subtasks` is a sibling of `spawned` rather than children embedded
in every Task, so the ordinary list, agenda and detail reads stay small and
only the one mutation that creates children carries them.
"""
import json

from django.test import Client, TestCase

from accounts.models import User
from lists import services
from lists.models import Item, List


class SpawnedSubtaskResponseTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.list_ = List.objects.create(owner=self.user, title="Programming")
        self.parent = Item.objects.create(
            list=self.list_,
            text="Weekly review",
            recurrence=Item.Recurrence.WEEKLY,
        )
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        response = self.client.get("/accounts/password/change/")
        self.csrf_token = response.cookies["csrftoken"].value

    def child(self, text, position, **extra):
        return Item.objects.create(
            list=self.list_,
            text=text,
            parent=self.parent,
            position=position,
            **extra,
        )

    def complete_parent(self):
        return self.client.patch(
            f"/api/items/{self.parent.id}/",
            data=json.dumps({"status": Item.Status.COMPLETED}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
        ).json()

    def test_returns_the_fresh_children_in_position_order(self):
        self.child("Read the notes", position=0)
        self.child("Write the summary", position=1)

        body = self.complete_parent()

        self.assertIn("spawned_subtasks", body)
        self.assertEqual(
            [each["text"] for each in body["spawned_subtasks"]],
            ["Read the notes", "Write the summary"],
        )

    def test_the_returned_children_belong_to_the_new_parent(self):
        # Captured before completing: afterwards two rows share this text,
        # the archived original and its clone.
        original = self.child("Read the notes", position=0)

        body = self.complete_parent()

        spawned_id = body["spawned"]["id"]
        [fresh] = body["spawned_subtasks"]
        self.assertEqual(fresh["parent"]["id"], spawned_id)
        self.assertNotEqual(fresh["id"], original.id)
        self.assertEqual(fresh["status"], Item.Status.ACTIVE)

    def test_leaves_out_a_child_that_opted_out_of_recurring(self):
        self.child("Read the notes", position=0)
        self.child("One-off errand", position=1, always_recurs=False)

        body = self.complete_parent()

        self.assertEqual(
            [each["text"] for each in body["spawned_subtasks"]],
            ["Read the notes"],
        )

    def test_leaves_out_a_child_archived_before_the_parent_was_completed(self):
        self.child("Read the notes", position=0)
        # Through the service: a status set directly would skip archived_at
        # and fail the valid_item_status_timestamps check constraint.
        services.archive_item(self.child("Abandoned", position=1))

        body = self.complete_parent()

        self.assertEqual(
            [each["text"] for each in body["spawned_subtasks"]],
            ["Read the notes"],
        )

    def test_a_recurring_parent_with_no_children_returns_an_empty_list(self):
        body = self.complete_parent()

        # Present and empty rather than absent: the client always reads an
        # array and never has to branch on the field existing.
        self.assertEqual(body["spawned_subtasks"], [])

    def test_a_non_recurring_task_returns_no_spawned_anything(self):
        plain = Item.objects.create(list=self.list_, text="One and done")

        body = self.client.patch(
            f"/api/items/{plain.id}/",
            data=json.dumps({"status": Item.Status.COMPLETED}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
        ).json()

        self.assertNotIn("spawned", body)
        self.assertNotIn("spawned_subtasks", body)

    def test_cascaded_stays_separate_from_spawned_subtasks(self):
        # cascaded describes existing rows this action moved; spawned_subtasks
        # describes rows it created. Conflating them would double-count.
        self.child("Read the notes", position=0)

        body = self.complete_parent()

        cascaded_ids = {each["id"] for each in body.get("cascaded", [])}
        spawned_ids = {each["id"] for each in body["spawned_subtasks"]}
        self.assertTrue(cascaded_ids.isdisjoint(spawned_ids))
        self.assertTrue(
            all(each["status"] == Item.Status.ACTIVE for each in body["spawned_subtasks"])
        )

    def test_serialises_children_with_their_tags(self):
        # tags is an m2m to Tag, so names go through the service that
        # resolves them rather than straight onto the relation.
        services.set_item_tags(self.child("Read the notes", position=0), ["reading"])

        body = self.complete_parent()

        [fresh] = body["spawned_subtasks"]
        self.assertEqual(fresh["tags"], ["reading"])
