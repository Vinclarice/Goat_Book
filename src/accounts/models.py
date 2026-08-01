import hashlib
import secrets

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models


class User(AbstractBaseUser, PermissionsMixin):
    username_validator = UnicodeUsernameValidator()

    email = models.EmailField(unique=True)
    username = models.CharField(
        max_length=150,
        unique=True,
        validators=[username_validator],
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    daily_digest = models.BooleanField(
        default=True,
        verbose_name="Email me a daily summary",
        help_text=(
            "A morning email listing anything overdue or due today. "
            "Nothing is sent on days when there's nothing to report."
        ),
    )

    class Theme(models.TextChoices):
        SYSTEM = "system", "Match my device"
        LIGHT = "light", "Light"
        DARK = "dark", "Dark"

    theme = models.CharField(
        max_length=6,
        choices=Theme.choices,
        default=Theme.SYSTEM,
    )

    objects = UserManager()

    REQUIRED_FIELDS = ["email"]
    USERNAME_FIELD = "username"

    def __str__(self):
        return self.username


def hash_token(raw):
    """SHA-256 rather than a password hasher, deliberately.

    A slow hash exists to make guessing a human-chosen password expensive.
    This is 32 bytes from `secrets`, so the key space already rules that
    out, and a fast hash is what lets every API request verify a token
    without a bcrypt round.
    """
    return hashlib.sha256(raw.encode()).hexdigest()


class PersonalAccessToken(models.Model):
    """How something that isn't a browser authenticates as a user.

    Only the hash is stored, the same way passwords are -- the raw value
    exists once, in the response to whoever created it, and cannot be
    recovered afterwards. Deleting the row is the whole of revocation:
    a revoked token and a deleted one are the same state, so there's no
    second `revoked` flag to keep in sync with it.
    """

    owner = models.ForeignKey(
        "accounts.User", related_name="tokens", on_delete=models.CASCADE
    )
    label = models.CharField(max_length=100, blank=True)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return self.label or f"Token {self.pk}"

    @staticmethod
    def generate(owner, label=""):
        """Returns (instance, raw). The raw value is available here and
        nowhere else, ever again.
        """
        raw = secrets.token_urlsafe(32)
        instance = PersonalAccessToken.objects.create(
            owner=owner, label=label, token_hash=hash_token(raw)
        )
        return instance, raw
