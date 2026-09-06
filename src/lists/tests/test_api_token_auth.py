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

from accounts.models import (
    SCOPE_AGENDA_READ,
    SCOPE_AGENDA_WRITE,
    PersonalAccessToken,
    User,
)
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


class PoolTokenAuthTest(TestCase):
    """The pool, reachable by a bearer -- android-overhaul-plan.md increment 3.

    **A deliberate widening, and the endpoint named its own trigger.**
    `lists.api_v1.pool`'s docstring said *session only. The phone has no pool
    surface, and widening a bearer to reach one before there is anything to
    reach would be the un-switched-on seam this project keeps finding.* That
    condition ends here: increment 3 gives the phone the surface, so the
    widening happens with the reason rather than ahead of it.

    **`agenda:read`, not a new scope.** The pool is what replaced the Agenda,
    `GET /api/v1/agenda` already takes exactly that scope, and a phone holding
    one of these tokens can already read every open task through it. A second
    scope naming the same material would be a distinction a person granting it
    could not act on.

    Read-only. Rule 8's *still wanted?* and everything else that writes to the
    pool stays session-only until a surface on the phone needs it.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.client = Client(enforce_csrf_checks=True)

    def get(self, token=None, query=""):
        extra = {}
        if token is not None:
            extra["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return self.client.get(f"/api/v1/pool{query}", **extra)

    def test_a_token_with_agenda_read_reaches_the_pool(self):
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=[SCOPE_AGENDA_READ]
        )

        response = self.get(token=raw)

        self.assertEqual(response.status_code, 200)
        # `fixed` and `floating` rather than one list -- the pool keeps
        # appointments and bills apart from tasks, and a client that merged
        # them would lose the distinction the split exists for.
        self.assertIn("floating", response.json())
        self.assertIn("open_count", response.json())

    def test_a_token_without_agenda_read_is_refused(self):
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=[SCOPE_AGENDA_WRITE]
        )

        self.assertEqual(self.get(token=raw).status_code, 401)

    def test_no_token_and_no_session_is_refused(self):
        self.assertEqual(self.get().status_code, 401)

    def test_a_token_sees_only_its_owners_pool(self):
        other = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        Item.objects.create(owner=other, text="Bob's loose end")
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=[SCOPE_AGENDA_READ]
        )

        rows = self.get(token=raw).json()["floating"]

        self.assertNotIn(
            "Bob's loose end",
            [(row.get("task") or {}).get("text") for row in rows],
        )

    def test_the_head_of_the_pool_is_reachable_too(self):
        """`head=true` is the panel beside the day rather than the page, and a
        phone wants that shape more than a browser does."""
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=[SCOPE_AGENDA_READ]
        )

        self.assertEqual(self.get(token=raw, query="?head=true").status_code, 200)

    def test_answering_the_pools_question_still_needs_a_session(self):
        """Read-only, and this is the assertion that keeps it that way. A
        bearer sits in a keystore for ninety days; letting one let go of a task
        is a different decision from letting one read the list."""
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=[SCOPE_AGENDA_READ]
        )
        task = Item.objects.create(owner=self.user, text="A loose end")

        response = self.client.post(
            f"/api/v1/pool/{task.id}/still-wanted",
            data=json.dumps({"answer": "keep"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {raw}",
        )

        # 403 rather than 401, and the difference is an artifact of *which*
        # auth refused: a session-only operation never consults the bearer at
        # all, so the request falls through to the cookie auth and fails its
        # CSRF check. Both mean refused; asserting the pair rather than one
        # keeps this about the refusal instead of about the mechanism.
        self.assertIn(response.status_code, (401, 403))
