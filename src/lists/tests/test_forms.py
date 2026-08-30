from accounts.models import User
from django.test import TestCase

from lists.forms import (
    EMPTY_TITLE_ERROR,
    EMPTY_ITEM_ERROR,
    ItemForm,
    ListTitleForm,
)
from lists.models import Item, List


class ItemFormTest(TestCase):
    # List.owner is required since release D slice 6; these tests are about
    # the form rather than about ownership, so one owner covers the class.
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(
            username="formowner", email="formowner@example.com",
        )

    def test_form_validation_for_blank_items(self):
        form = ItemForm(data={"text": ""})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["text"], [EMPTY_ITEM_ERROR])

    def test_form_save_handles_saving_to_a_list(self):
        mylist = List.objects.create(owner=self.owner)
        form = ItemForm(data={"text": "do me"})
        self.assertTrue(form.is_valid())
        new_item = form.save(for_list=mylist)
        self.assertEqual(new_item, Item.objects.get())
        self.assertEqual(new_item.text, "do me")
        self.assertEqual(new_item.list, mylist)


# `class NewListFormTest` stood here until August 30, 2026, and NewListForm
# is gone with the view that was its only caller --
# coherence-audit-2026-08-30.md F1. Both cases it made are remade against
# the endpoint that replaced it, in
# lists.tests.test_api_v1.CreateAreaEndpointTest.


class ListTitleFormTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(
            username="titleowner", email="titleowner@example.com",
        )

    def test_strips_and_saves_title(self):
        list_ = List.objects.create(owner=self.owner)
        form = ListTitleForm(data={"title": "  Home  "}, instance=list_)

        self.assertTrue(form.is_valid())
        form.save()

        list_.refresh_from_db()
        self.assertEqual(list_.title, "Home")

    def test_rejects_whitespace_only_title(self):
        form = ListTitleForm(data={"title": "   "}, instance=List())

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["title"], [EMPTY_TITLE_ERROR])
