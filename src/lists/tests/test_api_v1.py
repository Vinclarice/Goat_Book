import json
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from capture.models import Capture
from lists import agenda as agenda_reader
from lists import services as list_services
from lists.models import Item, List, Project


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
        self.assertEqual(len(payload["areas"]), 1)
        self.assertEqual(payload["areas"][0]["title"], "Programming")

    def test_assigns_a_deterministic_semantic_color_key(self):
        self.client.force_login(self.user)

        payload = self.client.get("/api/v1/agenda").json()

        self.assertEqual(
            payload["areas"][0]["color_key"],
            agenda_reader.color_key_for_list(self.list_.id),
        )

    def test_carries_the_caller_s_projects_so_a_task_row_can_show_its_own(self):
        """ui-second-pass-plan.md F2: a task's project is invisible on the
        Agenda because the payload never carried one. This is the fix's
        server half -- each project, now with its own url --
        project-workspace-plan.md closes the "no page of its own yet" gap.
        """
        project = Project.objects.create(owner=self.user, title="Kitchen remodel")
        Project.objects.create(owner=self.other_user, title="Not mine")
        self.client.force_login(self.user)

        payload = self.client.get("/api/v1/agenda").json()

        self.assertEqual(len(payload["projects"]), 1)
        self.assertEqual(payload["projects"][0]["title"], "Kitchen remodel")
        self.assertEqual(payload["projects"][0]["url"], f"/app/projects/{project.id}")


class AreaDetailEndpointTest(TestCase):
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
        response = self.client.get(f"/api/v1/areas/{self.list_.id}")

        self.assertEqual(response.status_code, 401)

    def test_404s_an_area_owned_by_someone_else(self):
        self.client.force_login(self.user)

        response = self.client.get(f"/api/v1/areas/{self.other_list.id}")

        self.assertEqual(response.status_code, 404)

    def test_returns_the_area_and_its_open_items(self):
        self.client.force_login(self.user)

        response = self.client.get(f"/api/v1/areas/{self.list_.id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["area"]["title"], "Programming")
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["text"], "Write tests")

    def test_carries_this_area_s_own_project_so_a_row_can_show_it(self):
        """project-workspace-plan.md 2: singular now, not a list -- an Area
        belongs to at most one Project. Scoped to this area only, unlike the
        Agenda/Daily/Archive join.
        """
        project = Project.objects.create(owner=self.user, title="Kitchen remodel")
        list_services.add_area_to_project(self.list_, project)
        self.client.force_login(self.user)

        payload = self.client.get(f"/api/v1/areas/{self.list_.id}").json()

        self.assertEqual(payload["project"]["title"], "Kitchen remodel")
        self.assertEqual(payload["project"]["url"], f"/app/projects/{project.id}")

    def test_no_project_section_when_the_area_is_not_in_one(self):
        self.client.force_login(self.user)

        payload = self.client.get(f"/api/v1/areas/{self.list_.id}").json()

        self.assertIsNone(payload["project"])

    def test_renames_the_area(self):
        self.client.force_login(self.user)

        response = self.client.patch(
            f"/api/v1/areas/{self.list_.id}",
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
            f"/api/v1/areas/{self.list_.id}",
            data=json.dumps({"title": "   "}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.list_.refresh_from_db()
        self.assertEqual(self.list_.title, "Programming")

    def test_cannot_rename_someone_else_s_area(self):
        self.client.force_login(self.user)

        response = self.client.patch(
            f"/api/v1/areas/{self.other_list.id}",
            data=json.dumps({"title": "Hijacked"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_deletes_the_area_and_its_items(self):
        self.client.force_login(self.user)

        response = self.client.delete(f"/api/v1/areas/{self.list_.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted": self.list_.id})
        self.assertFalse(List.objects.filter(id=self.list_.id).exists())

    def test_cannot_delete_someone_else_s_area(self):
        self.client.force_login(self.user)

        response = self.client.delete(f"/api/v1/areas/{self.other_list.id}")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(List.objects.filter(id=self.other_list.id).exists())


class ArchiveEndpointTest(TestCase):
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
            status=Item.Status.ACTIVE,
        )
        Item.objects.create(
            list=self.list_,
            text="Old task",
            status=Item.Status.ARCHIVED,
            completed_at=timezone.now(),
            archived_at=timezone.now(),
        )
        Item.objects.create(
            list=self.other_user.lists.create(title="Bob's list"),
            text="Not mine",
            status=Item.Status.ARCHIVED,
            completed_at=timezone.now(),
            archived_at=timezone.now(),
        )

    def test_rejects_anonymous_requests(self):
        response = self.client.get("/api/v1/archive")

        self.assertEqual(response.status_code, 401)

    def test_returns_only_the_caller_s_archived_items(self):
        self.client.force_login(self.user)

        response = self.client.get("/api/v1/archive")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["text"], "Old task")
        self.assertEqual(len(payload["areas"]), 1)
        self.assertEqual(payload["areas"][0]["title"], "Programming")

    def test_carries_the_caller_s_projects_so_a_row_can_show_its_own(self):
        """ui-second-pass-plan.md F2's sitting found the Archive silent
        about a project the same way the Agenda and Daily Page were --
        the last of the three surfaces the sitting actually observed.
        """
        project = Project.objects.create(owner=self.user, title="Kitchen remodel")
        Project.objects.create(owner=self.other_user, title="Not mine")
        self.client.force_login(self.user)

        payload = self.client.get("/api/v1/archive").json()

        self.assertEqual(len(payload["projects"]), 1)
        self.assertEqual(payload["projects"][0]["title"], "Kitchen remodel")
        self.assertEqual(payload["projects"][0]["url"], f"/app/projects/{project.id}")


class TaskDetailEndpointTest(TestCase):
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
        self.other_item = Item.objects.create(
            list=self.other_user.lists.create(title="Bob's list"),
            text="Not mine",
        )
        self.archived_item = Item.objects.create(
            list=self.list_,
            text="Old task",
            status=Item.Status.ARCHIVED,
            completed_at=timezone.now(),
            archived_at=timezone.now(),
        )

    def test_rejects_anonymous_requests(self):
        response = self.client.get(f"/api/v1/tasks/{self.item.id}")

        self.assertEqual(response.status_code, 401)

    def test_returns_the_task_and_its_area(self):
        self.client.force_login(self.user)

        response = self.client.get(f"/api/v1/tasks/{self.item.id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["task"]["text"], "Write tests")
        self.assertEqual(payload["area"]["title"], "Programming")

    def test_404s_a_task_owned_by_someone_else(self):
        self.client.force_login(self.user)

        response = self.client.get(f"/api/v1/tasks/{self.other_item.id}")

        self.assertEqual(response.status_code, 404)

    def test_404s_an_archived_task(self):
        """Archived tasks are managed from the Archive route instead."""
        self.client.force_login(self.user)

        response = self.client.get(f"/api/v1/tasks/{self.archived_item.id}")

        self.assertEqual(response.status_code, 404)


class NavEndpointTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.list_ = List.objects.create(owner=self.user, title="Programming")
        Item.objects.create(
            list=self.list_,
            text="Overdue thing",
            due_date=timezone.localdate() - timedelta(days=1),
        )
        Item.objects.create(list=self.list_, text="Open thing")
        Item.objects.create(
            list=self.list_,
            text="Archived thing",
            status=Item.Status.ARCHIVED,
            archived_at=timezone.now(),
        )
        Capture.objects.create(owner=self.user, text="A stray thought")
        Capture.objects.create(
            owner=self.user, text="Dealt with", resolved_at=timezone.now()
        )

        # Another user's everything, none of which may appear below.
        others = List.objects.create(owner=self.other, title="Bob's list")
        Item.objects.create(list=others, text="Not mine")
        Capture.objects.create(owner=self.other, text="Bob's thought")

    def test_rejects_anonymous_requests(self):
        response = self.client.get("/api/v1/nav")

        self.assertEqual(response.status_code, 401)

    def test_returns_areas_with_counts_for_the_caller_only(self):
        self.client.force_login(self.user)

        body = self.client.get("/api/v1/nav").json()

        self.assertEqual([each["title"] for each in body["areas"]], ["Programming"])
        self.assertEqual(body["areas"][0]["open_count"], 2)
        self.assertEqual(body["areas"][0]["overdue_count"], 1)

    def test_carries_the_caller_s_open_projects_for_f3s_own_nav_group(self):
        """ui-second-pass-plan.md F3: Vince's call was a top-level Projects
        group, flat across areas. Completed projects are left out -- this
        group is about ongoing work, the same reason the Agenda doesn't
        list completed tasks, and a project has a completion state an Area
        never does.
        """
        Project.objects.create(owner=self.user, title="Kitchen remodel")
        done = Project.objects.create(owner=self.user, title="Finished already")
        list_services.complete_project(done)
        Project.objects.create(owner=self.other, title="Not mine")
        self.client.force_login(self.user)

        body = self.client.get("/api/v1/nav").json()

        self.assertEqual(len(body["projects"]), 1)
        self.assertEqual(body["projects"][0]["title"], "Kitchen remodel")
        self.assertIn("open_task_count", body["projects"][0])

    def test_counts_the_archive_and_the_unresolved_inbox(self):
        self.client.force_login(self.user)

        body = self.client.get("/api/v1/nav").json()

        self.assertEqual(body["archived_count"], 1)
        # Only the unresolved one, and only this user's.
        self.assertEqual(body["inbox_count"], 1)

    def test_carries_the_links_that_leave_the_spa(self):
        self.client.force_login(self.user)

        body = self.client.get("/api/v1/nav").json()

        self.assertEqual(body["inbox_url"], "/capture/")
        self.assertTrue(body["settings_url"].startswith("/accounts/"))
