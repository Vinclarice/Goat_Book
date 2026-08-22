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

from datetime import timedelta

from django.db import DatabaseError, connection
from django.utils import timezone
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


# How far behind a scheduled outcome may fall before it is a signal rather than
# a schedule. Generous on purpose: the sweeps run once a day, so anything under
# roughly two of their intervals is an ordinary gap, and a check that flaps is
# a check that gets muted.
STALE_AFTER = timedelta(days=2)


def scheduled_work_is_current(*, now) -> bool:
    """Is the work the three cron jobs exist to do actually being done?

    **Outcomes, not heartbeats.** A ping answers "did the command run"; this
    answers "is anything overdue that the command should have handled". The
    second catches strictly more: the job unscheduled, the job raising, and the
    job running and silently skipping somebody -- which a ping cannot tell
    apart, because the ping fires either way.

    That choice is also why this needs no new model. Every signal here already
    exists for its own reasons, and `clarice` is not an installed app and could
    not hold a `ScheduledJobRun` without becoming one.

    Never raises, like `database_reachable` above -- and **fails to "overdue"
    rather than to "fine"**. A bug in this function then shows up as an alarm
    that will not clear, which somebody investigates; the other direction is a
    check that has been silently broken for a month and is indistinguishable
    from good news.
    """
    try:
        return not _overdue(now=now)
    except Exception:  # noqa: BLE001 -- see the docstring
        return False


def _overdue(*, now) -> bool:
    from accounts.services import due_for_purge

    # Erasure. An account still present days after its grace period ended is a
    # legal obligation outstanding, whichever way the sweep failed.
    if due_for_purge(now - STALE_AFTER).exists():
        return True

    # The digest. `send_due_digest` stamps `last_digest_date` for every eligible
    # user each morning, including the write-off path that stamps when nothing
    # was sent -- so the stamp records the command reaching that user rather
    # than mail going out.
    #
    # `last_digest_date__lt` and not `isnull`: a new account has never been
    # stamped and has missed nothing, which is the case a "max stamp is recent"
    # check reports backwards on a quiet site.
    from accounts.models import User

    # **A day of slack, and it is D16 rather than superstition.**
    # `last_digest_date` is stamped on the *owner's* clock by `scheduled_mail`,
    # and this cutoff is derived from UTC, so the two can disagree by up to a
    # day in either direction. Fixing that properly would mean a per-row zone
    # conversion for a check whose whole output is one boolean.
    #
    # So the skew is absorbed rather than removed, and deliberately in the
    # conservative direction: this is an **alerting** path, where a false alarm
    # is the expensive failure and alarming a day later is not. That is the
    # opposite trade from `recall.what_surrounded`, where the same skew was a
    # wrong answer shown to a person and had to be corrected exactly.
    cutoff = (now - STALE_AFTER - timedelta(days=1)).date()
    if User.objects.filter(
        is_active=True, daily_digest=True, last_digest_date__lt=cutoff
    ).exists():
        return True

    # The maintenance pass. Recorded per owner, and only for owners with notes
    # -- the same set the command iterates, so the two agree about who is owed
    # a pass rather than disagreeing about an empty account.
    from mind.instrumentation import last_maintenance_run
    from mind.queries import live_nodes

    for owner in User.objects.filter(is_active=True):
        if not live_nodes(owner).exists():
            continue
        ran = last_maintenance_run(owner)
        if ran is None or ran < now - STALE_AFTER:
            return True

    return False


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


@never_cache
@require_http_methods(["GET", "HEAD"])
def healthz_scheduled(request):
    """`ok` or `overdue`, and the status code is the part that matters.

    **A second endpoint rather than a branch in `healthz`.** They answer
    different questions and a monitor should be able to page differently on
    them: the site being down is an outage, and the erasure sweep being two days
    behind is not. Folding them together would mean a late cron job reporting
    the website as down, which is how a monitor stops being believed.

    It keeps `healthz`'s discipline of saying almost nothing. `overdue` names no
    job, no account and no date -- this URL answers anybody, forever, and which
    of three scheduled jobs is failing is a fact about the inside of the system.
    What is overdue belongs in the logs, where the commands already put it.
    """
    if not scheduled_work_is_current(now=timezone.now()):
        return HttpResponse("overdue", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")
