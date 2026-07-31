import datetime

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from lists import services
from lists.models import Item, List, Tag


class TaskServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )
        self.list_ = List.objects.create(owner=self.user, title="Programming")
        self.item = Item.objects.create(list=self.list_, text="Write tests")

    def test_complete_reopen_archive_and_restore(self):
        completed = services.complete_item(self.item)
        self.assertEqual(completed.status, Item.Status.COMPLETED)
        self.assertIsNotNone(completed.completed_at)

        reopened = services.reopen_item(completed)
        self.assertEqual(reopened.status, Item.Status.ACTIVE)
        self.assertIsNone(reopened.completed_at)

        archived = services.archive_item(reopened)
        self.assertEqual(archived.status, Item.Status.ARCHIVED)
        self.assertIsNone(archived.completed_at)
        self.assertIsNotNone(archived.archived_at)

        restored = services.restore_item(archived)
        self.assertEqual(restored.status, Item.Status.ACTIVE)
        self.assertIsNone(restored.completed_at)
        self.assertIsNone(restored.archived_at)

    def test_restore_rejects_duplicate_active_text(self):
        self.item.status = Item.Status.ARCHIVED
        self.item.completed_at = timezone.now()
        self.item.archived_at = timezone.now()
        self.item.save()
        Item.objects.create(list=self.list_, text=self.item.text)

        with self.assertRaisesMessage(
            services.TaskConflict,
            "already exists in its original list",
        ):
            services.restore_item(self.item)

        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.ARCHIVED)

    def test_edit_rejects_duplicate_and_archived_tasks(self):
        Item.objects.create(list=self.list_, text="Existing")
        with self.assertRaises(services.TaskConflict):
            services.edit_item(self.item, "Existing")

        self.item.status = Item.Status.ARCHIVED
        self.item.completed_at = timezone.now()
        self.item.archived_at = timezone.now()
        self.item.save()
        with self.assertRaises(services.InvalidTaskTransition):
            services.edit_item(self.item, "Changed")

    def test_only_archived_tasks_can_be_deleted(self):
        with self.assertRaises(services.InvalidTaskTransition):
            services.delete_archived_item(self.item)

        archived = services.archive_item(self.item)
        services.delete_archived_item(archived)
        self.assertFalse(Item.objects.filter(pk=self.item.pk).exists())

    def test_set_due_date(self):
        due = datetime.date(2026, 8, 1)
        updated = services.set_due_date(self.item, due)
        self.assertEqual(updated.due_date, due)

        cleared = services.set_due_date(self.item, None)
        self.assertIsNone(cleared.due_date)

    def test_set_due_date_rejects_archived_tasks(self):
        archived = services.archive_item(self.item)
        with self.assertRaises(services.InvalidTaskTransition):
            services.set_due_date(archived, datetime.date(2026, 8, 1))

    def test_new_items_are_positioned_after_existing_ones(self):
        second = services.create_item(self.list_, "Second task")
        third = services.create_item(self.list_, "Third task")
        self.assertLess(self.item.position, second.position)
        self.assertLess(second.position, third.position)

    def test_reorder_items(self):
        second = services.create_item(self.list_, "Second task")
        third = services.create_item(self.list_, "Third task")

        services.reorder_items(
            self.list_, [third.id, self.item.id, second.id],
        )

        reordered = list(self.list_.item_set.all())
        self.assertEqual([item.id for item in reordered], [third.id, self.item.id, second.id])

    def test_reorder_rejects_mismatched_id_set(self):
        services.create_item(self.list_, "Second task")
        with self.assertRaises(services.TaskConflict):
            services.reorder_items(self.list_, [self.item.id])

    def test_reorder_excludes_archived_items(self):
        archived = services.archive_item(self.item)
        second = services.create_item(self.list_, "Second task")
        # Archived items shouldn't need to be included, and shouldn't be
        # reachable through reorder either.
        services.reorder_items(self.list_, [second.id])
        archived.refresh_from_db()

    def test_create_item_with_tags_reuses_owner_tags(self):
        first = services.create_item(self.list_, "First", tags=["chores", "home"])
        second = services.create_item(self.list_, "Second", tags=["chores"])

        self.assertEqual(
            {tag.name for tag in first.tags.all()}, {"chores", "home"},
        )
        chores_tag_id = Tag.objects.get(name="chores", owner=self.user).id
        self.assertEqual(
            {tag.id for tag in second.tags.all()}, {chores_tag_id},
        )
        self.assertEqual(Tag.objects.filter(owner=self.user, name="chores").count(), 1)

    def test_set_item_tags_dedupes_and_strips(self):
        updated = services.set_item_tags(
            self.item, [" chores ", "chores", "", "home"],
        )
        self.assertEqual(
            sorted(tag.name for tag in updated.tags.all()), ["chores", "home"],
        )

        cleared = services.set_item_tags(self.item, [])
        self.assertEqual(list(cleared.tags.all()), [])

    def test_set_item_tags_rejects_archived_tasks(self):
        archived = services.archive_item(self.item)
        with self.assertRaises(services.InvalidTaskTransition):
            services.set_item_tags(archived, ["chores"])

    def test_completing_a_non_recurring_task_stays_completed(self):
        completed = services.complete_item(self.item)
        self.assertEqual(completed.status, Item.Status.COMPLETED)
        self.assertIsNone(getattr(completed, "_spawned", None))

    def test_completing_a_recurring_task_archives_it_and_spawns_next(self):
        services.set_due_date(self.item, datetime.date(2026, 8, 1))
        services.set_recurrence(self.item, Item.Recurrence.WEEKLY)

        completed = services.complete_item(self.item)

        self.assertEqual(completed.status, Item.Status.ARCHIVED)
        self.assertIsNotNone(completed.archived_at)

        spawned = completed._spawned
        self.assertEqual(spawned.text, self.item.text)
        self.assertEqual(spawned.status, Item.Status.ACTIVE)
        self.assertEqual(spawned.recurrence, Item.Recurrence.WEEKLY)
        self.assertEqual(spawned.due_date, datetime.date(2026, 8, 8))

    def test_recurring_task_without_due_date_advances_from_today(self):
        services.set_recurrence(self.item, Item.Recurrence.DAILY)
        completed = services.complete_item(self.item)
        expected = timezone.localdate() + datetime.timedelta(days=1)
        self.assertEqual(completed._spawned.due_date, expected)

    def test_monthly_recurrence_clamps_to_end_of_shorter_month(self):
        services.set_due_date(self.item, datetime.date(2026, 1, 31))
        services.set_recurrence(self.item, Item.Recurrence.MONTHLY)
        completed = services.complete_item(self.item)
        self.assertEqual(completed._spawned.due_date, datetime.date(2026, 2, 28))

    def test_set_recurrence_rejects_invalid_value(self):
        with self.assertRaises(services.TaskConflict):
            services.set_recurrence(self.item, "yearly")

    def test_notes_default_to_empty_and_round_trip(self):
        self.assertEqual(self.item.notes, "")

        noted = services.set_item_notes(self.item, "Ask about the warranty")

        self.assertEqual(noted.notes, "Ask about the warranty")

    def test_set_item_notes_strips_and_treats_blank_as_cleared(self):
        services.set_item_notes(self.item, "  Call first  ")
        self.item.refresh_from_db()
        self.assertEqual(self.item.notes, "Call first")

        services.set_item_notes(self.item, "   ")

        self.item.refresh_from_db()
        self.assertEqual(self.item.notes, "")

    def test_set_item_notes_rejects_an_archived_task(self):
        archived = services.archive_item(self.item)

        with self.assertRaises(services.InvalidTaskTransition):
            services.set_item_notes(archived, "Too late")

    def test_restoring_a_task_archived_while_active_returns_it_to_active(self):
        archived = services.archive_item(self.item)
        self.assertIsNone(archived.completed_at)

        restored = services.restore_item(archived)

        self.assertEqual(restored.status, Item.Status.ACTIVE)
        self.assertIsNone(restored.completed_at)
        self.assertIsNone(restored.archived_at)

    def test_restoring_a_task_archived_while_completed_returns_it_to_completed(self):
        completed = services.complete_item(self.item)
        completed_at = completed.completed_at

        archived = services.archive_item(completed)
        self.assertEqual(archived.completed_at, completed_at)

        restored = services.restore_item(archived)

        self.assertEqual(restored.status, Item.Status.COMPLETED)
        self.assertEqual(restored.completed_at, completed_at)
        self.assertIsNone(restored.archived_at)
