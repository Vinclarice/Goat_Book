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
from daily.api_v1 import router as daily_router
from lists.api_v1 import router as lists_router
from mind.api_v1 import router as capture_router
from review.api_v1 import router as review_router
from routines.api_v1 import router as routines_router

# `django_auth` is the *default*, not the rule. Operations override it
# per-operation, and fourteen of them do -- across `lists`, `mind`, `daily`,
# `accounts` and `routines` -- because the phone holds a bearer token and
# cannot carry a session cookie.
#
# **These notes said "session-only" for three of those routers and were wrong.**
# They were true when the phone only captured; slices 1 and 2 gave it the Day
# and the Agenda, and nothing checked a comment. So the surface is pinned in
# `clarice/tests/test_api_auth_surface.py`, which fails if an operation gains
# or loses token auth -- and the point of it is that widening what a token
# reaches takes a deliberate edit, since a bearer sits in an Android keystore
# and outlives a session by ninety days.
#
# Read that test for the list. What follows is only what is worth knowing per
# router, and the test is the authority.
api = NinjaAPI(auth=django_auth, urls_namespace="v1")
# `GET /agenda` takes a token; every write to a task and everything about
# areas and projects stays session-only. The phone reads the agenda and acts on
# individual tasks through their own URLs.
api.add_router("", lists_router)
# `GET /me` takes a token -- the one endpoint a freshly pasted token can call
# before anything else works, which is what the Connect screen needs. The rest
# of the account surface, including deletion and export, is session-only.
api.add_router("", accounts_router)
# Capture, and the original reason a token exists.
#
# It comes from `mind` rather than `capture` since Heron 4a. The URL, the token
# and the scope are unchanged -- what changed is that it writes a Node. That is
# what leaves the `capture` app with nothing on this API, so 4b can delete it.
api.add_router("", capture_router)
# Token *and* session, on all five operations: the phone reads the Day and
# writes it, pinning a focus and saving the day's own words. This said "a day
# is written from the browser", which stopped being the only way in slice 1.
api.add_router("", daily_router)
# Every routine write takes a token; `GET /routines` does not, which is worth
# noticing rather than assuming symmetric. This said logging from Android
# "has no product trigger yet" -- it has one, and it shipped.
api.add_router("", routines_router)
# The one router with no token operations at all, reads included. Nothing on
# the phone shows a weekly review, so nothing here has needed widening.
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
