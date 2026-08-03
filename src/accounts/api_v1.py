"""Ninja router registered onto clarice.api's /api/v1/ contract.

Password/security changes stay Django-owned (accounts.views.change_password)
-- this is only the fields AccountSettingsForm already covers, plus theme.
"""
from typing import Literal

from django.contrib.auth import authenticate, logout
from ninja import Router, Schema
from ninja.errors import HttpError

from accounts.forms import AccountSettingsForm
from accounts.models import PersonalAccessToken, User, known_time_zones

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
    a deactivated one, or a lockout in progress -- deliberately
    indistinguishable, the same as the web login form gives away nothing
    about which part was wrong.
    """
    user = authenticate(request, username=payload.username, password=payload.password)
    if user is None:
        raise HttpError(401, "Incorrect username or password.")
    _, raw = PersonalAccessToken.generate(user, label=payload.label)
    return {"token": raw, "username": user.username, "email": user.email}


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
