from django.contrib.auth import authenticate
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserChangeForm,
    UserCreationForm,
)
from django import forms

from accounts.models import User


class LoginForm(AuthenticationForm):
    """Distinguishes "wrong password" from "correct password, but the
    account is still pending admin approval" -- without leaking whether a
    username exists to anyone who doesn't already know its password.

    Django's ModelBackend never returns inactive users from authenticate(),
    so the normal AuthenticationForm.confirm_login_allowed() hook (which is
    where the built-in "inactive" message lives) never actually runs for
    them; this overrides clean() to check for that case directly instead.
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        "pending_approval": (
            "This account hasn't been approved yet. You'll be able to log "
            "in once an admin approves it."
        ),
    }

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username is not None and password:
            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password,
            )
            if self.user_cache is None:
                pending_user = (
                    User.objects.filter(username=username, is_active=False)
                    .first()
                )
                if pending_user and pending_user.check_password(password):
                    raise forms.ValidationError(
                        self.error_messages["pending_approval"],
                        code="pending_approval",
                    )
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class SignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def save(self, commit=True):
        # Self-service signups start inactive; an admin approves them from
        # /admin/ (see accounts.views.signup and accounts.emails).
        user = super().save(commit=False)
        user.is_active = False
        if commit:
            user.save()
        return user


class AdminUserCreationForm(UserCreationForm):
    """Like SignUpForm, but for admins adding accounts directly: those
    accounts don't need approval, so is_active keeps its normal default.
    """

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class AdminUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


class TokenForm(forms.Form):
    """Just a label. The token itself is generated server-side and never
    submitted by anyone, so there's nothing else to collect.
    """

    label = forms.CharField(
        label="What's it for?",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Phone"}),
    )


class AccountSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        # time_zone belongs here rather than only on the API schema: the
        # endpoint validates through this form precisely so the two paths
        # cannot enforce different rules, and being a model field it picks
        # up validate_time_zone for free.
        fields = ("username", "email", "daily_digest", "time_zone")

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
