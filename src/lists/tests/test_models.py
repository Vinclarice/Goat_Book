from accounts.models import User
from django.test import TestCase
from lists.models import Item, List
from django.db import IntegrityError
from django.core.exceptions import ValidationError


class ItemModelTest(TestCase):
    def test_default_text(self):
        item = Item()
        self.assertEqual(item.text, "")

    def test_item_is_related_to_list(self):
        mylist = List.objects.create()
        item = Item()
        item.list = mylist
        item.save()
        self.assertIn(item, mylist.item_set.all())

    def test_cannot_save_empty_list_items(self):
        mylist = List.objects.create()
        item = Item(list=mylist, text=None)
        with self.assertRaises(IntegrityError):
            item.save()

    def test_cannot_save_empty_list_items_validation(self):
        mylist = List.objects.create()
        item = Item(list=mylist, text="")
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_duplicate_items_are_invalid(self):
        mylist = List.objects.create()
        Item.objects.create(list=mylist, text="bla")
        with self.assertRaises(ValidationError):
            item = Item(list=mylist, text="bla")
            item.full_clean()

    def test_CAN_save_same_item_to_different_lists(self):
        list1 = List.objects.create()
        list2 = List.objects.create()
        Item.objects.create(list=list1, text="bla")
        item = Item(list=list2, text="bla")
        item.full_clean()  # should not raise

    def test_string_representation(self):
        item = Item(text="some text")
        self.assertEqual(str(item), "some text")

    def test_new_items_record_creation_time_and_start_incomplete(self):
        item = Item.objects.create(list=List.objects.create(), text="New task")

        self.assertIsNotNone(item.created_at)
        self.assertIsNotNone(item.updated_at)
        self.assertEqual(item.status, Item.Status.ACTIVE)
        self.assertIsNone(item.completed_at)
        self.assertIsNone(item.archived_at)

    def test_archived_item_does_not_block_reusing_its_text(self):
        mylist = List.objects.create()
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
    def test_get_absolute_url(self):
        mylist = List.objects.create()
        self.assertEqual(mylist.get_absolute_url(), f"/lists/{mylist.id}/")

    def test_list_items_order(self):
        list1 = List.objects.create()
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

    def test_list_owner_is_optional(self):
        List.objects.create()  # should not raise

    def test_list_name_is_its_title(self):
        list_ = List.objects.create(title="Programming")
        self.assertEqual(list_.title, "Programming")

    def test_empty_list_has_fallback_name(self):
        self.assertEqual(List.objects.create().title, "Untitled list")
