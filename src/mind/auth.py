"""Bearer authentication, for clients that cannot hold a session cookie.

Session auth already covers a browser, phone included. This exists for a native
client — specifically so the existing Android capture app, which has an encrypted
offline queue and a share-sheet handler already built and tested, can point at this
server by changing one build property.

Two things worth knowing:

**Bearer is tried before session, and that is what exempts it from CSRF.** A token
request carries no CSRF token and should not need one: CSRF defends against a browser
being tricked into using a cookie it already holds, and there is no cookie here. When
the bearer check succeeds, Ninja never consults the session backend that would enforce
it. When there is no `Authorization` header, the session path runs unchanged, CSRF and
all.

**`request.user` is set on success.** Ninja hands the authenticated principal back as
`request.auth`, but every view here reads `request.user`, and a view that silently
served `AnonymousUser` to a token request would be the kind of bug that looks like
missing data rather than broken auth.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from ninja.security import HttpBearer

from accounts.middleware import activate_for

from .models import ApiToken

# How stale `last_used_at` may get before it is rewritten. Capture is the hot path and
# a write per request buys nothing — the field exists to answer "is this device still
# in use", which minutes-level accuracy answers perfectly well.
LAST_USED_RESOLUTION = timedelta(minutes=5)


def resolve_token(raw: str) -> ApiToken | None:
    """The live token matching this string, or None.

    Looked up by hash, so the plaintext is never compared against anything stored and
    a database dump contains nothing presentable. No constant-time comparison is
    needed or possible here: the lookup is an indexed equality on the hash of a
    256-bit random secret, and there is no per-character leak to exploit.
    """
    if not raw:
        return None

    token = (
        ApiToken.objects.select_related("owner")
        .filter(token_hash=ApiToken.hash_token(raw), revoked_at__isnull=True)
        .first()
    )
    if token is None or not token.owner.is_active:
        return None

    now = timezone.now()
    if token.last_used_at is None or now - token.last_used_at > LAST_USED_RESOLUTION:
        # update() rather than save(), to avoid a full row write and any signal
        # traffic on the capture path.
        ApiToken.objects.filter(pk=token.pk).update(last_used_at=now)

    # The owner's zone, at the first moment there is an owner to read it from.
    # `TimeZoneMiddleware` runs before any of this and saw an anonymous
    # request, so without this line every relative date the capture parser
    # reads -- "tomorrow", "this Friday" -- resolves in the server's zone.
    # The task core carried the identical defect across six endpoints for
    # months (commercial-blueprint.md 2); this core has its own token table
    # and its own resolver, so it needs the same call in its own seam.
    #
    # Nothing undoes this here. The middleware's `finally` does, and it is what
    # keeps an activated zone from outliving the request on a reused worker
    # thread -- see the note there.
    activate_for(token.owner)
    return token


class BearerAuth(HttpBearer):
    """`Authorization: Bearer <token>`."""

    def authenticate(self, request, token):
        api_token = resolve_token(token)
        if api_token is None:
            return None
        request.user = api_token.owner
        request.api_token = api_token
        return api_token.owner
