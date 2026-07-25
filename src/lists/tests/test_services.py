from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from lists import services
from lists.models import Item, List


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
        self.assertIsNotNone(archived.completed_at)
        self.assertIsNotNone(archived.archived_at)

        restored = services.restore_item(archived)
        self.assertEqual(restored.status, Item.Status.COMPLETED)
        self.assertIsNotNone(restored.completed_at)
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
