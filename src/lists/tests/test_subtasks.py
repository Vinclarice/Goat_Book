"""Service-level behaviour for subtasks.

Kept separate from test_services.py because it is the bulk of one feature
rather than more cases for the existing ones. The database constraint that
backs all of this is tested directly in test_models.py, not through here:
services._duplicate_exists short-circuits before the database is reached on
most paths, so these would pass against a missing constraint.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from lists import services
from lists.models import Item, List


class SubtaskServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )
        self.list_ = List.objects.create(owner=self.user, title="Travel")
        self.parent = services.create_item(self.list_, "Plan Japan trip")
        self.child_a = services.create_item(
            self.list_, "Book flights", parent=self.parent
        )
        self.child_b = services.create_item(
            self.list_, "Book hotel", parent=self.parent
        )

    def refresh(self, item):
        return Item.objects.get(pk=item.pk)


class SubtaskStructureTest(SubtaskServiceTest):
    def test_subtasks_belong_to_their_parent(self):
        self.assertEqual(
            list(self.parent.subtasks.order_by("pk")),
            [self.child_a, self.child_b],
        )

    def test_positions_run_within_a_sibling_group(self):
        # First and second among siblings, not third and fourth in the list.
        self.assertEqual([self.child_a.position, self.child_b.position], [0, 1])

    def test_the_same_text_is_allowed_under_a_different_parent(self):
        other = services.create_item(self.list_, "Plan Peru trip")

        twin = services.create_item(self.list_, "Book flights", parent=other)

        self.assertEqual(twin.text, self.child_a.text)

    def test_duplicate_siblings_are_rejected(self):
        with self.assertRaises(services.TaskConflict):
            services.create_item(self.list_, "Book flights", parent=self.parent)

    def test_a_subtask_cannot_have_subtasks(self):
        with self.assertRaises(services.TaskConflict):
            services.create_item(
                self.list_, "Compare fares", parent=self.child_a
            )

    def test_a_parent_from_another_list_is_rejected(self):
        other_list = List.objects.create(owner=self.user, title="Home")

        with self.assertRaises(services.TaskConflict):
            services.create_item(other_list, "Book flights", parent=self.parent)

    def test_subtasks_cannot_be_created_with_recurrence(self):
        with self.assertRaises(services.TaskConflict):
            services.create_item(
                self.list_,
                "Weekly check",
                parent=self.parent,
                recurrence="weekly",
            )

    def test_recurrence_cannot_be_set_on_an_existing_subtask(self):
        with self.assertRaises(services.TaskConflict):
            services.set_recurrence(self.child_a, Item.Recurrence.WEEKLY)


class PromoteDemoteTest(SubtaskServiceTest):
    def test_promoting_a_subtask_makes_it_a_root_task(self):
        promoted = services.set_parent(self.child_a, None)

        self.assertIsNone(promoted.parent_id)

    def test_demoting_a_task_that_has_children_is_rejected(self):
        other = services.create_item(self.list_, "Plan Peru trip")

        with self.assertRaises(services.TaskConflict):
            services.set_parent(self.parent, other)

    def test_a_task_cannot_become_its_own_parent(self):
        with self.assertRaises(services.TaskConflict):
            services.set_parent(self.parent, self.parent)

    def test_demoting_into_a_group_that_already_has_that_text_is_rejected(self):
        stray = services.create_item(self.list_, "Book flights")

        with self.assertRaises(services.TaskConflict):
            services.set_parent(stray, self.parent)

    def test_a_promoted_subtask_takes_a_position_among_its_new_siblings(self):
        promoted = services.set_parent(self.child_a, None)

        # parent is at 0, so the newly-promoted task lands after it.
        self.assertEqual(promoted.position, 1)


class CompleteCascadeTest(SubtaskServiceTest):
    def test_completing_a_parent_completes_its_open_children(self):
        completed = services.complete_item(self.parent)

        self.assertEqual(
            self.refresh(self.child_a).status, Item.Status.COMPLETED
        )
        self.assertEqual(
            self.refresh(self.child_b).status, Item.Status.COMPLETED
        )
        self.assertEqual(completed.status, Item.Status.COMPLETED)

    def test_the_cascade_reports_only_the_children_it_moved(self):
        # child_b was already done, so an undo must not reopen it -- and
        # afterwards the two are indistinguishable, which is exactly why
        # complete_item hands the set back rather than recomputing it.
        services.complete_item(self.child_b)

        completed = services.complete_item(self.parent)

        self.assertEqual(
            [each.pk for each in completed._cascaded], [self.child_a.pk]
        )

    def test_completing_a_childless_task_cascades_to_nothing(self):
        alone = services.create_item(self.list_, "Buy stamps")

        completed = services.complete_item(alone)

        self.assertEqual(completed._cascaded, [])


class ArchiveRestoreCascadeTest(SubtaskServiceTest):
    def test_archiving_a_parent_archives_its_children(self):
        services.archive_item(self.parent)

        self.assertEqual(
            self.refresh(self.child_a).status, Item.Status.ARCHIVED
        )
        self.assertEqual(
            self.refresh(self.child_b).status, Item.Status.ARCHIVED
        )

    def test_restore_returns_each_child_to_the_status_it_had(self):
        services.complete_item(self.child_b)
        services.archive_item(self.parent)

        services.restore_item(self.refresh(self.parent))

        # child_a was active when archived; child_b was completed. Only
        # possible because migration 0018 stopped fabricating completed_at.
        self.assertEqual(self.refresh(self.child_a).status, Item.Status.ACTIVE)
        self.assertEqual(
            self.refresh(self.child_b).status, Item.Status.COMPLETED
        )

    def test_restore_leaves_separately_archived_children_alone(self):
        # Archived on its own, so it is not in the parent's archive group and
        # has no business coming back when the parent does.
        services.archive_item(self.child_b)
        services.archive_item(self.parent)

        services.restore_item(self.refresh(self.parent))

        self.assertEqual(self.refresh(self.child_a).status, Item.Status.ACTIVE)
        self.assertEqual(
            self.refresh(self.child_b).status, Item.Status.ARCHIVED
        )

    def test_one_archive_group_covers_the_parent_and_what_it_took(self):
        services.archive_item(self.parent)

        groups = {
            self.refresh(each).archive_group
            for each in (self.parent, self.child_a, self.child_b)
        }
        self.assertEqual(len(groups), 1)
        self.assertIsNotNone(groups.pop())

    def test_restoring_clears_the_archive_group(self):
        services.archive_item(self.parent)

        services.restore_item(self.refresh(self.parent))

        self.assertIsNone(self.refresh(self.parent).archive_group)
        self.assertIsNone(self.refresh(self.child_a).archive_group)


class RecurringParentTest(SubtaskServiceTest):
    def test_a_recurring_parent_carries_its_children_forward(self):
        today = timezone.localdate()
        services.set_due_date(self.parent, today)
        services.set_due_date(self.child_a, today - datetime.timedelta(days=2))
        services.set_recurrence(
            self.refresh(self.parent), Item.Recurrence.WEEKLY
        )

        completed = services.complete_item(self.refresh(self.parent))
        spawned = completed._spawned

        clones = {each.text: each for each in spawned.subtasks.all()}
        self.assertEqual(
            sorted(clones), ["Book flights", "Book hotel"]
        )
        self.assertTrue(
            all(each.status == Item.Status.ACTIVE for each in clones.values())
        )
        # The dated child keeps its two-day lead on the parent...
        self.assertEqual(
            clones["Book flights"].due_date,
            spawned.due_date - datetime.timedelta(days=2),
        )
        # ...and the undated one stays undated.
        self.assertIsNone(clones["Book hotel"].due_date)

    def test_the_clones_do_not_inherit_recurrence(self):
        services.set_recurrence(self.parent, Item.Recurrence.WEEKLY)

        completed = services.complete_item(self.refresh(self.parent))

        self.assertTrue(
            all(
                each.recurrence == Item.Recurrence.NONE
                for each in completed._spawned.subtasks.all()
            )
        )


class SiblingReorderTest(SubtaskServiceTest):
    def test_reorder_is_scoped_to_one_sibling_group(self):
        services.reorder_items(
            self.list_, [self.child_b.pk, self.child_a.pk], parent=self.parent
        )

        self.assertEqual(self.refresh(self.child_b).position, 0)
        self.assertEqual(self.refresh(self.child_a).position, 1)

    def test_reorder_rejects_ids_from_another_sibling_group(self):
        with self.assertRaises(services.TaskConflict):
            services.reorder_items(
                self.list_,
                [self.child_a.pk, self.child_b.pk, self.parent.pk],
                parent=self.parent,
            )

    def test_reordering_root_tasks_ignores_subtasks(self):
        other = services.create_item(self.list_, "Plan Peru trip")

        services.reorder_items(self.list_, [other.pk, self.parent.pk])

        self.assertEqual(self.refresh(other).position, 0)
        self.assertEqual(self.refresh(self.parent).position, 1)
