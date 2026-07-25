from django.contrib.auth.forms import UserCreationForm
from django import forms

from accounts.models import User


class SignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class AccountSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "email")

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
