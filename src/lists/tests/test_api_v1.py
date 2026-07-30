import json

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from lists import agenda as agenda_reader
from lists.models import Item, List


class AgendaEndpointTest(TestCase):
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
        Item.objects.create(
            list=self.list_,
            text="Ship the migration",
            due_date=timezone.localdate(),
        )
        Item.objects.create(list=self.other_user.lists.create(title="Bob's list"), text="Not mine")

    def test_rejects_anonymous_requests(self):
        response = self.client.get("/api/v1/agenda")

        self.assertEqual(response.status_code, 401)

    def test_returns_only_the_caller_s_agenda(self):
        self.client.force_login(self.user)

        response = self.client.get("/api/v1/agenda")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["username"], "alice")
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["text"], "Ship the migration")
        self.assertEqual(len(payload["lists"]), 1)
        self.assertEqual(payload["lists"][0]["title"], "Programming")

    def test_matches_the_shape_the_agenda_page_bootstraps_with(self):
        self.client.force_login(self.user)

        api_payload = self.client.get("/api/v1/agenda").json()
        page_payload = self.client.get("/dashboard/").context["agenda_workspace_data"]

        self.assertEqual(set(api_payload.keys()), set(page_payload.keys()))

    def test_assigns_a_deterministic_semantic_color_key(self):
        self.client.force_login(self.user)

        payload = self.client.get("/api/v1/agenda").json()

        self.assertEqual(
            payload["lists"][0]["color_key"],
            agenda_reader.color_key_for_list(self.list_.id),
        )


class ListDetailEndpointTest(TestCase):
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
        Item.objects.create(list=self.list_, text="Write tests")
        self.other_list = self.other_user.lists.create(title="Bob's list")

    def test_rejects_anonymous_requests(self):
        response = self.client.get(f"/api/v1/lists/{self.list_.id}")

        self.assertEqual(response.status_code, 401)

    def test_404s_a_list_owned_by_someone_else(self):
        self.client.force_login(self.user)

        response = self.client.get(f"/api/v1/lists/{self.other_list.id}")

        self.assertEqual(response.status_code, 404)

    def test_returns_the_list_and_its_open_items(self):
        self.client.force_login(self.user)

        response = self.client.get(f"/api/v1/lists/{self.list_.id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["list"]["title"], "Programming")
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["text"], "Write tests")

    def test_matches_the_shape_the_list_page_bootstraps_with_plus_archive_info(self):
        """The API response is a superset of task_workspace_data: it also
        carries archived_count/archive_url, which the legacy page gets
        from separate sibling context keys instead (archived_task_count,
        and a hardcoded {% url 'archive' %} in the template)."""
        self.client.force_login(self.user)

        api_payload = self.client.get(f"/api/v1/lists/{self.list_.id}").json()
        page_context = self.client.get(f"/lists/{self.list_.id}/").context

        self.assertEqual(
            set(api_payload.keys()) - {"archived_count", "archive_url"},
            set(page_context["task_workspace_data"].keys()),
        )
        self.assertEqual(
            api_payload["archived_count"],
            page_context["archived_task_count"],
        )

    def test_renames_the_list(self):
        self.client.force_login(self.user)

        response = self.client.patch(
            f"/api/v1/lists/{self.list_.id}",
            data=json.dumps({"title": "Side Projects"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Side Projects")
        self.list_.refresh_from_db()
        self.assertEqual(self.list_.title, "Side Projects")

    def test_rejects_an_empty_rename(self):
        self.client.force_login(self.user)

        response = self.client.patch(
            f"/api/v1/lists/{self.list_.id}",
            data=json.dumps({"title": "   "}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.list_.refresh_from_db()
        self.assertEqual(self.list_.title, "Programming")

    def test_cannot_rename_someone_else_s_list(self):
        self.client.force_login(self.user)

        response = self.client.patch(
            f"/api/v1/lists/{self.other_list.id}",
            data=json.dumps({"title": "Hijacked"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_deletes_the_list_and_its_items(self):
        self.client.force_login(self.user)

        response = self.client.delete(f"/api/v1/lists/{self.list_.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted": self.list_.id})
        self.assertFalse(List.objects.filter(id=self.list_.id).exists())

    def test_cannot_delete_someone_else_s_list(self):
        self.client.force_login(self.user)

        response = self.client.delete(f"/api/v1/lists/{self.other_list.id}")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(List.objects.filter(id=self.other_list.id).exists())
