import json

from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User
from lists.models import Item, List


class ApiV1IsolationTest(TestCase):
    """Every id-taking /api/v1/ endpoint, probed by a second logged-in user."""

    def setUp(self):
        self.owner = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )
        self.intruder = User.objects.create_user(
            "mallory",
            "mallory@example.com",
            "another secure password",
        )
        self.owner_list = List.objects.create(owner=self.owner, title="Programming")
        # task_detail only resolves active/completed items, so an archived
        # fixture here would 404 for the owner too and prove nothing.
        self.owner_item = Item.objects.create(list=self.owner_list, text="Write tests")
        self.intruder_list = List.objects.create(
            owner=self.intruder,
            title="Mallory's list",
        )
        self.owner_client = Client()
        self.owner_client.force_login(self.owner)
        self.intruder_client = Client()
        self.intruder_client.force_login(self.intruder)

    def test_404s_a_read_of_someone_else_s_list(self):
        response = self.intruder_client.get(f"/api/v1/areas/{self.owner_list.id}")

        self.assertEqual(response.status_code, 404)
        owner_view = self.owner_client.get(f"/api/v1/areas/{self.owner_list.id}")
        self.assertEqual(owner_view.status_code, 200)
        self.assertEqual(owner_view.json()["area"]["title"], "Programming")

    def test_404s_a_rename_of_someone_else_s_list(self):
        # The body has to be a valid ListRenameIn: ninja parses it before the
        # view runs, so an empty payload would 422 for the wrong reason.
        response = self.intruder_client.patch(
            f"/api/v1/areas/{self.owner_list.id}",
            data=json.dumps({"title": "Hijacked"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.owner_list.refresh_from_db()
        self.assertEqual(self.owner_list.title, "Programming")

    def test_the_same_rename_succeeds_on_the_intruder_s_own_list(self):
        """Control: the 404 above is about ownership, not a bad request."""
        response = self.intruder_client.patch(
            f"/api/v1/areas/{self.intruder_list.id}",
            data=json.dumps({"title": "Hijacked"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.intruder_list.refresh_from_db()
        self.assertEqual(self.intruder_list.title, "Hijacked")

    def test_404s_a_delete_of_someone_else_s_list(self):
        response = self.intruder_client.delete(f"/api/v1/areas/{self.owner_list.id}")

        self.assertEqual(response.status_code, 404)
        owner_view = self.owner_client.get(f"/api/v1/areas/{self.owner_list.id}")
        self.assertEqual(owner_view.status_code, 200)
        self.assertTrue(Item.objects.filter(id=self.owner_item.id).exists())

    def test_the_same_delete_succeeds_on_the_intruder_s_own_list(self):
        """Control: the 404 above is about ownership, not a dead route."""
        response = self.intruder_client.delete(
            f"/api/v1/areas/{self.intruder_list.id}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(List.objects.filter(id=self.intruder_list.id).exists())

    def test_404s_a_read_of_someone_else_s_task(self):
        response = self.intruder_client.get(f"/api/v1/tasks/{self.owner_item.id}")

        self.assertEqual(response.status_code, 404)
        owner_view = self.owner_client.get(f"/api/v1/tasks/{self.owner_item.id}")
        self.assertEqual(owner_view.status_code, 200)
        self.assertEqual(owner_view.json()["task"]["text"], "Write tests")


class LegacyApiIsolationTest(TestCase):
    """Every id-taking legacy /api/ endpoint, probed by a second logged-in user."""

    def setUp(self):
        self.owner = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )
        self.intruder = User.objects.create_user(
            "mallory",
            "mallory@example.com",
            "another secure password",
        )
        self.owner_list = List.objects.create(owner=self.owner, title="Programming")
        self.owner_item = Item.objects.create(
            list=self.owner_list,
            text="Write tests",
            position=0,
        )
        self.owner_second_item = Item.objects.create(
            list=self.owner_list,
            text="Ship the migration",
            position=1,
        )
        self.intruder_list = List.objects.create(
            owner=self.intruder,
            title="Mallory's list",
        )
        self.intruder_item = Item.objects.create(
            list=self.intruder_list,
            text="Nothing to see",
            position=0,
        )
        # Delete only accepts archived tasks, so the control below needs one.
        self.intruder_archived_item = Item.objects.create(
            list=self.intruder_list,
            text="Old task",
            status=Item.Status.ARCHIVED,
            completed_at=timezone.now(),
            archived_at=timezone.now(),
        )
        # Plain clients: CSRF is not what this module tests, and an unprimed
        # token would turn every mutation into a 403 that reads like a block
        # for entirely the wrong reason. test_api.py covers CSRF itself.
        self.owner_client = Client()
        self.owner_client.force_login(self.owner)
        self.intruder_client = Client()
        self.intruder_client.force_login(self.intruder)

    def request(self, client, method, url, payload=None):
        return getattr(client, method)(
            url,
            data=json.dumps(payload or {}),
            content_type="application/json",
        )

    def test_404s_an_item_created_on_someone_else_s_list(self):
        response = self.request(
            self.intruder_client,
            "post",
            f"/api/areas/{self.owner_list.id}/items/",
            {"text": "Planted"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["errors"]["item"], ["Task not found."])
        self.assertEqual(
            list(self.owner_list.item_set.values_list("text", flat=True)),
            ["Write tests", "Ship the migration"],
        )

    def test_the_same_create_succeeds_on_the_intruder_s_own_list(self):
        """Control: the 404 above is about ownership, not a bad request."""
        response = self.request(
            self.intruder_client,
            "post",
            f"/api/areas/{self.intruder_list.id}/items/",
            {"text": "Planted"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["text"], "Planted")

    def test_404s_a_reorder_of_someone_else_s_list(self):
        response = self.request(
            self.intruder_client,
            "post",
            f"/api/areas/{self.owner_list.id}/items/reorder/",
            {"ordered_ids": [self.owner_second_item.id, self.owner_item.id]},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["errors"]["list"], ["List not found."])
        self.owner_item.refresh_from_db()
        self.owner_second_item.refresh_from_db()
        self.assertEqual(self.owner_item.position, 0)
        self.assertEqual(self.owner_second_item.position, 1)

    def test_409s_a_reorder_carrying_another_user_s_item_id(self):
        """An id in the body, not the path -- the shape a future bug takes."""
        response = self.request(
            self.owner_client,
            "post",
            f"/api/areas/{self.owner_list.id}/items/reorder/",
            {
                "ordered_ids": [
                    self.owner_second_item.id,
                    self.owner_item.id,
                    self.intruder_item.id,
                ],
            },
        )

        # 409 rather than 404: the path id is the caller's own list, so the
        # smuggled id is caught by services.reorder_items' set-equality check
        # instead of the ownership filter. Rejected either way, and the whole
        # reorder is atomic, so neither list moves.
        self.assertEqual(response.status_code, 409)
        self.assertIn("ordered_ids", response.json()["errors"])
        self.owner_item.refresh_from_db()
        self.owner_second_item.refresh_from_db()
        self.intruder_item.refresh_from_db()
        self.assertEqual(self.owner_item.position, 0)
        self.assertEqual(self.owner_second_item.position, 1)
        self.assertEqual(self.intruder_item.position, 0)

    def test_the_same_reorder_succeeds_with_only_the_owner_s_own_ids(self):
        """Control: the 409 above is about the foreign id, not the payload."""
        response = self.request(
            self.owner_client,
            "post",
            f"/api/areas/{self.owner_list.id}/items/reorder/",
            {"ordered_ids": [self.owner_second_item.id, self.owner_item.id]},
        )

        self.assertEqual(response.status_code, 200)
        self.owner_item.refresh_from_db()
        self.owner_second_item.refresh_from_db()
        self.assertEqual(self.owner_second_item.position, 0)
        self.assertEqual(self.owner_item.position, 1)

    def test_404s_a_patch_of_someone_else_s_item(self):
        response = self.request(
            self.intruder_client,
            "patch",
            f"/api/items/{self.owner_item.id}/",
            {"text": "Hijacked"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["errors"]["item"], ["Task not found."])
        self.owner_item.refresh_from_db()
        self.assertEqual(self.owner_item.text, "Write tests")

    def test_the_same_patch_succeeds_on_the_intruder_s_own_item(self):
        """Control: the 404 above is about ownership, not a bad request."""
        response = self.request(
            self.intruder_client,
            "patch",
            f"/api/items/{self.intruder_item.id}/",
            {"text": "Hijacked"},
        )

        self.assertEqual(response.status_code, 200)
        self.intruder_item.refresh_from_db()
        self.assertEqual(self.intruder_item.text, "Hijacked")

    def test_404s_a_delete_of_someone_else_s_item(self):
        # Ownership is resolved before the archived-only rule, so a foreign
        # active task 404s rather than returning the 400 its owner would get.
        response = self.request(
            self.intruder_client,
            "delete",
            f"/api/items/{self.owner_item.id}/",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["errors"]["item"], ["Task not found."])
        self.assertTrue(Item.objects.filter(id=self.owner_item.id).exists())

    def test_the_same_delete_succeeds_on_the_intruder_s_own_item(self):
        """Control: the 404 above is about ownership, not a dead route."""
        response = self.request(
            self.intruder_client,
            "delete",
            f"/api/items/{self.intruder_archived_item.id}/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Item.objects.filter(id=self.intruder_archived_item.id).exists(),
        )
