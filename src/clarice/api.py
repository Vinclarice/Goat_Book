"""The /api/v1/ contract.

This is the Ninja-backed API the SPA migration (see the UI overhaul plan)
builds against going forward. It runs alongside, not in place of, the
hand-rolled endpoints in lists.api -- those keep serving the existing
per-page React islands until each route migrates over in its own PR.

Session auth via django_auth mirrors what the frontend already speaks
(session cookie + X-CSRFToken header, see frontend/src/api.ts), so no new
auth mechanism is introduced here.
"""
from ninja import NinjaAPI, Schema
from ninja.security import django_auth

api = NinjaAPI(auth=django_auth, urls_namespace="v1")


class MeOut(Schema):
    username: str
    email: str


@api.get("/me", response=MeOut)
def me(request):
    return {"username": request.user.username, "email": request.user.email}
