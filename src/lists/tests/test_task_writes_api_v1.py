"""Task writes on `/api/v1/`, typed — coherence-audit-2026-08-30.md F2.

**What this replaces and why it is worth a file of its own.** `/api/v1/` carried
exactly one task endpoint, `GET /tasks/{item_id}`, while every write went
through `lists.api`'s hand-rolled Django views and an untyped hand-written
client. So `dump_openapi_schema` → `generate:api` → `tsc --noEmit`, the chain
`CLAUDE.md` describes for keeping the SPA honest, covered Money completely and
the noun the application is named for not at all.

**Three deliberate differences from the views these replace**, each a shape the
rest of `/api/v1/` already uses:

- **A resource comes back, not a `{"data": ...}` envelope.** The one exception
  is `PATCH`, which returns `TaskUpdateOut` — a *named* result, because
  completing a recurring task really does produce a second task in the same
  request and pretending otherwise would hide it.
- **Errors are Ninja's `{"detail": "..."}`.** Nothing in the SPA ever read the
  field-keyed `{"errors": {...}}` shape: `api.ts`'s `firstError` collapsed it to
  one string and every caller printed `caught.message`.
- **Session-only is expressed in the auth list rather than checked at runtime.**
  `DELETE` and reorder simply do not list `TokenAuth`, where the old view
  answered 403 after authenticating.

**The old views are not deleted by this**, and `lists/api.py` says why: the
shipped Android build calls them and cannot be updated without a keystore that
does not exist.
"""
import json

from django.test import Client, TestCase

from accounts.models import SCOPE_AGENDA_WRITE, PersonalAccessToken, User
from lists import services
from lists.models import CadenceMode, Item, List, Priority


class TaskWriteApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other_user = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.area = List.objects.create(owner=self.user, title="Programming")
        self.other_area = List.objects.create(owner=self.other_user, title="Bob's")
        self.task = Item.objects.create(list=self.area, text="Write tests")
        self.client.force_login(self.user)

    def patch(self, task_id, payload):
        return self.client.patch(
            f"/api/v1/tasks/{task_id}",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def post(self, url, payload=None):
        return self.client.post(
            url, data=json.dumps(payload or {}), content_type="application/json"
        )

    # -- creating -------------------------------------------------------

    def test_creates_a_task_in_one_of_your_own_areas(self):
        response = self.post(f"/api/v1/areas/{self.area.id}/tasks", {"text": "Build it"})

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["text"], "Build it")
        self.assertEqual(body["status"], Item.Status.ACTIVE)
        self.assertEqual(body["area_id"], self.area.id)

    def test_creating_carries_a_due_date_tags_and_a_recurrence(self):
        response = self.post(
            f"/api/v1/areas/{self.area.id}/tasks",
            {
                "text": "Pay rent",
                "due_date": "2026-09-01",
                "tags": ["money"],
                "recurrence": "monthly",
            },
        )

        body = response.json()
        self.assertEqual(body["due_date"], "2026-09-01")
        self.assertEqual(body["tags"], ["money"])
        self.assertEqual(body["recurrence"], "monthly")

    def test_refuses_an_unparseable_due_date(self):
        response = self.post(
            f"/api/v1/areas/{self.area.id}/tasks",
            {"text": "Pay rent", "due_date": "the first"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Item.objects.filter(text="Pay rent").exists())

    def test_refuses_an_empty_task(self):
        response = self.post(f"/api/v1/areas/{self.area.id}/tasks", {"text": "   "})

        self.assertEqual(response.status_code, 400)

    def test_cannot_create_in_somebody_elses_area(self):
        response = self.post(
            f"/api/v1/areas/{self.other_area.id}/tasks", {"text": "Trespass"}
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Item.objects.filter(text="Trespass").exists())

    # -- editing, one field per request ---------------------------------

    def test_edits_the_text(self):
        response = self.patch(self.task.id, {"text": "Write better tests"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["task"]["text"], "Write better tests")

    def test_sets_and_clears_a_due_date(self):
        self.patch(self.task.id, {"due_date": "2026-09-02"})
        cleared = self.patch(self.task.id, {"due_date": None})

        self.assertIsNone(cleared.json()["task"]["due_date"])

    def test_moves_a_task_into_another_of_your_own_areas(self):
        destination = List.objects.create(owner=self.user, title="Home")

        response = self.patch(self.task.id, {"area_id": destination.id})

        self.assertEqual(response.json()["task"]["area_id"], destination.id)

    def test_unfiling_is_a_move_rather_than_an_error(self):
        response = self.patch(self.task.id, {"area_id": None})

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["task"]["area_id"])

    def test_refuses_a_move_into_somebody_elses_area(self):
        response = self.patch(self.task.id, {"area_id": self.other_area.id})

        self.assertEqual(response.status_code, 404)
        self.task.refresh_from_db()
        self.assertEqual(self.task.list_id, self.area.id)

    def test_sets_priority_notes_tags_and_lead_days(self):
        self.assertEqual(
            self.patch(self.task.id, {"priority": Priority.HIGH}).json()["task"][
                "priority"
            ],
            Priority.HIGH,
        )
        self.assertEqual(
            self.patch(self.task.id, {"notes": "Ask first"}).json()["task"]["notes"],
            "Ask first",
        )
        self.assertEqual(
            self.patch(self.task.id, {"tags": ["home"]}).json()["task"]["tags"],
            ["home"],
        )
        self.assertEqual(
            self.patch(self.task.id, {"lead_days": 3}).json()["task"]["lead_days"], 3
        )

    def test_refuses_an_unknown_priority(self):
        # 422, not the old view's hand-rolled 400: `TaskPriority` is a Literal,
        # so pydantic refuses it at the boundary and the allowed values appear
        # in the published schema where a generated client can see them.
        response = self.patch(self.task.id, {"priority": "urgent-ish"})

        self.assertEqual(response.status_code, 422)

    def test_refuses_negative_lead_days(self):
        response = self.patch(self.task.id, {"lead_days": -1})

        self.assertEqual(response.status_code, 400)

    def test_sets_a_cadence_mode_without_touching_the_cadence(self):
        self.patch(self.task.id, {"recurrence": "monthly"})

        response = self.patch(self.task.id, {"cadence_mode": CadenceMode.FLOATING})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["task"]["recurrence"], "monthly")

    def test_refuses_an_unknown_cadence_mode(self):
        # A Literal too -- see test_refuses_an_unknown_priority.
        response = self.patch(self.task.id, {"cadence_mode": "whenever"})

        self.assertEqual(response.status_code, 422)

    def test_refuses_a_negative_bill(self):
        response = self.patch(self.task.id, {"bill": {"amount": "-1"}})

        self.assertEqual(response.status_code, 400)

    def test_refuses_an_unparseable_amount(self):
        response = self.patch(self.task.id, {"bill": {"amount": "twelve"}})

        self.assertEqual(response.status_code, 400)

    def test_requires_exactly_one_field(self):
        """The discipline the old view ran on, kept deliberately.

        Two fields is ambiguous about ordering and about which failure rolls
        back which change; zero fields is a request that means nothing.
        """
        two = self.patch(self.task.id, {"text": "One", "notes": "Two"})
        none = self.patch(self.task.id, {})

        self.assertEqual(two.status_code, 400)
        self.assertEqual(none.status_code, 400)
        self.task.refresh_from_db()
        self.assertEqual(self.task.text, "Write tests")

    # -- status, and the successor a completion can produce ---------------

    def test_completes_and_reopens(self):
        completed = self.patch(self.task.id, {"status": Item.Status.COMPLETED})
        self.assertEqual(completed.json()["task"]["status"], Item.Status.COMPLETED)

        reopened = self.patch(self.task.id, {"status": Item.Status.ACTIVE})
        self.assertEqual(reopened.json()["task"]["status"], Item.Status.ACTIVE)

    def test_completing_a_recurring_task_returns_its_successor(self):
        """The one reason PATCH returns a named result rather than the task.

        A completion can create a second task, and the Agenda shows it without
        refetching. Dropping it to return a bare TaskOut would be a silent
        regression that no type would catch.
        """
        repeating = Item.objects.create(
            list=self.area,
            text="Pay rent",
            due_date="2026-09-01",
            recurrence=Item.Recurrence.MONTHLY,
        )

        response = self.patch(repeating.id, {"status": Item.Status.COMPLETED})

        body = response.json()
        self.assertIsNotNone(body["spawned"])
        self.assertEqual(body["spawned"]["text"], "Pay rent")
        self.assertEqual(body["spawned"]["due_date"], "2026-10-01")
        self.assertEqual(body["spawned_checklist_steps"], [])

    def test_an_ordinary_completion_spawns_nothing(self):
        body = self.patch(self.task.id, {"status": Item.Status.COMPLETED}).json()

        self.assertIsNone(body["spawned"])
        self.assertEqual(body["spawned_checklist_steps"], [])

    def test_refuses_an_unknown_status(self):
        # A Literal too -- see test_refuses_an_unknown_priority.
        response = self.patch(self.task.id, {"status": "nearly"})

        self.assertEqual(response.status_code, 422)

    # -- deleting ---------------------------------------------------------

    def test_deletes_an_archived_task(self):
        self.patch(self.task.id, {"status": Item.Status.ARCHIVED})

        response = self.client.delete(f"/api/v1/tasks/{self.task.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted": self.task.id})
        self.assertFalse(Item.objects.filter(pk=self.task.id).exists())

    def test_refuses_to_delete_a_task_that_is_not_archived(self):
        response = self.client.delete(f"/api/v1/tasks/{self.task.id}")

        self.assertEqual(response.status_code, 400)
        self.assertTrue(Item.objects.filter(pk=self.task.id).exists())

    # -- reordering -------------------------------------------------------

    def test_reorders_an_area(self):
        second = Item.objects.create(list=self.area, text="Second")

        response = self.post(
            f"/api/v1/areas/{self.area.id}/tasks/reorder",
            {"ordered_ids": [second.id, self.task.id]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([each["id"] for each in response.json()], [second.id, self.task.id])

    def test_reorder_refuses_a_set_that_is_not_the_area(self):
        response = self.post(
            f"/api/v1/areas/{self.area.id}/tasks/reorder", {"ordered_ids": [self.task.id, 9999]}
        )

        self.assertEqual(response.status_code, 400)

    # -- ownership --------------------------------------------------------

    def test_somebody_elses_task_is_not_found_rather_than_forbidden(self):
        theirs = Item.objects.create(list=self.other_area, text="Private")

        self.assertEqual(self.patch(theirs.id, {"text": "Mine now"}).status_code, 404)
        self.assertEqual(
            self.client.delete(f"/api/v1/tasks/{theirs.id}").status_code, 404
        )
        theirs.refresh_from_db()
        self.assertEqual(theirs.text, "Private")

    def test_anonymous_requests_are_refused(self):
        self.client.logout()

        self.assertEqual(self.patch(self.task.id, {"text": "Hi"}).status_code, 401)
        self.assertEqual(
            self.post(f"/api/v1/areas/{self.area.id}/tasks", {"text": "Hi"}).status_code,
            401,
        )


class TaskWriteTokenAuthTest(TestCase):
    """What a connected phone may do, and what it may not.

    The old view authenticated a token and *then* answered 403 for anything
    outside `_TOKEN_ALLOWED_FIELDS`. Here the narrow surface is the auth list:
    delete and reorder do not accept a token at all, so the refusal is a plain
    401 from Ninja rather than a runtime branch. The field restriction survives
    as a check, because it is genuinely about the body rather than the route.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.area = List.objects.create(owner=self.user, title="Programming")
        self.task = Item.objects.create(list=self.area, text="Write tests")
        _, self.raw = PersonalAccessToken.generate(
            self.user, scopes=[SCOPE_AGENDA_WRITE]
        )
        # enforce_csrf_checks so a token request proves it needs no cookie.
        self.client = Client(enforce_csrf_checks=True)

    def send(self, method, url, payload=None):
        return getattr(self.client, method)(
            url,
            data=json.dumps(payload or {}),
            content_type="application/json",
            headers={"authorization": f"Bearer {self.raw}"},
        )

    def test_a_phone_may_create_a_task(self):
        response = self.send(
            "post", f"/api/v1/areas/{self.area.id}/tasks", {"text": "From the phone"}
        )

        self.assertEqual(response.status_code, 201)

    def test_a_phone_may_complete_and_reschedule(self):
        self.assertEqual(
            self.send("patch", f"/api/v1/tasks/{self.task.id}", {"due_date": "2026-09-09"}).status_code,
            200,
        )
        self.assertEqual(
            self.send("patch", f"/api/v1/tasks/{self.task.id}", {"status": "completed"}).status_code,
            200,
        )

    def test_a_phone_may_not_edit_anything_else(self):
        response = self.send("patch", f"/api/v1/tasks/{self.task.id}", {"text": "Renamed"})

        self.assertEqual(response.status_code, 403)
        self.task.refresh_from_db()
        self.assertEqual(self.task.text, "Write tests")

    def test_a_phone_cannot_delete(self):
        # Not listed in the operation's auth at all, so this is 401 rather
        # than the old view's authenticated-then-refused 403.
        response = self.client.delete(
            f"/api/v1/tasks/{self.task.id}",
            headers={"authorization": f"Bearer {self.raw}"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertTrue(Item.objects.filter(pk=self.task.id).exists())

    def test_a_phone_cannot_reorder(self):
        response = self.send(
            "post",
            f"/api/v1/areas/{self.area.id}/tasks/reorder",
            {"ordered_ids": [self.task.id]},
        )

        self.assertEqual(response.status_code, 401)


class ArchivedTaskDetailTest(TestCase):
    """An archived task has a page — coherence-audit-2026-08-30.md F3.

    **It had none until August 30, 2026**, and that was the sharp end of F3:
    `GET /tasks/{id}` matched `edit_item`'s queryset, which excluded archived
    tasks, so the only surface that could show a task's notes, checklist and
    schedule refused to show an archived one at all. The Archive listed it and
    could delete it; nothing could read it.

    **Delete stays a two-step and the domain is unchanged.** `services` refuses
    every edit on an archived task with *"Restore this task before editing
    it"*, and `delete_archived_item` refuses anything not archived. What moved
    is where the two steps can be taken from, not what they are.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.area = List.objects.create(owner=self.user, title="Programming")
        self.task = Item.objects.create(list=self.area, text="Write tests")
        self.client.force_login(self.user)
        self.client.patch(
            f"/api/v1/tasks/{self.task.id}",
            data=json.dumps({"status": Item.Status.ARCHIVED}),
            content_type="application/json",
        )

    def test_an_archived_task_has_a_detail_page(self):
        response = self.client.get(f"/api/v1/tasks/{self.task.id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["task"]["text"], "Write tests")
        self.assertEqual(payload["task"]["status"], Item.Status.ARCHIVED)

    def test_it_carries_everything_an_active_task_does(self):
        payload = self.client.get(f"/api/v1/tasks/{self.task.id}").json()

        # The point of showing it at all: the record is readable.
        self.assertIn("checklist_steps", payload)
        self.assertIn("notes", payload["task"])
        self.assertEqual(payload["area"]["title"], "Programming")

    def test_editing_it_is_still_refused_by_the_domain(self):
        response = self.client.patch(
            f"/api/v1/tasks/{self.task.id}",
            data=json.dumps({"text": "Renamed while archived"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Restore this task", response.json()["detail"])

    def test_it_can_be_restored_and_then_deleted_from_its_own_page(self):
        restored = self.client.patch(
            f"/api/v1/tasks/{self.task.id}",
            data=json.dumps({"status": Item.Status.COMPLETED}),
            content_type="application/json",
        )
        self.assertEqual(restored.status_code, 200)

        # And an unarchived task still cannot be deleted -- the two-step is
        # the protection, and it is unchanged.
        refused = self.client.delete(f"/api/v1/tasks/{self.task.id}")
        self.assertEqual(refused.status_code, 400)
        self.assertTrue(Item.objects.filter(pk=self.task.id).exists())

    def test_deleting_it_while_archived_succeeds(self):
        response = self.client.delete(f"/api/v1/tasks/{self.task.id}")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Item.objects.filter(pk=self.task.id).exists())

    def test_somebody_elses_archived_task_is_still_not_found(self):
        other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        # Archived through the service, not by setting the column: the
        # `valid_item_status_timestamps` constraint refuses a status without
        # the timestamps that explain it, and it is right to.
        theirs = Item.objects.create(
            list=List.objects.create(owner=other, title="Bob's"), text="Private"
        )
        services.archive_item(theirs)

        self.assertEqual(
            self.client.get(f"/api/v1/tasks/{theirs.id}").status_code, 404
        )
