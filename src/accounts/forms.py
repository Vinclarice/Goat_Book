from datetime import timedelta

from django.contrib.auth import authenticate
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserChangeForm,
    UserCreationForm,
)
from django import forms
from django.utils import timezone

from accounts.models import (
    SCOPE_AGENDA_READ,
    SCOPE_AGENDA_WRITE,
    SCOPE_CAPTURE_WRITE,
    SCOPE_DAY_READ,
    SCOPE_DAY_WRITE,
    SCOPE_IDENTITY_READ,
    SCOPE_ROUTINES_WRITE,
    User,
)


class LoginForm(AuthenticationForm):
    """Distinguishes "wrong password" from "correct password, but this address
    has not been confirmed yet" -- without leaking whether a username exists to
    anyone who doesn't already know its password.

    Django's ModelBackend never returns inactive users from authenticate(),
    so the normal AuthenticationForm.confirm_login_allowed() hook (which is
    where the built-in "inactive" message lives) never actually runs for
    them; this overrides clean() to check for that case directly instead.

    **The message names the way out.** It used to say an admin would approve
    the account, which stopped being true when confirming an address became the
    only gate -- and the older wording had no next step in it at all, so
    somebody whose mail never arrived was told to wait for something that was
    never going to happen. The template turns `unconfirmed` into a link to
    `resend_activation`.
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        "unconfirmed": (
            "This account's email address hasn't been confirmed yet. Check "
            "your inbox for the confirmation link, or ask for a new one."
        ),
        "awaiting_approval": (
            "Thanks for confirming your email. Clarice is invitation-only "
            "while it's being built, so your account is waiting to be "
            "approved — we'll write to you when it's ready."
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
                    # Two different waits, and telling somebody the wrong one
                    # is the whole complaint about the flow this replaced:
                    # "confirm your email" to a person who already did sends
                    # them hunting for a link that will not work, and "we are
                    # reviewing it" to a person who never confirmed leaves them
                    # waiting on a queue they are not in.
                    code = (
                        "awaiting_approval"
                        if pending_user.email_confirmed_at is not None
                        else "unconfirmed"
                    )
                    raise forms.ValidationError(
                        self.error_messages[code], code=code
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
        # Inactive until the address is confirmed. `is_active` means
        # "verified" now rather than "approved" -- there is no admin step --
        # and it stays the field the login form checks because it is still
        # exactly the question being asked: may this account be used yet.
        user = super().save(commit=False)
        user.is_active = False
        if commit:
            user.save()
        return user


class AdminUserCreationForm(UserCreationForm):
    """Like SignUpForm, but for admins adding accounts directly: an address an
    admin typed needs no confirming, so is_active keeps its normal default.
    """

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class AdminUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


class TokenForm(forms.Form):
    """A label, what it's allowed to do, and how long it lasts. The token
    value itself is generated server-side and never submitted by anyone.

    Scope is required with nothing pre-checked -- token-scopes-plan.md's
    least-privilege default: an explicit choice every time, not a sensible-
    looking default somebody could rubber-stamp without reading. Expiry
    defaults to the shortest real option rather than "never", the same
    reasoning in reverse.
    """

    SCOPE_CHOICES = [
        (SCOPE_CAPTURE_WRITE, "Write captures — post a new thought to the Inbox"),
        (
            SCOPE_IDENTITY_READ,
            "Read your identity — confirm which account this token belongs to",
        ),
        (
            SCOPE_DAY_READ,
            "Read your Daily Page — today's focus, action items, routines and Compass",
        ),
        (SCOPE_AGENDA_READ, "Read your Agenda — every open task across every area"),
        (
            SCOPE_AGENDA_WRITE,
            "Complete, reopen or reschedule a task, and add new ones — nothing else "
            "about a task (its text, tags, notes or recurrence) can be changed this way",
        ),
        (
            SCOPE_DAY_WRITE,
            "Choose today's focus and write the day's own Intentions, Grateful for "
            "and Happenings",
        ),
        (
            SCOPE_ROUTINES_WRITE,
            "Log, skip, pause, resume or call a routine's period enough, and keep new "
            "routines",
        ),
    ]

    # Values are the field's own vocabulary, checked in expires_at() below
    # rather than trusted as literal day counts from anywhere else.
    EXPIRY_CHOICES = [
        ("90", "In 90 days"),
        ("365", "In 1 year"),
        ("never", "Never — not recommended"),
    ]

    label = forms.CharField(
        label="What's it for?",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Phone"}),
    )
    scopes = forms.MultipleChoiceField(
        label="What can it do?",
        choices=SCOPE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
    )
    expiry = forms.ChoiceField(
        label="Expires",
        choices=EXPIRY_CHOICES,
        initial="90",
    )

    def expires_at(self):
        """None for "never expires"; a real datetime otherwise. Computed
        here, the one place that knows what each choice means, rather than
        left for the view to reinterpret.
        """
        choice = self.cleaned_data["expiry"]
        if choice == "never":
            return None
        return timezone.now() + timedelta(days=int(choice))


class ContactForm(forms.Form):
    """The one public form a stranger can reach, so every field is hostile
    input until validated.

    Nothing collected here reaches a mail header. The name and message are
    rendered into the body and the only header built from user input is
    Reply-To, from an address EmailField has already validated. That is
    what makes header injection impossible rather than merely filtered --
    there is no code path that concatenates typed text into a header for a
    newline to break out of.
    """

    name = forms.CharField(label="Your name", max_length=100)
    email = forms.EmailField(label="Your email")
    message = forms.CharField(
        label="Message",
        max_length=5000,
        widget=forms.Textarea(attrs={"rows": 6}),
    )
    # Honeypot. Hidden from people and irresistible to form-fillers, so a
    # value here is never an accident. Named for plausibility rather than
    # accuracy: "website" is a field a bot expects to find.
    website = forms.CharField(
        label="Website",
        required=False,
        widget=forms.HiddenInput,
    )

    @property
    def looks_automated(self):
        return bool(self.cleaned_data.get("website"))


class AccountSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        # time_zone belongs here rather than only on the API schema: the
        # endpoint validates through this form precisely so the two paths
        # cannot enforce different rules, and being a model field it picks
        # up validate_time_zone for free.
        # The compass fields ride along for the same reason time_zone does:
        # the endpoint validates through this form so there is one place
        # where "what a settings save accepts" is defined. Both are
        # blank=True on the model, so a person who has never written one
        # saves the rest of the page without being asked for it.
        fields = (
            "username",
            "email",
            "daily_digest",
            "closing_nudge",
            "time_zone",
            "compass_purpose",
            "compass_question",
        )
        # landing_surface is deliberately absent, following `theme`: both are
        # a closed set of values with a default and no cross-field rule, so
        # the API's Literal already validates them and a required ModelForm
        # field would only mean every caller had to restate a preference it
        # was not changing.

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
