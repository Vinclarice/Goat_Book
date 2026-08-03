"""The HTTP contract for Projects -- release-d-plan.md 5 slice 7.

Model and service behaviour is in test_projects.py; this file is only about
what a client can see and do. Every owner-scoped, ID-taking route below gets
a direct isolation case, per principles.md.
"""
import json

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from lists.models import Item, List, Project
from lists import services


class ProjectEndpointTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.area = List.objects.create(owner=self.user, title="Work")
        self.their_area = List.objects.create(owner=self.other, title="Theirs")
        self.client.force_login(self.user)

    def post(self, path, body):
        return self.client.post(
            path, data=json.dumps(body), content_type="application/json",
        )

    def patch(self, path, body):
        return self.client.patch(
            path, data=json.dumps(body), content_type="application/json",
        )

    def test_rejects_anonymous_requests(self):
        self.client.logout()

        self.assertEqual(self.client.get("/api/v1/projects").status_code, 401)

    def test_creates_a_project_in_an_owned_area(self):
        response = self.post(
            "/api/v1/projects",
            {"area_id": self.area.id, "title": "Website Relaunch",
             "due_date": "2026-09-30"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["title"], "Website Relaunch")
        self.assertEqual(body["area_id"], self.area.id)
        self.assertEqual(body["due_date"], "2026-09-30")
        self.assertFalse(body["is_completed"])
        self.assertEqual(body["open_task_count"], 0)

    def test_rejects_a_blank_title(self):
        response = self.post(
            "/api/v1/projects", {"area_id": self.area.id, "title": "   "},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(Project.objects.count(), 0)

    def test_cannot_create_a_project_in_someone_else_s_area(self):
        response = self.post(
            "/api/v1/projects",
            {"area_id": self.their_area.id, "title": "Hijacked"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Project.objects.count(), 0)

    def test_lists_only_the_caller_s_projects_with_their_open_counts(self):
        mine = services.create_project(self.area, "Website Relaunch")
        Item.objects.create(list=self.area, text="Open one", project=mine)
        services.create_project(self.their_area, "Not mine")

        body = self.client.get("/api/v1/projects").json()

        self.assertEqual([each["title"] for each in body], ["Website Relaunch"])
        self.assertEqual(body[0]["open_task_count"], 1)

    def test_narrows_to_one_area_when_asked(self):
        """The Area page's actual query -- slice 8.

        Filtering client-side would work at three users and stop working
        quietly; the endpoint answering the question the page asks is the
        same reasoning charter rule 7 applies to indexes.
        """
        here = services.create_project(self.area, "Website Relaunch")
        elsewhere = List.objects.create(owner=self.user, title="Home")
        services.create_project(elsewhere, "Repaint the hallway")

        body = self.client.get(
            f"/api/v1/projects?area_id={self.area.id}"
        ).json()

        self.assertEqual([each["id"] for each in body], [here.id])

    def test_an_unowned_area_filter_returns_nothing_rather_than_everything(self):
        """A filter that silently fails open is worse than one that errors.

        Passing somebody else's area id must not fall back to "all my
        projects" -- that is the shape of bug where a narrowing parameter
        stops narrowing and nobody notices.
        """
        services.create_project(self.area, "Website Relaunch")

        body = self.client.get(
            f"/api/v1/projects?area_id={self.their_area.id}"
        ).json()

        self.assertEqual(body, [])

    def test_completes_and_reopens_a_project(self):
        project = services.create_project(self.area, "Website Relaunch")

        done = self.patch(
            f"/api/v1/projects/{project.id}", {"is_completed": True},
        )
        self.assertEqual(done.status_code, 200)
        self.assertTrue(done.json()["is_completed"])
        self.assertIsNotNone(done.json()["completed_at"])

        reopened = self.patch(
            f"/api/v1/projects/{project.id}", {"is_completed": False},
        )
        self.assertEqual(reopened.status_code, 200)
        self.assertFalse(reopened.json()["is_completed"])
        self.assertIsNone(reopened.json()["completed_at"])

    def test_renames_a_project_and_moves_its_due_date(self):
        project = services.create_project(self.area, "Website Relaunch")

        response = self.patch(
            f"/api/v1/projects/{project.id}",
            {"title": "Website Relaunch v2", "due_date": "2026-10-15"},
        )

        self.assertEqual(response.status_code, 200)
        project.refresh_from_db()
        self.assertEqual(project.title, "Website Relaunch v2")
        self.assertEqual(project.due_date.isoformat(), "2026-10-15")

    def test_clears_a_due_date_with_an_explicit_null(self):
        project = services.create_project(
            self.area, "Website Relaunch", due_date="2026-09-30",
        )

        response = self.patch(
            f"/api/v1/projects/{project.id}", {"due_date": None},
        )

        self.assertEqual(response.status_code, 200)
        project.refresh_from_db()
        self.assertIsNone(project.due_date)

    def test_404s_a_project_owned_by_someone_else(self):
        theirs = services.create_project(self.their_area, "Not mine")

        self.assertEqual(
            self.patch(f"/api/v1/projects/{theirs.id}", {"title": "Hijacked"})
            .status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(f"/api/v1/projects/{theirs.id}").status_code, 404
        )
        theirs.refresh_from_db()
        self.assertEqual(theirs.title, "Not mine")

    def test_deletes_a_project_without_deleting_its_tasks(self):
        project = services.create_project(self.area, "Website Relaunch")
        task = Item.objects.create(
            list=self.area, text="Write the brief", project=project,
        )

        response = self.client.delete(f"/api/v1/projects/{project.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted": project.id})
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())
        task.refresh_from_db()
        self.assertIsNone(task.project_id)


class TaskProjectAssignmentApiTest(TestCase):
    """Assigning a task lives on the task's own endpoint, not the project's.

    Every other single-field task edit -- due date, tags, recurrence, notes --
    already goes through PATCH /api/items/{id}/, and putting this one
    somewhere else would mean two shapes for one kind of change.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.area = List.objects.create(owner=self.user, title="Work")
        self.task = Item.objects.create(list=self.area, text="Write the brief")
        self.project = services.create_project(self.area, "Website Relaunch")
        self.client.force_login(self.user)

    def patch_task(self, body):
        return self.client.patch(
            f"/api/items/{self.task.id}/",
            data=json.dumps(body),
            content_type="application/json",
        )

    def test_a_task_carries_its_project_in_every_payload(self):
        body = self.client.get(f"/api/v1/tasks/{self.task.id}").json()

        self.assertIsNone(body["task"]["project_id"])

    def test_puts_a_task_into_a_project_and_takes_it_out_again(self):
        joined = self.patch_task({"project_id": self.project.id})

        self.assertEqual(joined.status_code, 200)
        self.assertEqual(joined.json()["data"]["project_id"], self.project.id)

        removed = self.patch_task({"project_id": None})

        self.assertEqual(removed.status_code, 200)
        self.assertIsNone(removed.json()["data"]["project_id"])

    def test_404s_a_project_belonging_to_somebody_else(self):
        """404 here, though the service raises a conflict for the same case.

        Written expecting 409 to match the service, and corrected while
        implementing rather than the other way round: the API looks projects
        up owner-scoped, so a foreign id is simply not found, and answering
        409 would confirm that some other account owns that id. The service
        keeps raising TaskConflict because by then the caller already holds
        the object -- the two layers know different things.
        """
        theirs = services.create_project(
            List.objects.create(owner=self.other, title="Theirs"), "Not yours",
        )

        response = self.patch_task({"project_id": theirs.id})

        self.assertEqual(response.status_code, 404)
        self.task.refresh_from_db()
        self.assertIsNone(self.task.project_id)

    def test_409s_a_project_in_a_different_area(self):
        elsewhere = List.objects.create(owner=self.user, title="Home")
        project = services.create_project(elsewhere, "Repaint the hallway")

        response = self.patch_task({"project_id": project.id})

        self.assertEqual(response.status_code, 409)

    def test_404s_a_project_that_does_not_exist(self):
        response = self.patch_task({"project_id": 9999})

        self.assertEqual(response.status_code, 404)

    def test_still_refuses_two_changes_in_one_request(self):
        """The one-field rule the endpoint already enforces, extended.

        project_id joining the set would silently break that rule if it were
        added to the dispatch without being added to the guard.
        """
        response = self.patch_task(
            {"project_id": self.project.id, "text": "Renamed too"},
        )

        self.assertEqual(response.status_code, 400)
