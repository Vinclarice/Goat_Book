import hashlib
import secrets
from datetime import timedelta
import uuid
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


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

    # When this person asked to be erased, or null. A field rather than a
    # model, so architecture-trajectory.md §4's charter test does not apply --
    # it has exactly the User's life cycle, one value per person.
    #
    # **Deliberately not `is_active`.** That flag already means "pending admin
    # approval", and one flag meaning two unrelated things is indistinguishable
    # in the admin and in every login path. The account also stays fully usable
    # while this is set, which is what keeps *cancel* reachable: they log in and
    # press the button, and no signed-link email flow has to exist for a window
    # that is theirs to close.
    #
    # `accounts.services.ACCOUNT_DELETION_GRACE` turns this into a date; nothing
    # is destroyed until `purge_deleted_accounts` reaches it.
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
    # **Two gates, and one flag cannot hold both.** Confirming an address and
    # being approved are separate facts: a confirmed stranger is still a
    # stranger, and an account approved before anyone proved they own the
    # address is approved on the strength of something typed into a form.
    # `is_active` answers "may this account be used", which is approval; this
    # answers "did somebody prove they read mail at that address".
    #
    # A timestamp rather than a boolean, for the same reason as the field
    # above: the *when* is the durable record, and "confirmed" is derivable
    # from it while the reverse is not. It is also what tells an admin looking
    # at a pending account whether the person confirmed a minute or a month
    # ago.
    #
    # Signed into the activation token (accounts.tokens), which is what makes
    # a confirmation link single-use.
    email_confirmed_at = models.DateTimeField(null=True, blank=True)

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
    # **Off by default, unlike the digest above it.** A second recurring
    # message is a different thing to agree to, and turning one on is a
    # smaller ask than discovering one -- more so because `/privacy/` said in
    # published text that the daily summary was "the one recurring message".
    # That sentence is amended alongside this field rather than left to
    # contradict the code.
    closing_nudge = models.BooleanField(
        default=False,
        verbose_name="Email me an evening nudge to close the day",
        help_text=(
            "An evening email with what the day held, asking what happened "
            "while it is still true. Nothing is sent once you have written "
            "the day."
        ),
    )
    last_closing_nudge_date = models.DateField(
        null=True, blank=True, editable=False
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

    @classmethod
    def from_db(cls, db, field_names, values):
        """Remember whether this account was active when it was loaded.

        Approval is a transition, not a state: `is_active` stays True for the
        rest of an account's life and `last_login` is written on every sign-in,
        so "saved and active" fires forever. Recording the loaded value here is
        what lets accounts.apps tell the one save that opened the account from
        the thousands that follow it, and it costs nothing -- no extra query,
        just the value the row already carried.

        Absent on an instance that was never loaded from the database, which is
        why the reader uses getattr with a default rather than trusting it.
        """
        instance = super().from_db(db, field_names, values)
        instance._loaded_is_active = instance.is_active
        return instance

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


# What a token is actually allowed to do -- see token-scopes-plan.md. Named
# one at a time, per resource, as each client feature actually needs one;
# not pre-declared for surfaces that don't exist yet.
SCOPE_CAPTURE_WRITE = "capture:write"
SCOPE_IDENTITY_READ = "identity:read"
SCOPE_DAY_READ = "day:read"
# agenda:write covers exactly create_item and item_detail's status/due_date
# fields -- not text/tags/recurrence/notes, and never DELETE. See
# token-scopes-plan.md §7 for the endpoint-level guard that enforces the
# narrower boundary; the scope name itself is deliberately no more precise
# than that, matching this file's existing per-surface granularity.
SCOPE_AGENDA_READ = "agenda:read"
SCOPE_AGENDA_WRITE = "agenda:write"
# day:write covers pin_to_day, unpin_from_day and write_day (daily/api_v1.py)
# -- choosing today's focus and writing the day's own Intentions/Grateful
# for/Happenings text. routines:write is the sibling scope for the whole of
# routines/api_v1.py's six mutations (create/log/skip/enough/pause/resume) --
# a separate scope because it's a structurally separate Ninja router, the
# same reasoning that kept agenda:write scoped to lists.api rather than
# folded into day:write.
SCOPE_DAY_WRITE = "day:write"
SCOPE_ROUTINES_WRITE = "routines:write"

ALL_SCOPES = (
    SCOPE_CAPTURE_WRITE,
    SCOPE_IDENTITY_READ,
    SCOPE_DAY_READ,
    SCOPE_AGENDA_READ,
    SCOPE_AGENDA_WRITE,
    SCOPE_DAY_WRITE,
    SCOPE_ROUTINES_WRITE,
)

# What POST /api/v1/login mints for the Android client without asking
# anyone to pick scopes to log in -- picking scopes belongs to the web's
# manual token-creation form, not to signing into the app you're holding.
ANDROID_DEFAULT_SCOPES = (
    SCOPE_CAPTURE_WRITE,
    SCOPE_IDENTITY_READ,
    SCOPE_DAY_READ,
    SCOPE_AGENDA_READ,
    SCOPE_AGENDA_WRITE,
    SCOPE_DAY_WRITE,
    SCOPE_ROUTINES_WRITE,
)

# How long a login-minted Android token lasts before its holder has to sign
# in again -- bounding a lost phone's exposure the way an unscoped, never-
# expiring token never did. Matches the middle option the web's own picker
# offers (token-scopes-plan.md §3), not a separate policy invented here.
ANDROID_TOKEN_LIFETIME = timedelta(days=90)

# What every token minted before scopes existed keeps being able to do,
# applied by the migration that adds the column -- nobody's phone stops
# working, and nobody's pre-existing token silently gains day:read it was
# never granted. See token-scopes-plan.md §3's grandfathering.
GRANDFATHERED_SCOPES = (SCOPE_CAPTURE_WRITE, SCOPE_IDENTITY_READ)


def _encode_scopes(scopes):
    return ",".join(sorted(set(scopes)))


class PersonalAccessToken(models.Model):
    """How something that isn't a browser authenticates as a user.

    Only the hash is stored, the same way passwords are -- the raw value
    exists once, in the response to whoever created it, and cannot be
    recovered afterwards. Deleting the row is the whole of revocation:
    a revoked token and a deleted one are the same state, so there's no
    second `revoked` flag to keep in sync with it.

    `scopes` is a sorted, comma-joined `TextField` rather than
    `django.contrib.postgres.fields.ArrayField`: production runs Postgres,
    but local dev and CI default to SQLite
    (`clarice/settings.py`, `DJANGO_DATABASE_URL` unset), and `ArrayField`
    has no SQLite backend at all. Nothing here ever queries *by* scope --
    only an in-process membership check after a token has already
    resolved -- so a plain text column loses nothing a real array type
    would have earned.
    """

    owner = models.ForeignKey(
        "accounts.User", related_name="tokens", on_delete=models.CASCADE
    )
    label = models.CharField(max_length=100, blank=True)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    scopes = models.TextField(blank=True)
    # Null means "never expires" -- kept that way for every row that
    # existed before this field did, rather than reinterpreted, so a
    # migration cannot silently expire somebody's already-working token.
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return self.label or f"Token {self.pk}"

    @property
    def scope_set(self):
        return set(filter(None, self.scopes.split(",")))

    def has_scope(self, scope):
        return scope in self.scope_set

    def is_expired(self):
        return self.expires_at is not None and self.expires_at < timezone.now()

    @staticmethod
    def generate(owner, label="", scopes=(), expires_at=None):
        """Returns (instance, raw). The raw value is available here and
        nowhere else, ever again.

        `scopes` defaults to none, not to "everything" -- a call site that
        forgets to pass it produces a token that can do nothing, which is a
        safe failure mode rather than a dangerous one.
        """
        raw = secrets.token_urlsafe(32)
        instance = PersonalAccessToken.objects.create(
            owner=owner,
            label=label,
            token_hash=hash_token(raw),
            scopes=_encode_scopes(scopes),
            expires_at=expires_at,
        )
        return instance, raw


class Invitation(models.Model):
    """A link that makes an account without a person in the loop — **S1**.

    S1's last require was *approval that is not a person*, and this is the
    answer taken on August 23, 2026. Vince mints one, whoever holds it signs up,
    and the account works immediately: the approval happened when the link was
    made, so there is a person in the story and **nobody in the loop**.

    **Not public self-service**, which was the other way to close it and is five
    lines. Refused because the posture answered on August 20 is *personal tool
    with an intent to invite*, and because terms and a privacy policy are still
    unwritten — opening signup to strangers before those exist would be
    collecting other people's data with nothing published about what happens to
    it.

    **It earns its own model**, by §4's test rather than by having a name.
    `accounts/tokens.py` is stateless on the argument that *"a token whose whole
    existence is 'this URL is valid until it is used' has no life cycle at
    all."* An invitation does have one — minted, held, redeemed or expired or
    revoked — and it is worth listing: *who have I invited, and did they come?*
    is a question only a table answers.

    **Charter compliance** (`architecture-trajectory.md` §4):

    - Rule 1, owned at birth: `created_by` is non-null from this migration.
    - Rule 2, public identifier: `public_id`, and here it is also the
      credential. A UUID4 is 122 bits of randomness, so guessing one is not a
      threat; what it buys over a hashed secret is that the link stays
      **re-displayable**, and a lost link that nobody can see is dead is worse
      than one that can be read off the page again.
    - Rule 3, snapshot: none needed. Nothing here is a copy of something that
      can change underneath it.
    - Rule 6, deletion: **revoked, not deleted.** Deleting the row would make
      *who have I invited* quietly unanswerable, which is the question the model
      exists for.
    """

    #: Fourteen days. Long enough to survive a holiday, short enough that a
    #: forwarded link found in an old inbox is dead. The window is the whole
    #: protection, since holding the link is all it takes to use it.
    LIFETIME = timedelta(days=14)

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(
        "accounts.User", related_name="invitations_sent", on_delete=models.CASCADE
    )
    #: Who it is for, in Vince's own words.
    #:
    #: **Not an email address, deliberately.** Binding the invitation to one
    #: means a typo kills it and a forward is refused, and he already chooses
    #: who to send it to. This is so *he* can tell two open invitations apart a
    #: fortnight later.
    note = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    redeemed_at = models.DateTimeField(null=True, blank=True)
    redeemed_by = models.ForeignKey(
        "accounts.User",
        related_name="invitation_used",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + self.LIFETIME
        return super().save(*args, **kwargs)

    @property
    def is_usable(self) -> bool:
        return (
            self.redeemed_at is None
            and self.revoked_at is None
            and self.expires_at > timezone.now()
        )

    @property
    def path(self) -> str:
        """The invitation's own URL path. Absolute URLs need a request."""
        from django.urls import reverse

        return reverse("join", kwargs={"public_id": self.public_id})

    def __str__(self):
        who = self.note or "someone"
        return f"invitation for {who} ({'live' if self.is_usable else 'spent'})"
