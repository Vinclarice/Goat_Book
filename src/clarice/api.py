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

from accounts.api_v1 import router as accounts_router
from accounts.auth import SessionAuthIfLoggedIn, TokenAuth
from accounts.models import SCOPE_IDENTITY_READ
from capture.api_v1 import router as capture_router
from daily.api_v1 import router as daily_router
from lists.api_v1 import router as lists_router
from review.api_v1 import router as review_router
from routines.api_v1 import router as routines_router

api = NinjaAPI(auth=django_auth, urls_namespace="v1")
api.add_router("", lists_router)
api.add_router("", accounts_router)
# The capture router overrides this default auth per-operation: it also
# accepts a bearer token, since a phone client can't carry a session
# cookie. Everything else here stays session-only.
api.add_router("", capture_router)
# Session-only, like lists and accounts: a day is written from the browser.
api.add_router("", daily_router)
# Session-only too. Logging from the Android client would need the
# token-authenticated zone activation per-user-time-zones-plan.md flags, and
# has no product trigger yet.
api.add_router("", routines_router)
# Session-only as well. The review reads everything and writes nothing until
# slice 4, and what it writes then is a person's own reflection.
api.add_router("", review_router)


class MeOut(Schema):
    username: str
    email: str


# Token auth as well as session, and in that order for the reason
# accounts.auth documents: a bearer request must not fall through to the
# session path and be told its problem is CSRF.
#
# This is the only endpoint a freshly pasted personal access token can call
# safely, which is what M2's Connect screen needs -- without it the sole
# way to check a token was to POST a capture, putting a junk row in the
# owner's Inbox every time somebody mistyped one. It also answers Settings'
# "which account is this phone connected to". identity:read is required
# like every other scope now -- token-scopes-plan.md deliberately keeps
# this endpoint uniform rather than special-casing it as always-open, with
# every Android-minted token carrying the scope by default so nothing
# observable changes for an existing connection.
@api.get("/me", response=MeOut, auth=[TokenAuth(SCOPE_IDENTITY_READ), SessionAuthIfLoggedIn()])
def me(request):
    return {"username": request.user.username, "email": request.user.email}
