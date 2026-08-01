from django import forms

from capture.services import EMPTY_CAPTURE_ERROR, EMPTY_IDEA_ERROR, create_capture

# Re-exported: this was the constant's home before the API needed the same
# rule, and it reads more naturally next to the form that shows it.
__all__ = ["EMPTY_CAPTURE_ERROR", "CaptureForm", "IdeaForm"]


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
    # capture arrives here as "" and the required error above covers it --
    # the same rule services.normalize_capture_text enforces for the API,
    # which is why create_capture is what actually writes the row.

    def save(self, owner):
        return create_capture(owner, self.cleaned_data["text"])


class IdeaForm(forms.Form):
    """Editing an idea in place on the Ideas page.

    Two fields rather than one because an idea's notes are where it
    actually develops -- the text stays the one-line thing you captured,
    and the thinking accumulates underneath it.
    """

    text = forms.CharField(
        label="Idea",
        error_messages={"required": EMPTY_IDEA_ERROR},
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    notes = forms.CharField(
        label="Notes",
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 3, "placeholder": "Anything worth remembering…"},
        ),
    )
