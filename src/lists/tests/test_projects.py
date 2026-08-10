"""A Project is a standalone workspace that can hold one or more Areas.

project-workspace-plan.md. The charter test in architecture-trajectory.md 4
names this pair as the example of a concept earning its own model -- a
different life cycle, not a different name -- and that hasn't changed;
what changed is which one contains the other.

Model and service behaviour live here; the HTTP contract is in
test_project_api.py, same split as ChecklistStep's two files.
"""
from datetime import date

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from lists import services
from lists.services import TaskConflict
from lists.models import Item, List, Project


class ProjectModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_starts_open_with_no_completion_stamp(self):
        project = Project.objects.create(owner=self.owner, title="Website Relaunch")

        self.assertFalse(project.is_completed)
        self.assertIsNone(project.completed_at)
        self.assertIsNone(project.due_date)
        self.assertIsNotNone(project.created_at)

    def test_belongs_to_its_owner_only(self):
        # project-workspace-plan.md 2 -- owner is the only ownership path
        # now; there is no parent record left to borrow one from.
        project = Project.objects.create(owner=self.owner, title="Website Relaunch")

        self.assertIn(project, self.owner.projects.all())

    def test_can_exist_with_no_areas(self):
        # The inverse of the old test_cannot_exist_without_an_area -- a
        # Project is the top-level record now.
        project = Project.objects.create(owner=self.owner, title="Just started")

        self.assertEqual(list(project.areas.all()), [])

    def test_a_completion_stamp_and_the_flag_cannot_disagree(self):
        with self.assertRaises(IntegrityError):
            Project.objects.create(
                owner=self.owner,
                title="Claims to be done",
                is_completed=True,
                completed_at=None,
            )

    def test_an_open_project_may_not_carry_a_completion_stamp(self):
        with self.assertRaises(IntegrityError):
            Project.objects.create(
                owner=self.owner,
                title="Claims to be open",
                is_completed=False,
                completed_at=timezone.now(),
            )


class ProjectServiceTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )

    def test_create_project_stamps_the_owner_passed_in(self):
        project = services.create_project(self.owner, "Website Relaunch")

        self.assertEqual(project.owner, self.owner)
        self.assertEqual(project.title, "Website Relaunch")

    def test_create_project_rejects_a_blank_title(self):
        with self.assertRaises(TaskConflict):
            services.create_project(self.owner, "   ")

    def test_create_project_strips_the_title(self):
        project = services.create_project(self.owner, "  Website Relaunch  ")

        self.assertEqual(project.title, "Website Relaunch")

    def test_create_project_takes_an_optional_due_date(self):
        project = services.create_project(
            self.owner, "Website Relaunch", due_date=date(2026, 9, 30),
        )

        self.assertEqual(project.due_date, date(2026, 9, 30))

    def test_completing_a_project_stamps_when(self):
        project = services.create_project(self.owner, "Website Relaunch")

        services.complete_project(project)

        project.refresh_from_db()
        self.assertTrue(project.is_completed)
        self.assertIsNotNone(project.completed_at)

    def test_completing_a_project_does_not_touch_its_areas_tasks(self):
        project = services.create_project(self.owner, "Website Relaunch")
        area = List.objects.create(owner=self.owner, title="Work", project=project)
        task = Item.objects.create(list=area, text="Write the brief")

        services.complete_project(project)

        task.refresh_from_db()
        self.assertEqual(task.status, Item.Status.ACTIVE)
        self.assertIsNone(task.completed_at)

    def test_completing_an_already_completed_project_keeps_the_first_stamp(self):
        project = services.create_project(self.owner, "Website Relaunch")
        services.complete_project(project)
        project.refresh_from_db()
        first = project.completed_at

        services.complete_project(project)

        project.refresh_from_db()
        self.assertEqual(project.completed_at, first)

    def test_reopening_a_project_clears_the_stamp(self):
        project = services.create_project(self.owner, "Website Relaunch")
        services.complete_project(project)

        services.reopen_project(project)

        project.refresh_from_db()
        self.assertFalse(project.is_completed)
        self.assertIsNone(project.completed_at)

    def test_an_area_can_be_added_to_a_project_and_removed_again(self):
        project = services.create_project(self.owner, "Website Relaunch")
        area = List.objects.create(owner=self.owner, title="Work")

        services.add_area_to_project(area, project)
        area.refresh_from_db()
        self.assertEqual(area.project, project)

        services.remove_area_from_project(area)
        area.refresh_from_db()
        self.assertIsNone(area.project)

    def test_an_area_cannot_join_a_project_belonging_to_somebody_else(self):
        """The guard fails closed, per principles.md.

        Checked in the service rather than only at the API, because the API
        is one caller and the invariant is the model's -- same shape
        capture.services.link_ideas already established.
        """
        theirs = services.create_project(self.other, "Not yours")
        area = List.objects.create(owner=self.owner, title="Work")

        with self.assertRaises(TaskConflict):
            services.add_area_to_project(area, theirs)

        area.refresh_from_db()
        self.assertIsNone(area.project)

    def test_creates_an_empty_area_with_no_project(self):
        # Vince's call, August 10, 2026: a user can create an area with no
        # task in it -- create_list_with_item's first-task requirement was
        # never a rule this needed to inherit, just the only path that
        # existed before a project needed one of its own.
        area = services.create_area(self.owner, "Legal")

        self.assertEqual(area.owner, self.owner)
        self.assertEqual(area.title, "Legal")
        self.assertEqual(list(area.item_set.all()), [])
        self.assertIsNone(area.project)

    def test_creates_an_area_already_inside_a_project(self):
        project = services.create_project(self.owner, "Website Relaunch")

        area = services.create_area(self.owner, "Design", project=project)

        self.assertEqual(area.project, project)

    def test_a_blank_area_title_falls_back_to_untitled(self):
        area = services.create_area(self.owner, "   ")

        self.assertEqual(area.title, "Untitled list")

    def test_cannot_create_an_area_directly_inside_somebody_elses_project(self):
        theirs = services.create_project(self.other, "Not yours")

        with self.assertRaises(TaskConflict):
            services.create_area(self.owner, "Legal", project=theirs)

        self.assertEqual(List.objects.filter(title="Legal").count(), 0)

    def test_deleting_a_project_is_a_hard_delete(self):
        project = services.create_project(self.owner, "Website Relaunch")

        services.delete_project(project)

        self.assertFalse(Project.objects.filter(pk=project.pk).exists())

    def test_deleting_a_project_leaves_its_areas_in_place(self):
        project = services.create_project(self.owner, "Website Relaunch")
        area = List.objects.create(owner=self.owner, title="Work", project=project)

        services.delete_project(project)

        area.refresh_from_db()
        self.assertIsNone(area.project)

    def test_deleting_an_area_leaves_its_project_alone(self):
        # project-workspace-plan.md's charter check: the old CASCADE ran the
        # other way (Project.area). Once the FK direction inverts, there is
        # no FK left for a delete on the Area to cascade through.
        project = services.create_project(self.owner, "Website Relaunch")
        area = List.objects.create(owner=self.owner, title="Work", project=project)

        area.delete()

        self.assertTrue(Project.objects.filter(pk=project.pk).exists())


class ProjectReadTest(TestCase):
    """Charter rule 4: reads answer questions, services mutate."""

    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )

    def test_lists_only_this_owners_projects_open_first(self):
        from lists import projects as project_reader

        done = services.create_project(self.owner, "Shipped last month")
        services.complete_project(done)
        open_one = services.create_project(self.owner, "Website Relaunch")
        services.create_project(self.other, "Not mine")

        found = list(project_reader.projects_for(self.owner))

        self.assertEqual(
            [each.title for each in found], [open_one.title, done.title],
        )

    def test_counts_the_open_tasks_across_every_area_in_the_project(self):
        # Two-hop now: project -> areas -> items. A fixture spanning two
        # areas is the regression this test exists to catch.
        from lists import projects as project_reader

        project = services.create_project(self.owner, "Website Relaunch")
        design = List.objects.create(
            owner=self.owner, title="Design", project=project,
        )
        dev = List.objects.create(owner=self.owner, title="Dev", project=project)
        Item.objects.create(list=design, text="Open one")
        Item.objects.create(
            list=dev,
            text="Finished one",
            status=Item.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        Item.objects.create(list=dev, text="Another open one")

        found = list(project_reader.projects_for(self.owner))

        self.assertEqual(found[0].open_task_count, 2)

    def test_a_project_with_no_areas_has_no_open_tasks(self):
        from lists import projects as project_reader

        services.create_project(self.owner, "Just started")

        found = list(project_reader.projects_for(self.owner))

        self.assertEqual(found[0].open_task_count, 0)
