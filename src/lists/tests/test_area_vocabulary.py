"""The API boundary says Area; the Django model stays `List`.

Release D slice 5. `architecture-trajectory.md` §7 refuses renaming the
`lists` app or the `List` model -- migration churn for no behaviour change --
and prescribes the vocabulary migration at the boundary instead, exactly as
`Item` already answers to "task" there. This file is the guard for that
boundary: every assertion below is about what a *client* reads, and none of
them touch what the ORM stores.

Kept as its own file rather than folded into test_api_v1.py because the
vocabulary is a cross-cutting contract of its own -- an endpoint's isolation
and shape belong with that endpoint, but "does this payload speak the
product's language" is one question asked of all of them at once.
"""
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from lists.models import Item, List


class AreaVocabularyTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.area = List.objects.create(owner=self.user, title="Programming")
        self.task = Item.objects.create(list=self.area, text="Write tests")
        Item.objects.create(
            list=self.area,
            text="Old task",
            status=Item.Status.ARCHIVED,
            completed_at=timezone.now(),
            archived_at=timezone.now(),
        )
        self.client.force_login(self.user)

    def test_the_agenda_calls_them_areas(self):
        payload = self.client.get("/api/v1/agenda").json()

        self.assertEqual(payload["areas"][0]["title"], "Programming")
        self.assertNotIn("lists", payload)
        self.assertIn("new_area_url", payload)
        self.assertNotIn("new_list_url", payload)

    def test_the_nav_calls_them_areas(self):
        payload = self.client.get("/api/v1/nav").json()

        self.assertEqual(payload["areas"][0]["title"], "Programming")
        self.assertNotIn("lists", payload)

    def test_the_archive_calls_them_areas(self):
        payload = self.client.get("/api/v1/archive").json()

        self.assertEqual(payload["areas"][0]["title"], "Programming")
        self.assertNotIn("lists", payload)

    def test_a_task_carries_the_area_it_belongs_to(self):
        payload = self.client.get(f"/api/v1/tasks/{self.task.id}").json()

        self.assertEqual(payload["area"]["title"], "Programming")
        self.assertEqual(payload["task"]["area_id"], self.area.id)
        self.assertNotIn("list", payload)
        self.assertNotIn("list_id", payload["task"])

    def test_an_area_is_read_renamed_and_deleted_under_its_own_route(self):
        detail = self.client.get(f"/api/v1/areas/{self.area.id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["area"]["title"], "Programming")
        self.assertNotIn("list", detail.json())

        renamed = self.client.patch(
            f"/api/v1/areas/{self.area.id}",
            data='{"title": "Side Projects"}',
            content_type="application/json",
        )
        self.assertEqual(renamed.status_code, 200)
        self.area.refresh_from_db()
        self.assertEqual(self.area.title, "Side Projects")

        deleted = self.client.delete(f"/api/v1/areas/{self.area.id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(List.objects.filter(id=self.area.id).exists())

    def test_the_old_list_route_is_gone_rather_than_kept_as_an_alias(self):
        """No compatibility window, stated deliberately.

        `principles.md` prefers staged, compatible API changes -- but that
        rule exists to avoid stranding a client, and there is no client to
        strand. The SPA ships in the same Django deploy as this endpoint, and
        the Android client only ever calls the capture API. Dual-serving both
        spellings would leave the drift the rename exists to remove.
        """
        self.assertEqual(
            self.client.get(f"/api/v1/lists/{self.area.id}").status_code, 404
        )

    def test_the_old_page_url_still_lands_somewhere(self):
        """The API got a clean break; a page URL does not.

        Nobody bookmarks /api/v1/lists/3, but /lists/3/ is a link a person
        could have saved, and `principles.md` asks that failure be
        recoverable rather than a bare 404. Both spellings redirect into the
        SPA, so the old one costs one extra hop and nothing else.
        """
        response = self.client.get(f"/lists/{self.area.id}/", follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain[-1][0], f"/app/areas/{self.area.id}"
        )
