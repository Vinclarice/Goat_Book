from django.test import TestCase

from lists.forms import (
    EMPTY_TITLE_ERROR,
    EMPTY_ITEM_ERROR,
    ItemForm,
    ListTitleForm,
    NewListForm,
)
from lists.models import Item, List


class ItemFormTest(TestCase):
    def test_form_validation_for_blank_items(self):
        form = ItemForm(data={"text": ""})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["text"], [EMPTY_ITEM_ERROR])

    def test_form_save_handles_saving_to_a_list(self):
        mylist = List.objects.create()
        form = ItemForm(data={"text": "do me"})
        self.assertTrue(form.is_valid())
        new_item = form.save(for_list=mylist)
        self.assertEqual(new_item, Item.objects.get())
        self.assertEqual(new_item.text, "do me")
        self.assertEqual(new_item.list, mylist)


class NewListFormTest(TestCase):
    def test_saves_named_list_and_first_item_for_owner(self):
        from accounts.models import User

        owner = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )
        form = NewListForm(
            data={"title": "Programming", "text": "Learn Django"},
        )

        self.assertTrue(form.is_valid())
        new_list = form.save(owner=owner)

        self.assertEqual(new_list.title, "Programming")
        self.assertEqual(new_list.owner, owner)
        self.assertEqual(new_list.item_set.get().text, "Learn Django")

    def test_uses_first_item_as_name_when_title_is_omitted(self):
        from accounts.models import User

        owner = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )
        form = NewListForm(data={"title": "", "text": "Plan the weekend"})

        self.assertTrue(form.is_valid())
        new_list = form.save(owner=owner)

        self.assertEqual(new_list.title, "Plan the weekend")


class ListTitleFormTest(TestCase):
    def test_strips_and_saves_title(self):
        list_ = List.objects.create()
        form = ListTitleForm(data={"title": "  Home  "}, instance=list_)

        self.assertTrue(form.is_valid())
        form.save()

        list_.refresh_from_db()
        self.assertEqual(list_.title, "Home")

    def test_rejects_whitespace_only_title(self):
        form = ListTitleForm(data={"title": "   "}, instance=List())

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["title"], [EMPTY_TITLE_ERROR])
