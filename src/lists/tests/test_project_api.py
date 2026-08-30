"""The HTTP contract for Projects -- project-workspace-plan.md.

Model and service behaviour is in test_projects.py; this file is only about
what a client can see and do. Every owner-scoped, ID-taking route below gets
a direct isolation case, per principles.md.
"""
import json
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from django.utils import timezone

from accounts.models import User
from lists.models import Item, List, Project
from lists import services
from mind import services as mind_services


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

    def test_creates_a_standalone_project(self):
        response = self.post(
            "/api/v1/projects",
            {"title": "Website Relaunch", "due_date": "2026-09-30"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["title"], "Website Relaunch")
        self.assertEqual(body["due_date"], "2026-09-30")
        self.assertFalse(body["is_completed"])
        self.assertEqual(body["open_task_count"], 0)
        self.assertEqual(body["areas"], [])

    def test_rejects_a_blank_title(self):
        response = self.post("/api/v1/projects", {"title": "   "})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(Project.objects.count(), 0)

    def test_lists_only_the_caller_s_projects_with_their_open_counts(self):
        mine = services.create_project(self.user, "Website Relaunch")
        services.add_area_to_project(self.area, mine)
        Item.objects.create(list=self.area, text="Open one")
        services.create_project(self.other, "Not mine")

        body = self.client.get("/api/v1/projects").json()

        self.assertEqual([each["title"] for each in body], ["Website Relaunch"])
        self.assertEqual(body[0]["open_task_count"], 1)
        self.assertEqual(
            [each["id"] for each in body[0]["areas"]], [self.area.id],
        )

    def test_reads_one_project_with_its_areas(self):
        project = services.create_project(self.user, "Website Relaunch")
        services.add_area_to_project(self.area, project)

        body = self.client.get(f"/api/v1/projects/{project.id}").json()

        self.assertEqual(body["title"], "Website Relaunch")
        self.assertEqual([each["title"] for each in body["areas"]], ["Work"])

    def test_404s_a_project_detail_owned_by_someone_else(self):
        theirs = services.create_project(self.other, "Not mine")

        response = self.client.get(f"/api/v1/projects/{theirs.id}")

        self.assertEqual(response.status_code, 404)

    def test_flags_a_past_due_project_as_overdue(self):
        # projects-mockup.html's signature addition: a due date in the past
        # should read differently than one still ahead, the same
        # ⚠-and-status-overdue-color treatment tasks and areas already get.
        services.create_project(
            self.user, "Late", due_date=timezone.localdate() - timedelta(days=1),
        )
        services.create_project(
            self.user, "On track", due_date=timezone.localdate() + timedelta(days=1),
        )
        services.create_project(self.user, "No deadline")

        body = self.client.get("/api/v1/projects").json()

        self.assertEqual(
            {each["title"]: each["is_overdue"] for each in body},
            {"Late": True, "On track": False, "No deadline": False},
        )

    def test_a_completed_project_is_never_overdue(self):
        project = services.create_project(
            self.user, "Late but done",
            due_date=timezone.localdate() - timedelta(days=1),
        )
        services.complete_project(project)

        body = self.client.get(f"/api/v1/projects/{project.id}").json()

        self.assertFalse(body["is_overdue"])

    def test_completes_and_reopens_a_project(self):
        project = services.create_project(self.user, "Website Relaunch")

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
        project = services.create_project(self.user, "Website Relaunch")

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
            self.user, "Website Relaunch", due_date="2026-09-30",
        )

        response = self.patch(
            f"/api/v1/projects/{project.id}", {"due_date": None},
        )

        self.assertEqual(response.status_code, 200)
        project.refresh_from_db()
        self.assertIsNone(project.due_date)

    def test_404s_a_project_owned_by_someone_else(self):
        theirs = services.create_project(self.other, "Not mine")

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

    def test_deletes_a_project_leaving_its_areas_in_place(self):
        project = services.create_project(self.user, "Website Relaunch")
        services.add_area_to_project(self.area, project)

        response = self.client.delete(f"/api/v1/projects/{project.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted": project.id})
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())
        self.area.refresh_from_db()
        self.assertIsNone(self.area.project)


class AreaProjectAssignmentApiTest(TestCase):
    """Putting an Area into a Project (or out again) -- project-workspace-plan.md 2."""

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.area = List.objects.create(owner=self.user, title="Work")
        self.project = services.create_project(self.user, "Website Relaunch")
        self.client.force_login(self.user)

    def patch_area(self, body):
        return self.client.patch(
            f"/api/v1/areas/{self.area.id}/project",
            data=json.dumps(body),
            content_type="application/json",
        )

    def test_puts_an_area_into_a_project_and_takes_it_out_again(self):
        joined = self.patch_area({"project_id": self.project.id})

        self.assertEqual(joined.status_code, 200)
        self.area.refresh_from_db()
        self.assertEqual(self.area.project_id, self.project.id)

        removed = self.patch_area({"project_id": None})

        self.assertEqual(removed.status_code, 200)
        self.area.refresh_from_db()
        self.assertIsNone(self.area.project_id)

    def test_404s_a_project_belonging_to_somebody_else(self):
        theirs = services.create_project(self.other, "Not yours")

        response = self.patch_area({"project_id": theirs.id})

        self.assertEqual(response.status_code, 404)
        self.area.refresh_from_db()
        self.assertIsNone(self.area.project_id)

    def test_404s_a_project_that_does_not_exist(self):
        response = self.patch_area({"project_id": 9999})

        self.assertEqual(response.status_code, 404)

    def test_cannot_assign_someone_elses_area(self):
        theirs = List.objects.create(owner=self.other, title="Theirs")

        response = self.client.patch(
            f"/api/v1/areas/{theirs.id}/project",
            data=json.dumps({"project_id": self.project.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)


class CreateAreaInProjectApiTest(TestCase):
    """A new, empty Area, created already inside a Project.

    Vince's call, August 10, 2026: the predominant use case for a project
    is areas that don't exist yet, not reassigning ones that do -- so this
    needs no first task, unlike the Agenda sidebar's own "+ New area".
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.project = services.create_project(self.user, "Website Relaunch")
        self.client.force_login(self.user)

    def post(self, project_id, body):
        return self.client.post(
            f"/api/v1/projects/{project_id}/areas",
            data=json.dumps(body),
            content_type="application/json",
        )

    def test_creates_an_empty_area_already_in_the_project(self):
        response = self.post(self.project.id, {"title": "Legal"})

        self.assertEqual(response.status_code, 200)
        area = List.objects.get(title="Legal")
        self.assertEqual(area.owner, self.user)
        self.assertEqual(area.project, self.project)
        self.assertEqual(list(area.item_set.all()), [])

    def test_404s_someone_elses_project(self):
        theirs = services.create_project(self.other, "Not yours")

        response = self.post(theirs.id, {"title": "Legal"})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(List.objects.filter(title="Legal").count(), 0)

    def test_404s_a_project_that_does_not_exist(self):
        response = self.post(9999, {"title": "Legal"})

        self.assertEqual(response.status_code, 404)


class TaskProjectDisplayApiTest(TestCase):
    """A task's project is derived through its Area now, read-only.

    project-workspace-plan.md 2 drops the task-level override
    (PATCH /api/v1/tasks/{id} no longer accepts project_id) -- a task belongs
    to a project only by belonging to an Area that's inside it.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.area = List.objects.create(owner=self.user, title="Work")
        self.task = Item.objects.create(list=self.area, text="Write the brief")
        self.project = services.create_project(self.user, "Website Relaunch")
        self.client.force_login(self.user)

    def test_a_task_has_no_project_until_its_area_joins_one(self):
        body = self.client.get(f"/api/v1/tasks/{self.task.id}").json()

        self.assertIsNone(body["task"]["project_id"])

    def test_a_task_carries_its_areas_project(self):
        services.add_area_to_project(self.area, self.project)

        body = self.client.get(f"/api/v1/tasks/{self.task.id}").json()

        self.assertEqual(body["task"]["project_id"], self.project.id)

    def test_project_id_is_no_longer_a_writable_task_field(self):
        response = self.client.patch(
            f"/api/v1/tasks/{self.task.id}",
            data=json.dumps({"project_id": self.project.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)


class ProjectPurposeEndpointTest(TestCase):
    """The HTTP half of S10's purpose field.

    Model and service behaviour is in test_projects.py, per this file's own
    split. What is here is what a client can read and write, plus the isolation
    case every owner-scoped, ID-taking route gets.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.client.force_login(self.user)

    def patch(self, path, body):
        return self.client.patch(
            path, data=json.dumps(body), content_type="application/json",
        )

    def post(self, path, body):
        return self.client.post(
            path, data=json.dumps(body), content_type="application/json",
        )

    def test_a_project_reports_its_purpose(self):
        project = services.create_project(
            self.user, "Website launch", purpose="Stop enquiries going to email.",
        )

        response = self.client.get(f"/api/v1/projects/{project.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["purpose"], "Stop enquiries going to email.")

    def test_a_project_without_one_reports_an_empty_string(self):
        """Never null over the wire.

        The client renders a text area either way, and a `None` it has to
        coerce is a second representation of "nothing written" reaching
        JavaScript -- exactly what blank-not-null exists to prevent.
        """
        project = services.create_project(self.user, "Website launch")

        response = self.client.get(f"/api/v1/projects/{project.id}")

        self.assertEqual(response.json()["purpose"], "")

    def test_a_project_can_be_created_with_a_purpose(self):
        response = self.post(
            "/api/v1/projects",
            {"title": "Website launch", "purpose": "Stop enquiries going to email."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["purpose"], "Stop enquiries going to email.")

    def test_a_purpose_can_be_written_after_the_fact(self):
        project = services.create_project(self.user, "Website launch")

        response = self.patch(
            f"/api/v1/projects/{project.id}",
            {"purpose": "Stop enquiries going to email."},
        )

        self.assertEqual(response.status_code, 200)
        project.refresh_from_db()
        self.assertEqual(project.purpose, "Stop enquiries going to email.")

    def test_a_purpose_can_be_cleared(self):
        """Empty string clears; absent leaves alone.

        Unlike `due_date`, this needs no absent-versus-null dance: "" is the
        cleared state and `None` only ever means the client did not mention the
        field. Tested because that asymmetry with the neighbouring field is the
        kind of thing a later reader would assume away.
        """
        project = services.create_project(
            self.user, "Website launch", purpose="Something I no longer mean.",
        )

        response = self.patch(f"/api/v1/projects/{project.id}", {"purpose": ""})

        self.assertEqual(response.status_code, 200)
        project.refresh_from_db()
        self.assertEqual(project.purpose, "")

    def test_a_patch_that_omits_purpose_leaves_it_alone(self):
        project = services.create_project(
            self.user, "Website launch", purpose="Stop enquiries going to email.",
        )

        response = self.patch(
            f"/api/v1/projects/{project.id}", {"title": "Website relaunch"}
        )

        self.assertEqual(response.status_code, 200)
        project.refresh_from_db()
        self.assertEqual(project.title, "Website relaunch")
        self.assertEqual(project.purpose, "Stop enquiries going to email.")

    def test_cannot_write_a_purpose_onto_someone_else_s_project(self):
        theirs = services.create_project(self.other, "Their launch")

        response = self.patch(f"/api/v1/projects/{theirs.id}", {"purpose": "Mine now."})

        self.assertEqual(response.status_code, 404)
        theirs.refresh_from_db()
        self.assertEqual(theirs.purpose, "")


class ProjectBriefEndpointTest(TestCase):
    """The HTTP contract for a project's brief.

    Assembly is tested in test_project_brief.py; this is only what a client
    sees. A separate route rather than a fatter `ProjectOut`, because a brief
    runs a full-text retrieval and a project detail is fetched constantly --
    paying for the search on every render of a page that mostly wants a title
    would be the wrong default, and it is a *briefing*: asked for, not implied.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.project = services.create_project(
            self.user,
            "Website launch",
            purpose=(
                "Replace the enquiries inbox with a booking form so the venue "
                "stops losing bookings to email."
            ),
        )
        self.client.force_login(self.user)

    def test_rejects_anonymous_requests(self):
        self.client.logout()

        response = self.client.get(f"/api/v1/projects/{self.project.id}/brief")

        self.assertEqual(response.status_code, 401)

    def test_returns_three_sections(self):
        response = self.client.get(f"/api/v1/projects/{self.project.id}/brief")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("material", body)
        self.assertIn("questions", body)
        self.assertIn("commitments", body)

    def test_material_carries_its_evidence(self):
        """The reason travels to the client, or the client invents one.

        A brief whose items arrive without the terms that selected them leaves
        the interface to say "related", which is the unfalsifiable label this
        whole mechanic exists to avoid.
        """
        mind_services.capture(
            self.user,
            content=(
                "The booking form should collect the venue and the enquiries "
                "contact."
            ),
            captured_at=timezone.now() - timedelta(days=30),
            source="web",
            actor="alice",
        )

        body = self.client.get(f"/api/v1/projects/{self.project.id}/brief").json()

        self.assertTrue(body["material"])
        self.assertTrue(body["material"][0]["reason"])
        self.assertTrue(body["material"][0]["text"])

    def test_a_brief_for_someone_else_s_project_is_not_found(self):
        theirs = services.create_project(self.other, "Their launch")

        response = self.client.get(f"/api/v1/projects/{theirs.id}/brief")

        self.assertEqual(response.status_code, 404)
        # And 404 because it is theirs, not because the route is missing --
        # an absent route answers 404 too, so without this the isolation case
        # would pass against no implementation at all.
        self.assertEqual(
            self.client.get(f"/api/v1/projects/{self.project.id}/brief").status_code,
            200,
        )


class ProjectDesiredOutcomeEndpointTest(TestCase):
    """The HTTP half of the outcome field — v2 increment 3.

    Model behaviour lives in `test_projects.py`, per this file's split. What is
    here is what a client can read and write, plus the isolation case every
    owner-scoped, ID-taking route gets.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.client.force_login(self.user)

    def patch(self, path, body):
        return self.client.patch(
            path, data=json.dumps(body), content_type="application/json",
        )

    def test_a_project_reports_its_outcome(self):
        project = services.create_project(self.user, "Website launch")
        project.desired_outcome = "The booking form is live."
        project.save(update_fields=["desired_outcome"])

        response = self.client.get(f"/api/v1/projects/{project.pk}")

        self.assertEqual(
            response.json()["desired_outcome"], "The booking form is live."
        )

    def test_a_project_with_none_reports_an_empty_string(self):
        """Never null over the wire, so a client renders text either way."""
        project = services.create_project(self.user, "Website launch")

        response = self.client.get(f"/api/v1/projects/{project.pk}")

        self.assertEqual(response.json()["desired_outcome"], "")

    def test_an_outcome_can_be_written(self):
        project = services.create_project(self.user, "Website launch")

        response = self.patch(
            f"/api/v1/projects/{project.pk}",
            {"desired_outcome": "  The booking form is live.  "},
        )

        self.assertEqual(response.status_code, 200)
        project.refresh_from_db()
        self.assertEqual(project.desired_outcome, "The booking form is live.")

    def test_an_outcome_can_be_cleared(self):
        project = services.create_project(self.user, "Website launch")
        project.desired_outcome = "Something"
        project.save(update_fields=["desired_outcome"])

        self.patch(f"/api/v1/projects/{project.pk}", {"desired_outcome": ""})

        project.refresh_from_db()
        self.assertEqual(project.desired_outcome, "")

    def test_not_mentioning_it_leaves_it_alone(self):
        project = services.create_project(self.user, "Website launch")
        project.desired_outcome = "The booking form is live."
        project.save(update_fields=["desired_outcome"])

        self.patch(f"/api/v1/projects/{project.pk}", {"title": "Site launch"})

        project.refresh_from_db()
        self.assertEqual(project.desired_outcome, "The booking form is live.")

    def test_one_person_cannot_write_another_s_outcome(self):
        project = services.create_project(self.other, "Bob's project")

        response = self.patch(
            f"/api/v1/projects/{project.pk}", {"desired_outcome": "Mine now."},
        )

        self.assertEqual(response.status_code, 404)
        project.refresh_from_db()
        self.assertEqual(project.desired_outcome, "")


class ProjectPauseEndpointTest(TestCase):
    """Parking a project over HTTP — v2 increment 3.

    `is_paused` on the update payload rather than its own route, mirroring
    `is_completed` exactly: both are "which of this project's states is it in",
    and giving one a boolean and the other a verb would make two spellings of
    one idea.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.client.force_login(self.user)

    def patch(self, path, body):
        return self.client.patch(
            path, data=json.dumps(body), content_type="application/json",
        )

    def test_a_new_project_reports_no_pause(self):
        project = services.create_project(self.user, "Website launch")

        response = self.client.get(f"/api/v1/projects/{project.pk}")

        self.assertIsNone(response.json()["paused_at"])

    def test_a_project_can_be_paused_and_says_when(self):
        project = services.create_project(self.user, "Website launch")

        response = self.patch(
            f"/api/v1/projects/{project.pk}", {"is_paused": True}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json()["paused_at"])
        project.refresh_from_db()
        self.assertIsNotNone(project.paused_at)

    def test_a_project_can_be_resumed(self):
        project = services.create_project(self.user, "Website launch")
        services.pause_project(project)

        response = self.patch(
            f"/api/v1/projects/{project.pk}", {"is_paused": False}
        )

        self.assertIsNone(response.json()["paused_at"])
        project.refresh_from_db()
        self.assertIsNone(project.paused_at)

    def test_not_mentioning_it_leaves_the_pause_alone(self):
        project = services.create_project(self.user, "Website launch")
        services.pause_project(project)

        self.patch(f"/api/v1/projects/{project.pk}", {"title": "Site launch"})

        project.refresh_from_db()
        self.assertIsNotNone(project.paused_at)

    def test_one_person_cannot_pause_another_s_project(self):
        project = services.create_project(self.other, "Bob's project")

        response = self.patch(
            f"/api/v1/projects/{project.pk}", {"is_paused": True}
        )

        self.assertEqual(response.status_code, 404)
        project.refresh_from_db()
        self.assertIsNone(project.paused_at)
