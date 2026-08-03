"""A Project is work that completes; an Area never does.

release-d-plan.md 3. The charter test in architecture-trajectory.md 4 names
this exact pair as the example of a concept earning its own model -- a
different life cycle, not a different name.

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
        cls.area = List.objects.create(owner=cls.owner, title="Work")

    def test_starts_open_with_no_completion_stamp(self):
        project = Project.objects.create(
            owner=self.owner, area=self.area, title="Website Relaunch",
        )

        self.assertFalse(project.is_completed)
        self.assertIsNone(project.completed_at)
        self.assertIsNone(project.due_date)
        self.assertIsNotNone(project.created_at)

    def test_belongs_to_its_owner_and_its_area(self):
        project = Project.objects.create(
            owner=self.owner, area=self.area, title="Website Relaunch",
        )

        self.assertIn(project, self.owner.projects.all())
        self.assertIn(project, self.area.projects.all())

    def test_cannot_exist_without_an_area(self):
        """Decided against release-d-plan.md 3's own recommendation.

        3 proposed a nullable `area` on reversibility grounds; slice 6 had
        just finished paying the nullable-to-required cost on List.owner --
        an audit and a destructive migration -- while required-to-nullable is
        a bare AlterField with no data work. The permissive choice was the
        expensive one to undo.
        """
        with self.assertRaises(IntegrityError):
            Project.objects.create(owner=self.owner, title="Homeless")

    def test_dies_with_its_area(self):
        """CASCADE, the consequence of `area` being required.

        Deleting an Area already deletes the tasks in it; a project inside it
        has no meaning once the area is gone either.
        """
        doomed = List.objects.create(owner=self.owner, title="Temporary")
        project = Project.objects.create(
            owner=self.owner, area=doomed, title="Short-lived",
        )

        doomed.delete()

        self.assertFalse(Project.objects.filter(pk=project.pk).exists())

    def test_a_completion_stamp_and_the_flag_cannot_disagree(self):
        """Rule 6's spirit at the database, the way Item already does it.

        Item carries valid_item_status_timestamps for the same reason. This
        table is new and has no legacy rows, so the constraint is free here
        and would be a data migration later -- which is the charter's whole
        asymmetry argument.
        """
        with self.assertRaises(IntegrityError):
            Project.objects.create(
                owner=self.owner,
                area=self.area,
                title="Claims to be done",
                is_completed=True,
                completed_at=None,
            )

    def test_an_open_project_may_not_carry_a_completion_stamp(self):
        with self.assertRaises(IntegrityError):
            Project.objects.create(
                owner=self.owner,
                area=self.area,
                title="Claims to be open",
                is_completed=False,
                completed_at=timezone.now(),
            )


class TaskJoinsAProjectTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        cls.area = List.objects.create(owner=cls.owner, title="Work")

    def test_a_task_has_no_project_by_default(self):
        task = Item.objects.create(list=self.area, text="Write the brief")

        self.assertIsNone(task.project_id)

    def test_a_task_keeps_its_area_and_additionally_joins_a_project(self):
        """release-d-plan.md 3: additive, not a replacement for Item.list.

        Letting Item.list point at either an Area or a Project would touch
        the FK that unique_active_item and every agenda query key off.
        """
        project = Project.objects.create(
            owner=self.owner, area=self.area, title="Website Relaunch",
        )
        task = Item.objects.create(
            list=self.area, text="Write the brief", project=project,
        )

        self.assertEqual(task.list, self.area)
        self.assertIn(task, project.tasks.all())

    def test_deleting_a_project_leaves_its_tasks_alone(self):
        """SET_NULL: a project references its tasks, it does not own them.

        The same reasoning DailyFocus.task already follows -- charter rule 5,
        reference never copy. Someone deleting a project has said the
        grouping was wrong, not that the work is gone.
        """
        project = Project.objects.create(
            owner=self.owner, area=self.area, title="Website Relaunch",
        )
        task = Item.objects.create(
            list=self.area, text="Write the brief", project=project,
        )

        project.delete()

        task.refresh_from_db()
        self.assertIsNone(task.project_id)
        self.assertEqual(task.text, "Write the brief")


class ProjectServiceTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.area = List.objects.create(owner=self.owner, title="Work")

    def test_create_project_stamps_the_owner_from_the_area(self):
        project = services.create_project(self.area, "Website Relaunch")

        self.assertEqual(project.owner, self.owner)
        self.assertEqual(project.area, self.area)
        self.assertEqual(project.title, "Website Relaunch")

    def test_create_project_rejects_a_blank_title(self):
        with self.assertRaises(TaskConflict):
            services.create_project(self.area, "   ")

    def test_create_project_strips_the_title(self):
        project = services.create_project(self.area, "  Website Relaunch  ")

        self.assertEqual(project.title, "Website Relaunch")

    def test_create_project_takes_an_optional_due_date(self):
        project = services.create_project(
            self.area, "Website Relaunch", due_date=date(2026, 9, 30),
        )

        self.assertEqual(project.due_date, date(2026, 9, 30))

    def test_completing_a_project_stamps_when(self):
        project = services.create_project(self.area, "Website Relaunch")

        services.complete_project(project)

        project.refresh_from_db()
        self.assertTrue(project.is_completed)
        self.assertIsNotNone(project.completed_at)

    def test_completing_a_project_does_not_touch_its_tasks(self):
        """release-d-plan.md 3's acceptance example, and charter rule 5.

        The Daily Focus join already works this way: a surface references a
        task, it does not own its status.
        """
        project = services.create_project(self.area, "Website Relaunch")
        task = Item.objects.create(
            list=self.area, text="Write the brief", project=project,
        )

        services.complete_project(project)

        task.refresh_from_db()
        self.assertEqual(task.status, Item.Status.ACTIVE)
        self.assertIsNone(task.completed_at)

    def test_completing_an_already_completed_project_keeps_the_first_stamp(self):
        project = services.create_project(self.area, "Website Relaunch")
        services.complete_project(project)
        project.refresh_from_db()
        first = project.completed_at

        services.complete_project(project)

        project.refresh_from_db()
        self.assertEqual(project.completed_at, first)

    def test_reopening_a_project_clears_the_stamp(self):
        project = services.create_project(self.area, "Website Relaunch")
        services.complete_project(project)

        services.reopen_project(project)

        project.refresh_from_db()
        self.assertFalse(project.is_completed)
        self.assertIsNone(project.completed_at)

    def test_a_task_can_be_put_into_a_project_and_taken_out_again(self):
        project = services.create_project(self.area, "Website Relaunch")
        task = Item.objects.create(list=self.area, text="Write the brief")

        services.set_task_project(task, project)
        task.refresh_from_db()
        self.assertEqual(task.project, project)

        services.set_task_project(task, None)
        task.refresh_from_db()
        self.assertIsNone(task.project_id)

    def test_a_task_cannot_join_a_project_belonging_to_somebody_else(self):
        """The guard fails closed, per principles.md.

        Ownership is checked in the service rather than only at the API,
        because the API is one caller and the invariant is the model's.
        """
        theirs = services.create_project(
            List.objects.create(owner=self.other, title="Theirs"), "Not yours",
        )
        task = Item.objects.create(list=self.area, text="Write the brief")

        with self.assertRaises(TaskConflict):
            services.set_task_project(task, theirs)

        task.refresh_from_db()
        self.assertIsNone(task.project_id)

    def test_a_task_cannot_join_a_project_in_a_different_area(self):
        """A project groups work inside one area, so this would be a lie.

        Not merely tidiness: slice 8 renders a project's tasks from the area
        page, and a task in another area would appear under a heading it does
        not belong to.
        """
        elsewhere = List.objects.create(owner=self.owner, title="Home")
        project = services.create_project(elsewhere, "Repaint the hallway")
        task = Item.objects.create(list=self.area, text="Write the brief")

        with self.assertRaises(TaskConflict):
            services.set_task_project(task, project)

    def test_deleting_a_project_is_a_hard_delete(self):
        """Charter rule 6, stated. No tombstone: rule 2 does not apply here,
        because no client creates or holds a Project offline.
        """
        project = services.create_project(self.area, "Website Relaunch")

        services.delete_project(project)

        self.assertFalse(Project.objects.filter(pk=project.pk).exists())


class ProjectReadTest(TestCase):
    """Charter rule 4: reads answer questions, services mutate."""

    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.area = List.objects.create(owner=self.owner, title="Work")

    def test_lists_only_this_owners_projects_open_first(self):
        from lists import projects as project_reader

        done = services.create_project(self.area, "Shipped last month")
        services.complete_project(done)
        open_one = services.create_project(self.area, "Website Relaunch")
        services.create_project(
            List.objects.create(owner=self.other, title="Theirs"), "Not mine",
        )

        found = list(project_reader.projects_for(self.owner))

        self.assertEqual([each.title for each in found],
                         [open_one.title, done.title])

    def test_counts_the_open_tasks_in_each_project(self):
        from lists import projects as project_reader

        project = services.create_project(self.area, "Website Relaunch")
        Item.objects.create(list=self.area, text="Open one", project=project)
        Item.objects.create(
            list=self.area,
            text="Finished one",
            project=project,
            status=Item.Status.COMPLETED,
            completed_at=timezone.now(),
        )

        found = list(project_reader.projects_for(self.owner))

        self.assertEqual(found[0].open_task_count, 1)
