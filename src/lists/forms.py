from django import forms
from django.core.exceptions import ValidationError

from lists.models import Item, List
from lists.services import (
    DUPLICATE_ITEM_ERROR,
    EMPTY_ITEM_ERROR,
    TaskConflict,
    create_item,
    create_list_with_item,
    edit_item,
)

EMPTY_TITLE_ERROR = "Give this list a name"


class ItemForm(forms.Form):
    text = forms.CharField(
        error_messages={"required": EMPTY_ITEM_ERROR},
        required=True,
    )

    def save(self, for_list):
        return create_item(for_list, self.cleaned_data["text"])


class NewListForm(ItemForm):
    title = forms.CharField(max_length=100, required=False)

    def clean_title(self):
        return self.cleaned_data["title"].strip()

    def save(self, owner):
        return create_list_with_item(
            owner,
            self.cleaned_data["title"],
            self.cleaned_data["text"],
        )


class ListTitleForm(forms.ModelForm):
    title = forms.CharField(
        max_length=100,
        error_messages={"required": EMPTY_TITLE_ERROR},
    )

    class Meta:
        model = List
        fields = ("title",)

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if not title:
            raise ValidationError(EMPTY_TITLE_ERROR)
        return title


class ExistingListItemForm(ItemForm):
    def __init__(self, for_list, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._for_list = for_list

    def clean_text(self):
        text = self.cleaned_data["text"]
        if self._for_list.item_set.exclude(
            status=Item.Status.ARCHIVED,
        ).filter(
            text=text,
        ).exists():
            raise forms.ValidationError(DUPLICATE_ITEM_ERROR)
        return text

    def save(self):
        return super().save(for_list=self._for_list)


class TaskTextForm(ItemForm):
    def __init__(self, for_item, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._for_item = for_item
        self.fields["text"].initial = for_item.text

    def clean_text(self):
        text = self.cleaned_data["text"].strip()
        duplicates = self._for_item.list.item_set.exclude(
            status=Item.Status.ARCHIVED,
        ).exclude(pk=self._for_item.pk).filter(text=text)
        if duplicates.exists():
            raise forms.ValidationError(DUPLICATE_ITEM_ERROR)
        return text

    def save(self):
        try:
            return edit_item(self._for_item, self.cleaned_data["text"])
        except TaskConflict as error:
            raise ValidationError(str(error)) from error
