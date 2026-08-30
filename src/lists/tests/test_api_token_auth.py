"""Bearer-token auth for lists.api's hand-rolled create_item/item_detail --
android-full-client-plan.md slice 2. token-scopes-plan.md §7 has the full
mechanism; this is the endpoint-level proof.

enforce_csrf_checks=True throughout, same as CaptureEndpointTest and for
the same reason: the whole point of a bearer request is that it needs no
CSRF token at all, and the default test client would hide a regression
there by disabling CSRF checking outright.
"""
import json

from django.test import Client, TestCase

from accounts.models import SCOPE_AGENDA_WRITE, PersonalAccessToken, User
from lists.models import Item, List


PASSWORD = "correct horse battery staple 47!"


class CreateItemTokenAuthTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.list_ = List.objects.create(owner=self.user, title="Programming")
        self.client = Client(enforce_csrf_checks=True)

    def post(self, list_id, payload, token=None):
        extra = {}
        if token is not None:
            extra["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return self.client.post(
            f"/api/areas/{list_id}/items/",
            data=json.dumps(payload),
            content_type="application/json",
            **extra,
        )

    def test_a_token_with_agenda_write_creates_a_task_with_no_csrf_token_sent(self):
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=[SCOPE_AGENDA_WRITE]
        )

        response = self.post(self.list_.id, {"text": "Call the vet"}, token=raw)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Item.objects.get().text, "Call the vet")

    def test_a_token_without_agenda_write_is_refused(self):
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=["capture:write"]
        )

        response = self.post(self.list_.id, {"text": "Call the vet"}, token=raw)

        self.assertEqual(response.status_code, 401)
        self.assertFalse(Item.objects.exists())

    def test_a_token_cannot_create_a_task_in_someone_elses_area(self):
        other = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        _, raw = PersonalAccessToken.generate(other, scopes=[SCOPE_AGENDA_WRITE])

        response = self.post(self.list_.id, {"text": "Not yours"}, token=raw)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Item.objects.exists())

    def test_a_logged_in_browser_still_needs_its_csrf_token(self):
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/areas/{self.list_.id}/items/",
            data=json.dumps({"text": "Forged"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Item.objects.exists())


class ItemDetailTokenAuthTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.list_ = List.objects.create(owner=self.user, title="Programming")
        self.item = Item.objects.create(list=self.list_, text="Write tests")
        self.client = Client(enforce_csrf_checks=True)

    def patch(self, item_id, payload, token=None):
        extra = {}
        if token is not None:
            extra["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return self.client.patch(
            f"/api/items/{item_id}/",
            data=json.dumps(payload),
            content_type="application/json",
            **extra,
        )

    def test_a_token_completes_a_task_with_no_csrf_token_sent(self):
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=[SCOPE_AGENDA_WRITE]
        )

        response = self.patch(
            self.item.id, {"status": Item.Status.COMPLETED}, token=raw
        )

        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.COMPLETED)

    def test_a_token_reschedules_a_tasks_due_date(self):
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=[SCOPE_AGENDA_WRITE]
        )

        response = self.patch(
            self.item.id, {"due_date": "2026-09-01"}, token=raw
        )

        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(str(self.item.due_date), "2026-09-01")

    def test_a_token_without_agenda_write_is_refused(self):
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=["capture:write"]
        )

        response = self.patch(
            self.item.id, {"status": Item.Status.COMPLETED}, token=raw
        )

        self.assertEqual(response.status_code, 401)
        self.item.refresh_from_db()
        self.assertNotEqual(self.item.status, Item.Status.COMPLETED)

    def test_nothing_but_status_and_due_date_is_accepted_at_all(self):
        """Four separate tests stood here asserting 403 for text, tags, notes
        and recurrence, and one for DELETE.

        coherence-audit-2026-08-30.md F2 trimmed this endpoint to the two
        fields a phone sends and removed DELETE, so the refusal is now a 400 --
        those fields are not part of this endpoint rather than being withheld
        from this caller, which is a more honest status and a smaller surface.
        What a phone may do on the typed router is
        `lists.tests.test_task_writes_api_v1.TaskWriteTokenAuthTest`.
        """
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=[SCOPE_AGENDA_WRITE]
        )

        for field, value in [
            ("text", "Rewritten by a phone"),
            ("tags", ["urgent"]),
            ("notes", "secret plan"),
            ("recurrence", "daily"),
        ]:
            with self.subTest(field=field):
                response = self.patch(self.item.id, {field: value}, token=raw)
                self.assertEqual(response.status_code, 400)

        self.item.refresh_from_db()
        self.assertEqual(self.item.text, "Write tests")

    def test_there_is_no_delete_on_this_endpoint_any_more(self):
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=[SCOPE_AGENDA_WRITE]
        )

        response = self.client.delete(
            f"/api/items/{self.item.id}/",
            HTTP_AUTHORIZATION=f"Bearer {raw}",
        )

        # 405, not the old 403: the method is gone rather than refused.
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Item.objects.filter(pk=self.item.pk).exists())

    def test_a_token_cannot_touch_someone_elses_task(self):
        other = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        _, raw = PersonalAccessToken.generate(other, scopes=[SCOPE_AGENDA_WRITE])

        response = self.patch(
            self.item.id, {"status": Item.Status.COMPLETED}, token=raw
        )

        self.assertEqual(response.status_code, 404)

    def test_a_logged_in_browser_still_needs_its_csrf_token(self):
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/areas/{self.list_.id}/items/",
            data=json.dumps({"text": "Forged"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Item.objects.exists())


class ItemDetailTokenAuthTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.list_ = List.objects.create(owner=self.user, title="Programming")
        self.item = Item.objects.create(list=self.list_, text="Write tests")
        self.client = Client(enforce_csrf_checks=True)

    def patch(self, item_id, payload, token=None):
        extra = {}
        if token is not None:
            extra["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return self.client.patch(
            f"/api/items/{item_id}/",
            data=json.dumps(payload),
            content_type="application/json",
            **extra,
        )

    def test_a_token_completes_a_task_with_no_csrf_token_sent(self):
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=[SCOPE_AGENDA_WRITE]
        )

        response = self.patch(
            self.item.id, {"status": Item.Status.COMPLETED}, token=raw
        )

        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.COMPLETED)

    def test_a_token_reschedules_a_tasks_due_date(self):
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=[SCOPE_AGENDA_WRITE]
        )

        response = self.patch(
            self.item.id, {"due_date": "2026-09-01"}, token=raw
        )

        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(str(self.item.due_date), "2026-09-01")

    def test_a_token_without_agenda_write_is_refused(self):
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=["capture:write"]
        )

        response = self.patch(
            self.item.id, {"status": Item.Status.COMPLETED}, token=raw
        )

        self.assertEqual(response.status_code, 401)
        self.item.refresh_from_db()
        self.assertNotEqual(self.item.status, Item.Status.COMPLETED)

    def test_nothing_but_status_and_due_date_is_accepted_at_all(self):
        """Four separate tests stood here asserting 403 for text, tags, notes
        and recurrence, and one for DELETE.

        coherence-audit-2026-08-30.md F2 trimmed this endpoint to the two
        fields a phone sends and removed DELETE, so the refusal is now a 400 --
        those fields are not part of this endpoint rather than being withheld
        from this caller, which is a more honest status and a smaller surface.
        What a phone may do on the typed router is
        `lists.tests.test_task_writes_api_v1.TaskWriteTokenAuthTest`.
        """
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=[SCOPE_AGENDA_WRITE]
        )

        for field, value in [
            ("text", "Rewritten by a phone"),
            ("tags", ["urgent"]),
            ("notes", "secret plan"),
            ("recurrence", "daily"),
        ]:
            with self.subTest(field=field):
                response = self.patch(self.item.id, {field: value}, token=raw)
                self.assertEqual(response.status_code, 400)

        self.item.refresh_from_db()
        self.assertEqual(self.item.text, "Write tests")

    def test_there_is_no_delete_on_this_endpoint_any_more(self):
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=[SCOPE_AGENDA_WRITE]
        )

        response = self.client.delete(
            f"/api/items/{self.item.id}/",
            HTTP_AUTHORIZATION=f"Bearer {raw}",
        )

        # 405, not the old 403: the method is gone rather than refused.
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Item.objects.filter(pk=self.item.pk).exists())

    def test_a_token_cannot_touch_someone_elses_task(self):
        other = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        _, raw = PersonalAccessToken.generate(other, scopes=[SCOPE_AGENDA_WRITE])

        response = self.patch(
            self.item.id, {"status": Item.Status.COMPLETED}, token=raw
        )

        self.assertEqual(response.status_code, 404)

    # `test_a_logged_in_browser_can_still_edit_text_and_delete` stood here.
    # It asserted that trimming a *token's* reach left the browser's alone --
    # true when written, and moot now: coherence-audit-2026-08-30.md F2 moved
    # the browser off this endpoint entirely, so there is no browser
    # capability here left to be unaffected. What replaced it is
    # lists.tests.test_task_writes_api_v1.

    def test_a_logged_in_browser_still_needs_its_csrf_token(self):
        self.client.force_login(self.user)

        response = self.client.patch(
            f"/api/items/{self.item.id}/",
            data=json.dumps({"status": Item.Status.COMPLETED}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
