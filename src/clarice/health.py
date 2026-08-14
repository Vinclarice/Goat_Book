"""Is this site actually serving?

`commercial-blueprint.md` defect 9: Sentry reports errors from a *running*
application, so a dead container, a dead host, an expired certificate or a hung
gunicorn produce zero events — indistinguishable from a quiet night. This is the
endpoint an external monitor polls; the monitor itself is the other half and
lives outside this repository, because a watchdog running on the machine it
watches is not a watchdog.

Its own module rather than a branch in `urls.py`, for the same reason
`monitoring.py` exists: the decision about what "healthy" means is a function
with a test, not a line of configuration nobody reads.

**Three deliberate restrictions.**

*It checks the database.* A liveness check that always returns 200 answers "did
gunicorn accept a socket", and gunicorn accepting sockets while every request
500s on a dead connection pool is an ordinary way to be down. The monitor is
only as good as the weakest thing this is willing to notice.

*It says almost nothing.* No version, no hostname, no database name, no
exception text. This is the one URL that answers anybody, forever, and a health
endpoint reporting its own internals is free reconnaissance — including, on a
bad day, a connection string inside an error message. What broke belongs in the
logs, where it is already going.

*It cannot fail by raising.* `database_reachable` returns False rather than
propagating, so the view has one job and no branch of it can 500. An endpoint
that crashes while reporting health reports its own bug as an outage.
"""

from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods


def database_reachable() -> bool:
    """Can this process talk to Postgres right now?

    `ensure_connection` rather than a query: it opens the connection if it is
    closed and is a no-op if it is already open, which is exactly the question,
    and it costs nothing on the ordinary path where the answer is yes.

    Catching `DatabaseError` rather than `OperationalError` alone -- a health
    check narrower than the failures it is watching for is worse than none,
    because it reports healthy through the ones it forgot.
    """
    try:
        connection.ensure_connection()
    except DatabaseError:
        return False
    return True


@never_cache
@require_http_methods(["GET", "HEAD"])
def healthz(request):
    """`ok` or `unhealthy`, and the status code is the part that matters.

    Uptime services read the code; several of them will happily report a
    200-with-a-sad-message as up. HEAD is allowed because several of them
    default to it, and a 405 there would read as an outage on a working site.
    """
    if not database_reachable():
        return HttpResponse("unhealthy", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")
