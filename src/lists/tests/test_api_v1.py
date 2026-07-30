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
