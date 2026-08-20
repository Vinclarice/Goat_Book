"""Delivering one message per person per local day, once.

Extracted from `send_due_digest` unchanged, because a second scheduled send was
about to copy it. Six behaviours live here, each of which cost something to
learn and any of which would drift if there were two copies:

1. **The zone is the recipient's**, with the server's as a fallback rather than
   an exception -- one unresolvable zone must not cost everybody else their
   mail.
2. **A stamp per person per day**, so an hourly cron is a no-op after the first
   send. Without it a task becoming overdue at 14:00 mails a "good morning" at
   15:00.
3. **At or after the hour, not equal to it.** An equality test silently drops a
   whole day whenever the run is missed -- a reboot, a slow image pull, or a
   spring-forward that skips the hour outright in some zones.
4. **A window that closes.** Past `until_hour` the day falls through to being
   stamped without sending, which is how a missed morning is written off rather
   than delivered stale in the evening.
5. **Stamped even when there was nothing to say**, which is the whole
   difference between a scheduled message and an alarm.
6. **One recipient's failure is theirs alone**, and a failure does not stamp --
   their day was not decided, so the next hourly run tries again and the
   window's close is what eventually ends it. An unguarded raise here did not
   merely delay the rest of the list; it never delivered to them at all.

`clarice/` rather than either app, the same placement `clarice/search.py` has
for a rule both cores need: a scheduler that belongs to whichever app called it
last is a scheduler with two definitions.
"""

import logging
from zoneinfo import ZoneInfo

from django.conf import settings

from accounts.models import resolve_time_zone


logger = logging.getLogger(__name__)


def deliver_once_a_day(
    *,
    recipients,
    stamp_field,
    send_hour,
    until_hour,
    now,
    compose,
    deliver,
    stamp=True,
    logger=None,
    label="mail",
):
    """Walk ``recipients`` and deliver to whoever's window is open.

    ``compose(user, today)`` returns ``(subject, body)`` or None when there is
    nothing worth sending; ``deliver(user, subject, body)`` does the sending,
    so a dry run swaps it rather than threading a flag through this loop.

    ``stamp=False`` for a dry run: writing the stamp would make the rehearsal
    cost the real send.

    ``logger`` is the *caller's*, deliberately. `send_due_digest`'s own comment
    records why the name matters: sentry-sdk's LoggingIntegration reports at
    ERROR, so `logger.exception` is what puts a failed send in front of
    somebody -- and "digest failed" under the command's own module is a more
    useful report than one under this one. A test names that logger.

    Returns ``(sent, failed)`` -- the count delivered and the usernames whose
    turn raised. Reporting is otherwise the caller's, because a management
    command's output is its own contract.
    """
    log = logger or globals()["logger"]
    sent = 0
    failed = []
    for user in recipients.order_by("username"):
        try:
            zone = resolve_time_zone(user.time_zone) or ZoneInfo(settings.TIME_ZONE)
            local_now = now.astimezone(zone)
            today = local_now.date()

            if getattr(user, stamp_field) == today:
                continue
            if local_now.hour < send_hour:
                continue

            if local_now.hour < until_hour:
                message = compose(user, today)
                if message is not None:
                    deliver(user, *message)
                    sent += 1

            if stamp:
                setattr(user, stamp_field, today)
                user.save(update_fields=[stamp_field])
        except Exception:
            # Broad on purpose: the mail backend's failure modes are not ours
            # to enumerate, and any of them costs the same thing.
            failed.append(user.get_username())
            log.exception("%s failed for %s", label, user.get_username())
    return sent, failed
