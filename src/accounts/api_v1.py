"""Ninja router registered onto clarice.api's /api/v1/ contract.

Password/security changes stay Django-owned (accounts.views.change_password)
-- this is only the fields AccountSettingsForm already covers, plus theme.
"""
from datetime import datetime
from typing import Literal

from axes.handlers.proxy import AxesProxyHandler
from axes.helpers import get_credentials, get_failure_limit
from axes.utils import reset as axes_reset
from django.contrib.auth import authenticate, logout
from django_otp import match_token
from django.http import HttpResponse
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from accounts import export
from accounts import pairing
from accounts import services as account_services
from accounts.forms import AccountSettingsForm
from accounts.mfa import has_a_second_factor
from accounts.models import (
    ANDROID_DEFAULT_SCOPES,
    ANDROID_TOKEN_LIFETIME,
    PersonalAccessToken,
    User,
    known_time_zones,
)

router = Router()


class LoginIn(Schema):
    username: str
    password: str
    label: str = "Android"
    totp: str = ""
    """The second factor, when the account has one — a TOTP code or a recovery
    token.

    **Optional, and that is not a bypass.** An account with nothing armed never
    reaches the check that reads this, so the field changes nothing for the
    people who have no factor; an account *with* one is refused unless this
    verifies. Optional here means *not everybody has a second factor*, not
    *the second factor is skippable*.

    A plain string rather than an int: recovery tokens from `otp_static` are
    not digits, and a TOTP code with a leading zero stops being six characters
    the moment anything treats it as a number.
    """


class LoginOut(Schema):
    token: str
    username: str
    email: str


#: Named rather than inlined so this message and the test's assertion cannot
#: drift apart.
#:
#: ~~and so the reversal this plan promises -- "the day a signed release can
#: carry a TOTP field" -- has one place to happen.~~ **That reversal happened
#: on September 6, 2026, and without the signed release** -- the trigger was
#: never the keystore. The argument is at `log_in` below and the decision is
#: `roadmap.md`'s M1.
#:
#: **The Android client keeps no copy of either string**, which is why the
#: first half of the old note is gone too. It reads `detail` off the response
#: body (`ClariceApi.parseDetail`), so the sentence somebody reads on the
#: phone is this one, and there is nothing on that side to keep in sync.
SECOND_FACTOR_REQUIRED = (
    "This account has a second factor. Enter the code from your authenticator "
    "app, or one of your recovery codes."
)
#: Wrong code, right password. Separate from the message above because they
#: ask for different things: one says *there is a box you have not filled*, and
#: the other says *what you put in it did not match*. One message for both
#: would leave somebody re-typing a correct code into a field they had not
#: realised was already being read.
SECOND_FACTOR_INCORRECT = (
    "That code did not match. Codes expire after about thirty seconds, so try "
    "the current one."
)


# `has_a_second_factor` ~~was defined here~~ -- **moved to `accounts/mfa.py` on
# September 7, 2026**, when `/pair/` needed the same answer before demanding a
# verified session. Two doors disagreeing about what *has a second factor*
# means is one of them becoming a way around the other, so it is imported at
# the top of this module rather than copied.


@router.post("/login", response={200: LoginOut}, auth=None)
def log_in(request, payload: LoginIn):
    """Trade a password for a token, once. design/android-login-plan.md.

    Unauthenticated on purpose -- this is how the Android app gets its
    first token instead of requiring someone to paste one created on the
    web. Routed through authenticate() rather than a hand-rolled check so
    axes' five-attempts lockout (AUTHENTICATION_BACKENDS, accounts/apps.py)
    covers this exactly as it already covers the web login form; a
    hand-rolled check here would be a second place that protection could
    drift from the first.

    One generic 401 for every failure -- wrong password, no such account,
    or a deactivated one -- deliberately indistinguishable, the same as the
    web login form gives away nothing about which part was wrong. The
    attempts-remaining count in the message is safe alongside that: axes
    counts by the username string typed, real account or not, so a made-up
    username counts down exactly the same way a real one does.
    """
    user = authenticate(request, username=payload.username, password=payload.password)
    if user is None:
        raise HttpError(401, _incorrect_credentials_message(request, payload.username))
    # AXES_RESET_ON_SUCCESS fires on Django's user_logged_in signal, which
    # this endpoint never sends -- it mints a token rather than starting a
    # session, deliberately, so there is nothing to log out of later.
    # Cleared explicitly instead, the same way
    # ClearLockoutPasswordResetConfirmView already does after a reset.
    axes_reset(username=user.username)
    # **The other door -- `admin-mfa-plan.md` 2.1.** This endpoint starts no
    # session, so every session-based gate misses it: a second factor on
    # `/admin/` while a password alone still mints a ninety-day token is a
    # second factor on one of two doors.
    #
    # ~~**Refused rather than extended.** The obvious fix is a `totp` field and
    # a third box on the Connect screen, and it is not merely more work, it is
    # unavailable: `assembleRelease` produces nothing usable until the signing
    # keystore exists... Accepting a field no shipped client can send would
    # leave the bypass open for as long as the keystore does not exist.~~
    #
    # **Extended on September 6, 2026**, and that argument expired by its own
    # terms. An account with a confirmed device already gets a 403 from every
    # shipped build, so *requiring* the field breaks nothing that works -- the
    # bypass it worried about was a field accepted and not enforced, which is
    # not what this is. Vince: *"I want to be able to enter my username/pw and
    # it connect automatically."*
    #
    # **The property is unchanged.** A password alone still cannot mint a
    # ninety-day token on an account with a second factor. What changed is
    # where the factor can be proved: here, as well as on the web.
    #
    # **A specific refusal, not the generic 401 above.** That one is deliberately
    # indistinguishable across wrong-password, no-such-account and deactivated;
    # this is a correct password on a real account, and saying so is what stops
    # somebody resetting a password that was never the problem. It leaks that
    # the account has a second factor, to somebody who has just proved they
    # know its password.
    if has_a_second_factor(user):
        # `match_token` walks every confirmed device, so a TOTP code and an
        # `otp_static` recovery token both land here -- which matters, because
        # somebody whose phone is the thing they have lost is trying to connect
        # a *new* phone and has only recovery codes.
        #
        # **It consumes what it matches**: a static token is deleted and a TOTP
        # step will not verify twice. That is the property that makes this
        # worth doing at all rather than a formality.
        if not payload.totp:
            raise HttpError(403, SECOND_FACTOR_REQUIRED)
        if match_token(user, payload.totp) is None:
            raise HttpError(403, SECOND_FACTOR_INCORRECT)
    # The Android client's own fixed default -- token-scopes-plan.md: nobody
    # should have to understand scopes to log into the app they're holding,
    # and a bounded expiry means a lost phone isn't a standing, unbounded
    # risk the way an unscoped, never-expiring token always was.
    _, raw = PersonalAccessToken.generate(
        user,
        label=payload.label,
        scopes=ANDROID_DEFAULT_SCOPES,
        expires_at=timezone.now() + ANDROID_TOKEN_LIFETIME,
    )
    return {"token": raw, "username": user.username, "email": user.email}


def _incorrect_credentials_message(request, username):
    """How many tries are left, or nothing -- never a false "0 remaining".

    The attempt that actually reaches the limit is never answered by this
    function: axes' own middleware computes the lockout the moment that
    failure is recorded and replaces the whole response for that request,
    before this view's return value ever leaves. So `remaining` here is
    always for an attempt that is still genuinely possible, and the
    generic message below exists only as an honest fallback for a
    "no count available" condition this code path cannot actually reach
    today, rather than a promise this function can't keep.
    """
    credentials = get_credentials(username=username)
    failures = AxesProxyHandler.get_failures(request, credentials)
    remaining = get_failure_limit(request, credentials) - failures
    if remaining <= 0:
        return "Incorrect username or password."
    plural = "" if remaining == 1 else "s"
    return (
        f"Incorrect username or password. {remaining} attempt{plural} "
        "remaining before a temporary lock."
    )


ThemeChoice = Literal["system", "light", "dark"]
LandingChoice = Literal["day", "agenda"]


class PreferencesOut(Schema):
    username: str
    email: str
    daily_digest: bool
    #: Defaulted here as well as on the model, the same guard `landing_surface`
    #: carries below: an older client that has never heard of this must not be
    #: able to turn it off by omission.
    closing_nudge: bool = False
    theme: ThemeChoice
    time_zone: str
    # The Personal Compass. Edited here, on the one settings surface, and
    # displayed on every Daily Page -- "stored and edited once", per
    # crane-plan.md slice 5.
    compass_purpose: str = ""
    compass_question: str = ""
    # Where a session lands. Defaulted here as well as on the model so an
    # older client that has never heard of it cannot blank it by omission --
    # the same trap the theme request nearly sprang on the time zone.
    landing_surface: LandingChoice = "day"


class PreferencesIn(Schema):
    username: str
    email: str
    daily_digest: bool
    closing_nudge: bool = False
    theme: ThemeChoice
    time_zone: str
    # The Personal Compass. Edited here, on the one settings surface, and
    # displayed on every Daily Page -- "stored and edited once", per
    # crane-plan.md slice 5.
    compass_purpose: str = ""
    compass_question: str = ""
    # Where a session lands. Defaulted here as well as on the model so an
    # older client that has never heard of it cannot blank it by omission --
    # the same trap the theme request nearly sprang on the time zone.
    landing_surface: LandingChoice = "day"


class TimeZonesOut(Schema):
    time_zones: list[str]


def _preferences_out(user: User) -> dict:
    return {
        "username": user.username,
        "email": user.email,
        "daily_digest": user.daily_digest,
        "closing_nudge": user.closing_nudge,
        "theme": user.theme,
        "time_zone": user.time_zone,
        "compass_purpose": user.compass_purpose,
        "compass_question": user.compass_question,
        "landing_surface": user.landing_surface,
    }


@router.post("/me/logout", response={204: None})
def log_out(request):
    """End the session the SPA is holding.

    An endpoint rather than a logout form copied into React: the typed
    client already sends X-CSRFToken on non-GET requests, Django's own
    logout() keeps its session-invalidation and session-key-cycling
    behaviour, and the SPA gets a definite success before it throws away
    its cached queries and navigates.

    POST only, and CSRF-checked by the session auth the whole router uses,
    so a cross-site request cannot log someone out as a nuisance.
    """
    logout(request)
    return 204, None


@router.get("/time-zones", response=TimeZonesOut)
def list_time_zones(request):
    """The zones the picker may offer.

    Served rather than read from the browser's own Intl list: the two can
    disagree, and a disagreement would show up as a validation error on a
    zone this application had just offered the person.
    """
    return {"time_zones": list(known_time_zones())}


@router.get("/me/preferences", response=PreferencesOut)
def get_preferences(request):
    return _preferences_out(request.user)


# ---------------------------------------------------------------------------
# Leaving
# ---------------------------------------------------------------------------


class DeletionIn(Schema):
    password: str


class DeletionOut(Schema):
    deletion_requested_at: datetime | None
    purge_at: datetime | None


def _deletion_out(user: User) -> dict:
    return {
        "deletion_requested_at": user.deletion_requested_at,
        "purge_at": account_services.purge_at(user),
    }


@router.post("/me/delete", response=DeletionOut)
def request_deletion(request, payload: DeletionIn):
    """Schedule this account for erasure, after a grace period.

    **Password re-entry, and it is not theatre.** Everything else on this router
    is recoverable; this is the one action that ends with data that cannot be
    got back, and a session left open on a shared machine should not be enough
    to start it.

    Checked with `check_password` rather than `authenticate`: this person is
    already signed in, and routing through the auth stack would count a typo
    towards an axes lockout — locking somebody out of the account they are
    trying to leave, from a form that is not a login.
    """
    if not request.user.check_password(payload.password):
        raise HttpError(400, "That password did not match.")

    account_services.request_deletion(request.user, now=timezone.now())
    return _deletion_out(request.user)


@router.post("/me/delete/cancel", response=DeletionOut)
def cancel_deletion(request):
    """Change your mind. No password: undoing a destructive thing should never
    be harder than starting it."""
    account_services.cancel_deletion(request.user)
    return _deletion_out(request.user)


@router.get("/me/export")
def export_account(request):
    """Everything this account owns, as a zip.

    Session auth only, which the whole router already enforces — deliberately
    not reachable with a scoped token. `capture:write` on a phone should not be
    able to walk off with the entire account, and no scope exists that would
    sensibly mean "all of it".
    """
    stamp = timezone.now()
    response = HttpResponse(
        export.build_archive(request.user, now=stamp),
        content_type="application/zip",
    )
    filename = f"clarice-{request.user.get_username()}-{stamp:%Y-%m-%d}.zip"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@router.patch("/me/preferences", response=PreferencesOut)
def update_preferences(request, payload: PreferencesIn):
    user = request.user
    # Reuses AccountSettingsForm's own validation (uniqueness, email
    # normalization) rather than re-implementing it, so the Django-rendered
    # settings page and this endpoint can't quietly enforce different rules.
    form = AccountSettingsForm(
        data={
            "username": payload.username,
            "email": payload.email,
            "daily_digest": payload.daily_digest,
            "closing_nudge": payload.closing_nudge,
            "time_zone": payload.time_zone,
            "compass_purpose": payload.compass_purpose,
            "compass_question": payload.compass_question,
        },
        instance=user,
    )
    if not form.is_valid():
        first_field = next(iter(form.errors))
        raise HttpError(400, form.errors[first_field][0])
    form.save()
    user.theme = payload.theme
    user.landing_surface = payload.landing_surface
    user.save(update_fields=["theme", "landing_surface"])
    return _preferences_out(user)


class PairStartOut(Schema):
    """What a phone shows and what it keeps.

    `device_code` is the credential half and is never displayed by the client;
    `user_code` is the half a person carries to a laptop and grants nothing on
    its own.
    """

    user_code: str
    device_code: str
    expires_at: datetime
    #: Seconds between polls. Sent rather than hard-coded in the client so the
    #: server can slow a phone down without shipping an APK -- and because the
    #: nginx zone for the poll endpoint is sized from this number, which makes
    #: two copies of it a way to rate-limit the app into failure.
    interval: int


class PairStartIn(Schema):
    #: What to call this phone on the web token page. Cosmetic, and defaulted,
    #: so a client that sends nothing still gets a usable label.
    label: str = "Android"


class PairPollIn(Schema):
    device_code: str


class PairPollOut(Schema):
    #: The token, once, when somebody has approved. Null while waiting --
    #: which is also the answer for a code that expired or never existed.
    token: str | None = None


# **Unauthenticated on purpose, and listed in `test_api_auth_surface.py`'s
# `UNAUTHENTICATED` set beside `/login`.** A phone starting a pairing has no
# credential yet; that is the entire point of the flow. Both of these carry an
# nginx rate limit, which that test file requires and
# `test_unauthenticated_endpoints_are_throttled` enforces against the real
# template.
#
# **Nothing here grants anything.** This mints a request that is inert until
# somebody who is logged in, and past their second factor, approves it. The
# dangerous verb in this flow is on the web, not here.
@router.post("/pair/start", response={200: PairStartOut}, auth=None)
def pair_start(request, payload: PairStartIn):
    started = pairing.start(label=payload.label)
    return {
        "user_code": started.user_code,
        "device_code": started.device_code,
        "expires_at": started.expires_at,
        "interval": started.interval,
    }


# **One answer for three states, deliberately** -- waiting, expired, and never
# existed all return a null token with a 200. A poll that distinguished them
# would let anyone enumerate live codes, and the phone has nothing different to
# do in any of the three: it keeps asking until its own window closes.
#
# 200 rather than 202 or 404 for the same reason. A status code is as much of
# an oracle as a body.
@router.post("/pair/poll", response={200: PairPollOut}, auth=None)
def pair_poll(request, payload: PairPollIn):
    return {"token": pairing.redeem(payload.device_code)}
