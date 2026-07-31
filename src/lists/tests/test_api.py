import json

from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User
from lists.models import Item, List


class TaskApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )
        self.other_user = User.objects.create_user(
            "bob",
            "bob@example.com",
            "another secure password",
        )
        self.list_ = List.objects.create(owner=self.user, title="Programming")
        self.item = Item.objects.create(list=self.list_, text="Write tests")
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        # Any login-required page that still renders a real {% csrf_token %}
        # form primes the cookie -- list/archive/agenda no longer render
        # one themselves now that they're pure redirects into the SPA.
        response = self.client.get("/accounts/password/change/")
        self.csrf_token = response.cookies["csrftoken"].value

    def request(self, method, url, payload=None, include_csrf=True):
        kwargs = {
            "data": json.dumps(payload or {}),
            "content_type": "application/json",
        }
        if include_csrf:
            kwargs["HTTP_X_CSRFTOKEN"] = self.csrf_token
        return getattr(self.client, method)(url, **kwargs)

    def test_create_edit_and_complete_task(self):
        create_response = self.request(
            "post",
            f"/api/lists/{self.list_.id}/items/",
            {"text": "Build interface"},
        )
        created = create_response.json()["data"]

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(created["status"], Item.Status.ACTIVE)

        edit_response = self.request(
            "patch",
            created["url"],
            {"text": "Build React interface"},
        )
        complete_response = self.request(
            "patch",
            created["url"],
            {"status": Item.Status.COMPLETED},
        )

        self.assertEqual(edit_response.status_code, 200)
        self.assertEqual(edit_response.json()["data"]["text"], "Build React interface")
        self.assertEqual(
            complete_response.json()["data"]["status"],
            Item.Status.COMPLETED,
        )

    def test_create_with_due_date_and_update_it(self):
        create_response = self.request(
            "post",
            f"/api/lists/{self.list_.id}/items/",
            {"text": "Renew passport", "due_date": "2026-09-01"},
        )
        created = create_response.json()["data"]
        self.assertEqual(created["due_date"], "2026-09-01")

        update_response = self.request(
            "patch",
            created["url"],
            {"due_date": "2026-09-15"},
        )
        self.assertEqual(update_response.json()["data"]["due_date"], "2026-09-15")

        clear_response = self.request(
            "patch",
            created["url"],
            {"due_date": None},
        )
        self.assertIsNone(clear_response.json()["data"]["due_date"])

    def test_rejects_invalid_due_date(self):
        response = self.request(
            "patch",
            f"/api/items/{self.item.id}/",
            {"due_date": "not-a-date"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("due_date", response.json()["errors"])

    def test_create_and_update_tags(self):
        create_response = self.request(
            "post",
            f"/api/lists/{self.list_.id}/items/",
            {"text": "Buy milk", "tags": ["groceries", "groceries", " home "]},
        )
        created = create_response.json()["data"]
        self.assertEqual(sorted(created["tags"]), ["groceries", "home"])

        update_response = self.request(
            "patch",
            created["url"],
            {"tags": ["errands"]},
        )
        self.assertEqual(update_response.json()["data"]["tags"], ["errands"])

    def test_rejects_non_string_tags(self):
        response = self.request(
            "patch",
            f"/api/items/{self.item.id}/",
            {"tags": [1, 2]},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("tags", response.json()["errors"])

    def test_create_with_recurrence_and_update_it(self):
        create_response = self.request(
            "post",
            f"/api/lists/{self.list_.id}/items/",
            {"text": "Take out trash", "recurrence": "weekly"},
        )
        created = create_response.json()["data"]
        self.assertEqual(created["recurrence"], "weekly")

        update_response = self.request(
            "patch",
            created["url"],
            {"recurrence": "daily"},
        )
        self.assertEqual(update_response.json()["data"]["recurrence"], "daily")

    def test_rejects_invalid_recurrence(self):
        response = self.request(
            "post",
            f"/api/lists/{self.list_.id}/items/",
            {"text": "Bad recurrence", "recurrence": "yearly"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("recurrence", response.json()["errors"])

    def test_completing_a_recurring_task_returns_spawned_item(self):
        self.request(
            "patch",
            f"/api/items/{self.item.id}/",
            {"recurrence": "daily"},
        )

        response = self.request(
            "patch",
            f"/api/items/{self.item.id}/",
            {"status": Item.Status.COMPLETED},
        )
        body = response.json()
        self.assertEqual(body["data"]["status"], Item.Status.ARCHIVED)
        self.assertIn("spawned", body)
        self.assertEqual(body["spawned"]["text"], self.item.text)
        self.assertEqual(body["spawned"]["status"], Item.Status.ACTIVE)

    def test_reorder_items(self):
        second = Item.objects.create(list=self.list_, text="Second", position=1)

        response = self.request(
            "post",
            f"/api/lists/{self.list_.id}/items/reorder/",
            {"ordered_ids": [second.id, self.item.id]},
        )

        self.assertEqual(response.status_code, 200)
        ordered_ids = [row["id"] for row in response.json()["data"]]
        self.assertEqual(ordered_ids, [second.id, self.item.id])
        self.assertEqual(list(self.list_.item_set.all()), [second, self.item])

    def test_reorder_rejects_mismatched_ids(self):
        response = self.request(
            "post",
            f"/api/lists/{self.list_.id}/items/reorder/",
            {"ordered_ids": [self.item.id, 999999]},
        )
        self.assertEqual(response.status_code, 409)

    def test_reorder_requires_list_of_ints(self):
        response = self.request(
            "post",
            f"/api/lists/{self.list_.id}/items/reorder/",
            {"ordered_ids": "not-a-list"},
        )
        self.assertEqual(response.status_code, 400)

    def test_restore_conflict_returns_409(self):
        self.item.status = Item.Status.ARCHIVED
        self.item.completed_at = timezone.now()
        self.item.archived_at = timezone.now()
        self.item.save()
        Item.objects.create(list=self.list_, text=self.item.text)

        response = self.request(
            "patch",
            f"/api/items/{self.item.id}/",
            {"status": Item.Status.COMPLETED},
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("conflict", response.json()["errors"])

    def test_restoring_a_task_archived_while_active_returns_it_to_active(self):
        # The restore request says "completed" because that is the only status
        # the API accepts for un-archiving, but since 0018 the response can
        # legitimately come back active -- the task was active when archived.
        # The SPA drops the row from the archive and refetches, so it doesn't
        # depend on the echoed status; this pins the contract anyway.
        self.item.status = Item.Status.ARCHIVED
        self.item.completed_at = None
        self.item.archived_at = timezone.now()
        self.item.save()

        response = self.request(
            "patch",
            f"/api/items/{self.item.id}/",
            {"status": Item.Status.COMPLETED},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], Item.Status.ACTIVE)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.ACTIVE)
        self.assertIsNone(self.item.completed_at)

    def test_delete_requires_archived_status(self):
        active_response = self.request(
            "delete",
            f"/api/items/{self.item.id}/",
        )
        self.assertEqual(active_response.status_code, 400)

        self.item.status = Item.Status.ARCHIVED
        self.item.completed_at = timezone.now()
        self.item.archived_at = timezone.now()
        self.item.save()
        archived_response = self.request(
            "delete",
            f"/api/items/{self.item.id}/",
        )

        self.assertEqual(archived_response.status_code, 200)
        self.assertFalse(Item.objects.filter(pk=self.item.pk).exists())

    def test_rejects_missing_csrf_token(self):
        response = self.request(
            "patch",
            f"/api/items/{self.item.id}/",
            {"status": Item.Status.COMPLETED},
            include_csrf=False,
        )

        self.assertEqual(response.status_code, 403)

    def test_other_users_task_is_hidden(self):
        other_list = List.objects.create(owner=self.other_user, title="Private")
        other_item = Item.objects.create(list=other_list, text="Private task")

        response = self.request(
            "patch",
            f"/api/items/{other_item.id}/",
            {"status": Item.Status.COMPLETED},
        )

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_request_returns_json_401(self):
        anonymous_client = Client()

        response = anonymous_client.patch(
            f"/api/items/{self.item.id}/",
            data=json.dumps({"status": Item.Status.COMPLETED}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("authentication", response.json()["errors"])
