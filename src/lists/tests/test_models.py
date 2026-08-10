from accounts.models import User
from django.test import TestCase
from lists.models import ChecklistStep, Item, List, Project
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.utils import timezone


class ItemModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(
            username="itemowner", email="itemowner@example.com",
        )

    def test_default_text(self):
        item = Item()
        self.assertEqual(item.text, "")

    def test_item_is_related_to_list(self):
        mylist = List.objects.create(owner=self.owner)
        item = Item()
        item.list = mylist
        item.save()
        self.assertIn(item, mylist.item_set.all())

    def test_cannot_save_empty_list_items(self):
        mylist = List.objects.create(owner=self.owner)
        item = Item(list=mylist, text=None)
        with self.assertRaises(IntegrityError):
            item.save()

    def test_cannot_save_empty_list_items_validation(self):
        mylist = List.objects.create(owner=self.owner)
        item = Item(list=mylist, text="")
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_duplicate_items_are_invalid(self):
        mylist = List.objects.create(owner=self.owner)
        Item.objects.create(list=mylist, text="bla")
        with self.assertRaises(ValidationError):
            item = Item(list=mylist, text="bla")
            item.full_clean()

    def test_CAN_save_same_item_to_different_lists(self):
        list1 = List.objects.create(owner=self.owner)
        list2 = List.objects.create(owner=self.owner)
        Item.objects.create(list=list1, text="bla")
        item = Item(list=list2, text="bla")
        item.full_clean()  # should not raise

    def test_string_representation(self):
        item = Item(text="some text")
        self.assertEqual(str(item), "some text")

    def test_new_items_record_creation_time_and_start_incomplete(self):
        item = Item.objects.create(list=List.objects.create(owner=self.owner), text="New task")

        self.assertIsNotNone(item.created_at)
        self.assertIsNotNone(item.updated_at)
        self.assertEqual(item.status, Item.Status.ACTIVE)
        self.assertIsNone(item.completed_at)
        self.assertIsNone(item.archived_at)

    def test_archived_item_does_not_block_reusing_its_text(self):
        mylist = List.objects.create(owner=self.owner)
        Item.objects.create(
            list=mylist,
            text="Repeatable task",
            status=Item.Status.ARCHIVED,
            completed_at="2026-07-24T12:00:00Z",
            archived_at="2026-07-24T12:01:00Z",
        )

        new_item = Item(list=mylist, text="Repeatable task")
        new_item.full_clean()


class ListModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(
            username="listowner", email="listowner@example.com",
        )

    def test_an_area_cannot_exist_without_an_owner(self):
        """Charter rule 1, stated without its last exception.

        architecture-trajectory.md 4 asks every new record to be owned at
        birth, and List was the one model that pre-dated the rule and never
        satisfied it. Asserting at the database rather than in a service
        because that is where the guarantee now lives -- a service check
        would only cover the write paths that remembered to call it.
        """
        with self.assertRaises(IntegrityError):
            List.objects.create(title="Nobody's area")

    def test_get_absolute_url(self):
        mylist = List.objects.create(owner=self.owner)
        self.assertEqual(mylist.get_absolute_url(), f"/areas/{mylist.id}/")

    def test_list_items_order(self):
        list1 = List.objects.create(owner=self.owner)
        item1 = Item.objects.create(list=list1, text="i1")
        item2 = Item.objects.create(list=list1, text="item 2")
        item3 = Item.objects.create(list=list1, text="3")
        self.assertEqual(
            list(list1.item_set.all()),
            [item1, item2, item3],
        )

    def test_lists_can_have_owners(self):
        user = User.objects.create(username="alice", email="a@b.com")
        mylist = List.objects.create(owner=user)
        self.assertIn(mylist, user.lists.all())

    def test_list_name_is_its_title(self):
        list_ = List.objects.create(owner=self.owner, title="Programming")
        self.assertEqual(list_.title, "Programming")

    def test_empty_list_has_fallback_name(self):
        self.assertEqual(List.objects.create(owner=self.owner).title, "Untitled list")

    def test_an_area_belongs_to_no_project_by_default(self):
        # project-workspace-plan.md 2 -- the inverse of the old
        # Project.area: an Area optionally belongs to a Project now.
        mylist = List.objects.create(owner=self.owner)

        self.assertIsNone(mylist.project)

    def test_an_area_can_join_a_project(self):
        project = Project.objects.create(
            owner=self.owner,
            area=List.objects.create(owner=self.owner, title="Home"),
            title="Launch the business",
        )
        mylist = List.objects.create(owner=self.owner, title="Legal")

        mylist.project = project
        mylist.save()

        self.assertIn(mylist, project.areas.all())

    def test_deleting_a_project_leaves_its_areas_in_place(self):
        # SET_NULL, not CASCADE: a Project groups Areas, it does not own
        # them -- deleting one says the grouping was wrong, not that the
        # work is gone.
        project = Project.objects.create(
            owner=self.owner,
            area=List.objects.create(owner=self.owner, title="Home"),
            title="Launch the business",
        )
        mylist = List.objects.create(
            owner=self.owner, title="Legal", project=project,
        )

        project.delete()

        mylist.refresh_from_db()
        self.assertIsNone(mylist.project)


class UniqueActiveItemConstraintTest(TestCase):
    """Exercises unique_active_item at the database, not through services.

    services._duplicate_exists short-circuits before the database is reached
    on most paths, so a service-level test would still pass against a broken
    or missing constraint. These go straight at it.

    No longer skipped on SQLite -- release-d-plan.md 5: dropping Item.parent
    left `(list, text)` as the constraint's only fields, neither of them
    nullable, so nulls_distinct=False was doing nothing and its removal lets
    SQLite create the constraint like any other.
    """

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(
            username="constraintowner", email="constraintowner@example.com",
        )

    def test_duplicate_root_tasks_are_still_rejected(self):
        mylist = List.objects.create(owner=self.owner)
        Item.objects.create(list=mylist, text="Book flights")

        with self.assertRaises(IntegrityError):
            Item.objects.create(list=mylist, text="Book flights")

    def test_archiving_frees_the_text_for_reuse(self):
        mylist = List.objects.create(owner=self.owner)
        first = Item.objects.create(list=mylist, text="Book flights")
        first.status = Item.Status.ARCHIVED
        first.archived_at = timezone.now()
        first.save()

        Item.objects.create(list=mylist, text="Book flights")  # should not raise


class ChecklistStepModelTest(TestCase):
    """release-d-plan.md 2: a Checklist Step is a new, lightweight model --
    no due date, no tags, cannot recur, dies with its parent task.
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            username="alice", email="a@b.com", password="x"
        )
        self.mylist = List.objects.create(owner=self.owner)
        self.task = Item.objects.create(list=self.mylist, text="Get the dog ready")

    def test_default_state(self):
        step = ChecklistStep.objects.create(
            owner=self.owner, task=self.task, text="Refill medication"
        )
        self.assertFalse(step.is_done)
        self.assertIsNone(step.completed_at)
        self.assertTrue(step.carries_forward)
        self.assertEqual(step.position, 0)

    def test_string_representation(self):
        step = ChecklistStep(text="Book the kennel")
        self.assertEqual(str(step), "Book the kennel")

    def test_step_is_related_to_its_task(self):
        step = ChecklistStep.objects.create(
            owner=self.owner, task=self.task, text="Book the kennel"
        )
        self.assertIn(step, self.task.checklist_steps.all())

    def test_step_is_related_to_its_owner(self):
        step = ChecklistStep.objects.create(
            owner=self.owner, task=self.task, text="Book the kennel"
        )
        self.assertIn(step, self.owner.checklist_steps.all())

    def test_deleting_the_task_deletes_its_steps(self):
        step = ChecklistStep.objects.create(
            owner=self.owner, task=self.task, text="Book the kennel"
        )
        self.task.delete()
        self.assertFalse(ChecklistStep.objects.filter(pk=step.pk).exists())

    def test_steps_are_ordered_by_position(self):
        second = ChecklistStep.objects.create(
            owner=self.owner, task=self.task, text="second", position=1
        )
        first = ChecklistStep.objects.create(
            owner=self.owner, task=self.task, text="first", position=0
        )
        self.assertEqual(
            list(self.task.checklist_steps.all()), [first, second]
        )

    def test_duplicate_open_step_text_is_rejected(self):
        ChecklistStep.objects.create(
            owner=self.owner, task=self.task, text="Book the kennel"
        )
        with self.assertRaises(IntegrityError):
            ChecklistStep.objects.create(
                owner=self.owner, task=self.task, text="Book the kennel"
            )

    def test_a_done_step_frees_its_text_for_reuse(self):
        first = ChecklistStep.objects.create(
            owner=self.owner, task=self.task, text="Book the kennel"
        )
        first.is_done = True
        first.completed_at = timezone.now()
        first.save()

        ChecklistStep.objects.create(  # should not raise
            owner=self.owner, task=self.task, text="Book the kennel"
        )

    def test_the_same_text_may_appear_under_different_tasks(self):
        other_task = Item.objects.create(list=self.mylist, text="Plan Japan trip")
        ChecklistStep.objects.create(
            owner=self.owner, task=self.task, text="Book flights"
        )
        ChecklistStep.objects.create(
            owner=self.owner, task=other_task, text="Book flights"
        )
        self.assertEqual(ChecklistStep.objects.filter(text="Book flights").count(), 2)
