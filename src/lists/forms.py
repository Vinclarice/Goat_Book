from django import forms
from django.core.exceptions import ValidationError
from django.utils.formats import date_format

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


class QuickAddForm(forms.Form):
    """Adds a task to any of the user's lists from the agenda page.

    The list choices are built from the owner rather than trusted from
    the POST, so a guessed list id belonging to someone else can't be
    submitted.
    """

    text = forms.CharField(
        error_messages={"required": EMPTY_ITEM_ERROR},
        required=True,
    )
    due_date = forms.DateField(required=False)

    def __init__(self, owner, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._owner = owner
        self.fields["list"] = forms.ModelChoiceField(
            queryset=List.objects.filter(owner=owner).order_by("id"),
            empty_label=None,
            error_messages={"required": "Choose a list for this task."},
        )

    def clean_text(self):
        return self.cleaned_data["text"].strip()

    def clean(self):
        cleaned = super().clean()
        for_list = cleaned.get("list")
        text = cleaned.get("text")
        if for_list is None or not text:
            return cleaned
        if for_list.item_set.exclude(
            status=Item.Status.ARCHIVED,
        ).filter(text=text).exists():
            self.add_error("text", DUPLICATE_ITEM_ERROR)
        return cleaned

    def save(self):
        return create_item(
            self.cleaned_data["list"],
            self.cleaned_data["text"],
            due_date=self.cleaned_data["due_date"],
        )


class DueDateForm(forms.Form):
    """Reschedules a single task. An empty value clears the due date."""

    due_date = forms.DateField(required=False)

    def confirmation_for(self, item):
        due_date = self.cleaned_data["due_date"]
        if due_date is None:
            return f'Cleared the due date on "{item.text}".'
        # date_format keeps this working on Windows, where strftime has
        # no portable "no leading zero" directive.
        return f'"{item.text}" is now due {date_format(due_date, "M j")}.'


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
