from django import forms
from django.core.exceptions import ValidationError

from lists.models import List
from lists.services import EMPTY_ITEM_ERROR, create_item, create_list_with_item

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


