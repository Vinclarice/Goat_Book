"""Bearer-token authentication for API surfaces that aren't the SPA.

Lives in accounts rather than capture (where the plan first sketched it)
because nothing about it is capture-specific: it resolves a token to its
owner, and capture just happens to be the first endpoint that needs that.
"""
from functools import wraps

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from ninja.security import HttpBearer, SessionAuth
from ninja.utils import check_csrf

from accounts.models import PersonalAccessToken, hash_token


def _resolve_scoped_token(raw_token, scope):
    """The owner of a token that resolves, is active, unexpired, and
    carries [scope] -- or None. Shared by [TokenAuth] (Ninja operations)
    and [token_or_session_required] (the hand-rolled lists.api views), so
    the two can never drift on what "a valid token for this scope" means.
    """
    try:
        pat = PersonalAccessToken.objects.select_related("owner").get(
            token_hash=hash_token(raw_token)
        )
    except PersonalAccessToken.DoesNotExist:
        return None
    # A deactivated account is one awaiting approval or shut off on
    # purpose; a token it happens to hold shouldn't outlive that.
    if not pat.owner.is_active:
        return None
    if pat.is_expired():
        return None
    if not pat.has_scope(scope):
        return None
    pat.last_used_at = timezone.now()
    pat.save(update_fields=["last_used_at"])
    return pat.owner


class TokenAuth(HttpBearer):
    """Authenticates `Authorization: Bearer <token>` against a stored hash,
    and only for the one [scope] this operation actually declared it needs
    -- token-scopes-plan.md. Every call site names its scope explicitly
    (`TokenAuth("day:read")`); there is no scope-blind default, so a new
    endpoint that forgets to think about this fails to construct at all
    rather than silently accepting any valid token.

    Meant to sit *before* django_auth in an operation's auth list, not
    instead of it. Ninja tries each in order and stops at the first that
    resolves, so a request with no bearer header falls straight through to
    the session path the SPA already uses -- and, importantly, only the
    cookie auth runs a CSRF check, which a token-bearing client has no way
    to satisfy and no need to.

    A token that resolves but is expired, or resolves but lacks [scope], is
    refused exactly the way an unknown token is -- returning None here is
    what makes Ninja answer a plain 401, with nothing in the response to
    tell the caller *which* check failed. That's deliberate, not an
    oversight: Android already collapses every 401 into the same
    "reconnect" message, and a more specific error would hand an attacker
    holding a stolen, narrowly-scoped token a free oracle for exactly which
    scope to go steal next.
    """

    def __init__(self, scope):
        self.scope = scope
        super().__init__()

    def authenticate(self, request, token):
        owner = _resolve_scoped_token(token, self.scope)
        if owner is None:
            return None
        # Ninja puts the return value on request.auth; setting request.user
        # too means endpoints read the same attribute either way and don't
        # have to care which of the two authenticated the caller.
        request.user = owner
        return owner


class SessionAuthIfLoggedIn(SessionAuth):
    """Session auth that declines quietly instead of raising CSRF at a
    caller who never had a session in the first place.

    Ninja's SessionAuth runs its CSRF check inside `_get_key`, *before*
    looking for the cookie -- so a token client that sent a revoked or
    mistyped token falls through to this one and gets `403 CSRF check
    Failed`, which is both the wrong status and a misleading reason.
    Found with curl; the Django test client can't see it, because it
    disables CSRF enforcement by default.

    Declining when there's no authenticated session doesn't weaken
    anything: the attack CSRF exists to stop is a cross-site POST riding
    on a victim's cookie, and in that request the user *is* authenticated,
    so the check below still runs exactly as before.
    """

    def __call__(self, request):
        if not request.user.is_authenticated:
            return None
        return super().__call__(request)


def token_or_session_required(scope):
    """The `TokenAuth(scope)` + `SessionAuthIfLoggedIn()` choice, ported to
    a plain Django view -- for `lists.api`'s hand-rolled endpoints, which
    predate Ninja's `auth=` mechanism and stay off the Ninja router on
    purpose (see that module's own docstring), so token support has to
    reach them some other way. token-scopes-plan.md §7 has the full
    mechanism this reproduces; the short version:

    Every Ninja view is Django-`csrf_exempt` already, and a *session*
    request through Ninja gets checked manually, inside `SessionAuth`,
    only when that auth class is actually reached. This decorator does the
    same two things by hand: `@csrf_exempt` so Django's own
    `CsrfViewMiddleware` never touches this view, and a manual
    `ninja.utils.check_csrf` call on the session path only -- reusing
    Ninja's own primitive rather than re-deriving CSRF-checking logic,
    a place a subtle mistake would be expensive. A bearer request never
    reaches that call, the same ordering reason `TokenAuth`'s own docstring
    gives.

    Sets `request.token_authenticated` either way, so a view that must
    refuse a token a capability it would otherwise be scoped for --
    `item_detail`'s `DELETE` and its non-agenda fields, see
    token-scopes-plan.md §7's scope-creep note -- has something to check.
    """

    def decorator(view):
        @csrf_exempt
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            header = request.headers.get("Authorization", "")
            if header.startswith("Bearer "):
                owner = _resolve_scoped_token(
                    header.removeprefix("Bearer ").strip(), scope
                )
                if owner is None:
                    # A bearer header was sent but didn't resolve -- refused
                    # outright rather than falling through to the session
                    # path, the same ordering TokenAuth relies on: a failed
                    # token must not be told its problem is a missing
                    # cookie.
                    return JsonResponse(
                        {"errors": {"authentication": ["Login required."]}},
                        status=401,
                    )
                request.user = owner
                request.token_authenticated = True
                return view(request, *args, **kwargs)

            request.token_authenticated = False
            if check_csrf(request) is not None:
                return JsonResponse(
                    {"errors": {"authentication": ["CSRF check failed."]}},
                    status=403,
                )
            if not request.user.is_authenticated:
                return JsonResponse(
                    {"errors": {"authentication": ["Login required."]}},
                    status=401,
                )
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
