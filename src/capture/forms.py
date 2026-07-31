from django import forms

from capture.models import Capture

EMPTY_CAPTURE_ERROR = "Write something down first"


class CaptureForm(forms.Form):
    # A Textarea rather than a TextInput because captures are sentences as
    # often as they're fragments, and autofocus because the page exists to
    # be typed into -- one keystroke of friction is the whole cost model
    # for a capture box.
    text = forms.CharField(
        label="Capture",
        error_messages={"required": EMPTY_CAPTURE_ERROR},
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "autofocus": True,
                "placeholder": "What's on your mind?",
            },
        ),
    )

    # No clean_text: CharField strips by default, so a whitespace-only
    # capture arrives here as "" and the required error above covers it.

    def save(self, owner):
        return Capture.objects.create(owner=owner, text=self.cleaned_data["text"])
