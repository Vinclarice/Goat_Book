"""Ninja router registered onto clarice.api's /api/v1/ contract.

Password/security changes stay Django-owned (accounts.views.change_password)
-- this is only the fields AccountSettingsForm already covers, plus theme.
"""
from typing import Literal

from axes.handlers.proxy import AxesProxyHandler
from axes.helpers import get_credentials, get_failure_limit
from axes.utils import reset as axes_reset
from django.contrib.auth import authenticate, logout
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from accounts.forms import AccountSettingsForm
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


class LoginOut(Schema):
    token: str
    username: str
    email: str


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
