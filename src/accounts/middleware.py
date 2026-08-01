"""Makes "today" mean the user's today rather than the server's."""
from django.utils import timezone

from accounts.models import resolve_time_zone


class TimeZoneMiddleware:
    """Activate each authenticated user's own time zone for the request.

    Everything that decides a day boundary -- agenda bucketing, per-list
    overdue counts, snooze presets, the completed-today range -- reads the
    active zone through django.utils.timezone. Activating it once here is
    what makes all of them per-user without any of them having to know a
    user exists.

    The finally is not tidiness. activate() sets a thread-local and the
    server reuses worker threads, so leaving one set would let a request
    from one zone silently redefine "today" for whoever that thread
    served next.

    Token-authenticated API requests are outside this: Ninja resolves the
    token inside the view, so request.user is still anonymous here. The
    only token surface is capture, which stores timestamps rather than
    local dates -- but a future date-bearing token endpoint has to
    activate the owner's zone itself.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        zone = (
            resolve_time_zone(user.time_zone)
            if user is not None and user.is_authenticated
            else None
        )
        if zone is None:
            timezone.deactivate()
        else:
            timezone.activate(zone)
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
