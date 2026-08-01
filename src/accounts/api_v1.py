"""Ninja router registered onto clarice.api's /api/v1/ contract.

Password/security changes stay Django-owned (accounts.views.change_password)
-- this is only the fields AccountSettingsForm already covers, plus theme.
"""
from typing import Literal

from ninja import Router, Schema
from ninja.errors import HttpError

from accounts.forms import AccountSettingsForm
from accounts.models import User, known_time_zones

router = Router()

ThemeChoice = Literal["system", "light", "dark"]


class PreferencesOut(Schema):
    username: str
    email: str
    daily_digest: bool
    theme: ThemeChoice
    time_zone: str


class PreferencesIn(Schema):
    username: str
    email: str
    daily_digest: bool
    theme: ThemeChoice
    time_zone: str


class TimeZonesOut(Schema):
    time_zones: list[str]


def _preferences_out(user: User) -> dict:
    return {
        "username": user.username,
        "email": user.email,
        "daily_digest": user.daily_digest,
        "theme": user.theme,
        "time_zone": user.time_zone,
    }


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
        },
        instance=user,
    )
    if not form.is_valid():
        first_field = next(iter(form.errors))
        raise HttpError(400, form.errors[first_field][0])
    form.save()
    user.theme = payload.theme
    user.save(update_fields=["theme"])
    return _preferences_out(user)
