"""An unfiled task can be listed and opened, not just created.

`Item.list` became nullable so a commitment accepted from the knowledge core
would not have to answer a filing question first. `test_a_task_without_an_area`
proves such a task can be *written*. Nothing proved it could be read back, and
it could not: two serializers reach through `item.list` without a guard.

`serialize_item` is the severe one. It runs for every task in the agenda
payload, so a single unfiled task did not degrade its own row — it raised, and
took the entire agenda with it. Accepting one commitment was enough to make the
main page of the application 500 for that person until somebody filed the task
by hand.

Found by asking what a person would actually do after tapping "Add to tasks",
rather than by anything failing: the write path is covered, the read path was
not, and a nullable column is only half-introduced until both are.
"""

from django.test import TestCase

from accounts.models import User
from lists import services
from lists.models import Item, List


class UnfiledTaskIsReadableTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "a@example.com", "pw")
        self.client.force_login(self.user)
        # A filed task alongside it, so these prove the unfiled one is handled
        # rather than that the page happens to be empty.
        self.area = List.objects.create(owner=self.user, title="Home")
        services.create_item(self.area, "Wash the car")
        self.unfiled = services.create_item(
            None, "Dentist on the 24th", owner=self.user
        )

    def test_the_agenda_still_loads(self):
        """The whole page, not one row. `serialize_item` is called for every
        task in the payload, so one unfiled task raising takes all of them."""
        response = self.client.get("/api/v1/agenda")

        self.assertEqual(response.status_code, 200)

    def test_the_agenda_includes_it(self):
        response = self.client.get("/api/v1/agenda")

        texts = [task["text"] for task in response.json()["items"]]
        self.assertIn("Dentist on the 24th", texts)

    def test_it_reports_no_area_rather_than_omitting_the_field(self):
        """`area_id: null` is a task that is unfiled. A missing key would make
        the client guess, and guessing is how a filed task and an unfiled one
        end up rendered the same."""
        response = self.client.get("/api/v1/agenda")

        task = next(
            task
            for task in response.json()["items"]
            if task["text"] == "Dentist on the 24th"
        )
        self.assertIsNone(task["area_id"])
        self.assertIsNone(task["project_id"])

    def test_it_can_be_opened(self):
        """What somebody does immediately after accepting a commitment: tap it."""
        response = self.client.get(f"/api/v1/tasks/{self.unfiled.id}")

        self.assertEqual(response.status_code, 200)

    def test_its_detail_says_it_has_no_area(self):
        response = self.client.get(f"/api/v1/tasks/{self.unfiled.id}")

        self.assertIsNone(response.json()["area"])

    def test_a_filed_task_still_reports_its_area(self):
        """The regression guard. Making `area` nullable must not quietly make it
        absent for the tasks that have one."""
        filed = Item.objects.get(text="Wash the car")

        response = self.client.get(f"/api/v1/tasks/{filed.id}")

        self.assertEqual(response.json()["area"]["title"], "Home")

    def test_the_archive_still_loads_with_an_unfiled_task_in_it(self):
        services.archive_item(services.complete_item(self.unfiled))

        response = self.client.get("/api/v1/archive")

        self.assertEqual(response.status_code, 200)
