import json

from django.test import Client, TestCase

from accounts.models import User
from lists.models import ChecklistStep, Item, List


class ChecklistStepApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password",
        )
        self.other_user = User.objects.create_user(
            "bob", "bob@example.com", "another secure password",
        )
        self.list_ = List.objects.create(owner=self.user, title="Travel")
        self.task = Item.objects.create(list=self.list_, text="Get the dog ready")
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
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

    def create_step(self, text="Refill medication", **extra):
        response = self.request(
            "post",
            f"/api/tasks/{self.task.id}/checklist-steps/",
            {"text": text, **extra},
        )
        return response.json()["data"]

    def test_create_a_checklist_step(self):
        response = self.request(
            "post",
            f"/api/tasks/{self.task.id}/checklist-steps/",
            {"text": "Refill medication"},
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["text"], "Refill medication")
        self.assertFalse(data["is_done"])
        self.assertTrue(data["carries_forward"])
        self.assertEqual(data["task_id"], self.task.id)

    def test_create_opted_out_of_carrying_forward(self):
        data = self.create_step("One-time errand", carries_forward=False)

        self.assertFalse(data["carries_forward"])

    def test_rejects_a_duplicate_open_step(self):
        self.create_step("Refill medication")

        response = self.request(
            "post",
            f"/api/tasks/{self.task.id}/checklist-steps/",
            {"text": "Refill medication"},
        )

        self.assertEqual(response.status_code, 400)

    def test_create_on_another_users_task_is_a_404(self):
        theirs = Item.objects.create(
            list=List.objects.create(owner=self.other_user), text="Not yours",
        )

        response = self.request(
            "post",
            f"/api/tasks/{theirs.id}/checklist-steps/",
            {"text": "Sneaky step"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(ChecklistStep.objects.count(), 0)

    def test_toggle_done_and_back(self):
        step = self.create_step()

        done_response = self.request("patch", step["url"], {"is_done": True})
        self.assertTrue(done_response.json()["data"]["is_done"])
        self.assertIsNotNone(done_response.json()["data"]["completed_at"])

        undone_response = self.request("patch", step["url"], {"is_done": False})
        self.assertFalse(undone_response.json()["data"]["is_done"])
        self.assertIsNone(undone_response.json()["data"]["completed_at"])

    def test_toggle_carries_forward(self):
        step = self.create_step()

        response = self.request(
            "patch", step["url"], {"carries_forward": False},
        )

        self.assertFalse(response.json()["data"]["carries_forward"])

    def test_rename_a_step(self):
        step = self.create_step("Refil medicaton")

        response = self.request(
            "patch", step["url"], {"text": "Refill medication"},
        )

        self.assertEqual(response.json()["data"]["text"], "Refill medication")

    def test_one_field_per_request_is_enforced(self):
        step = self.create_step()

        response = self.request(
            "patch", step["url"], {"is_done": True, "carries_forward": False},
        )

        self.assertEqual(response.status_code, 400)

    def test_delete_a_step(self):
        step = self.create_step()

        response = self.request("delete", step["url"])

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ChecklistStep.objects.filter(id=step["id"]).exists())

    def test_another_users_step_is_a_404(self):
        theirs_list = List.objects.create(owner=self.other_user)
        theirs_task = Item.objects.create(list=theirs_list, text="Not yours")
        theirs = ChecklistStep.objects.create(
            owner=self.other_user, task=theirs_task, text="Not yours either",
        )

        response = self.request("patch", f"/api/checklist-steps/{theirs.id}/", {"is_done": True})

        self.assertEqual(response.status_code, 404)
        theirs.refresh_from_db()
        self.assertFalse(theirs.is_done)

    def test_reorder_steps(self):
        first = self.create_step("first")
        second = self.create_step("second")

        response = self.request(
            "post",
            f"/api/tasks/{self.task.id}/checklist-steps/reorder/",
            {"ordered_ids": [second["id"], first["id"]]},
        )

        self.assertEqual(response.status_code, 200)
        ordered = response.json()["data"]
        self.assertEqual([step["id"] for step in ordered], [second["id"], first["id"]])

    def test_reorder_rejects_a_mismatched_id_set(self):
        step = self.create_step()

        response = self.request(
            "post",
            f"/api/tasks/{self.task.id}/checklist-steps/reorder/",
            {"ordered_ids": [step["id"], 999999]},
        )

        self.assertEqual(response.status_code, 409)

    def test_promote_a_step(self):
        step = self.create_step("Book the kennel")

        response = self.request("post", step["promote_url"])

        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["text"], "Book the kennel")
        self.assertFalse(ChecklistStep.objects.filter(id=step["id"]).exists())

    def test_promote_conflicting_with_an_existing_task_returns_409(self):
        Item.objects.create(list=self.list_, text="Book the kennel")
        step = self.create_step("Book the kennel")

        response = self.request("post", step["promote_url"])

        self.assertEqual(response.status_code, 409)
        self.assertTrue(ChecklistStep.objects.filter(id=step["id"]).exists())

    def test_completing_a_recurring_task_reports_spawned_checklist_steps(self):
        recurring = Item.objects.create(
            list=self.list_, text="Weekly review", recurrence="weekly",
        )
        step_response = self.request(
            "post",
            f"/api/tasks/{recurring.id}/checklist-steps/",
            {"text": "Check inbox zero"},
        )
        self.assertEqual(step_response.status_code, 201)

        response = self.request(
            "patch",
            f"/api/items/{recurring.id}/",
            {"status": "completed"},
        )

        payload = response.json()
        self.assertIn("spawned_checklist_steps", payload)
        self.assertEqual(len(payload["spawned_checklist_steps"]), 1)
        self.assertEqual(
            payload["spawned_checklist_steps"][0]["text"], "Check inbox zero",
        )
        self.assertEqual(
            payload["spawned_checklist_steps"][0]["task_id"], payload["spawned"]["id"],
        )

    def test_completing_a_non_recurring_task_reports_no_spawned_checklist_steps(self):
        response = self.request(
            "patch",
            f"/api/items/{self.task.id}/",
            {"status": "completed"},
        )

        self.assertNotIn("spawned_checklist_steps", response.json())
