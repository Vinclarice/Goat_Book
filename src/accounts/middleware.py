"""Makes "today" mean the user's today rather than the server's."""
from django.utils import timezone

from accounts.models import resolve_time_zone


def activate_for(user):
    """Make this user's zone the active one, or clear it if there is no user.

    Shared with `accounts.auth._resolve_scoped_token`, which calls it when a
    bearer token resolves — by then the middleware below has already run and
    seen an anonymous request. Keeping both halves of the policy in one
    function is what stops the two authentication paths deciding "today"
    differently, which they did until August 14, 2026.

    Whoever calls this is relying on the middleware's `finally` to undo it.
    That is fine for a request and load-bearing: see the note there.
    """
    zone = resolve_time_zone(user.time_zone) if user is not None else None
    if zone is None:
        timezone.deactivate()
    else:
        timezone.activate(zone)


class TimeZoneMiddleware:
    """Activate each authenticated user's own time zone for the request.

    Everything that decides a day boundary -- agenda bucketing, per-list
    overdue counts, snooze presets, the completed-today range -- reads the
    active zone through django.utils.timezone. Activating it once here is
    what makes all of them per-user without any of them having to know a
    user exists.

    The finally is not tidiness, and it now covers two activations rather
    than one. activate() sets a thread-local and the server reuses worker
    threads, so leaving one set would let a request from one zone silently
    redefine "today" for whoever that thread served next. **A token request
    activates its zone later, from `accounts.auth`, and relies on this
    `finally` to undo it** -- so removing this middleware would not merely
    restore the old behaviour, it would leak a zone across requests.

    Token-authenticated requests cannot be handled here: Ninja resolves the
    bearer header inside the view, so `request.user` is still anonymous at
    this point. This docstring used to end by saying "a future date-bearing
    token endpoint has to activate the owner's zone itself" -- six of them
    then shipped across `daily` and `routines`, and not one did. A note
    telling the next person to remember something is not a mechanism; the
    zone is now activated where the owner first becomes known instead, which
    is `_resolve_scoped_token`.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        activate_for(user if user is not None and user.is_authenticated else None)
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
