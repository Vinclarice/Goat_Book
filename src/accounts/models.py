import hashlib
import secrets
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.db import models


# What every user's day meant before this field existed, so adding the
# field changes nobody's semantics. Deliberately a literal rather than a
# read of settings.TIME_ZONE: this is a historical fact about existing
# rows, and changing the setting later must not silently redefine the day
# for people who never chose anything.
DEFAULT_TIME_ZONE = "America/New_York"


@lru_cache(maxsize=1)
def known_time_zones():
    """Every IANA key this server can resolve, sorted.

    Cached because available_timezones() walks the whole tzdata tree on
    each call, and the answer can only change when the image does.
    """
    return tuple(sorted(available_timezones()))


def validate_time_zone(value):
    """Insist a stored zone is one the server can actually resolve.

    A validator rather than `choices=`: Django writes choices into the
    migration file, so ~600 zone names would be inlined into it and churn
    every time tzdata ships a release. The picker offers the list; the
    model only insists the key is real.
    """
    if value not in known_time_zones():
        raise ValidationError(
            "%(value)s is not a known time zone.",
            code="unknown_time_zone",
            params={"value": value},
        )


def resolve_time_zone(key):
    """The ZoneInfo for a stored key, or None if it no longer resolves.

    Callers fall back to settings.TIME_ZONE. tzdata does occasionally
    retire a zone, and that must not break the day for whoever held it --
    in a request it would be a 500 on every page, and in the digest it
    would stop the run for everyone after them.
    """
    try:
        return ZoneInfo(key)
    except (ZoneInfoNotFoundError, ValueError):
        return None


class User(AbstractBaseUser, PermissionsMixin):
    username_validator = UnicodeUsernameValidator()

    class LandingSurface(models.TextChoices):
        DAY = "day", "Today's page"
        AGENDA = "agenda", "Agenda"

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

    # The Personal Compass: the paper template's standing purpose and
    # guiding question, re-read every morning rather than answered again.
    # Fields on the user rather than a model of their own, per the test in
    # architecture-trajectory.md §4 -- a concept earns a model when it has a
    # different life cycle, and this one has exactly the User's: one per
    # person, for as long as the person exists. Blank rather than null for
    # the same reason as Item.notes: "never written" and "cleared" are the
    # same state and nothing should have to handle both.
    #
    # Deliberately not on DailyEntry. roadmap.md keeps the Compass separate
    # from a day's Intentions, and copying it onto each day would make
    # editing it rewrite history -- see daily/tests/test_compass.py.
    # Where a session lands. Defaulted to the Daily Page because Crane makes
    # it the home surface and the product should take a position; settable
    # because the screen somebody opens every morning is a poor place to be
    # told they are wrong about their own workflow. Decided August 2, 2026 --
    # see crane-plan.md §6.
    #
    # Read in exactly one place, lists.views.dashboard, which is
    # LOGIN_REDIRECT_URL -- so every way in agrees without any of them
    # knowing the rule.
    landing_surface = models.CharField(
        max_length=10,
        choices=LandingSurface.choices,
        default=LandingSurface.DAY,
        verbose_name="Start me on",
        help_text="Where Clarice opens when you sign in.",
    )

    compass_purpose = models.TextField(
        blank=True,
        default="",
        verbose_name="Purpose",
        help_text="Why this work matters. Shown on every day's page.",
    )
    compass_question = models.TextField(
        blank=True,
        default="",
        verbose_name="Guiding question",
        help_text="The question worth asking each morning.",
    )

    time_zone = models.CharField(
        max_length=64,
        default=DEFAULT_TIME_ZONE,
        validators=[validate_time_zone],
        verbose_name="Time zone",
        help_text=(
            "Decides when your day starts and ends: what counts as overdue "
            "or due today, what the snooze options mean, and when the daily "
            "summary arrives."
        ),
    )
    # The user's *own* local date the digest was last sent for, which is
    # what makes an hourly job safe to run: a retried run, a restarted
    # container, or a DST repeat all find the day already handled. Not
    # editable -- it is a record of what happened, not a preference.
    last_digest_date = models.DateField(null=True, blank=True, editable=False)

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
